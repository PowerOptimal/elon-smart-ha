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

"""Binary sensors for Elon Water Heater."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ElonDataUpdateCoordinator
from .entity import ElonEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [ElonConnectivitySensor(coordinator), ElonAlarmSensor(coordinator)]
    )


class ElonConnectivitySensor(ElonEntity, BinarySensorEntity):
    """Reports whether the device is reachable.

    Every other entity goes ``unavailable`` when the device drops off, which
    is correct but awkward to build an automation on.  This entity stays
    available and simply reports ``off``, so a user can trigger a notification
    on "offline for more than fifteen minutes" and find out that the geyser
    has lost power.
    """

    _attr_name = "Connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: ElonDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, "connectivity")

    @property
    def available(self) -> bool:
        """Always available -- reporting the outage is this entity's job."""
        return True

    @property
    def is_on(self) -> bool:
        """True while the last refresh succeeded."""
        return self.coordinator.last_update_success


class ElonAlarmSensor(ElonEntity, BinarySensorEntity):
    """Reports the device's own alarm flag.

    The device raises this when it detects a fault -- for instance when grid
    heating is engaged but the element draws no current, which is what a
    failed element looks like.  The flag latches: it stays set after the
    condition clears, and the protocol exposes no way to acknowledge it.
    """

    _attr_name = "Alarm"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: ElonDataUpdateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, "alarm")

    @property
    def is_on(self) -> bool | None:
        """True while the device reports an open alarm."""
        if self.elon_data is None:
            return None
        return self.elon_data.has_open_alarms
