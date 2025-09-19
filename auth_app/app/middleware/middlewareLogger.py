from app.utils.log import log
from app.utils.timezones import timezone_utils

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse


class LoggerMiddleware(BaseHTTPMiddleware):
    """Record request log middleware"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = timezone_utils.get_timezone_datetime()
        try:
            # Process the request and get the response
            response = await call_next(request)
        except NameError as e:
            # Handle cases where variables (e.g., 'port') are undefined
            log.error(f"NameError occurred: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"error": "A server error occurred", "details": f"Undefined variable: {str(e)}"},
            )
        except Exception as e:
            # Generic error handling for other unexpected exceptions
            log.error(f"Unhandled error: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"error": "A server error occurred", "details": "An unexpected error occurred"},
            )
        finally:
            # Calculate and log the request's processing time
            end_time = timezone_utils.get_timezone_datetime()
            log.info(f'{request.method} {request.url} completed in {end_time - start_time}')
        return response
