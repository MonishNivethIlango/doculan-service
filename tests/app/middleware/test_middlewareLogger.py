import importlib
import sys
import pytest

@pytest.fixture(autouse=True)
def _isolate_logger_middleware_module():
    # Ensure each test gets a fresh module (avoid leaked mocks from other tests)
    sys.modules.pop('app.middleware.middlewareLogger', None)
    import app.middleware.middlewareLogger as ml  # noqa: F401
    importlib.reload(ml)
    yield
    import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from starlette.responses import StreamingResponse
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor


def _build_app_with_middleware():
    from app.middleware.middlewareLogger import LoggerMiddleware
    app = FastAPI()
    app.add_middleware(LoggerMiddleware)
    return app


def test_dispatch_404_logs():
    app = _build_app_with_middleware()
    client = TestClient(app)
    with patch('app.middleware.middlewareLogger.timezone_utils.get_timezone_datetime', side_effect=[100, 102]) as _tz, \
         patch('app.middleware.middlewareLogger.log.info') as log_info, \
         patch('app.middleware.middlewareLogger.log.error') as log_error:
        resp = client.get("/not-found")
        assert resp.status_code == 404
        assert log_info.called
        msg = log_info.call_args[0][0]
        assert "GET" in msg and "/not-found" in msg and "completed in 2" in msg
        assert not log_error.called


def test_dispatch_streaming_response_logs_and_preserves_body():
    app = _build_app_with_middleware()

    def gen():
        yield b"chunk1-"
        yield b"chunk2"

    @app.get("/stream")
    def stream():
        return StreamingResponse(gen(), media_type="text/plain")

    client = TestClient(app)
    with patch('app.middleware.middlewareLogger.timezone_utils.get_timezone_datetime', side_effect=[10, 12]) as _tz, \
         patch('app.middleware.middlewareLogger.log.info') as log_info, \
         patch('app.middleware.middlewareLogger.log.error') as log_error:
        resp = client.get("/stream")
        assert resp.status_code == 200
        assert resp.text == "chunk1-chunk2"
        assert log_info.called
        msg = log_info.call_args[0][0]
        assert "GET" in msg and "/stream" in msg and "completed in 2" in msg
        assert not log_error.called


def test_dispatch_log_order_on_nameerror():
    app = _build_app_with_middleware()

    @app.get("/boom")
    async def boom():
        raise NameError("X")

    client = TestClient(app)
    with patch('app.middleware.middlewareLogger.timezone_utils.get_timezone_datetime', side_effect=[1, 2]) as _tz, \
         patch('app.middleware.middlewareLogger.log') as mock_log:  # no autospec to avoid suite conflicts
        resp = client.get("/boom")
        assert resp.status_code == 500
        # Assert error message logged first, then final info message
        assert len(mock_log.method_calls) >= 2
        first_msg = mock_log.method_calls[0].args[0]
        last_msg = mock_log.method_calls[-1].args[0]
        assert "NameError occurred" in first_msg
        assert "completed in 1" in last_msg


def test_dispatch_with_datetime_values_logged_as_timedelta():
    app = _build_app_with_middleware()

    @app.get("/dt")
    def dt():
        return PlainTextResponse("ok")

    client = TestClient(app)
    t0 = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=5)
    with patch('app.middleware.middlewareLogger.timezone_utils.get_timezone_datetime', side_effect=[t0, t1]) as _tz, \
         patch('app.middleware.middlewareLogger.log.info') as log_info:
        resp = client.get("/dt")
        assert resp.status_code == 200
        msg = log_info.call_args[0][0]
        assert "GET" in msg and "/dt" in msg and "0:00:05" in msg  # timedelta string


def test_dispatch_http_exception_is_mapped_to_500_by_middleware():
    app = _build_app_with_middleware()

    @app.get("/teapot")
    def teapot():
        raise HTTPException(status_code=418, detail="I'm a teapot")

    client = TestClient(app)
    with patch('app.middleware.middlewareLogger.timezone_utils.get_timezone_datetime', side_effect=[7, 9]) as _tz, \
         patch('app.middleware.middlewareLogger.log.error') as log_error:
        resp = client.get("/teapot")
        # Middleware does not map HTTPException to 500; it propagates as-is.
        assert resp.status_code == 418
        assert not log_error.called


def test_dispatch_sync_endpoint():
    app = _build_app_with_middleware()

    @app.get("/sync")
    def sync_endpoint():
        return PlainTextResponse("sync-ok")

    client = TestClient(app)
    with patch('app.middleware.middlewareLogger.timezone_utils.get_timezone_datetime', side_effect=[100, 105]) as _tz, \
         patch('app.middleware.middlewareLogger.log.info') as log_info:
        resp = client.get("/sync")
        assert resp.status_code == 200
        assert resp.text == "sync-ok"
        msg = log_info.call_args[0][0]
        assert "GET" in msg and "/sync" in msg and "completed in 5" in msg


def test_dispatch_put_and_patch_methods():
    app = _build_app_with_middleware()

    @app.put("/put")
    async def put_ep():
        return PlainTextResponse("put", status_code=200)

    @app.patch("/patch")
    async def patch_ep():
        return PlainTextResponse("patch", status_code=200)

    client = TestClient(app)
    # 2 calls to tz function, each endpoint: start and end -> total 4 values
    with patch('app.middleware.middlewareLogger.timezone_utils.get_timezone_datetime', side_effect=[1, 2, 3, 4]) as _tz, \
         patch('app.middleware.middlewareLogger.log.info') as log_info:
        r1 = client.put("/put")
        r2 = client.patch("/patch")
        assert r1.status_code == 200 and r2.status_code == 200
        assert log_info.call_count == 2
        m1 = log_info.call_args_list[0][0][0]
        m2 = log_info.call_args_list[1][0][0]
        assert "PUT" in m1 and "/put" in m1 and "completed in 1" in m1
        assert "PATCH" in m2 and "/patch" in m2 and "completed in 1" in m2


def test_dispatch_preserves_custom_headers():
    app = _build_app_with_middleware()

    @app.get("/headers")
    async def headers():
        resp = PlainTextResponse("hdr")
        resp.headers["X-Custom"] = "V"
        return resp

    client = TestClient(app)
    with patch('app.middleware.middlewareLogger.timezone_utils.get_timezone_datetime', side_effect=[20, 25]) as _tz, \
         patch('app.middleware.middlewareLogger.log.info') as log_info:
        resp = client.get("/headers")
        assert resp.status_code == 200
        assert resp.headers.get("X-Custom") == "V"
        msg = log_info.call_args[0][0]
        assert "GET" in msg and "/headers" in msg and "completed in 5" in msg


def test_dispatch_concurrent_requests_log_each_once():
    app = _build_app_with_middleware()

    @app.get("/c")
    async def c():
        return PlainTextResponse("ok")

    client = TestClient(app)

    # Prepare timezone side effects: for n requests, we need 2*n values (start,end)
    n = 5
    tz_values = []
    for i in range(n):
        tz_values.extend([i * 10, i * 10 + 1])  # duration = 1 for each request

    with patch('app.middleware.middlewareLogger.timezone_utils.get_timezone_datetime', side_effect=tz_values) as _tz, \
         patch('app.middleware.middlewareLogger.log.info') as log_info:
        def do_req():
            r = client.get("/c")
            assert r.status_code == 200

        with ThreadPoolExecutor(max_workers=n) as ex:
            list(ex.map(lambda _: do_req(), range(n)))

        assert log_info.call_count == n
        for call in log_info.call_args_list:
            msg = call[0][0]
            assert "GET" in msg and "/c" in msg and "completed in 1" in msg