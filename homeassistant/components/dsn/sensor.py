from typing import Union

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfFrequency, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import DsnApi
from .const import DOMAIN


def dsn_sensor_builder(
    device_class: SensorDeviceClass,
    unit_of_measurement: Union[UnitOfPower, UnitOfFrequency],
):
    if type(unit_of_measurement).__name__.startswith("UnitOf"):
        specialword = type(unit_of_measurement).__name__[6:].lower()
    else:
        specialword = type(unit_of_measurement).__name__.lower()

    class DsnSensor(CoordinatorEntity[DataUpdateCoordinator[dict]], SensorEntity):
        """Implementation of a Deep Space Network Site sensor."""

        _attr_has_entity_name = True
        _attr_name = None

        def __init__(
            self,
            coordinator: DataUpdateCoordinator[dict],
            entry: ConfigEntry,
            device_name: str,
            sensor_name: str,
            sensor_value: float,
        ) -> None:
            """Pass coordinator to CoordinatorEntity."""
            super().__init__(coordinator)
            self._attr_unique_id = entry.entry_id + device_name + specialword
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, device_name)},
                name=device_name,
            )
            self.entity_description = SensorEntityDescription(
                device_class=device_class,
                key=f"dsn_{specialword}_decription",
                unit_of_measurement=unit_of_measurement,
            )
            self._attr_name = sensor_name
            self._attr_native_value = sensor_value
            self._attr_native_unit_of_measurement = unit_of_measurement

    return DsnSensor


DsnSensors = {
    "@power": dsn_sensor_builder(SensorDeviceClass.POWER, UnitOfPower.KILO_WATT),
    "@frequency": dsn_sensor_builder(
        SensorDeviceClass.FREQUENCY, UnitOfFrequency.HERTZ
    ),
}


class SpacecraftFinder:
    def __init__(self, dsn_config: dict) -> None:
        self.spacecrafts = (
            dsn_config.get("config", {}).get("spacecraftMap", {}).get("spacecraft")
        )
        self.known_spacecrafts = {}

    def spacecraft_name_from_code_name(self, code_name: str):
        if name := self.known_spacecrafts.get(code_name) is not None:
            return name
        wanted_spacecrafts = [
            _ for _ in self.spacecrafts if _.get("@name") == code_name.lower()
        ]
        wanted_spacecraft = wanted_spacecrafts[0]
        name = wanted_spacecraft.get("@friendlyName")
        self.known_spacecrafts.update({code_name: name})
        return name


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: DataUpdateCoordinator[dict] = hass.data[DOMAIN]

    dsn_config = await DsnApi.fetch_config()
    dsn_data = await DsnApi.fetch_data()
    spacecraft_finder = SpacecraftFinder(dsn_config=dsn_config)
    to_add = []
    for dish in dsn_data.get("dsn", {}).get("dish", []):
        # get the current target of each dish
        if not isinstance(dish, dict):
            continue

        targets = dish.get("target")
        if isinstance(targets, dict):
            targets = [targets]
        for target in targets:
            if not isinstance(target, dict):
                continue
            target.get("@id")
            device_code_name: str = target.get("@name")

        up_signals = dish.get("upSignal")
        if isinstance(up_signals, dict):
            up_signals = [up_signals]
        if isinstance(up_signals, list):
            for up_signal in up_signals:
                power = up_signal.get("@power")
                frequency = up_signal.get("@frequency")
                device_code_name = up_signal.get("@spacecraft")
                device_name = spacecraft_finder.spacecraft_name_from_code_name(
                    device_code_name
                )
                power = float(power)
                to_add.append(
                    DsnSensors.get("@power")(
                        coordinator=coordinator,
                        entry=entry,
                        device_name=device_name,
                        sensor_name=device_name + " up power",
                        sensor_value=power,
                    )
                )

                frequency = float(frequency)
                to_add.append(
                    DsnSensors.get("@frequency")(
                        coordinator=coordinator,
                        entry=entry,
                        device_name=device_name,
                        sensor_name=device_name + " up frequency",
                        sensor_value=power,
                    )
                )

    async_add_entities(to_add)
