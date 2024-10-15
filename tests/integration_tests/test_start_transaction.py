"""Tests for the start_transaction endpoint"""

from fastapi import status
from httpx import AsyncClient
from ocpp.v16 import call_result
from ocpp.v16.enums import AuthorizationStatus

from tests.conftest import FakeFCS


async def test_start_transaction(async_client: AsyncClient, fake_fcs: FakeFCS) -> None:
    """Test starting a transaction."""
    fake_fcs.connectors[1].plugged_in = True
    fake_fcs.call_return = call_result.AuthorizePayload(
        id_tag_info={"status": AuthorizationStatus.accepted}
    )

    response = await async_client.post("/fcs/connector/1/start?rfid=1234")

    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_start_transaction_not_plugged(async_client: AsyncClient) -> None:
    """Test starting a transaction when connector is not plugged."""
    response = await async_client.post("/fcs/connector/1/start")

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == (
        "Request rejected by the CS: Unable to authorize when nothing is plugged in"
    )


async def test_start_transaction_no_response(
    async_client: AsyncClient, fake_fcs: FakeFCS
) -> None:
    """Test starting a transaction when CSMS doesn't respond to the auth request."""
    fake_fcs.connectors[1].plugged_in = True

    response = await async_client.post("/fcs/connector/1/start?rfid=1234")

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == (
        "Request rejected by the CSMS: Could not authorize RFID: 1234"
    )


async def test_start_transaction_invalid(
    async_client: AsyncClient, fake_fcs: FakeFCS
) -> None:
    """Test starting a transaction when CSMS rejects the auth request."""
    fake_fcs.connectors[1].plugged_in = True
    fake_fcs.call_return = call_result.AuthorizePayload(
        id_tag_info={"status": AuthorizationStatus.invalid}
    )

    response = await async_client.post("/fcs/connector/1/start?rfid=1234")

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == (
        "Request rejected by the CSMS: Could not authorize RFID: 1234"
    )
