import logging
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)

# SECRET_KEY must be set for stable JWT signing across restarts
if not settings.secret_key:
    _secret = uuid.uuid4().hex
    logger.warning(
        "SECRET_KEY is not set! Generated a random key — all sessions will be "
        "lost on restart. Set SECRET_KEY in .env for production."
    )
else:
    _secret = settings.secret_key

if not settings.auth_password:
    logger.warning(
        "AUTH_PASSWORD is not set — authentication is DISABLED. "
        "Set AUTH_PASSWORD in .env to enable login protection."
    )

TOKEN_EXPIRE_HOURS = 24


class LoginRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    if not settings.auth_password:
        raise HTTPException(status_code=500, detail="服务器未配置登录密码")
    if body.password != settings.auth_password:
        raise HTTPException(status_code=401, detail="密码错误")

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
        raise HTTPException(status_code=401, detail="未登录")

    try:
        jwt.decode(credentials.credentials, _secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="登录已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效的登录凭证")

    return True
