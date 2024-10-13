"""Module holding definitions and endpoints of the application."""

import asyncio
import os
import signal
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Body, Depends, FastAPI, Response
from ocpp.v16.enums import ChargingProfileStatus
from websockets.headers import build_authorization_basic

from .custom_logger import get_logger
from .fcs_v16.fcs_v16 import get_fcs, quick_start_fcs, stop_fcs
from .session import SessionPlanRequest, execute_session_plan
from .settings import Settings, get_settings

LOGGER = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan of the app.

    Runs up a FCS on application start up, and connects to the CSMS backend
    through WebSocket. Once the application is shutdown, tries to disconnect
    the FCS gracefully with the CSMS.

    If the On Demand feature is activated, FCS only starts once a session plan
    is sent.
    """
    try:
        # Start a FCS and connect to WS
        settings = get_settings()
        if not settings.on_demand:
            app.FCS = await get_fcs(settings=settings)  # type: ignore[attr-defined]
        else:
            LOGGER.info(
                "Starting server without an FCS instance."
                " Use the session_plan endpoint to create an FCS instance."
            )
        yield
    except asyncio.exceptions.CancelledError:
        pass
    finally:
        # Stop FCS gracefully
        if app.FCS:  # type: ignore[attr-defined]
            await stop_fcs(fcs=app.FCS)  # type: ignore[attr-defined]


app = FastAPI(
    title="Fake Charging Station App",
    lifespan=lifespan,
    description="API for controlling a fake charging station.",
)


session_plan_example = Body(
    ...,
    example=SessionPlanRequest(
        cs_id="fake_v16_station",
        password="9TaK9aKGaDaaaNaN",
        ws_url="ws://csms.url.com/cpo_url",
        vendor="Foo",
        model="Bar-42",
        steps=[
            ["wait", 2],
            ["plugin", 1, "12341234"],
            ["wait", 2],
            ["charge", 1, 500],
            ["wait", 30],
            ["stop", 1],
            ["wait", 30],
            ["unplug", 1],
            ["disconnect"],
        ],
    ).dict(),
)


@app.post("/fcs/session_plan")
async def session_plan(
    session_plan_request: SessionPlanRequest = session_plan_example,
) -> dict[str, str]:
    """Start a new FCS instance and follow a session plan.

    \f Truncate output for OpenAPI doc

    Args:
        session_plan_request: Plan for the charging session to be followed
    """
    await execute_session_plan(session_plan_request=session_plan_request)
    return {"message": "Session plan executed"}


@app.get("/fcs/connector/{connector_id}/status")
async def status(connector_id: int = 1) -> dict[str, str]:
    """Send status notification to CSMS.

    \f Truncate output for OpenAPI doc

    Args:
        connector_id: The ID of the connector
    """
    response = await app.FCS.send_status_notification(connector_id=connector_id)  # type: ignore[attr-defined]
    return {"message": "Sending status"}


@app.get("/fcs/connector/{connector_id}/plugin")
async def plugin(connector_id: int = 1, rfid: str | None = None) -> dict[str, str]:
    """Plug in a connector, and authenticate if RFID is given.

    Make sure the RFID is a know driver in the CSMS.

    \f Truncate output for OpenAPI doc

    Args:
        connector_id: The ID of the connector
        rfid: RFID used to authenticate against the CSMS.
            If given, tries to authenticate and starts a charging session
    """
    await app.FCS.plug_in(rfid=rfid, connector_id=connector_id)  # type: ignore[attr-defined]
    return {"message": "Plugging in"}


@app.get("/fcs/connector/{connector_id}/start")
async def start(connector_id: int = 1, rfid: str = "12341234") -> dict[str, str]:
    """Authenticates and starts transaction at a connector.

    Make sure the RFID is a know driver in the CSMS.

    \f Truncate output for OpenAPI doc

    Args:
        connector_id: The ID of the connector
        rfid: RFID used to authenticate against the CSMS
    """
    await app.FCS.send_auth_start(connector_id=connector_id, rfid=rfid)  # type: ignore[attr-defined]
    return {"message": "Authenticating and starting transaction"}


@app.get("/fcs/connector/{connector_id}/send_charging_profile")
async def send_charging_profile(connector_id: int = 1, limit: int = 100) -> dict[str, str]:
    """Send a charging profile with a limit in W.

    Limits have different effects on the EV's behavior:
    - Limit > 0   -> EV will charge with the amount of W every meter value interval
    - Limit == 0  -> EV will stop charging and SuspendedEVSE will be reported
    - Limit == -1 -> EV will stop charging and SuspendedEV will be reported
    - Limit == -2 -> EV will stop charging and Finishing will be reported

    \f Truncate output for OpenAPI doc

    Args:
        connector_id: The ID of the connector
        limit: Limit of the charging profile in W
    """
    response = await app.FCS.on_set_charging_profile(  # type: ignore[attr-defined]
        connector_id=connector_id,
        cs_charging_profiles={
            "charging_schedule": {"charging_schedule_period": [{"limit": limit}]}
        },
    )

    if response.status == ChargingProfileStatus.rejected:
        return {"message": "Unable to set charging profile to the requested connector"}

    await app.FCS.after_set_charging_profile(connector_id=connector_id)  # type: ignore[attr-defined]
    return {"message": "Charging profile sent"}


@app.post("/fcs/data_transfer")
async def send_data_transfer(payload: dict[str, object] = {}) -> dict[str, str]:
    """Send a DataTransfer payload to the CSMS.

    \f Truncate output for OpenAPI doc

    Args:
        payload: Payload to be sent in a DataTransfer request
    """
    await app.FCS.send_data_transfer(payload=payload)  # type: ignore[attr-defined]
    return {"message": "Sending data transfer payload"}


@app.get("/fcs/connector/{connector_id}/stop")
async def stop(connector_id: int = 1, reason: str | None = None) -> dict[str, str]:
    """Stop transaction at a connector.

    In order to also unplug the EV, pass `reason=EVDisconnected`

    \f Truncate output for OpenAPI doc

    Args:
        connector_id: The ID of the connector
        reason: Reason for stopping the transaction. Defaults to None.
    """
    await app.FCS.send_stop_transaction(connector_id=connector_id, reason=reason)  # type: ignore[attr-defined]
    return {"message": "Stopping transaction"}


@app.get("/fcs/connector/{connector_id}/unplug")
async def unplug(connector_id: int = 1, stop_tx: bool = True) -> dict[str, str]:
    """Unplug a connector.

    Also sends a StopTransaction if it wasn't remotely stopped.

    \f Truncate output for OpenAPI doc

    Args:
        connector_id: The ID of the connector
        stop_tx: Whether transaction should be stopped after unplugging connector.
            Defaults to True.
    """
    await app.FCS.unplug(connector_id=connector_id, stop_tx=stop_tx)  # type: ignore[attr-defined]
    return {"message": "Unplugging"}


@app.get("/fcs/disc")
async def disconnect() -> dict[str, str]:
    """Disconnect the FCS from the CSMS."""
    await app.FCS.disconnect()  # type: ignore[attr-defined]
    return {"message": "Disconnecting"}


@app.get("/fcs/shutdown")
async def shutdown() -> dict[str, str]:
    """Shutdown the FCS instance."""
    os.kill(os.getpid(), signal.SIGTERM)
    return {"message": "Shutting down"}
