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

"""Regression tests for boost state started outside Home Assistant.

Reported behaviour: enabling or cancelling grid boost in the Elon phone app
did not change anything in Home Assistant, while doing the same from Home
Assistant did show up in the app.

The cause was requiring AC current above 2 A *in addition to* the grid power
source.  Live probing showed the device engages the grid relay
(``powerSource`` 2) on a boost request regardless of whether the element then
draws anything -- 13.848 A on a connected unit, 0.013 A on one with no
element, and effectively nothing on a tank already at target.
"""

from datetime import timedelta

from homeassistant.components.water_heater import STATE_ELECTRIC
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .conftest import (
    MEASUREMENTS_BOOST_NO_LOAD,
    MEASUREMENTS_BOOST_WITH_LOAD,
    MEASUREMENTS_IDLE,
    STATUS_BOOST_NO_LOAD,
    STATUS_BOOST_WITH_LOAD,
    STATUS_IDLE_SOLAR,
    mock_device,
    setup_integration,
)

WATER_HEATER = "water_heater.elon_5570"
SWITCH = "switch.elon_5570_grid_boost"
HEATING_STATE = "sensor.elon_5570_heating_state"


async def test_boost_detected_when_element_draws_current(hass, aioclient_mock):
    """The straightforward case: grid engaged and 13.8 A flowing."""
    await setup_integration(
        hass,
        aioclient_mock,
        status=STATUS_BOOST_WITH_LOAD,
        sensors=MEASUREMENTS_BOOST_WITH_LOAD,
    )

    assert hass.states.get(WATER_HEATER).state == STATE_ELECTRIC
    assert hass.states.get(SWITCH).state == STATE_ON


async def test_boost_detected_when_element_draws_nothing(hass, aioclient_mock):
    """Grid engaged but no meaningful current still counts as boosting.

    This is the reported bug. A boost enabled from the phone app on a tank at
    target draws no current, and the old predicate reported the geyser as off.
    """
    await setup_integration(
        hass,
        aioclient_mock,
        status=STATUS_BOOST_NO_LOAD,
        sensors=MEASUREMENTS_BOOST_NO_LOAD,
    )

    assert hass.states.get(WATER_HEATER).state == STATE_ELECTRIC
    assert hass.states.get(SWITCH).state == STATE_ON


async def test_idle_on_solar_is_off(hass, aioclient_mock):
    """Solar heating is not grid boost and must not light the tile."""
    await setup_integration(hass, aioclient_mock)

    assert hass.states.get(WATER_HEATER).state == STATE_OFF
    assert hass.states.get(SWITCH).state == STATE_OFF


async def test_cancel_from_the_app_is_picked_up(hass, aioclient_mock):
    """A boost cancelled outside HA returns the entities to off."""
    await setup_integration(
        hass,
        aioclient_mock,
        status=STATUS_BOOST_WITH_LOAD,
        sensors=MEASUREMENTS_BOOST_WITH_LOAD,
    )
    assert hass.states.get(SWITCH).state == STATE_ON

    # The app cancels: the device drops back to solar and current stops.
    aioclient_mock.clear_requests()
    mock_device(aioclient_mock, status=STATUS_IDLE_SOLAR, sensors=MEASUREMENTS_IDLE)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=90))
    await hass.async_block_till_done()

    assert hass.states.get(SWITCH).state == STATE_OFF
    assert hass.states.get(WATER_HEATER).state == STATE_OFF


async def test_switch_and_water_heater_never_disagree(hass, aioclient_mock):
    """Both entities drive one relay and must report the same thing."""
    for status, sensors, switch_state, heater_state in [
        (STATUS_IDLE_SOLAR, MEASUREMENTS_IDLE, STATE_OFF, STATE_OFF),
        (STATUS_BOOST_NO_LOAD, MEASUREMENTS_BOOST_NO_LOAD, STATE_ON, STATE_ELECTRIC),
        (
            STATUS_BOOST_WITH_LOAD,
            MEASUREMENTS_BOOST_WITH_LOAD,
            STATE_ON,
            STATE_ELECTRIC,
        ),
    ]:
        entry = await setup_integration(
            hass, aioclient_mock, status=status, sensors=sensors
        )
        assert hass.states.get(SWITCH).state == switch_state
        assert hass.states.get(WATER_HEATER).state == heater_state

        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        aioclient_mock.clear_requests()


async def test_heating_state_still_distinguishes_actual_draw(hass, aioclient_mock):
    """Current draw remains visible, just not as the boost predicate.

    Grid engaged with no element draw is reported as idle, which is how a
    failed element presents.
    """
    await setup_integration(
        hass,
        aioclient_mock,
        status=STATUS_BOOST_NO_LOAD,
        sensors=MEASUREMENTS_BOOST_NO_LOAD,
    )
    assert hass.states.get(HEATING_STATE).state == "Grid (Idle)"


async def test_heating_state_reports_heating_under_load(hass, aioclient_mock):
    """Grid engaged with the element drawing reads as heating."""
    await setup_integration(
        hass,
        aioclient_mock,
        status=STATUS_BOOST_WITH_LOAD,
        sensors=MEASUREMENTS_BOOST_WITH_LOAD,
    )
    assert hass.states.get(HEATING_STATE).state == "Heating"
