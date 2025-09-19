from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from auth_app.app.utils.security import decode_token


class JWTBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super(JWTBearer, self).__init__(auto_error=auto_error)

    async def __call__(self, request: Request):
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)
        if not credentials or credentials.scheme.lower() != "bearer":
            raise HTTPException(status_code=403, detail="Invalid or missing authentication scheme.")

        # Decode and validate token
        payload = decode_token(credentials.credentials)
        if not payload or not payload.get("email"):
            raise HTTPException(status_code=403, detail="Invalid or expired token.")

        return payload  # Return claims like user ID, role, etc.
