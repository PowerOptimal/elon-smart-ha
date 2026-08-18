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

"""Water heater platform for Elon.

Exposes the device as a single ``water_heater`` entity so that the HomeKit
Bridge / Matter Server exports one accessory carrying both the current water
temperature and the on/off control.  This gives Apple Home (and other Matter
controllers) the natural pairing the user expects: *what is the water
temperature, and heat it now if I want to shower*.

For driving grid boost from timers and other automations, see the ``switch``
platform, which controls the same relay through the same coordinator state.
"""

from homeassistant.components.water_heater import (
    STATE_ELECTRIC,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ElonDataUpdateCoordinator
from .entity import ElonEntity

# The tile is binary: ``electric`` when grid boost is engaged, otherwise
# ``off``.  Solar (DC) heating is informational and lives on the dedicated
# sensor entities -- exposing it here would make Apple Home / HomeKit Bridge
# map *any* non-off operation to "heating", lighting the tile up while solar
# warms the tank.
OPERATION_MODES = [STATE_OFF, STATE_ELECTRIC]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the water heater entity from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ElonWaterHeater(coordinator)])


class ElonWaterHeater(ElonEntity, WaterHeaterEntity):
    """Elon water heater entity.

    Turning the entity on calls ``ForceReheat``; turning it off calls
    ``CancelGridHeating``.  Setting operation mode to ``electric`` is the same
    as turn-on; any other mode is treated as a cancel.
    """

    _attr_name = None  # use device name so the tile reads as the device
    # Relabels the operation modes in the UI: "electric" reads as "Grid",
    # which is what the device actually does.  The underlying state string is
    # unchanged, so automations still match on ``electric``.
    _attr_translation_key = "grid_boost"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_operation_list = OPERATION_MODES
    _attr_supported_features = (
        WaterHeaterEntityFeature.OPERATION_MODE | WaterHeaterEntityFeature.ON_OFF
    )
    _attr_min_temp = 5
    _attr_max_temp = 80

    def __init__(self, coordinator: ElonDataUpdateCoordinator) -> None:
        """Initialise the entity."""
        super().__init__(coordinator, "water_heater")

    @property
    def current_temperature(self) -> float | None:
        """Current water temperature in °C."""
        if self.elon_data is None:
            return None
        temp = self.elon_data.status.get("waterTemperature")
        return round(temp, 1) if temp is not None else None

    @property
    def current_operation(self) -> str | None:
        """``electric`` while grid boost is engaged, otherwise ``off``."""
        boost = self.coordinator.boost_active
        if boost is None:
            return None
        return STATE_ELECTRIC if boost else STATE_OFF

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Translate a mode change into a Force/Cancel API call."""
        await self.coordinator.async_set_boost(operation_mode == STATE_ELECTRIC)

    async def async_turn_on(self) -> None:
        """Trigger an immediate grid heat cycle."""
        await self.coordinator.async_set_boost(True)

    async def async_turn_off(self) -> None:
        """Cancel any active forced grid heat cycle."""
        await self.coordinator.async_set_boost(False)
