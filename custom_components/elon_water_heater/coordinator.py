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

"""Data coordinator for Elon Water Heater."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import ElonApiClient, ElonConnectionError
from .const import (
    ACTION_SETTLE_DELAY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    HEATING_CURRENT_THRESHOLD,
    POLLED_SENSOR_IDS,
    SENSOR_ID_AC_CURRENT,
    SENSOR_RESOLUTIONS,
    PowerSource,
)
from .discovery import async_resolve_host

_LOGGER = logging.getLogger(__name__)

# How long a user's on/off intent overrides what the device reports.  The
# device switches power source within ~10 s and a settle refresh is scheduled
# at 15 s, so this only has to cover the gap plus some slack.
OPTIMISTIC_TIMEOUT = timedelta(seconds=45)


@dataclass
class ElonData:
    """A single snapshot of device state.

    Bundles the two calls that make up a refresh so every entity reads a
    consistent view.
    """

    status: dict
    sensors: dict[int, int] = field(default_factory=dict)

    @property
    def is_grid_boost_active(self) -> bool:
        """Whether the device is switched to grid heating.

        This is ``powerSource == AC_GRID`` alone.  It is deliberately *not*
        qualified by AC current draw: the device engages the grid relay in
        response to a boost request whether or not the element then draws
        power, and a tank already at target draws nothing.  Conflating the two
        is what made boosts started from the phone app invisible to Home
        Assistant.

        Use :attr:`is_drawing_grid_power` for the separate question of whether
        the element is actually pulling current.
        """
        return self.status.get("powerSource") == PowerSource.AC_GRID

    @property
    def ac_current(self) -> float:
        """AC RMS current in amps, zero if the reading is unavailable."""
        raw = self.sensors.get(SENSOR_ID_AC_CURRENT, 0)
        return raw * SENSOR_RESOLUTIONS[SENSOR_ID_AC_CURRENT]

    @property
    def is_drawing_grid_power(self) -> bool:
        """Whether the element is actually drawing meaningful grid current."""
        return self.is_grid_boost_active and self.ac_current > HEATING_CURRENT_THRESHOLD

    @property
    def has_open_alarms(self) -> bool:
        """Whether the device is reporting an open alarm.

        The flag latches -- it stays set after the underlying condition clears
        and there is no documented endpoint to acknowledge it.
        """
        return bool(self.status.get("hasOpenAlarms"))


class ElonDataUpdateCoordinator(DataUpdateCoordinator[ElonData]):
    """Coordinator for fetching data from the Elon water heater.

    Owns device addressing as well as polling.  When the device is configured
    by serial rather than by a fixed address, its ``.local`` name is resolved
    over mDNS and the resulting address cached on the API client; a connection
    failure drops the cached address so the next attempt re-resolves.  That is
    what lets the integration recover from a power cycle without restarting
    Home Assistant.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        api: ElonApiClient,
        serial_number: str,
        config_entry: ConfigEntry,
        manual_host: str | None = None,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance.
            api: Device API client.
            serial_number: Device serial number, used for mDNS resolution.
            config_entry: The owning config entry.
            manual_host: A user-supplied host or IP.  When set, mDNS is never
                used and the address is treated as fixed.
        """
        self.api = api
        self.serial_number = serial_number
        self.manual_host = manual_host
        self.last_successful_update: datetime | None = None

        # A user's most recent on/off intent, held briefly so the UI responds
        # to a press before the device has switched.  ``None`` means defer
        # entirely to the device.  This lives on the coordinator rather than
        # per entity so the switch and the water heater cannot disagree about
        # the state of one physical relay.
        self._optimistic_boost: bool | None = None
        self._optimistic_until: datetime | None = None

        # Cancel handle for the pending post-action refresh, if any.
        self._cancel_settle: CALLBACK_TYPE | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

        config_entry.async_on_unload(self._cancel_pending_settle)

    async def _async_ensure_host(self) -> None:
        """Make sure the API client has an address to talk to.

        No-op when the host is fixed by configuration or already resolved.
        """
        if self.manual_host or self.api.host:
            return

        address = await async_resolve_host(self.hass, self.serial_number)
        if address is None:
            raise UpdateFailed(
                f"Could not resolve ELON-{self.serial_number}.local over mDNS"
            )
        _LOGGER.debug("Resolved ELON-%s.local to %s", self.serial_number, address)
        self.api.host = address

    def _invalidate_host(self) -> None:
        """Drop the cached address so the next refresh re-resolves it.

        Only meaningful when resolving by serial; a user-supplied host is left
        alone because re-resolving it would not help.
        """
        if not self.manual_host:
            self.api.host = None

    async def _async_update_data(self) -> ElonData:
        """Fetch a fresh snapshot from the device.

        Raises:
            UpdateFailed: The device status could not be fetched, meaning the
                device is unreachable.  Entities go unavailable.
        """
        await self._async_ensure_host()

        try:
            status = await self.api.get_device_status()
        except ElonConnectionError as err:
            self._invalidate_host()
            raise UpdateFailed(str(err)) from err

        # The measurement query is the slow call and fails more readily than
        # the status query.  Losing it degrades the derived sensors but does
        # not mean the device is offline, so keep the previous readings rather
        # than marking everything unavailable.
        sensors = self.data.sensors if self.data else {}
        try:
            sensors = await self.api.get_measurements(POLLED_SENSOR_IDS)
        except ElonConnectionError as err:
            _LOGGER.warning(
                "Failed to fetch sensor measurements; keeping previous values: %s", err
            )

        self.last_successful_update = dt_util.utcnow()
        return ElonData(status=status, sensors=sensors)

    @property
    def boost_active(self) -> bool | None:
        """Whether grid boost is on, honouring recent user intent.

        Returns ``None`` before the first successful refresh.  Inside the
        optimistic window the user's intent wins over the device so a press
        registers immediately; the device reasserts control as soon as it
        agrees, or once the window lapses.
        """
        if self.data is None:
            return None

        actual = self.data.is_grid_boost_active
        if self._optimistic_boost is None or self._optimistic_until is None:
            return actual
        if dt_util.utcnow() > self._optimistic_until:
            return actual
        if actual == self._optimistic_boost:
            return actual
        return self._optimistic_boost

    async def async_set_boost(self, active: bool) -> None:
        """Turn grid boost on or off.

        The optimistic intent is recorded only after the device accepts the
        command, so a rejected action does not leave the UI showing a state
        the device never entered.

        Raises:
            ElonApiError: The device was unreachable or refused the action.
        """
        if active:
            await self.api.force_reheat()
        else:
            await self.api.cancel_grid_heating()

        self._optimistic_boost = active
        self._optimistic_until = dt_util.utcnow() + OPTIMISTIC_TIMEOUT
        self.async_update_listeners()
        self.async_schedule_settle_refresh()

    def _cancel_pending_settle(self) -> None:
        """Cancel a scheduled post-action refresh, if one is pending."""
        if self._cancel_settle is not None:
            self._cancel_settle()
            self._cancel_settle = None

    def async_schedule_settle_refresh(self) -> None:
        """Refresh shortly after a user action.

        The device takes about ten seconds to switch power source, well inside
        the normal poll interval.  Without this the tile would keep showing the
        optimistic guess for up to a full minute after a press.

        Only one refresh is ever pending; a rapid second action replaces the
        first.  The handle is cancelled on unload so the callback cannot fire
        against a torn-down coordinator.
        """
        self._cancel_pending_settle()

        async def _refresh(_now) -> None:
            self._cancel_settle = None
            await self.async_request_refresh()

        self._cancel_settle = async_call_later(
            self.hass, ACTION_SETTLE_DELAY, _refresh
        )
