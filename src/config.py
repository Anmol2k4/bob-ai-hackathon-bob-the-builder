import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("APP_HOST", "127.0.0.1")
    port: int = int(os.getenv("APP_PORT", "8000"))
    mongodb_uri: str = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017")
    mongodb_database: str = os.getenv("MONGODB_DATABASE", "trialguard")
    session_secret: str = os.getenv("SESSION_SECRET", "local-demo-session-secret")
    session_hours: int = int(os.getenv("SESSION_HOURS", "8"))


settings = Settings()
