import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import Request, Response
from app.middleware.middlewareLogger import LoggerMiddleware

@pytest.mark.asyncio
@patch('app.middleware.middlewareLogger.timezone_utils')
@patch('app.middleware.middlewareLogger.log')
async def test_dispatch_success(mock_log, mock_tz):
    # Arrange
    mock_tz.get_timezone_datetime.side_effect = [1, 2]
    middleware = LoggerMiddleware(app=None)
    request = MagicMock(spec=Request)
    call_next = AsyncMock(return_value=Response('ok', status_code=200))
    # Act
    response = await middleware.dispatch(request, call_next)
    # Assert
    assert response.status_code == 200
    mock_log.info.assert_called()
    call_next.assert_awaited_once()

@pytest.mark.asyncio
@patch('app.middleware.middlewareLogger.timezone_utils')
@patch('app.middleware.middlewareLogger.log')
async def test_dispatch_nameerror(mock_log, mock_tz):
    mock_tz.get_timezone_datetime.side_effect = [1, 2]
    middleware = LoggerMiddleware(app=None)
    request = MagicMock(spec=Request)
    call_next = AsyncMock(side_effect=NameError('port'))
    response = await middleware.dispatch(request, call_next)
    assert response.status_code == 500
    assert response.body
    mock_log.error.assert_called()

@pytest.mark.asyncio
@patch('app.middleware.middlewareLogger.timezone_utils')
@patch('app.middleware.middlewareLogger.log')
async def test_dispatch_generic_exception(mock_log, mock_tz):
    mock_tz.get_timezone_datetime.side_effect = [1, 2]
    middleware = LoggerMiddleware(app=None)
    request = MagicMock(spec=Request)
    call_next = AsyncMock(side_effect=Exception('fail'))
    response = await middleware.dispatch(request, call_next)
    assert response.status_code == 500
    assert response.body
    mock_log.error.assert_called()
