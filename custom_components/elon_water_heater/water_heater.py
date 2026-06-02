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

Optimistic state
----------------
``ForceReheat`` is a no-op when the device is already at the AC target
temperature, and there is no device-side flag indicating "user requested a
grid heat".  Without help, the tile would not light up after a press in that
case and the family would assume the integration is broken.

To paper over that, the entity tracks an *optimistic* on/off intent for a
short window after each user action.  The optimistic state is dropped as
soon as the real device state catches up, or after
:data:`OPTIMISTIC_TIMEOUT` has elapsed -- whichever comes first.
"""

from datetime import datetime, timedelta, timezone

from homeassistant.components.water_heater import (
    STATE_ELECTRIC,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    HEATING_CURRENT_THRESHOLD,
    SENSOR_ID_AC_CURRENT,
    SENSOR_RESOLUTIONS,
    PowerSource,
)
from .coordinator import ElonDataUpdateCoordinator


# The tile is binary: ``electric`` iff the device is actively drawing grid
# power, otherwise ``off``.  Solar (DC) heating is informational and lives on
# the dedicated sensor entities -- exposing it here would make Apple Home /
# HomeKit Bridge map *any* non-off operation to "heating", lighting the tile
# up while solar warms the tank.
OPERATION_MODES = [STATE_OFF, STATE_ELECTRIC]

# How long after a user action we trust the optimistic state.  Three coordinator
# refresh cycles (30 s each) -- long enough for ForceReheat to wake the element
# and start drawing current, short enough that a no-op press doesn't lie to the
# family for long.
OPTIMISTIC_TIMEOUT = timedelta(seconds=90)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the water heater entity from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ElonWaterHeater(coordinator)])


class ElonWaterHeater(WaterHeaterEntity):
    """Elon water heater entity.

    ``current_operation`` is binary, mapping cleanly to Apple Home / HomeKit
    Bridge heating-state:

    * ``electric`` -- powerSource == AC_GRID *and* AC current exceeds the
      heating threshold (genuinely drawing grid power).
    * ``off``      -- everything else, including DC solar warming (which is
      exposed via the dedicated sensor entities, not here).

    Turning the entity on calls ``ForceReheat``; turning it off calls
    ``CancelGridHeating``.  Setting operation mode to ``electric`` is the same
    as turn-on; any other mode is treated as a cancel.
    """

    _attr_has_entity_name = True
    _attr_name = None  # use device name so the tile reads as the device
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_operation_list = OPERATION_MODES
    _attr_supported_features = (
        WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.ON_OFF
    )
    _attr_min_temp = 5
    _attr_max_temp = 80

    def __init__(self, coordinator: ElonDataUpdateCoordinator) -> None:
        """Initialise the entity."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.serial_number}_water_heater"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.serial_number)},
            "name": f"Elon {coordinator.serial_number}",
            "manufacturer": "Elon",
            "model": "Smart Water Heater",
        }

        # Optimistic state: True == we believe the device is heating from the
        # grid because the user just pressed on; False == we believe it isn't
        # because they just pressed off; None == defer entirely to the device.
        self._optimistic_on: bool | None = None
        self._optimistic_until: datetime | None = None

    async def async_added_to_hass(self) -> None:
        """Register coordinator callback."""
        self.coordinator.async_add_listener(self._handle_update)

    @callback
    def _handle_update(self) -> None:
        """Push updated state to HA."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Available once the coordinator has fetched data at least once."""
        return self.coordinator.data is not None

    @property
    def current_temperature(self) -> float | None:
        """Current water temperature in °C."""
        data = self.coordinator.data
        if not data:
            return None
        temp = data.get("waterTemperature")
        return round(temp, 1) if temp is not None else None

    def _device_operation(self) -> str | None:
        """Operation mode as the device currently reports it.

        Returns ``None`` if no data yet, otherwise one of the values in
        :data:`OPERATION_MODES`.
        """
        data = self.coordinator.data
        sensors = self.coordinator.sensor_data
        if not data:
            return None

        power_source = data.get("powerSource")
        ac_current_raw = sensors.get(SENSOR_ID_AC_CURRENT, 0)
        ac_current = ac_current_raw * SENSOR_RESOLUTIONS[SENSOR_ID_AC_CURRENT]

        if (
            power_source == PowerSource.AC_GRID
            and ac_current > HEATING_CURRENT_THRESHOLD
        ):
            return STATE_ELECTRIC
        return STATE_OFF

    @property
    def current_operation(self) -> str | None:
        """Operation mode, masked by recent optimistic intent.

        While the optimistic window is active the user's intent wins so the
        tile responds immediately.  The optimistic value is dropped as soon as
        the real device state catches up, or once the window expires.
        """
        real = self._device_operation()
        if self._optimistic_on is None or self._optimistic_until is None:
            return real

        if datetime.now(timezone.utc) > self._optimistic_until:
            # Window closed -- trust the device again.
            self._optimistic_on = None
            self._optimistic_until = None
            return real

        real_is_on = real == STATE_ELECTRIC
        if real_is_on == self._optimistic_on:
            # Device caught up to the user's intent; stop overriding.
            self._optimistic_on = None
            self._optimistic_until = None
            return real

        return STATE_ELECTRIC if self._optimistic_on else STATE_OFF

    def _set_optimistic(self, on: bool) -> None:
        """Latch an optimistic on/off intent for the next ``OPTIMISTIC_TIMEOUT``."""
        self._optimistic_on = on
        self._optimistic_until = datetime.now(timezone.utc) + OPTIMISTIC_TIMEOUT

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Translate a mode change into a Force/Cancel API call."""
        if operation_mode == STATE_ELECTRIC:
            self._set_optimistic(True)
            await self.coordinator.api.force_reheat()
        else:
            self._set_optimistic(False)
            await self.coordinator.api.cancel_grid_heating()
        self.async_write_ha_state()
        await self.coordinator.async_refresh()

    async def async_turn_on(self) -> None:
        """Trigger an immediate grid heat cycle."""
        self._set_optimistic(True)
        await self.coordinator.api.force_reheat()
        self.async_write_ha_state()
        await self.coordinator.async_refresh()

    async def async_turn_off(self) -> None:
        """Cancel any active forced grid heat cycle."""
        self._set_optimistic(False)
        await self.coordinator.api.cancel_grid_heating()
        self.async_write_ha_state()
        await self.coordinator.async_refresh()
