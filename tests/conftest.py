from typing import AsyncGenerator

import pytest
from httpx import AsyncClient

from fake_charging_station.app import app
from fake_charging_station.fcs_v16.fcs_v16 import FakeChargingStation


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Async client for testing purposes."""
    app.FCS = FakeFCS("test_id", "test_vendor", "test_model")
    async with AsyncClient(app=app, base_url="http://test") as async_client:
        yield async_client


class FakeFCS(FakeChargingStation):
    async def send_status_notification(self, connector_id: int):
        return
