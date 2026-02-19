import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./japan_planner.db"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-key-change-me")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ROOT_PATH: str = os.getenv("ROOT_PATH", "")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
