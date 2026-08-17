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

"""Tests for the device API client."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.elon_water_heater.api import (
    ElonActionRejected,
    ElonApiClient,
    ElonConnectionError,
)

from .conftest import ACTION_FAILED, ACTION_OK, STATUS_IDLE_SOLAR, TEST_HOST

FORCE_URL = f"http://{TEST_HOST}/V1/Thermostat/ForceReheat"
STATUS_URL = f"http://{TEST_HOST}/V1/DeviceStatus/Query"
MEASUREMENTS_URL = f"http://{TEST_HOST}/V1/CurrentMeasurements/Query"


def _client(hass: HomeAssistant) -> ElonApiClient:
    return ElonApiClient(TEST_HOST, async_get_clientsession(hass))


async def test_get_device_status_unwraps_first_entry(hass, aioclient_mock):
    """The client returns the status object, not the wrapping list."""
    aioclient_mock.post(STATUS_URL, json=STATUS_IDLE_SOLAR)

    status = await _client(hass).get_device_status()

    assert status["powerSource"] == 1
    assert status["waterTemperature"] == 58.7


async def test_get_device_status_tolerates_empty_list(hass, aioclient_mock):
    """An empty deviceStatuses list yields an empty dict, not an IndexError."""
    aioclient_mock.post(STATUS_URL, json={"deviceStatuses": []})

    assert await _client(hass).get_device_status() == {}


async def test_get_measurements_drops_unimplemented_sensors(hass, aioclient_mock):
    """Sensor 9 is echoed back as ID 0 by the firmware and must be discarded."""
    aioclient_mock.post(
        MEASUREMENTS_URL,
        json={
            "deviceSerial": 7343,
            "measurements": [
                {"sensorId": 7, "value": 13848},
                {"sensorId": 0, "value": 0},
            ],
        },
    )

    assert await _client(hass).get_measurements([7, 9]) == {7: 13848}


async def test_force_reheat_accepts_ok_envelope(hass, aioclient_mock):
    """A well-formed Okay envelope completes without raising."""
    aioclient_mock.post(FORCE_URL, json=ACTION_OK)

    await _client(hass).force_reheat()


async def test_force_reheat_raises_on_rejection(hass, aioclient_mock):
    """A non-Okay envelope raises, carrying the device's failureReason.

    The device returns HTTP 200 with a failure envelope, so this is invisible
    unless the body is inspected.
    """
    aioclient_mock.post(FORCE_URL, json=ACTION_FAILED)

    with pytest.raises(ElonActionRejected, match="Thermostat busy"):
        await _client(hass).force_reheat()


async def test_connection_failure_is_wrapped(hass, aioclient_mock):
    """Transport errors surface as ElonConnectionError, not raw aiohttp."""
    aioclient_mock.post(STATUS_URL, exc=TimeoutError)

    with pytest.raises(ElonConnectionError):
        await _client(hass).get_device_status()
