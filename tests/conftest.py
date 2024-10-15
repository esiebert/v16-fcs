"""Fixtures and utils for testing."""

from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from fake_charging_station.app import app
from fake_charging_station.fcs_v16.fcs_v16 import FakeChargingStation


@pytest.fixture
def fake_fcs():
    app.FCS = FakeFCS()
    return app.FCS


@pytest.fixture
async def async_client(fake_fcs) -> AsyncGenerator[AsyncClient, None]:
    """Async client for testing purposes."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


class FakeFCS(FakeChargingStation):
    """Fake instance of a FCS."""

    def __init__(self, call_return: object | None = None) -> None:
        """Initialize the fake FCS."""
        super().__init__("test_id", "test_vendor", "test_model")
        self.call_return = call_return

    async def send_status_notification(self, connector_id: int) -> None:
        return

    async def send_start_transaction(self, connector_id: int) -> None:
        return

    async def call(self, request):
        """Return a predefined object on `call`."""
        return self.call_return
