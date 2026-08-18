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

"""Regression tests for recovering after the device is power-cycled.

Reported behaviour: once the device had been off, Home Assistant kept failing
with *Cannot connect to host elon-10789.local:80 ... DNS server returned answer
with no data*, and only came back after a full Home Assistant restart.

The device is only reachable by an mDNS name.  Handing that name to aiohttp
resolves it through unicast DNS, which answers NODATA.  The integration now
resolves the address itself through Home Assistant's Zeroconf instance and
drops the cached address whenever a connection fails, so the next poll
re-resolves rather than retrying a dead address forever.
"""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.elon_water_heater.const import CONF_SERIAL_NUMBER, DOMAIN

from .conftest import (
    MEASUREMENTS_IDLE,
    STATUS_IDLE_SOLAR,
    TEST_SERIAL,
    setup_integration,
)

FIRST_IP = "192.0.2.10"
SECOND_IP = "192.0.2.55"

WATER_HEATER = "water_heater.elon_5570"


def _endpoints(ip: str) -> dict[str, str]:
    return {
        "status": f"http://{ip}/V1/DeviceStatus/Query",
        "measurements": f"http://{ip}/V1/CurrentMeasurements/Query",
    }


def _serve(aioclient_mock, ip: str) -> None:
    """Serve healthy responses at the given address."""
    urls = _endpoints(ip)
    aioclient_mock.post(urls["status"], json=STATUS_IDLE_SOLAR)
    aioclient_mock.post(urls["measurements"], json=MEASUREMENTS_IDLE)


async def _setup_by_serial(hass, aioclient_mock, resolver):
    """Set up an entry that has no fixed host and must resolve over mDNS."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SERIAL_NUMBER: TEST_SERIAL},
        unique_id=TEST_SERIAL,
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.elon_water_heater.coordinator.async_resolve_host",
        side_effect=resolver,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_resolves_over_mdns_when_no_host_configured(hass, aioclient_mock):
    """With only a serial, the address is resolved and then used."""
    _serve(aioclient_mock, FIRST_IP)

    async def resolver(_hass, _serial):
        return FIRST_IP

    await _setup_by_serial(hass, aioclient_mock, resolver)

    assert hass.states.get(WATER_HEATER).state != STATE_UNAVAILABLE


async def test_unresolvable_device_retries_rather_than_failing(hass, aioclient_mock):
    """A device that does not answer mDNS leaves the entry retrying.

    It must not land in a terminal error state -- the device is probably just
    powered off, and setup has to succeed by itself once it returns.
    """

    async def resolver(_hass, _serial):
        return None

    entry = await _setup_by_serial(hass, aioclient_mock, resolver)

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_reresolves_after_the_device_moves(hass, aioclient_mock):
    """A power cycle that changes the DHCP lease is recovered from.

    The first address stops answering, which must invalidate the cached
    address so the next poll asks mDNS again and picks up the new one --
    without a Home Assistant restart.
    """
    _serve(aioclient_mock, FIRST_IP)
    resolved = [FIRST_IP, SECOND_IP]

    async def resolver(_hass, _serial):
        return resolved[0]

    await _setup_by_serial(hass, aioclient_mock, resolver)
    assert hass.states.get(WATER_HEATER).state != STATE_UNAVAILABLE

    # Device loses power: the old address stops answering.
    aioclient_mock.clear_requests()
    aioclient_mock.post(_endpoints(FIRST_IP)["status"], exc=TimeoutError)

    with patch(
        "custom_components.elon_water_heater.coordinator.async_resolve_host",
        side_effect=resolver,
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=90))
        await hass.async_block_till_done()

    assert hass.states.get(WATER_HEATER).state == STATE_UNAVAILABLE

    # Device returns on a new lease.
    resolved[0] = SECOND_IP
    aioclient_mock.clear_requests()
    _serve(aioclient_mock, SECOND_IP)

    with patch(
        "custom_components.elon_water_heater.coordinator.async_resolve_host",
        side_effect=resolver,
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=180))
        await hass.async_block_till_done()

    assert hass.states.get(WATER_HEATER).state != STATE_UNAVAILABLE


async def test_manual_host_is_never_reresolved(hass, aioclient_mock):
    """A user-supplied address is fixed; mDNS is not consulted for it."""
    await setup_integration(hass, aioclient_mock)

    with patch(
        "custom_components.elon_water_heater.coordinator.async_resolve_host"
    ) as resolve:
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=90))
        await hass.async_block_till_done()

    resolve.assert_not_called()
