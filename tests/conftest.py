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

"""Shared fixtures.

The device payloads below are recorded verbatim from two live units during a
``ForceReheat`` / ``CancelGridHeating`` cycle:

* **5570** -- a complete installation.  Boosting drives 13.848 A at 233.3 V.
* **7343** -- no element and no solar connection.  Boosting engages the grid
  relay but draws no current, and the device raises an alarm ~30 s later.

7343 is the important one: it proves ``powerSource`` tracks the *boost
request* while AC current tracks the *load*, and those are independent.  A
tank already at target behaves the same way, which is the case users hit when
they enable boost from the phone app and Home Assistant fails to notice.
"""

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.elon_water_heater.const import (
    CONF_HOST,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)

pytest_plugins = "pytest_homeassistant_custom_component"

# Host used throughout the tests.  Config entries set the manual host override
# so request URLs are predictable and no mDNS resolution is attempted.
TEST_HOST = "192.0.2.10"
TEST_SERIAL = "5570"

STATUS_URL = f"http://{TEST_HOST}/V1/DeviceStatus/Query"
MEASUREMENTS_URL = f"http://{TEST_HOST}/V1/CurrentMeasurements/Query"
FORCE_REHEAT_URL = f"http://{TEST_HOST}/V1/Thermostat/ForceReheat"
CANCEL_URL = f"http://{TEST_HOST}/V1/Thermostat/CancelGridHeating"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Make the custom component importable in every test."""
    return


@pytest.fixture(autouse=True)
def stub_zeroconf(mock_async_zeroconf):
    """Stand in for the zeroconf integration.

    The manifest depends on ``zeroconf`` so the device address can be resolved
    over mDNS.  Setting the real one up would open multicast sockets, which
    the test harness blocks.
    """
    return mock_async_zeroconf


def device_status(
    *,
    power_source: int,
    water_temperature: float = 58.7,
    has_open_alarms: bool = False,
    ac_not_present: bool = False,
    device: int = 5570,
) -> dict:
    """Build a DeviceStatus/Query response.

    Field names and types mirror the live device exactly, including
    ``reheatTime``, which the firmware never sets to anything but ``0``.
    """
    return {
        "deviceStatuses": [
            {
                "device": device,
                "lastComms": 209137527,
                "waterTemperature": water_temperature,
                "hasOpenAlarms": has_open_alarms,
                "acNotPresent": ac_not_present,
                "powerSource": power_source,
                "logicalName": "Dave Main",
                "streetAddress": " 12 The Crofts",
                "reheatTime": 0,
            }
        ]
    }


def measurements(*, ac_current_raw: int = 0, ac_voltage_raw: int = 0) -> dict:
    """Build a CurrentMeasurements/Query response.

    AC voltage reads zero while the grid relay is open, so the pair moves
    together.  Raw integers are scaled by ``SENSOR_RESOLUTIONS``.
    """
    return {
        "deviceSerial": 5570,
        "measurements": [
            {"sensorId": 2, "value": 373},
            {"sensorId": 3, "value": 16},
            {"sensorId": 4, "value": 51},
            {"sensorId": 6, "value": ac_voltage_raw},
            {"sensorId": 7, "value": ac_current_raw},
        ],
    }


# Idle on solar: the relay is open, no current, no alarms.
STATUS_IDLE_SOLAR = device_status(power_source=1)
MEASUREMENTS_IDLE = measurements()

# 5570 mid-boost with a real element: 13.848 A at 233.3 V.
STATUS_BOOST_WITH_LOAD = device_status(power_source=2)
MEASUREMENTS_BOOST_WITH_LOAD = measurements(ac_current_raw=13848, ac_voltage_raw=2333)

# 7343 mid-boost with no element: grid engaged, 0.013 A, alarm latched.
# This is the payload that reproduces the app-to-HA sync bug.
STATUS_BOOST_NO_LOAD = device_status(
    power_source=2, water_temperature=21.5, has_open_alarms=True, device=7343
)
MEASUREMENTS_BOOST_NO_LOAD = measurements(ac_current_raw=13)

# Action endpoint envelopes.
ACTION_OK = {"actionResult": "Okay", "seqNo": 0, "failureReason": ""}
ACTION_FAILED = {
    "actionResult": "Failed",
    "seqNo": 0,
    "failureReason": "Thermostat busy",
}


def mock_device(
    aioclient_mock: AiohttpClientMocker,
    *,
    status: dict,
    sensors: dict,
) -> None:
    """Serve a full set of device endpoints returning the given payloads."""
    aioclient_mock.post(STATUS_URL, json=status)
    aioclient_mock.post(MEASUREMENTS_URL, json=sensors)
    aioclient_mock.post(FORCE_REHEAT_URL, json=ACTION_OK)
    aioclient_mock.post(CANCEL_URL, json=ACTION_OK)


async def setup_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    *,
    status: dict = STATUS_IDLE_SOLAR,
    sensors: dict = MEASUREMENTS_IDLE,
) -> MockConfigEntry:
    """Set up the integration against mocked device endpoints.

    The entry carries an explicit host so no mDNS resolution is attempted.
    """
    mock_device(aioclient_mock, status=status, sensors=sensors)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SERIAL_NUMBER: TEST_SERIAL, CONF_HOST: TEST_HOST},
        unique_id=TEST_SERIAL,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
