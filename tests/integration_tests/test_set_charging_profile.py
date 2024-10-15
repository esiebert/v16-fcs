"""Tests for the set_charging_profile endpoint."""

from fastapi import status
from httpx import AsyncClient
from ocpp.v16.enums import ChargePointStatus

from tests.conftest import FakeFCS


async def test_set_charging_profile(
    async_client: AsyncClient, fake_fcs: FakeFCS
) -> None:
    """Test setting a charging profile."""
    fake_fcs.connectors[1].status = ChargePointStatus.preparing
    fake_fcs.connectors[1].plugged_in = True

    response = await async_client.post("/fcs/connector/1/set_charging_profile?limit=99")

    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_set_charging_profile_not_ready_to_charge(
    async_client: AsyncClient,
) -> None:
    """Test setting a charging profile when it's not ready to charge."""
    response = await async_client.post("/fcs/connector/1/set_charging_profile?limit=99")

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == (
        "Unable to set charging profile: connector not ready to charge"
    )
