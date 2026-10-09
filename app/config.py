import os
from zoneinfo import ZoneInfo
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    # Spotify Configuration
    SPOTIFY_CLIENT_ID: str = os.getenv("SPOTIFY_CLIENT_ID", "")
    SPOTIFY_CLIENT_SECRET: str = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    SPOTIFY_REDIRECT_URI: str = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/auth/callback")
    SPOTIFY_AUTH_URL: str = "https://accounts.spotify.com/authorize"
    SPOTIFY_TOKEN_URL: str = "https://accounts.spotify.com/api/token"
    SPOTIFY_RECENTLY_PLAYED_URL: str = "https://api.spotify.com/v1/me/player/recently-played"
    SPOTIFY_SCOPES: str = "user-read-recently-played"

    # SerpAPI Configuration
    SERPAPI_API_KEY: str = os.getenv("SERPAPI_API_KEY", "")
    SERPAPI_DAILY_BUDGET: int = int(os.getenv("SERPAPI_DAILY_BUDGET", "15"))

    # Daily Limits & Timezone
    USER_DAILY_REFRESH_LIMIT: int = int(os.getenv("USER_DAILY_REFRESH_LIMIT", "15"))
    APP_TIMEZONE: str = os.getenv("APP_TIMEZONE", "Asia/Kolkata")

    # Local Ollama AI
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
    OLLAMA_TIMEOUT_SECONDS: int = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))

    # Security & Storage
    SECRET_KEY: str = os.getenv("SECRET_KEY", "feels-hacktober-secret-key-2026")
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "feels.db")

    # Scope City
    TARGET_CITY: str = "Pune, Maharashtra, India"

    @classmethod
    def get_current_date_str(cls) -> str:
        """Returns the current date string (YYYY-MM-DD) in the configured timezone."""
        try:
            tz = ZoneInfo(cls.APP_TIMEZONE)
        except Exception:
            tz = ZoneInfo("UTC")
        return datetime.now(tz).strftime("%Y-%m-%d")

    @classmethod
    def get_timezone_info(cls) -> ZoneInfo:
        try:
            return ZoneInfo(cls.APP_TIMEZONE)
        except Exception:
            return ZoneInfo("UTC")

settings = Settings()
