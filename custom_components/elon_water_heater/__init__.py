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

"""Elon Water Heater integration for Home Assistant."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ElonApiClient
from .const import CONF_HOST, CONF_SERIAL_NUMBER, DOMAIN
from .coordinator import ElonDataUpdateCoordinator
from .dashboard import async_schedule_dashboard_setup

PLATFORMS = ["binary_sensor", "sensor", "switch", "water_heater"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration via YAML (optional legacy method)."""
    domain_config = config.get(DOMAIN)

    if domain_config:
        serial_number = domain_config.get(CONF_SERIAL_NUMBER)
        if serial_number:
            # Create a minimal config entry for YAML setup
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": "yaml"},
                    data={CONF_SERIAL_NUMBER: serial_number},
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    serial_number = entry.data[CONF_SERIAL_NUMBER]
    manual_host = entry.data.get(CONF_HOST)

    # Home Assistant's shared session is correctly configured and torn down
    # with the instance.  The integration previously built its own, which was
    # closed only on setup failure and so leaked on every reload.
    session = async_get_clientsession(hass)

    api = ElonApiClient(manual_host, session)
    coordinator = ElonDataUpdateCoordinator(
        hass, api, serial_number, entry, manual_host=manual_host
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Schedule dashboard creation to run after HA has fully started
    async_schedule_dashboard_setup(hass, serial_number)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
