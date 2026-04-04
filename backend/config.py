"""Application configuration via Pydantic BaseSettings.

Reads environment variables from .env file and provides typed settings
for the entire backend application.
"""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DUCKDB_PATH: str = "./data/stock_dashboard.duckdb"

    # External API keys
    ANTHROPIC_API_KEY: str = ""
    FINNHUB_API_KEY: str = ""

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    # Cache TTL (seconds)
    MARKET_DATA_TTL: int = 900  # 15 minutes
    FUNDAMENTALS_TTL: int = 86400  # 1 day

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def duckdb_path(self) -> Path:
        """Return DuckDB path as a Path object."""
        return Path(self.DUCKDB_PATH)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return cached settings singleton.

    Returns:
        Settings: Application settings instance.
    """
    global _settings  # noqa: PLW0603
    if _settings is None:
        _settings = Settings()
    return _settings
