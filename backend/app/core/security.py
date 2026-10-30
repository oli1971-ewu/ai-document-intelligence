from fastapi import Header, HTTPException, status
from .config import settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Simple API-key auth. In production, swap for OAuth2/JWT."""
    if not x_api_key or x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header",
        )
