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

"""API client for Elon Water Heater."""

import logging

import aiohttp
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DEVICE_HTTP_TIMEOUT,
    ENDPOINT_CANCEL_HEATING,
    ENDPOINT_DEVICE_STATUS,
    ENDPOINT_FORCE_REHEAT,
    ENDPOINT_MEASUREMENTS,
)

_LOGGER = logging.getLogger(__name__)

# The device wraps every action response in this envelope.  Anything other
# than ``Okay`` means the device declined to act.
ACTION_RESULT_OK = "Okay"


class ElonApiError(HomeAssistantError):
    """Base error for device communication.

    Derives from :class:`HomeAssistantError` so that a failure raised out of a
    service call surfaces as a readable message in the UI rather than a raw
    ``aiohttp`` traceback.
    """


class ElonConnectionError(ElonApiError):
    """The device could not be reached."""


class ElonActionRejected(ElonApiError):
    """The device was reached but refused to perform the action."""


class ElonApiClient:
    """Client for communicating with the Elon water heater device.

    The client is deliberately dumb about addressing: it talks to whatever
    :attr:`host` currently holds.  Resolving the device's ``.local`` name to an
    address, and re-resolving it when the device moves or reboots, is the
    coordinator's job.
    """

    def __init__(self, host: str | None, session: aiohttp.ClientSession) -> None:
        """Initialize the API client.

        Args:
            host: Hostname or IP address of the device, without scheme or port.
                ``None`` means the address is not yet known; the coordinator
                resolves one before the first request.
            session: aiohttp client session, owned by the caller.
        """
        self.host = host
        self._session = session

    async def _post(self, endpoint: str, data: dict | None = None) -> dict:
        """Make a POST request to the device.

        Args:
            endpoint: API endpoint path.
            data: Optional JSON payload; an empty object is sent if omitted.

        Returns:
            The decoded response body.

        Raises:
            ElonConnectionError: The device was unreachable, timed out, or
                returned a non-2xx status.
        """
        url = f"http://{self.host}/{endpoint}"
        payload = data if data is not None else {}

        _LOGGER.debug("POST %s  body=%s", url, payload)
        try:
            async with self._session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=DEVICE_HTTP_TIMEOUT),
            ) as response:
                response.raise_for_status()
                # The device serves JSON without a JSON content type.
                return await response.json(content_type=None)
        except aiohttp.ClientError as err:
            raise ElonConnectionError(f"Cannot reach Elon device at {self.host}") from err
        except TimeoutError as err:
            raise ElonConnectionError(f"Timed out talking to Elon device at {self.host}") from err

    async def _action(self, endpoint: str) -> None:
        """Invoke an action endpoint and check the result envelope.

        Raises:
            ElonConnectionError: The device was unreachable.
            ElonActionRejected: The device declined, carrying ``failureReason``.
        """
        result = await self._post(endpoint, {})
        outcome = result.get("actionResult")
        if outcome != ACTION_RESULT_OK:
            reason = result.get("failureReason") or "no reason given"
            raise ElonActionRejected(f"Device refused {endpoint}: {outcome} ({reason})")

    async def get_device_status(self) -> dict:
        """Get device status.

        Returns:
            The first entry of ``deviceStatuses``, carrying ``powerSource``,
            ``waterTemperature``, ``hasOpenAlarms`` and friends.  An empty dict
            if the device reported no statuses.
        """
        result = await self._post(ENDPOINT_DEVICE_STATUS)
        statuses = result.get("deviceStatuses")
        return statuses[0] if statuses else {}

    async def get_measurements(self, sensor_ids: list[int]) -> dict[int, int]:
        """Get raw sensor measurements.

        Values are returned unscaled; callers apply ``SENSOR_RESOLUTIONS``.

        Args:
            sensor_ids: Sensor IDs to retrieve.

        Returns:
            Mapping of sensor ID to raw integer reading.  Sensors the firmware
            does not implement are echoed back as ID ``0`` and dropped here.
        """
        result = await self._post(ENDPOINT_MEASUREMENTS, {"SensorIds": sensor_ids})
        return {
            item["sensorId"]: item["value"]
            for item in result.get("measurements", [])
            if item.get("sensorId")
        }

    async def force_reheat(self) -> None:
        """Trigger immediate grid heating."""
        await self._action(ENDPOINT_FORCE_REHEAT)

    async def cancel_grid_heating(self) -> None:
        """Cancel a previously triggered heat cycle."""
        await self._action(ENDPOINT_CANCEL_HEATING)
