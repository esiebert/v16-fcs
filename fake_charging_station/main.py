import asyncio
import logging
from functools import cache

from websockets.headers import build_authorization_basic

from .fcs_v16 import FakeChargingStation
from .settings import Settings

LOGGER = logging.getLogger("main")
logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.INFO)


@cache
async def get_fcs(
    cs_id, vendor, model, connectors, password, ws_url
) -> FakeChargingStation:
    fcs = FakeChargingStation(
        id=cs_id,
        vendor=vendor,
        model=model,
        number_of_connectors=connectors,
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
