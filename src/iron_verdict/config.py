import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    SESSION_TIMEOUT_HOURS: int = int(os.getenv("SESSION_TIMEOUT_HOURS", "4"))
    DISPLAY_CAP: int = int(os.getenv("DISPLAY_CAP", "20"))
    ALLOWED_ORIGIN: str = os.getenv("ALLOWED_ORIGIN", "*")
    APP_VERSION: str = os.getenv("APP_VERSION", "dev")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    SNAPSHOT_PATH: str = os.getenv("SNAPSHOT_PATH", "/data/sessions.json")


settings = Settings()
