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

"""Switch platform for Elon grid boost.

A plain ``switch`` is what generic helpers speak: timer add-ons, scheduler
cards and ``switch.turn_off`` automations all drive one, whereas
``water_heater`` needs bespoke handling.  This exists so a user can point a
timer at the geyser and get a thirty-minute boost that cancels itself.

It controls the same relay as the ``water_heater`` entity and reads the same
coordinator state, so the two can never disagree.
"""

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
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
    """Set up the grid boost switch from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ElonGridBoostSwitch(coordinator)])


class ElonGridBoostSwitch(ElonEntity, SwitchEntity):
    """Switch that forces or cancels grid heating."""

    _attr_name = "Grid Boost"
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:water-boiler"

    def __init__(self, coordinator: ElonDataUpdateCoordinator) -> None:
        """Initialise the switch."""
        super().__init__(coordinator, "grid_boost")

    @property
    def is_on(self) -> bool | None:
        """Whether grid boost is currently engaged."""
        return self.coordinator.boost_active

    async def async_turn_on(self, **kwargs) -> None:
        """Trigger an immediate grid heat cycle."""
        await self.coordinator.async_set_boost(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Cancel any active forced grid heat cycle."""
        await self.coordinator.async_set_boost(False)
