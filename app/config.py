import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    app_name: str = "Patent Agent API"
    app_version: str = "1.0.0"
    debug: bool = False

    llm_api_key: str = os.getenv("LLM_API_KEY")
    llm_base_url: str = os.getenv("LLM_BASE_URL")
    llm_model_name: str = os.getenv("LLM_MODEL_NAME")
    deepseek_max_tokens: int = 4096
    deepseek_temperature: float = 0.3

    db_path: str = "patent_sessions.db"

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8501"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

@lru_cache()
def get_settings() -> Settings:
    return Settings()

