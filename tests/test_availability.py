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

"""Regression tests for the device staying "online" after losing power.

Reported behaviour: pulling power from the unit left every entity live in the
UI, still showing the last water temperature and still accepting on/off
commands that went nowhere.
"""

from datetime import timedelta

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .conftest import (
    MEASUREMENTS_IDLE,
    STATUS_IDLE_SOLAR,
    STATUS_URL,
    mock_device,
    setup_integration,
)

# Entities that must go dark when the device is unreachable.
DEVICE_BACKED_ENTITIES = [
    "water_heater.elon_5570",
    "switch.elon_5570_grid_boost",
    "sensor.elon_5570_water_temperature",
    "sensor.elon_5570_power_source",
]


async def _go_offline(hass, aioclient_mock) -> None:
    """Make the device unreachable and let one poll cycle elapse."""
    aioclient_mock.clear_requests()
    aioclient_mock.post(STATUS_URL, exc=TimeoutError)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=90))
    await hass.async_block_till_done()


async def _come_back(hass, aioclient_mock) -> None:
    """Make the device reachable again and let one poll cycle elapse."""
    aioclient_mock.clear_requests()
    mock_device(aioclient_mock, status=STATUS_IDLE_SOLAR, sensors=MEASUREMENTS_IDLE)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=90))
    await hass.async_block_till_done()


async def test_entities_start_available(hass, aioclient_mock):
    """Baseline: a reachable device produces live entities."""
    await setup_integration(hass, aioclient_mock)

    for entity_id in DEVICE_BACKED_ENTITIES:
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE, entity_id


async def test_entities_go_unavailable_when_device_loses_power(hass, aioclient_mock):
    """Every device-backed entity goes unavailable once polling fails.

    Previously the coordinator returned the last good payload on error, so
    ``last_update_success`` stayed true and the stale water temperature kept
    being displayed indefinitely.
    """
    await setup_integration(hass, aioclient_mock)
    await _go_offline(hass, aioclient_mock)

    for entity_id in DEVICE_BACKED_ENTITIES:
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE, entity_id


async def test_connectivity_sensor_reports_the_outage(hass, aioclient_mock):
    """The connectivity sensor stays available and flips off.

    This is the entity an automation can watch; the others merely disappear.
    """
    await setup_integration(hass, aioclient_mock)
    assert hass.states.get("binary_sensor.elon_5570_connectivity").state == STATE_ON

    await _go_offline(hass, aioclient_mock)

    assert hass.states.get("binary_sensor.elon_5570_connectivity").state == STATE_OFF


async def test_last_seen_survives_the_outage(hass, aioclient_mock):
    """Last Seen keeps reporting the last good poll while the device is down."""
    await setup_integration(hass, aioclient_mock)
    last_seen = hass.states.get("sensor.elon_5570_last_seen").state
    assert last_seen != STATE_UNAVAILABLE

    await _go_offline(hass, aioclient_mock)

    assert hass.states.get("sensor.elon_5570_last_seen").state == last_seen


async def test_recovers_without_restart(hass, aioclient_mock):
    """Entities come back on their own once the device answers again.

    Reported behaviour was that only a Home Assistant restart brought the
    integration back after the device was repowered.
    """
    await setup_integration(hass, aioclient_mock)
    await _go_offline(hass, aioclient_mock)
    assert hass.states.get("water_heater.elon_5570").state == STATE_UNAVAILABLE

    await _come_back(hass, aioclient_mock)

    assert hass.states.get("water_heater.elon_5570").state != STATE_UNAVAILABLE
    assert hass.states.get("binary_sensor.elon_5570_connectivity").state == STATE_ON
