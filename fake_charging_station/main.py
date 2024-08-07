import asyncio
from functools import cache

from websockets.headers import build_authorization_basic

from .custom_logger import get_logger
from .fcs_v16 import FakeChargingStation
from .settings import Settings

LOGGER = get_logger("main")


@cache
async def get_fcs(
    cs_id, vendor, model, connectors, password, ws_url, tx_start_charge
) -> FakeChargingStation:
    fcs = FakeChargingStation(
        id=cs_id,
        vendor=vendor,
        model=model,
        number_of_connectors=connectors,
        tx_start_charge=tx_start_charge,
    )
    basic_auth = {"Authorization": build_authorization_basic(cs_id, password)}
    try:
        if not await fcs.boot_up(ws_url, basic_auth):
            return None
    except Exception as e:
        LOGGER.exception(str(e))
    return fcs


async def stop_fcs(fcs: FakeChargingStation) -> None:
    LOGGER.info("Stopping services gracefully")
    for connector_id in fcs.connectors.keys():
        await fcs.unplug(connector_id)
    await asyncio.sleep(5)
    if fcs.connected:
        await fcs.disconnect()
