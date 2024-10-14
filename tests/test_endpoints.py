from fastapi import status
from httpx import AsyncClient


async def test_endpoint(async_client: AsyncClient) -> None:
    response = await async_client.post("/fcs/connector/1/status")

    assert response.status_code == status.HTTP_204_NO_CONTENT
