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

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    POWER_SOURCE_NAMES,
    SENSOR_ID_AC_CURRENT,
    SENSOR_ID_AC_VOLTAGE,
    SENSOR_ID_AMBIENT_TEMP,
    SENSOR_ID_DC_CURRENT,
    SENSOR_ID_DC_VOLTAGE,
    SENSOR_RESOLUTIONS,
    PowerSource,
)
from .coordinator import ElonData, ElonDataUpdateCoordinator
from .entity import ElonEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            WaterTemperatureSensor(coordinator),
            AmbientTemperatureSensor(coordinator),
            PowerSourceSensor(coordinator),
            HeatingStateSensor(coordinator),
            ACCurrentSensor(coordinator),
            ACPowerSensor(coordinator),
            DCPowerSensor(coordinator),
            LastSeenSensor(coordinator),
        ]
    )


def _scaled(data: ElonData, sensor_id: int) -> float | None:
    """Apply a sensor's resolution to its raw integer reading."""
    raw = data.sensors.get(sensor_id)
    if raw is None:
        return None
    return raw * SENSOR_RESOLUTIONS[sensor_id]


class ElonSensor(ElonEntity, SensorEntity):
    """Base sensor for Elon Water Heater."""


class WaterTemperatureSensor(ElonSensor):
    """Water temperature sensor.

    Read from the device status rather than sensor 1.  Both report water
    temperature but they refresh on different cadences and disagree slightly,
    so the integration commits to one source.
    """

    _attr_name = "Water Temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: ElonDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, "water_temperature")

    @property
    def native_value(self) -> float | None:
        """Return water temperature."""
        if self.elon_data is None:
            return None
        temp = self.elon_data.status.get("waterTemperature")
        return round(temp, 1) if temp is not None else None


class AmbientTemperatureSensor(ElonSensor):
    """Ambient temperature sensor."""

    _attr_name = "Ambient Temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: ElonDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, "ambient_temperature")

    @property
    def native_value(self) -> float | None:
        """Return ambient temperature."""
        if self.elon_data is None:
            return None
        value = _scaled(self.elon_data, SENSOR_ID_AMBIENT_TEMP)
        return None if value is None else round(value, 1)


class PowerSourceSensor(ElonSensor):
    """Power source sensor."""

    _attr_name = "Power Source"

    def __init__(self, coordinator: ElonDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, "power_source")

    @property
    def native_value(self) -> str | None:
        """Return power source."""
        if self.elon_data is None:
            return None
        return POWER_SOURCE_NAMES.get(
            self.elon_data.status.get("powerSource"), "Unknown"
        )


class HeatingStateSensor(ElonSensor):
    """Heating state, combining power source with actual current draw.

    Distinguishes grid boost that is genuinely drawing power from grid boost
    where the element is idle -- the latter being normal for a tank already at
    target, and a fault indication when it persists.
    """

    _attr_name = "Heating State"

    def __init__(self, coordinator: ElonDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, "heating_state")

    @property
    def native_value(self) -> str | None:
        """Return heating state."""
        data = self.elon_data
        if data is None:
            return None

        if data.is_drawing_grid_power:
            return "Heating"

        power_source = data.status.get("powerSource")
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
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    def __init__(self, coordinator: ElonDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, "ac_current")

    @property
    def native_value(self) -> float | None:
        """Return AC current."""
        if self.elon_data is None:
            return None
        value = _scaled(self.elon_data, SENSOR_ID_AC_CURRENT)
        return None if value is None else round(value, 3)


class ACPowerSensor(ElonSensor):
    """Instantaneous AC power draw, in Watts.

    Derived from AC RMS current and voltage.  Both read zero while the grid
    relay is open, so this correctly reports no draw when idle.
    """

    _attr_name = "AC Power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator: ElonDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, "ac_power")

    @property
    def native_value(self) -> float | None:
        """Return AC power draw."""
        if self.elon_data is None:
            return None
        current = _scaled(self.elon_data, SENSOR_ID_AC_CURRENT)
        voltage = _scaled(self.elon_data, SENSOR_ID_AC_VOLTAGE)
        if current is None or voltage is None:
            return None
        return round(current * voltage, 1)


class DCPowerSensor(ElonSensor):
    """Instantaneous DC (solar PV) power, in Watts.

    Derived from DC current and voltage.  ``None`` if either reading is
    missing.
    """

    _attr_name = "DC Power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator: ElonDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, "dc_power")

    @property
    def native_value(self) -> float | None:
        """Return DC power."""
        if self.elon_data is None:
            return None
        current = _scaled(self.elon_data, SENSOR_ID_DC_CURRENT)
        voltage = _scaled(self.elon_data, SENSOR_ID_DC_VOLTAGE)
        if current is None or voltage is None:
            return None
        return round(current * voltage, 1)


class LastSeenSensor(ElonSensor):
    """When the device was last successfully polled.

    Sourced from the coordinator rather than the device's ``lastComms`` field,
    which is an irregular device-side counter and not wall-clock time.  Stays
    available while the device is offline so a dashboard can show how stale
    the readings are instead of silently displaying an old temperature.
    """

    _attr_name = "Last Seen"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ElonDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, "last_seen")

    @property
    def available(self) -> bool:
        """Always available -- reporting staleness is this entity's job."""
        return True

    @property
    def native_value(self) -> datetime | None:
        """Return the timestamp of the last successful poll."""
        return self.coordinator.last_successful_update
