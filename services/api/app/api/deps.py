from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

bearer = HTTPBearer(auto_error=False)


def require_auth(
    creds: HTTPAuthorizationCredentials | None = Security(bearer),
) -> str:
    settings = get_settings()
    token = creds.credentials if creds else None
    if not token or token != settings.shelfready_api_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return token
