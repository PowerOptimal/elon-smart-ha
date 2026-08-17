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

"""Config flow for Elon Water Heater."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_HOST, CONF_SERIAL_NUMBER, DOMAIN
from .discovery import serial_from_service_name

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERIAL_NUMBER): str,
        vol.Optional(CONF_HOST): str,
    }
)


class ElonWaterHeaterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elon Water Heater."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the flow."""
        self._discovered_serial: str | None = None
        self._discovered_host: str | None = None

    def _create_entry(self, serial: str, host: str | None):
        """Create the config entry for a device.

        Args:
            serial: Device serial number.
            host: Optional fixed host or IP.  When omitted the address is
                resolved over mDNS at runtime.
        """
        data = {CONF_SERIAL_NUMBER: serial}
        if host:
            data[CONF_HOST] = host
        return self.async_create_entry(
            title=f"Elon Water Heater ({serial})", data=data
        )

    async def async_step_user(self, user_input=None):
        """Handle a manually initiated flow."""
        errors = {}

        if user_input is not None:
            serial = user_input.get(CONF_SERIAL_NUMBER, "").strip()
            host = (user_input.get(CONF_HOST) or "").strip() or None

            if not serial:
                errors[CONF_SERIAL_NUMBER] = "required"
            elif not serial.replace("-", "").replace("_", "").isalnum():
                errors[CONF_SERIAL_NUMBER] = "invalid"

            if not errors:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                return self._create_entry(serial, host)

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo):
        """Handle a device found on the network.

        The device publishes no TXT records, so the serial number is taken
        from the mDNS instance name (``ELON-<serial>._http._tcp.local.``).
        """
        serial = serial_from_service_name(discovery_info.name)
        if serial is None:
            return self.async_abort(reason="not_elon_device")

        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured()

        self._discovered_serial = serial
        self._discovered_host = discovery_info.host
        self.context["title_placeholders"] = {"name": f"Elon {serial}"}

        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Ask the user to confirm adding a discovered device.

        The discovered address is not stored: it is a DHCP lease that may
        change, and resolving by serial over mDNS handles that automatically.
        """
        if user_input is not None:
            return self._create_entry(self._discovered_serial, None)

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "serial": self._discovered_serial,
                "host": self._discovered_host,
            },
        )

    async def async_step_yaml(self, user_input=None):
        """Handle YAML configuration."""
        return await self.async_step_user(user_input)
