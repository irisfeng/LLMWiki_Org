from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://wiki:changeme123@localhost:5432/teamwiki"
    database_url_sync: str = "postgresql://wiki:changeme123@localhost:5432/teamwiki"
    redis_url: str = "redis://localhost:6379/0"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.minimax.chat/v1"
    llm_model: str = "abab6.5s-chat"
    mineru_api_key: str = ""
    auth_password: str = ""
    secret_key: str = ""
    raw_storage_path: str = "./data/raw"
    embedding_model: str = "text-embedding-v3"
    embedding_dim: int = 1024

    class Config:
        env_file = ".env"

settings = Settings()
