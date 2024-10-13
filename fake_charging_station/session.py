"""Module for implementing the session plan feature."""

import asyncio

from pydantic import BaseModel

from .custom_logger import get_logger
from .fcs_v16.fcs_v16 import get_fcs, stop_fcs
from .settings import Settings

LOGGER = get_logger("Session Planner")


class SessionPlanRequest(BaseModel):
    """Model of a session plan request."""

    cs_id: str
    vendor: str
    model: str
    ws_url: str
    password: str
    connectors: int = 1
    steps: list[list[str]]


async def execute_session_plan(session_plan_request: SessionPlanRequest) -> bool:
    """Execute a session plan for a new instance of a FCS."""
    LOGGER.info(f"Executing session plan with {session_plan_request=}")

    fcs = await get_fcs(
        cs_id=session_plan_request.cs_id,
        vendor=session_plan_request.vendor,
        model=session_plan_request.model,
        connectors=session_plan_request.connectors,
        password=session_plan_request.password,
        ws_url=session_plan_request.ws_url,
    )

    for step in session_plan_request.steps:
        match step[0]:
            case "status":
                pass
            case "plugin":
                await fcs.plug_in(connector_id=int(step[1]), rfid=step[2])
            case "stop":
                reason = step[2] if len(step) == 3 else None
                await fcs.send_stop_transaction(connector_id=int(step[1]), reason=reason)
            case "unplug":
                stop_tx = step[2] if len(step) == 3 else True
                await fcs.unplug(connector_id=int(step[1]), stop_tx=stop_tx)
            case "charge":
                await fcs.on_set_charging_profile(
                    connector_id=int(step[1]),
                    cs_charging_profiles={
                        "charging_schedule": {"charging_schedule_period": [{"limit": step[2]}]}
                    },
                )
                await fcs.after_set_charging_profile(connector_id=int(step[1]))
            case "wait":
                LOGGER.info(f"Waiting {step[1]}s")
                await asyncio.sleep(int(step[1]))
            case "disconnect":
                await fcs.disconnect()
            case _:
                LOGGER.warning(f"Skipping unsupported: {step}")

    LOGGER.info("Finished session plan")
    await fcs.disconnect()
    return True
