from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings

EXEMPT_PATHS = {"/", "/health"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse({"detail": "Missing or malformed Authorization header"}, status_code=401)

        token = auth.removeprefix("Bearer ").strip()
        if token != settings.api_key:
            return JSONResponse({"detail": "Invalid API key"}, status_code=401)

        return await call_next(request)
