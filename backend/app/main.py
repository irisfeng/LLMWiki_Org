from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import sources, wiki, chat, lint
from app.auth import router as auth_router, verify_token

app = FastAPI(title="Team LLM Wiki", version="0.1.0")

# CORS: configure via CORS_ORIGINS env var (comma-separated).
# In production, frontend is served via nginx reverse proxy (same origin),
# so CORS is not needed. Only set CORS_ORIGINS for dev or cross-origin setups.
from app.config import settings as _settings

_cors_origins = [o.strip() for o in _settings.cors_origins.split(",") if o.strip()] if _settings.cors_origins else []

if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Public routes
app.include_router(auth_router)

# Protected routes (require valid token when AUTH_PASSWORD is set)
app.include_router(sources.router, dependencies=[Depends(verify_token)])
app.include_router(wiki.router, dependencies=[Depends(verify_token)])
app.include_router(chat.router, dependencies=[Depends(verify_token)])
app.include_router(lint.router, dependencies=[Depends(verify_token)])


@app.get("/health")
async def health():
    return {"status": "ok"}
