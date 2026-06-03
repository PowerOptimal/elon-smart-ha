# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 PowerOptimal
#
# This file is part of elon-smart-ha.
# elon-smart-ha is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. It is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License at <https://www.gnu.org/licenses/> for details.

"""Sensors for Elon Water Heater."""

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfPower, UnitOfTemperature, UnitOfElectricCurrent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SENSOR_ID_WATER_TEMP,
    SENSOR_ID_AMBIENT_TEMP,
    SENSOR_ID_AC_CURRENT,
    SENSOR_ID_AC_VOLTAGE,
    SENSOR_ID_DC_CURRENT,
    SENSOR_ID_DC_VOLTAGE,
    SENSOR_RESOLUTIONS,
    POWER_SOURCE_NAMES,
    PowerSource,
    HEATING_CURRENT_THRESHOLD,
)
from .coordinator import ElonDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        WaterTemperatureSensor(coordinator),
        AmbientTemperatureSensor(coordinator),
        PowerSourceSensor(coordinator),
        HeatingStateSensor(coordinator),
        ACCurrentSensor(coordinator),
        ACPowerSensor(coordinator),
        DCPowerSensor(coordinator),
    ]

    async_add_entities(sensors)


def _scaled(sensors: dict[int, int], sensor_id: int) -> float | None:
    """Apply the sensor's resolution to its raw integer reading."""
    raw = sensors.get(sensor_id)
    if raw is None:
        return None
    return raw * SENSOR_RESOLUTIONS[sensor_id]


class ElonSensor(SensorEntity):
    """Base sensor for Elon Water Heater."""

    _attr_has_entity_name = True
    # Subclasses must set _unique_id_suffix
    _unique_id_suffix: str = ""

    def __init__(self, coordinator: ElonDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.serial_number}_{self._unique_id_suffix}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.serial_number)},
            "name": f"Elon {coordinator.serial_number}",
            "manufacturer": "Elon",
            "model": "Smart Water Heater",
        }

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.coordinator.async_add_listener(self._handle_update)

    @callback
    def _handle_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class WaterTemperatureSensor(ElonSensor):
    """Water temperature sensor."""

    _attr_name = "Water Temperature"
    _unique_id_suffix = "water_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> float | None:
        """Return water temperature."""
        data = self.coordinator.data
        if not data:
            return None
        temp = data.get("waterTemperature")
        return round(temp, 1) if temp is not None else None


class AmbientTemperatureSensor(ElonSensor):
    """Ambient temperature sensor."""

    _attr_name = "Ambient Temperature"
    _unique_id_suffix = "ambient_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> float | None:
        """Return ambient temperature."""
        sensors = self.coordinator.sensor_data
        raw = sensors.get(SENSOR_ID_AMBIENT_TEMP)
        if raw is None:
            return None
        resolution = SENSOR_RESOLUTIONS[SENSOR_ID_AMBIENT_TEMP]
        return round(raw * resolution, 1)


class PowerSourceSensor(ElonSensor):
    """Power source sensor."""

    _attr_name = "Power Source"
    _unique_id_suffix = "power_source"

    @property
    def native_value(self) -> str | None:
        """Return power source."""
        data = self.coordinator.data
        if not data:
            return None
        source = data.get("powerSource")
        return POWER_SOURCE_NAMES.get(source, "Unknown")


class HeatingStateSensor(ElonSensor):
    """Heating state sensor (derived from power source and AC current)."""

    _attr_name = "Heating State"
    _unique_id_suffix = "heating_state"

    @property
    def native_value(self) -> str | None:
        """Return heating state."""
        data = self.coordinator.data
        sensors = self.coordinator.sensor_data

        if not data:
            return None

        power_source = data.get("powerSource")
        ac_current_raw = sensors.get(SENSOR_ID_AC_CURRENT, 0)
        ac_current = ac_current_raw * SENSOR_RESOLUTIONS[SENSOR_ID_AC_CURRENT]

        # If AC current > threshold, actively heating from grid
        if power_source == PowerSource.AC_GRID and ac_current > HEATING_CURRENT_THRESHOLD:
            return "Heating"

        # DC Solar power source means DC heating (even if current is low)
        if power_source == PowerSource.DC_SOLAR:
            return "Solar"

        if power_source == PowerSource.AC_GRID:
            return "Grid (Idle)"

        if power_source == PowerSource.DISCONNECTED:
            return "Disconnected"

        return "Unknown"


class ACCurrentSensor(ElonSensor):
    """AC RMS Current sensor."""

    _attr_name = "AC Current"
    _unique_id_suffix = "ac_current"
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    @property
    def native_value(self) -> float | None:
        """Return AC current."""
        value = _scaled(self.coordinator.sensor_data, SENSOR_ID_AC_CURRENT)
        return None if value is None else round(value, 3)


class ACPowerSensor(ElonSensor):
    """Instantaneous AC power draw, in Watts.

    Derived from AC RMS current and AC RMS voltage.  ``None`` if either reading
    is missing.
    """

    _attr_name = "AC Power"
    _unique_id_suffix = "ac_power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    @property
    def native_value(self) -> float | None:
        sensors = self.coordinator.sensor_data
        current = _scaled(sensors, SENSOR_ID_AC_CURRENT)
        voltage = _scaled(sensors, SENSOR_ID_AC_VOLTAGE)
        if current is None or voltage is None:
            return None
        return round(current * voltage, 1)


class DCPowerSensor(ElonSensor):
    """Instantaneous DC (solar PV) power, in Watts.

    Derived from DC current and DC voltage.  ``None`` if either reading is
    missing.
    """

    _attr_name = "DC Power"
    _unique_id_suffix = "dc_power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    @property
    def native_value(self) -> float | None:
        sensors = self.coordinator.sensor_data
        current = _scaled(sensors, SENSOR_ID_DC_CURRENT)
        voltage = _scaled(sensors, SENSOR_ID_DC_VOLTAGE)
        if current is None or voltage is None:
            return None
        return round(current * voltage, 1)
