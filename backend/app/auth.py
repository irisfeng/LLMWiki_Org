import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)

# Auto-generate secret key if not set
_secret = settings.secret_key or uuid.uuid4().hex

TOKEN_EXPIRE_HOURS = 24


class LoginRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    if not settings.auth_password:
        raise HTTPException(status_code=500, detail="AUTH_PASSWORD not configured on server")
    if body.password != settings.auth_password:
        raise HTTPException(status_code=401, detail="Incorrect password")

    payload = {
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
        "sub": "team-user",
    }
    token = jwt.encode(payload, _secret, algorithm="HS256")
    return TokenResponse(access_token=token)


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Dependency that protects routes. Skipped if AUTH_PASSWORD is empty."""
    if not settings.auth_password:
        return None  # No auth configured, allow all

    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        jwt.decode(credentials.credentials, _secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    return True
