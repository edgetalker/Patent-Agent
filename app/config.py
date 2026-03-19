from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Patent Agent API"
    app_version: str = "1.0.0"
    debug: bool = False

    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepkseek.com/v1"
    deepseek_model: str = "deepseek-reasoning"
    deepseek_max_tokens: int = 4096
    deepseek_temperature: float = 0.3

    db_path: str = "patent_sessions.db"

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8501"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

@lru_cache()
def get_settings() -> Settings:
    return Settings()

