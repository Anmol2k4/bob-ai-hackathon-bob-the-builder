import os
from dataclasses import dataclass
from pathlib import Path

# Auto-load .env if present (never required — env vars take precedence)
try:
    from dotenv import load_dotenv
    _env = Path(__file__).parent / ".env"
    if _env.exists():
        load_dotenv(_env)
except ImportError:
    pass  # python-dotenv not installed — rely on environment variables directly


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("APP_HOST", "127.0.0.1")
    port: int = int(os.getenv("APP_PORT", "8000"))
    mongodb_uri: str = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017")
    mongodb_database: str = os.getenv("MONGODB_DATABASE", "trialguard")
    session_secret: str = os.getenv("SESSION_SECRET", "local-demo-session-secret")
    session_hours: int = int(os.getenv("SESSION_HOURS", "8"))


settings = Settings()
