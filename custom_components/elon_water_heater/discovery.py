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

"""mDNS address resolution for Elon devices.

The device is only reachable by its ``ELON-<serial>.local`` name, which is an
mDNS name.  Handing that name to ``aiohttp`` pushes it through the standard
resolver, which sends it to the configured unicast DNS server; that server
answers NODATA, and the connection fails with *DNS server returned answer with
no data*.  Worse, whatever answered once tends to keep answering the same way
until Home Assistant restarts.

Resolving through Home Assistant's own Zeroconf instance sidesteps that
entirely: we ask the multicast responder directly and hand ``aiohttp`` a plain
IP address, so no name resolution happens at request time at all.
"""

import logging

from homeassistant.components import zeroconf
from homeassistant.core import HomeAssistant
from zeroconf.asyncio import AsyncServiceInfo

from .const import ZEROCONF_RESOLVE_TIMEOUT_MS, ZEROCONF_TYPE

_LOGGER = logging.getLogger(__name__)


def service_name(serial_number: str) -> str:
    """Return the mDNS service instance name for a serial number.

    The device advertises as ``ELON-<serial>`` under ``_http._tcp.local.``.
    """
    return f"ELON-{serial_number}.{ZEROCONF_TYPE}"


def serial_from_service_name(name: str) -> str | None:
    """Extract the serial number from an mDNS instance name.

    The device publishes no TXT records, so the instance name is the only
    source for the serial.

    Args:
        name: An instance name such as ``ELON-5570._http._tcp.local.``.

    Returns:
        The serial number, or ``None`` if the name is not an Elon device.
    """
    instance = name.split(".", 1)[0]
    if not instance.lower().startswith("elon-"):
        return None
    serial = instance[len("elon-") :]
    return serial or None


async def async_resolve_host(hass: HomeAssistant, serial_number: str) -> str | None:
    """Resolve a device serial number to an IP address over mDNS.

    Args:
        hass: Home Assistant instance.
        serial_number: Serial number printed on the device.

    Returns:
        The device's IP address, or ``None`` if it did not answer.
    """
    aiozc = await zeroconf.async_get_async_instance(hass)
    info = AsyncServiceInfo(ZEROCONF_TYPE, service_name(serial_number))

    if not await info.async_request(aiozc.zeroconf, ZEROCONF_RESOLVE_TIMEOUT_MS):
        _LOGGER.debug("No mDNS response for ELON-%s", serial_number)
        return None

    addresses = info.parsed_addresses()
    if not addresses:
        _LOGGER.debug("ELON-%s answered mDNS but published no address", serial_number)
        return None

    return addresses[0]
