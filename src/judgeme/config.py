import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    SESSION_TIMEOUT_HOURS: int = int(os.getenv("SESSION_TIMEOUT_HOURS", "4"))
    DISPLAY_CAP: int = int(os.getenv("DISPLAY_CAP", "20"))
    ALLOWED_ORIGIN: str = os.getenv("ALLOWED_ORIGIN", "*")


settings = Settings()
