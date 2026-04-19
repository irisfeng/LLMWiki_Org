from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://wiki:changeme123@localhost:5432/teamwiki"
    database_url_sync: str = "postgresql://wiki:changeme123@localhost:5432/teamwiki"
    redis_url: str = "redis://localhost:6379/0"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.minimax.chat/v1"
    llm_model: str = "abab6.5s-chat"
    llm_provider: str = "dashscope"  # "dashscope" | "doubao" | "openai" — controls thinking param dialect
    # Volcengine Ark fallback. Triggers on primary 5xx/timeout/429.
    fallback_api_key: str = ""
    fallback_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    fallback_model: str = "doubao-seed-2-0-lite-260215"
    fallback_provider: str = "doubao"
    mineru_api_key: str = ""
    auth_password: str = ""
    secret_key: str = ""
    raw_storage_path: str = "./data/raw"
    embedding_model: str = "text-embedding-v3"
    embedding_dim: int = 1024
    cors_origins: str = ""  # Comma-separated allowed origins, empty = same-origin only
    debug: bool = False  # Set DEBUG=true in .env for local development (allows no auth password)

    class Config:
        env_file = ".env"

settings = Settings()
