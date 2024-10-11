from datetime import datetime, timezone
from typing import Any

METER_VALUES_SAMPLED_DATA = [
    "Power.Offered",
    "Power.Active.Import",
    "Energy.Active.Import.Register",
    "Voltage",
    "SoC",
]


def generate_meter_values(
    power_offered: float,
    energy_import_register: float,
) -> list[dict[str, Any]]:
    meter_values = {
        "timestamp": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sampledValue": [
            _get_power_active_import(round(power_offered, 3)),
            _get_power_offered(round(power_offered, 3)),
            _get_energy_active_import_register(round(energy_import_register, 3)),
            _get_voltage(),
            _get_soc(),
        ],
    }

    return [meter_values]


def _create_sampled_value(measurand: str, unit: str, value: str) -> dict[str, str]:
    return {
        "context": "Sample.Periodic",
        "location": "Outlet",
        "measurand": measurand,
        "unit": unit,
        "value": value,
    }


def _get_power_offered(power_offered: float) -> dict[str, str]:
    return _create_sampled_value("Power.Offered", "W", str(power_offered))


def _get_power_active_import(power_offered: float) -> dict[str, str]:
    return _create_sampled_value("Power.Active.Import", "W", str(power_offered))


def _get_energy_active_import_register(energy_import_register: float) -> dict[str, str]:
    return _create_sampled_value(
        "Energy.Active.Import.Register", "Wh", str(energy_import_register)
    )


def _get_voltage() -> dict[str, str]:
    return _create_sampled_value("Voltage", "V", "230")


def _get_soc() -> dict[str, str]:
    return _create_sampled_value("SoC", "Percent", "0")
