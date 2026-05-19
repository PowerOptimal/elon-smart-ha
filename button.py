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

"""Buttons for Elon Water Heater."""

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, PowerSource, HEATING_CURRENT_THRESHOLD, SENSOR_ID_AC_CURRENT, SENSOR_RESOLUTIONS
from .coordinator import ElonDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up buttons from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ElonReheatButton(coordinator)])


class ElonButton(ButtonEntity):
    """Base button for Elon Water Heater."""

    def __init__(self, coordinator: ElonDataUpdateCoordinator) -> None:
        """Initialize the button."""
        self.coordinator = coordinator
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


class ElonReheatButton(ElonButton):
    """Button to trigger or cancel grid heating."""

    _attr_name = "Grid Heating"

    @property
    def available(self) -> bool:
        """Available when we have data."""
        return self.coordinator.data is not None

    @property
    def icon(self) -> str:
        """Return icon based on state."""
        if self._is_heating:
            return "mdi:radiator-off"
        return "mdi:radiator"

    @property
    def _is_heating(self) -> bool:
        """Check if actively heating from grid."""
        data = self.coordinator.data
        sensors = self.coordinator.sensor_data

        if not data:
            return False

        power_source = data.get("powerSource")
        ac_current_raw = sensors.get(SENSOR_ID_AC_CURRENT, 0)
        ac_current = ac_current_raw * SENSOR_RESOLUTIONS[SENSOR_ID_AC_CURRENT]

        return (
            power_source == PowerSource.AC_GRID
            and ac_current > HEATING_CURRENT_THRESHOLD
        )

    async def async_press(self) -> None:
        """Handle button press."""
        if self._is_heating:
            await self.coordinator.api.cancel_grid_heating()
        else:
            await self.coordinator.api.force_reheat()

        # Refresh data after action
        await self.coordinator.async_refresh()


