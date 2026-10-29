from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / "backend/.env"), extra="ignore")
    database_url: str = "postgresql://rag:rag_local_only@127.0.0.1:55432/security_rag"
    library_database: Path = PROJECT_ROOT / "database/sqlite/library.sqlite3"
    api_key: str = ""
    chat_base_url: str = "https://api.deepseek.com"
    chat_api_key: str = ""
    chat_model: str = "deepseek-flash"
    embedding_base_url: str = "http://127.0.0.1:8001/v1"
    embedding_api_key: str = ""
    embedding_model: str = "replace-with-your-embedding-model"
    embedding_dim: int = Field(default=1024, ge=1, le=2000)

    @property
    def embedding_space(self) -> str:
        # 同维度不同模型也不允许混用。
        return f"{self.embedding_base_url.rstrip('/')}|{self.embedding_model}|{self.embedding_dim}"


@lru_cache
def settings() -> Settings:
    return Settings()
