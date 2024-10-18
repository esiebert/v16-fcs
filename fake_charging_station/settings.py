"""FCS Config."""

from functools import cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application Settings."""

    cs_id: str
    vendor: str
    model: str
    ws_url: str
    password: str
    connectors: int = 1
    quick_start: bool | None = False
    quick_start_rfid: str | None = "12341234"
    quick_start_connector: int | None = 1
    quick_start_charging: int | None = None


@cache
def get_settings() -> Settings:
    """Get application settings."""
    return Settings()  # type: ignore[call-arg]
