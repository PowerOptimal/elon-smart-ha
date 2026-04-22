"""API client for Elon Water Heater."""

import logging
import aiohttp
from .const import (
    HOSTNAME_FORMAT,
    ENDPOINT_DEVICE_STATUS,
    ENDPOINT_MEASUREMENTS,
    ENDPOINT_FORCE_REHEAT,
    ENDPOINT_CANCEL_HEATING,
)


_LOGGER = logging.getLogger(__name__)


class ElonApiClient:
    """Client for communicating with the Elon water heater device."""

    def __init__(self, serial_number: str, session: aiohttp.ClientSession):
        """Initialize the API client.

        Args:
            serial_number: Device serial number
            session: aiohttp client session
        """
        self._host = HOSTNAME_FORMAT.format(serial=serial_number)
        self._session = session

    async def _post(self, endpoint: str, data: dict | None = None) -> dict:
        """Make a POST request to the device.

        Args:
            endpoint: API endpoint path
            data: Optional JSON payload

        Returns:
            Response JSON

        Raises:
            aiohttp.ClientError: On connection error
        """
        url = f"http://{self._host}/{endpoint}"
        payload = data if data is not None else {}

        _LOGGER.debug("POST %s  body=%s", url, payload)
        async with self._session.post(url, json=payload) as response:
            raw = await response.text()
            _LOGGER.debug("POST %s  status=%s  response=%s", url, response.status, raw)
            response.raise_for_status()
            return await response.json(content_type=None)

    async def get_device_status(self) -> dict:
        """Get device status including power source and reheat info.

        Returns:
            Device status dict with powerSource, waterTemperature, etc.
        """
        result = await self._post(ENDPOINT_DEVICE_STATUS)
        if result.get("deviceStatuses"):
            return result["deviceStatuses"][0]
        return {}

    async def get_measurements(self, sensor_ids: list[int]) -> dict:
        """Get sensor measurements.

        Args:
            sensor_ids: List of sensor IDs to retrieve

        Returns:
            Dict mapping sensor ID to value
        """
        result = await self._post(ENDPOINT_MEASUREMENTS, {"SensorIds": sensor_ids})
        _LOGGER.debug("get_measurements top-level keys: %s", list(result.keys()))

        measurements = {}
        # Find the list of sensor readings — key name may vary by firmware
        items = None
        for key in ("sensorValues", "measurements", "values", "sensors"):
            if key in result:
                items = result[key]
                _LOGGER.debug("get_measurements: using key '%s'", key)
                break

        if items is None:
            _LOGGER.warning(
                "get_measurements: no recognised list key in response keys=%s  full=%s",
                list(result.keys()), result,
            )
            return measurements

        # Log the first item so we can see the actual field names
        if items:
            _LOGGER.debug("get_measurements: first item fields=%s  value=%s", list(items[0].keys()), items[0])

        for item in items:
            # Try common field name variants
            sensor_id = item.get("sensorId") or item.get("id") or item.get("sensor_id")
            raw_value = item.get("value") if item.get("value") is not None else item.get("reading") or item.get("rawValue", 0)
            if sensor_id is not None:
                measurements[sensor_id] = raw_value

        _LOGGER.debug("get_measurements parsed: %s", measurements)
        return measurements

    async def force_reheat(self) -> bool:
        """Trigger immediate grid heating.

        Returns:
            True if successful
        """
        await self._post(ENDPOINT_FORCE_REHEAT, {})
        return True

    async def cancel_grid_heating(self) -> bool:
        """Cancel a previously triggered heat cycle.

        Returns:
            True if successful
        """
        await self._post(ENDPOINT_CANCEL_HEATING, {})
        return True