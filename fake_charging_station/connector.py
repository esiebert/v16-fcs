from ocpp.v16.call import MeterValuesPayload
from ocpp.v16.enums import AvailabilityType, ChargePointErrorCode, ChargePointStatus

from .custom_logger import get_logger
from .meter_values import generate_meter_values

LOGGER = get_logger("connector")


class Connector:
    """Connector for Fake Charging Station."""

    def __init__(self, connector_id: int) -> None:
        self.id = connector_id
        self.change_to_unavailable = False
        self.reset()

    def reset(self, postpone_stop_tx=False) -> None:
        """Reset connector's attribute to initial state."""
        # Store transaction related fields for later StopTransaction
        self.pending_stop_tx = None
        if postpone_stop_tx:
            self.pending_stop_tx = {
                "id_tag": self.id_tag,
                "transaction_id": self.transaction_id,
                "energy_import_register": self.energy_import_register,
            }

        self.id_tag = None
        self.transaction_id = None

        self.energy_import_register = 0.0
        self.power_offered = 0.0
        self.error_code = ChargePointErrorCode.noError

        self.plugged_in = False
        self.already_stopped = True

        if self.change_to_unavailable:
            self.status = ChargePointStatus.unavailable
        else:
            self.status = ChargePointStatus.available

    def ready_to_charge(self) -> bool:
        return self.status == ChargePointStatus.preparing and self.plugged_in

    def consume_energy(self) -> None:
        """Simulate consumption of energy.

        Connector consumes the same amount of power as it is offered.
        """
        self.energy_import_register += self.power_offered

    def status_changed(self) -> bool:
        """Change status according to power offered.

        - Power offered == 0 -> Suspended EVSE
        - Power offered != 0 -> Charging
        - Power offered == -1 -> Suspended EV
        - Power offered == -2 -> Finishing

        Returns:
            True if status was changed.
        """
        if self.power_offered == 0 and self.status != ChargePointStatus.suspended_evse:
            LOGGER.info(f"Changing connector {self.id} status to Suspended EVSE")
            self.status = ChargePointStatus.suspended_evse
            return True

        elif self.power_offered == -1 and self.status != ChargePointStatus.suspended_ev:
            LOGGER.info(f"Changing connector {self.id} status to Suspended EV")
            self.status = ChargePointStatus.suspended_ev
            return True

        elif self.power_offered == -2 and self.status != ChargePointStatus.finishing:
            LOGGER.info(f"Changing connector {self.id} status to Finishing")
            self.status = ChargePointStatus.finishing
            return True

        elif self.power_offered != 0 and self.status != ChargePointStatus.charging:
            LOGGER.info(f"Changing connector {self.id} status to Charging")
            self.status = ChargePointStatus.charging
            return True

        return False

    def get_meter_values(self) -> MeterValuesPayload:
        """Return a meter values payload."""
        return MeterValuesPayload(
            connector_id=self.id,
            meter_value=generate_meter_values(
                power_offered=self.power_offered,
                energy_import_register=self.energy_import_register,
            ),
            transaction_id=self.transaction_id,
        )

    def change_availability(self, availability_type: AvailabilityType):
        if availability_type == AvailabilityType.inoperative:
            if self.status == ChargePointStatus.available:
                self.status = ChargePointStatus.unavailable
                return True
            else:
                self.change_to_unavailable = True
        elif (
            availability_type == AvailabilityType.operative
            and self.status == ChargePointStatus.unavailable
        ):
            self.status = ChargePointStatus.available
            self.change_to_unavailable = False
            return True
        return False
