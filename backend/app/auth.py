"""
Simple single-user bearer-token authentication.

Every protected route gets `Depends(require_auth)`. The token is read from
the Authorization header as "Bearer <token>" and compared against APP_TOKEN
from .env. No JWTs, no sessions, no multi-user logic needed.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

# FastAPI's built-in bearer scheme — extracts the token from the header
bearer_scheme = HTTPBearer()


def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> None:
    """
    Dependency that validates the bearer token.
    Raises 401 if the token is missing or wrong.
    """
    if credentials.credentials != settings.app_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
