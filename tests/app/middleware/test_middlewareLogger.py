from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from unittest.mock import patch, AsyncMock
import pytest

from fastapi.testclient import TestClient

@pytest.mark.asyncio
@patch('app.middleware.middlewareLogger.timezone_utils.get_timezone_datetime')
@patch('app.middleware.middlewareLogger.log')
async def test_dispatch_success(mock_log, mock_get_tz):
    mock_log.info = AsyncMock()
    mock_log.error = AsyncMock()
    mock_log.info.reset_mock()
    mock_get_tz.side_effect = [1, 2]

    from app.middleware.middlewareLogger import LoggerMiddleware

    app = FastAPI()
    app.add_middleware(LoggerMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return PlainTextResponse("ok", status_code=200)

    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 200

@pytest.mark.asyncio
@patch('app.middleware.middlewareLogger.timezone_utils.get_timezone_datetime')
@patch('app.middleware.middlewareLogger.log')
async def test_dispatch_nameerror(mock_log, mock_get_tz):
    mock_log.info = AsyncMock()
    mock_log.error = AsyncMock()
    mock_log.error.reset_mock()
    mock_log.info.reset_mock()
    mock_get_tz.side_effect = [1, 2]

    from app.middleware.middlewareLogger import LoggerMiddleware

    app = FastAPI()
    app.add_middleware(LoggerMiddleware)

    @app.get("/test")
    async def test_endpoint():
        raise NameError("port")

    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 500

@pytest.mark.asyncio
@patch('app.middleware.middlewareLogger.timezone_utils.get_timezone_datetime')
@patch('app.middleware.middlewareLogger.log')
async def test_dispatch_generic_exception(mock_log, mock_get_tz):
    mock_log.info = AsyncMock()
    mock_log.error = AsyncMock()
    mock_log.error.reset_mock()
    mock_log.info.reset_mock()
    mock_get_tz.side_effect = [1, 2]

    from app.middleware.middlewareLogger import LoggerMiddleware

    app = FastAPI()
    app.add_middleware(LoggerMiddleware)

    @app.get("/test")
    async def test_endpoint():
        raise Exception("fail")

    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 500

@pytest.mark.asyncio
@patch('app.middleware.middlewareLogger.timezone_utils.get_timezone_datetime')
@patch('app.middleware.middlewareLogger.log')
async def test_dispatch_logs_time_difference(mock_log, mock_get_tz):
    mock_log.info = AsyncMock()
    mock_log.error = AsyncMock()
    mock_log.info.reset_mock()
    mock_get_tz.side_effect = [10, 20]

    from app.middleware.middlewareLogger import LoggerMiddleware

    app = FastAPI()
    app.add_middleware(LoggerMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return PlainTextResponse("ok", status_code=200)

    client = TestClient(app)
    client.get("/test")
    assert mock_log.info.called
    log_args = mock_log.info.call_args[0][0]
    assert "completed in 10" in log_args

@pytest.mark.asyncio
@patch('app.middleware.middlewareLogger.timezone_utils.get_timezone_datetime')
@patch('app.middleware.middlewareLogger.log')
async def test_dispatch_request_and_url_in_log(mock_log, mock_get_tz):
    mock_log.info = AsyncMock()
    mock_log.error = AsyncMock()
    mock_log.info.reset_mock()
    mock_get_tz.side_effect = [1, 2]

    from app.middleware.middlewareLogger import LoggerMiddleware

    app = FastAPI()
    app.add_middleware(LoggerMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return PlainTextResponse("ok", status_code=200)

    client = TestClient(app)
    client.get("/test")
    assert mock_log.info.called
    log_args = mock_log.info.call_args[0][0]
    assert "GET" in log_args
    assert "/test" in log_args