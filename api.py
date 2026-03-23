"""API client for Elon Water Heater."""

import aiohttp
from .const import (
    HOSTNAME_FORMAT,
    ENDPOINT_DEVICE_STATUS,
    ENDPOINT_MEASUREMENTS,
    ENDPOINT_FORCE_REHEAT,
    ENDPOINT_CANCEL_HEATING,
)


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

        async with self._session.post(url, json=payload) as response:
            response.raise_for_status()
            return await response.json()

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

        measurements = {}
        if "sensorValues" in result:
            for item in result["sensorValues"]:
                sensor_id = item.get("sensorId")
                raw_value = item.get("value", 0)
                measurements[sensor_id] = raw_value

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