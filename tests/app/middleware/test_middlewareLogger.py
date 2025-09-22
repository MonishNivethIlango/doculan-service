import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import Request, Response

@pytest.mark.asyncio
@patch('app.middleware.middlewareLogger.timezone_utils.get_timezone_datetime', new_callable=AsyncMock)
@patch('app.middleware.middlewareLogger.log')
async def test_dispatch_success(mock_log, mock_get_tz):
    from app.middleware.middlewareLogger import LoggerMiddleware
    mock_log.info.reset_mock()
    mock_get_tz.side_effect = [1, 2]
    middleware = LoggerMiddleware(app=None)
    request = MagicMock(spec=Request)
    call_next = AsyncMock(return_value=Response('ok', status_code=200))
    response = await middleware.dispatch(request, call_next)
    assert response.status_code == 200
    assert mock_log.info.called
    call_next.assert_awaited_once()

@pytest.mark.asyncio
@patch('app.middleware.middlewareLogger.timezone_utils.get_timezone_datetime', new_callable=AsyncMock)
@patch('app.middleware.middlewareLogger.log')
async def test_dispatch_nameerror(mock_log, mock_get_tz):
    from app.middleware.middlewareLogger import LoggerMiddleware
    mock_log.error.reset_mock()
    mock_log.info.reset_mock()
    mock_get_tz.side_effect = [1, 2]
    middleware = LoggerMiddleware(app=None)
    request = MagicMock(spec=Request)
    call_next = AsyncMock(side_effect=NameError('port'))
    response = await middleware.dispatch(request, call_next)
    assert response.status_code == 500
    assert response.body
    assert mock_log.error.called
    assert mock_log.info.called

@pytest.mark.asyncio
@patch('app.middleware.middlewareLogger.timezone_utils.get_timezone_datetime', new_callable=AsyncMock)
@patch('app.middleware.middlewareLogger.log')
async def test_dispatch_generic_exception(mock_log, mock_get_tz):
    from app.middleware.middlewareLogger import LoggerMiddleware
    mock_log.error.reset_mock()
    mock_log.info.reset_mock()
    mock_get_tz.side_effect = [1, 2]
    middleware = LoggerMiddleware(app=None)
    request = MagicMock(spec=Request)
    call_next = AsyncMock(side_effect=Exception('fail'))
    response = await middleware.dispatch(request, call_next)
    assert response.status_code == 500
    assert response.body
    assert mock_log.error.called
    assert mock_log.info.called

@pytest.mark.asyncio
@patch('app.middleware.middlewareLogger.timezone_utils.get_timezone_datetime', new_callable=AsyncMock)
@patch('app.middleware.middlewareLogger.log')
async def test_dispatch_logs_time_difference(mock_log, mock_get_tz):
    from app.middleware.middlewareLogger import LoggerMiddleware
    mock_log.info.reset_mock()
    mock_get_tz.side_effect = [10, 20]
    middleware = LoggerMiddleware(app=None)
    request = MagicMock(spec=Request)
    call_next = AsyncMock(return_value=Response('ok', status_code=200))
    await middleware.dispatch(request, call_next)
    assert mock_log.info.called
    log_args = mock_log.info.call_args[0][0]
    assert "completed in 10" in log_args



@pytest.mark.asyncio
@patch('app.middleware.middlewareLogger.timezone_utils.get_timezone_datetime', new_callable=AsyncMock)
@patch('app.middleware.middlewareLogger.log')
async def test_dispatch_request_and_url_in_log(mock_log, mock_get_tz):
    from app.middleware.middlewareLogger import LoggerMiddleware
    mock_log.info.reset_mock()
    mock_get_tz.side_effect = [1, 2]
    middleware = LoggerMiddleware(app=None)
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url = "http://testserver/test"
    call_next = AsyncMock(return_value=Response('ok', status_code=200))
    await middleware.dispatch(request, call_next)
    assert mock_log.info.called
    log_args = mock_log.info.call_args[0][0]
    assert "GET" in log_args
    assert "http://testserver/test" in log_args