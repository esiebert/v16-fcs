import asyncio
import os
import signal
from contextlib import asynccontextmanager

from fastapi import Body, Depends, FastAPI, Response
from ocpp.v16.enums import ChargingProfileStatus
from websockets.headers import build_authorization_basic

from .custom_logger import get_logger
from .main import get_fcs, stop_fcs
from .session import SessionPlanRequest, execute_session_plan
from .settings import Settings, get_settings

FCS = None
LOGGER = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> Response:
    """Lifespan of the app."""
    try:
        # Start a FCS and connect to WS
        global FCS
        settings = get_settings()
        if not settings.on_demand:
            FCS = await get_fcs(
                cs_id=settings.cs_id,
                vendor=settings.vendor,
                model=settings.model,
                connectors=settings.connectors,
                password=settings.password,
                ws_url=settings.ws_url,
                tx_start_charge=settings.quick_start_charging,
            )
            if FCS:
                if settings.quick_start:
                    await asyncio.sleep(3)
                    await FCS.plug_in(
                        settings.quick_start_rfid, settings.quick_start_connector
                    )
                    if settings.quick_start_charging:
                        await asyncio.sleep(3)
                        await FCS.on_set_charging_profile(
                            settings.quick_start_connector,
                            {
                                "charging_schedule": {
                                    "charging_schedule_period": [
                                        {"limit": settings.quick_start_charging}
                                    ]
                                }
                            },
                        )
                        await FCS.after_set_charging_profile(
                            settings.quick_start_connector
                        )
        else:
            LOGGER.info(
                "Starting server without an FCS instance."
                " Use the session_plan endpoint to create an FCS instance."
            )
        yield
    except asyncio.exceptions.CancelledError:
        pass
    finally:
        if FCS:
            await stop_fcs(fcs=FCS)


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
) -> Response:
    """Start a new FCS instance and follow a session plan."""
    await execute_session_plan(session_plan_request)
    return {"message": "Session plan executed"}


@app.get("/fcs/connector/{connector_id}/status")
async def status(connector_id: int = 1) -> Response:
    """Send status notification to CSMS."""
    response = await FCS.send_status_notification(connector_id=connector_id)
    return {"message": "Sending status"}


@app.get("/fcs/connector/{connector_id}/plugin")
async def plugin(connector_id: int = 1, rfid: str | None = None) -> Response:
    """Plug in a connector, and authenticate if RFID is given.

    Make sure the RFID is a know driver in the CSMS.

    \f Truncate output for OpenAPI doc

    Args:
        connector_id: The ID of the connector
        rfid: RFID used to authenticate against the CSMS.
            If given, tries to authenticate and starts a charging session
    """
    await FCS.plug_in(rfid=rfid, connector_id=connector_id)
    return {"message": "Plugging in"}


@app.get("/fcs/connector/{connector_id}/start")
async def start(connector_id: int = 1, rfid: str = "12341234") -> Response:
    """Authenticates and starts transaction at a connector.

    Make sure the RFID is a know driver in the CSMS.

    \f Truncate output for OpenAPI doc

    Args:
        connector_id: The ID of the connector
        rfid: RFID used to authenticate against the CSMS.
    """
    await FCS.send_auth_start(connector_id=connector_id, rfid=rfid)
    return {"message": "Authenticating and starting transaction"}


@app.get("/fcs/connector/{connector_id}/send_charging_profile")
async def send_charging_profile(connector_id: int = 1, limit: int = 100) -> Response:
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
    response = await FCS.on_set_charging_profile(
        connector_id=connector_id,
        cs_charging_profiles={
            "charging_schedule": {"charging_schedule_period": [{"limit": limit}]}
        },
    )

    if response.status == ChargingProfileStatus.rejected:
        return {"message": "Unable to set charging profile to the requested connector"}

    await FCS.after_set_charging_profile(connector_id)
    return {"message": "Charging profile sent"}


@app.post("/fcs/data_transfer")
async def send_data_transfer(payload: dict[str, object] = {}) -> Response:
    """Send a DataTransfer payload to the CSMS.

    \f Truncate output for OpenAPI doc

    Args:
        connector_id: The ID of the connector
        limit: Limit of the charging profile in W
    """
    await FCS.send_data_transfer(payload)
    return {"message": "Sending data transfer payload"}


@app.get("/fcs/connector/{connector_id}/stop")
async def stop(connector_id: int = 1, reason: str | None = None) -> Response:
    """Stop transaction at a connector.

    In order to also unplug the EV, pass `reason=EVDisconnected`

    \f Truncate output for OpenAPI doc

    Args:
        connector_id: The ID of the connector
        send_reason: Whether to send the reason
    """
    await FCS.send_stop_transaction(connector_id=connector_id, reason=reason)
    return {"message": "Stopping transaction"}


@app.get("/fcs/connector/{connector_id}/unplug")
async def unplug(connector_id: int = 1, stop_tx: bool = True) -> Response:
    """Unplug a connector.

    Also sends a StopTransaction if it wasn't remotely stopped.

    \f Truncate output for OpenAPI doc

    Args:
        connector_id: The ID of the connector
    """
    await FCS.unplug(connector_id, stop_tx)
    return {"message": "Unplugging"}


@app.get("/fcs/disc")
async def disconnect() -> Response:
    """Disconnect the FCS from the CSMS."""
    await FCS.disconnect()
    return {"message": "Disconnecting"}


@app.get("/fcs/shutdown")
async def shutdown() -> Response:
    """Shutdown the FCS instance."""
    os.kill(os.getpid(), signal.SIGTERM)
    return {"message": "Shutting down"}
