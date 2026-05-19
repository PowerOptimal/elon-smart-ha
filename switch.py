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

"""Switch platform for Elon Water Heater."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    PowerSource,
)
from .coordinator import ElonDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ElonGridHeatSwitch(coordinator)])


class ElonGridHeatSwitch(SwitchEntity):
    """Switch to trigger or cancel grid heating.

    Exposed as a Matter-compatible switch so it can be controlled via Siri /
    HomePod.  On = heating from grid; Off = cancel / not heating.
    """

    _attr_has_entity_name = True
    _attr_name = "Grid Heating"
    _attr_icon = "mdi:radiator"

    def __init__(self, coordinator: ElonDataUpdateCoordinator) -> None:
        """Initialise the switch."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.serial_number}_grid_heat"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.serial_number)},
            "name": f"Elon {coordinator.serial_number}",
            "manufacturer": "Elon",
            "model": "Smart Water Heater",
        }

    async def async_added_to_hass(self) -> None:
        """Register coordinator callback."""
        self.coordinator.async_add_listener(self._handle_update)

    @callback
    def _handle_update(self) -> None:
        """Push updated state to HA."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Available when coordinator has data."""
        return self.coordinator.data is not None

    @property
    def is_on(self) -> bool:
        """True when the device is not on AC grid power.

        ForceReheat is active (or relevant) when the device is operating on
        solar or is disconnected.  Once powerSource == ACGrid the device is
        already heating from the grid and CancelGridHeating becomes the action.
        """
        data = self.coordinator.data
        if not data:
            return False
        return data.get("powerSource") != PowerSource.AC_GRID

    @property
    def icon(self) -> str:
        """Radiator icon, filled when heating."""
        return "mdi:radiator" if self.is_on else "mdi:radiator-off"

    async def async_turn_on(self, **kwargs) -> None:
        """Request immediate grid heating."""
        await self.coordinator.api.force_reheat()
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Cancel the forced heat cycle."""
        await self.coordinator.api.cancel_grid_heating()
        await self.coordinator.async_refresh()
