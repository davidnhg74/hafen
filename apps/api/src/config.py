from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    database_url: str = os.getenv("DATABASE_URL", "postgresql://depart:depart_dev_pw@localhost:5432/depart_dev")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    environment: str = os.getenv("ENVIRONMENT", "development")
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    max_upload_size: int = 10 * 1024 * 1024  # 10MB

    class Config:
        env_file = ".env"


settings = Settings()
