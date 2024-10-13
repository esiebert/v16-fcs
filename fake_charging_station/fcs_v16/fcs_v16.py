"""Implementation of the OCPP v1.6 fake charging station."""

import json
from asyncio import Task, create_task, sleep
from datetime import datetime, timezone
from typing import cast

from ocpp.routing import after, on
from ocpp.v16 import ChargePoint, call, call_result
from ocpp.v16.enums import (
    Action,
    AuthorizationStatus,
    AvailabilityType,
    ChargePointStatus,
    ChargingProfileStatus,
    ConfigurationStatus,
    Reason,
    RegistrationStatus,
    RemoteStartStopStatus,
)
from websockets.client import connect as connect_ws
from websockets.headers import build_authorization_basic

from fake_charging_station.custom_logger import get_logger
from fake_charging_station.settings import Settings

from .connector import Connector
from .meter_values import METER_VALUES_SAMPLED_DATA

LOGGER = get_logger("fcs")


class FakeChargingStation(ChargePoint):
    """Implementation of a fake OCPP 1.6 charging station."""

    class RejectedRequestError(Exception):
        """Custom error for when a request was rejected by the CS/CSMS."""

        def __init__(self, source: str, message: str) -> None:
            """Construct the exception."""
            self.source = source
            self.message = f"Request rejected by the {source}: {message}"

    def __init__(
        self,
        id: int,
        vendor: str,
        model: str,
        number_of_connectors: int = 1,
        tx_start_charge: int | None = None,
    ) -> None:
        ChargePoint.__init__(self, id, None)

        self.id = id
        self.connectors = {
            (i + 1): Connector(connector_id=(i + 1)) for i in range(number_of_connectors)
        }
        self.tasks: list[Task] = []
        self.vendor = vendor
        self.model = model
        self.firmware_version = "v1337"
        self.serial_number = "12345678"
        self.configuration = {
            "HeartbeatInterval": "600",
            "MeterValuesSampledData": METER_VALUES_SAMPLED_DATA,
            "MeterValueSampleInterval": "10",
            "NumberOfConnectors": str(number_of_connectors),
            "AuthorizeRemoteTxRequests": "false",
        }
        self.transaction_connector: dict[int, int] = {}
        self.connected = False
        self.tx_start_charge = tx_start_charge

    async def start(self) -> None:
        """Start charge point's receiver task."""
        await super().start()

    async def boot_up(self, ws_url: str, extra_headers: dict[str, str]) -> bool:
        """Boot the charging station up."""
        LOGGER.info(f"Connecting {self.id} to backend: {ws_url}")
        try:
            self._connection = await connect_ws(
                f"{ws_url}/{self.id}",
                subprotocols=["ocpp1.6"],  # type: ignore[list-item]
                ssl=None,
                extra_headers=extra_headers,
            )
        except Exception as e:
            raise Exception("Server rejected WS connection. Is this CS configured in the CSMS?")

        # Start receiver task
        recv_task = create_task(self.start())

        # Send boot notification followed by status notification
        if not await self.send_boot_notification():
            LOGGER.warning("BootNotification was not accepted. Cancelling task.")
            recv_task.cancel()
            return False

        # Send status notification for all connectors
        await self.send_status_notification(connector_id=0)

        # Start heartbeat and meter values loops
        heartbeat_loop = create_task(self.send_heartbeat())
        meter_values_loop = create_task(self.meter_value_loop())
        self.tasks = [recv_task, heartbeat_loop, meter_values_loop]

        self.connected = True
        LOGGER.info(f"{self.id} connected to backend")
        return True

    async def send_heartbeat(self) -> None:
        """Make the heart beat."""
        LOGGER.info("Starting Heartbeat loop")
        await sleep(5)
        while True:
            request = call.HeartbeatPayload()
            await self.call(request)
            await sleep(
                int(self.configuration["HeartbeatInterval"])  # type: ignore[call-overload]
            )

    async def meter_value_loop(self) -> None:
        """Main loop for sending meter values of all configured connectors.

        Only sends meter values of connectors that are currently charging (non-zero
        offered power).
        """
        LOGGER.info("Starting Meter Values Task")
        while True:
            for connector in self.connectors.values():
                if connector.status == ChargePointStatus.charging:
                    connector.consume_energy()
                    request = connector.get_meter_values()
                    await self.call(request)
            await sleep(
                int(self.configuration["MeterValueSampleInterval"])  # type: ignore[call-overload]
            )

    async def disconnect(self) -> None:
        """Close websocket connection and stop sending meter values and heartbeats."""
        LOGGER.info(f"Disconnecting {self.id} from CSMS")
        [task.cancel() for task in self.tasks]
        self.tasks = []
        await self._connection.close()
        self.connected = False

    async def send_boot_notification(self) -> bool:
        """Send a boot notification and set heartbeat interval."""
        request = call.BootNotificationPayload(
            charge_point_model=self.model,
            charge_point_vendor=self.vendor,
            charge_point_serial_number=self.serial_number,
            firmware_version=self.firmware_version,
        )
        resp = await self.call(request)

        LOGGER.info("BootNotification status: %s", resp.status)
        if resp.status == RegistrationStatus.rejected:
            return False

        self.configuration["HeartbeatInterval"] = resp.interval
        return True

    async def plug_in(self, rfid: str | None, connector_id: int) -> None:
        """Plug a connector, sends auth request and starts transaction."""
        LOGGER.info(f"Plugging in {connector_id=}")

        self.connectors[connector_id].plugged_in = True
        await self.change_status(connector_id=connector_id, new_status=ChargePointStatus.preparing)

        if rfid:
            LOGGER.info(f"Authenticating and starting transaction {connector_id=}")
            await self.send_auth_start(connector_id=connector_id, rfid=rfid)

    async def send_auth_start(self, connector_id: int, rfid: str) -> None:
        """Authorize against CSMS and start transaction if RFID is present."""
        if not self.connectors[connector_id].plugged_in:
            raise FakeChargingStation.RejectedRequestError(
                source="CS", message="Unable to authorize when nothing is plugged in"
            )
        if await self.send_authorize(connector_id=connector_id, rfid=rfid):
            await self.send_start_transaction(connector_id=connector_id)
        else:
            raise FakeChargingStation.RejectedRequestError(
                source="CSMS", message=f"Could not authorize RFID: {rfid}"
            )

    async def send_authorize(self, connector_id: int, rfid: str) -> bool:
        """Send auth request and status notification."""
        auth_request = call.AuthorizePayload(id_tag=rfid)
        resp = await self.call(auth_request)
        if resp is None:
            return False

        LOGGER.debug(
            f"Auth status for {connector_id=} with {rfid}:" f" {resp.id_tag_info['status']}"
        )

        if resp.id_tag_info["status"] == AuthorizationStatus.accepted:
            self.connectors[connector_id].id_tag = rfid
            await self.change_status(
                connector_id=connector_id, new_status=ChargePointStatus.preparing
            )
            return True
        return False

    async def change_status(self, connector_id: int, new_status: ChargePointStatus) -> None:
        """Change status of a connector.

        Send StatusNotification if status is different from previous one.
        """
        connector = self.connectors[connector_id]
        if connector.status != new_status:
            connector.status = new_status
            await self.send_status_notification(connector_id=connector_id)

    async def send_start_transaction(self, connector_id: int) -> None:
        """Start transaction in a connector."""
        LOGGER.debug(f"Sending StartTransaction for {connector_id=}")

        connector = self.connectors[connector_id]
        request = call.StartTransactionPayload(
            connector_id=connector_id,
            id_tag=connector.id_tag,
            meter_start=0,
            timestamp=datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

        resp = await self.call(request)
        if not resp.transaction_id:
            return

        connector.transaction_id = resp.transaction_id
        connector.already_stopped = False
        self.transaction_connector[resp.transaction_id] = connector_id

        if self.tx_start_charge:
            connector.power_offered = self.tx_start_charge
            connector.update_status()

        await sleep(5)
        await self.send_status_notification(connector_id=connector_id)

    @on(Action.RemoteStartTransaction)
    async def on_remote_start_transaction(
        self, id_tag: str, connector_id: int | None = None, chaging_profile=None
    ):
        """Handle RemoteStartTransaction request."""
        LOGGER.info(f"Remote start transaction requested for {connector_id=} with {id_tag=}")
        if connector_id is None:
            return call_result.RemoteStartTransactionPayload(status=RemoteStartStopStatus.rejected)
        self.connectors[connector_id].id_tag = id_tag
        return call_result.RemoteStartTransactionPayload(status=RemoteStartStopStatus.accepted)

    @after(Action.RemoteStartTransaction)
    async def after_remote_start_transaction(
        self, id_tag: str, connector_id: int = 1, chaging_profile=None
    ):
        """Action to be taken after a RemoteStartTransaction was handled."""
        if self.connectors[connector_id].id_tag is not None:
            await self.send_start_transaction(connector_id=connector_id)

    async def send_stop_transaction(self, connector_id: int, reason: Reason | None = None) -> None:
        """Stop transaction in a connector."""
        connector = self.connectors[connector_id]
        if connector.pending_stop_tx is None:
            transaction_id = cast(int, connector.transaction_id)
            id_tag = cast(str, connector.id_tag)
            energy_import_register = round(cast(float, connector.energy_import_register))
        else:
            # Handle case where a stop transaction was pending e.g. the connector
            # was unplugged but we want to send the stop transaction afterwards
            transaction_id = cast(int, connector.pending_stop_tx["transaction_id"])
            id_tag = cast(str, connector.pending_stop_tx["id_tag"])
            energy_import_register = round(
                cast(float, connector.pending_stop_tx["energy_import_register"])
            )

        request = call.StopTransactionPayload(
            transaction_id=transaction_id,
            id_tag=id_tag,
            meter_stop=energy_import_register,
            timestamp=datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            reason=reason,
        )

        LOGGER.debug(f"Sending StopTransaction for {connector_id=}")
        await self.call(request)
        del self.transaction_connector[transaction_id]
        if connector.pending_stop_tx is None:
            connector.already_stopped = True
            await self.change_status(
                connector_id=connector_id, new_status=ChargePointStatus.finishing
            )
        else:
            connector.reset()

    @on(Action.RemoteStopTransaction)
    async def on_remote_stop_transaction(self, transaction_id: str):
        """Handle RemoteStopTransaction request."""
        LOGGER.info(f"Remote stop transaction requested for {transaction_id=}")
        if transaction_id in self.transaction_connector.keys():
            return call_result.RemoteStopTransactionPayload(status=RemoteStartStopStatus.accepted)
        return call_result.RemoteStopTransactionPayload(status=RemoteStartStopStatus.rejected)

    @after(Action.RemoteStopTransaction)
    async def after_remote_stop_transaction(self, transaction_id: str):
        """Action to be taken after a RemoteStopTransaction was handled."""
        if transaction_id in self.transaction_connector.keys():
            await self.send_stop_transaction(
                connector_id=self.transaction_connector[int(transaction_id)]
            )

    async def send_status_notification(self, connector_id: int = 1):
        """Notify status of a connector."""

        async def _notify_status(connector: Connector):
            request = call.StatusNotificationPayload(
                connector_id=connector.id,
                error_code=connector.error_code,
                status=connector.status,
            )
            LOGGER.debug(f"Sending StatusNotification for {connector.id=}")
            return await self.call(request)

        if connector_id == 0:
            LOGGER.debug(f"Sending StatusNotification for all connectors")
            return [
                await _notify_status(connector=connector) for connector in self.connectors.values()
            ]

        return await _notify_status(connector=self.connectors[connector_id])

    async def unplug(self, connector_id: int = 1, stop_tx: bool = True) -> None:
        """Unplug a connector, and send status notification."""
        if not self.connectors[connector_id].plugged_in:
            LOGGER.warning(f"{connector_id=} already unplugged")
            return

        # If transaction was stopped remotely or before, skip this
        if not self.connectors[connector_id].already_stopped and stop_tx:
            await self.send_stop_transaction(
                connector_id=connector_id, reason=Reason.ev_disconnected
            )
            await self.send_status_notification(connector_id=connector_id)
            await sleep(5)

        LOGGER.info(f"Unplugging {connector_id=}")
        self.connectors[connector_id].reset(postpone_stop_tx=not stop_tx)
        await self.send_status_notification(connector_id=connector_id)

    @on(Action.GetConfiguration)
    async def on_get_configuration(self, keys: list[str] | None = None):
        """Return existent and unknown configuration keys."""
        if keys is None:
            return call_result.GetConfigurationPayload(
                configuration_key=[
                    {"key": k, "readonly": False, "value": str(v)}
                    for k, v in self.configuration.items()
                ]
            )

        requested_keys = set(keys)
        available_keys = self.configuration.keys()

        unknown_keys = requested_keys - available_keys
        existing_keys = available_keys & requested_keys

        configuration_keys = []
        for key in existing_keys:
            configuration_keys.append(
                {"key": key, "readonly": False, "value": self.configuration[key]}
            )
        return call_result.GetConfigurationPayload(
            configuration_key=[configuration_keys], unknown_key=list(unknown_keys)
        )

    @on(Action.ChangeConfiguration)
    async def on_change_configuration(self, key: str, value: str):
        """Change configuration and return accepted status."""
        LOGGER.info(f"Setting {key=} to {value=}")
        self.configuration[key] = value
        return call_result.ChangeConfigurationPayload(status=ConfigurationStatus.accepted)

    @on(Action.ChangeAvailability)
    async def on_change_availability(self, connector_id: int, type: AvailabilityType):
        """Handle ChangeAvailability request."""
        return call_result.ChangeAvailabilityPayload(status=ConfigurationStatus.accepted)

    @after(Action.ChangeAvailability)
    async def after_change_availability(self, connector_id: int, type: AvailabilityType):
        """Action to be taken after handling ChangeAvailability request."""
        if self.connectors[connector_id].change_availability(type):
            await self.send_status_notification(connector_id=connector_id)

    @on(Action.SetChargingProfile)
    async def on_set_charging_profile(
        self, connector_id: int, cs_charging_profiles: dict[str, object]
    ):
        """Set limit of the first charging schedule to connector's power offered."""
        connector = self.connectors[connector_id]
        if not connector.ready_to_charge():
            LOGGER.warning(
                f"Unable to set charging profile to {connector_id=}: not ready to charge"
            )
            return call_result.SetChargingProfilePayload(status=ChargingProfileStatus.rejected)

        connector.power_offered = float(
            cs_charging_profiles["charging_schedule"]["charging_schedule_period"][0][  # type: ignore[index]
                "limit"
            ]
        )

        return call_result.SetChargingProfilePayload(status=ChargingProfileStatus.accepted)

    @after(Action.SetChargingProfile)
    async def after_set_charging_profile(self, connector_id: int, *args, **kwargs):
        """Notify CSMS if status changed."""
        if self.connectors[connector_id].update_status():
            await self.send_status_notification(connector_id=connector_id)

    async def send_data_transfer(self, payload: dict[str, object] = {}):
        """Notify status of a connector."""
        request = call.DataTransferPayload(vendor_id=self.vendor, data=json.dumps(payload))
        LOGGER.debug("Sending DataTransfer")
        return await self.call(request)


async def get_fcs(settings: Settings) -> FakeChargingStation:
    """Build a FCS instance."""
    fcs = FakeChargingStation(
        id=int(settings.cs_id),
        vendor=settings.vendor,
        model=settings.model,
        number_of_connectors=settings.connectors,
        tx_start_charge=settings.quick_start_charging,
    )

    basic_auth = {"Authorization": build_authorization_basic(settings.cs_id, settings.password)}

    await fcs.boot_up(ws_url=settings.ws_url, extra_headers=basic_auth)

    await quick_start_fcs(fcs=fcs, settings=settings)

    return fcs


async def stop_fcs(fcs: FakeChargingStation) -> None:
    """Stops a FCS gracefully."""
    LOGGER.info("Stopping services gracefully")
    for connector_id in fcs.connectors.keys():
        await fcs.unplug(connector_id=connector_id)

    await sleep(5)

    if fcs.connected:
        await fcs.disconnect()


async def quick_start_fcs(fcs: FakeChargingStation, settings: Settings) -> None:
    """Applies quick start configuration on a FCS."""
    if (
        not settings.quick_start
        or not settings.quick_start_rfid
        or not settings.quick_start_connector
    ):
        return

    await sleep(3)
    await fcs.plug_in(settings.quick_start_rfid, settings.quick_start_connector)

    if settings.quick_start_charging:
        await sleep(3)
        await fcs.on_set_charging_profile(
            connector_id=settings.quick_start_connector,
            cs_charging_profiles={
                "charging_schedule": {
                    "charging_schedule_period": [{"limit": settings.quick_start_charging}]
                }
            },
        )
        await fcs.after_set_charging_profile(connector_id=settings.quick_start_connector)
