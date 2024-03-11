"""FCS Config."""

from functools import cache

from pydantic import BaseSettings


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
    quick_start_charging_limit: int | None = None
    on_demand: bool | None = True

    class Config:
        """Settings Config."""

        env_nested_delimiter = "__"
        allow_mutation = False
        frozen = True


@cache
def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
