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

"""Tests for the config flow, including mDNS discovery."""

from ipaddress import ip_address
from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from custom_components.elon_water_heater.const import (
    CONF_HOST,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)
from custom_components.elon_water_heater.discovery import serial_from_service_name

from .conftest import TEST_HOST, TEST_SERIAL, setup_integration

DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address(TEST_HOST),
    ip_addresses=[ip_address(TEST_HOST)],
    port=80,
    hostname=f"ELON-{TEST_SERIAL}.local.",
    type="_http._tcp.local.",
    name=f"ELON-{TEST_SERIAL}._http._tcp.local.",
    properties={},
)


def test_serial_extracted_from_instance_name():
    """The serial comes from the instance name; there are no TXT records."""
    assert serial_from_service_name("ELON-5570._http._tcp.local.") == "5570"


def test_non_elon_service_is_rejected():
    """Other HTTP services on the network must not be treated as devices."""
    assert serial_from_service_name("HP Laser 107w._http._tcp.local.") is None


async def test_user_flow_without_host(hass):
    """A serial alone is enough; the address is resolved at runtime."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "custom_components.elon_water_heater.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SERIAL_NUMBER: TEST_SERIAL}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_SERIAL_NUMBER: TEST_SERIAL}


async def test_user_flow_with_manual_host(hass):
    """A supplied host is stored and bypasses mDNS entirely."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "custom_components.elon_water_heater.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL_NUMBER: TEST_SERIAL, CONF_HOST: TEST_HOST},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == TEST_HOST


async def test_user_flow_rejects_bad_serial(hass):
    """A serial with illegal characters is refused with a field error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SERIAL_NUMBER: "12/34"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_SERIAL_NUMBER: "invalid"}


async def test_zeroconf_discovery_creates_entry(hass):
    """A discovered device is added after confirmation.

    The discovered address is deliberately not stored: it is a DHCP lease, and
    resolving by serial handles it moving.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=DISCOVERY
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with patch(
        "custom_components.elon_water_heater.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_SERIAL_NUMBER: TEST_SERIAL}


async def test_zeroconf_ignores_other_http_services(hass):
    """The printer advertising _http._tcp must not open a flow."""
    other = ZeroconfServiceInfo(
        ip_address=ip_address("192.0.2.99"),
        ip_addresses=[ip_address("192.0.2.99")],
        port=80,
        hostname="printer.local.",
        type="_http._tcp.local.",
        name="HP Laser 107w._http._tcp.local.",
        properties={},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=other
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_elon_device"


async def test_discovery_of_configured_device_aborts(hass, aioclient_mock):
    """Rediscovering an already-configured device does not duplicate it."""
    await setup_integration(hass, aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=DISCOVERY
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
