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

"""Tests for driving grid boost from Home Assistant."""

import pytest
from homeassistant.const import STATE_OFF, STATE_ON

from custom_components.elon_water_heater.api import ElonActionRejected

from .conftest import (
    ACTION_FAILED,
    CANCEL_URL,
    FORCE_REHEAT_URL,
    MEASUREMENTS_BOOST_WITH_LOAD,
    STATUS_BOOST_WITH_LOAD,
    setup_integration,
)

SWITCH = "switch.elon_5570_grid_boost"


async def _call(hass, service: str) -> None:
    await hass.services.async_call(
        "switch", service, {"entity_id": SWITCH}, blocking=True
    )


async def test_turn_on_calls_force_reheat(hass, aioclient_mock):
    """Turning the switch on hits ForceReheat."""
    await setup_integration(hass, aioclient_mock)

    await _call(hass, "turn_on")

    assert [str(call[1]) for call in aioclient_mock.mock_calls].count(
        FORCE_REHEAT_URL
    ) == 1


async def test_turn_off_calls_cancel(hass, aioclient_mock):
    """Turning the switch off hits CancelGridHeating."""
    await setup_integration(
        hass,
        aioclient_mock,
        status=STATUS_BOOST_WITH_LOAD,
        sensors=MEASUREMENTS_BOOST_WITH_LOAD,
    )

    await _call(hass, "turn_off")

    assert [str(call[1]) for call in aioclient_mock.mock_calls].count(CANCEL_URL) == 1


async def test_turn_on_shows_immediately(hass, aioclient_mock):
    """The switch reports on straight away, before the device has switched.

    The device takes about ten seconds to change power source. Without an
    optimistic window the switch would snap back to off and look broken.
    """
    await setup_integration(hass, aioclient_mock)
    assert hass.states.get(SWITCH).state == STATE_OFF

    await _call(hass, "turn_on")

    assert hass.states.get(SWITCH).state == STATE_ON


async def test_rejected_action_does_not_fake_the_state(hass, aioclient_mock):
    """If the device refuses, the switch must not claim it turned on.

    The device answers HTTP 200 with a failure envelope, so this is only
    visible by inspecting the body.
    """
    await setup_integration(hass, aioclient_mock)
    aioclient_mock.clear_requests()
    aioclient_mock.post(FORCE_REHEAT_URL, json=ACTION_FAILED)

    with pytest.raises(ElonActionRejected):
        await _call(hass, "turn_on")

    assert hass.states.get(SWITCH).state == STATE_OFF
