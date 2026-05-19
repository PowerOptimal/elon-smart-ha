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

"""Data coordinator for Elon Water Heater."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import ElonApiClient
from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    SENSOR_ID_WATER_TEMP,
    SENSOR_ID_AMBIENT_TEMP,
    SENSOR_ID_DC_VOLTAGE,
    SENSOR_ID_DC_CURRENT,
    SENSOR_ID_DC_ENERGY,
    SENSOR_ID_AC_VOLTAGE,
    SENSOR_ID_AC_CURRENT,
    SENSOR_ID_AC_ENERGY,
    SENSOR_ID_ELEMENT_RESISTANCE,
)


class ElonDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator for fetching data from the Elon water heater."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: ElonApiClient,
        serial_number: str,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.api = api
        self.serial_number = serial_number

        # Data storage
        self.data: dict | None = None
        self.sensor_data: dict[int, int] = {}

        super().__init__(
            hass,
            logging.getLogger(__name__),
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from the device."""
        # Fetch device status
        try:
            self.data = await self.api.get_device_status()
        except Exception as exc:
            # If we can't reach device, keep old data but raise
            if self.data is None:
                raise exc
            # Return existing data on failure
            return self.data

        # Fetch sensor measurements
        try:
            sensor_ids = [
                SENSOR_ID_WATER_TEMP,
                SENSOR_ID_AMBIENT_TEMP,
                SENSOR_ID_DC_VOLTAGE,
                SENSOR_ID_DC_CURRENT,
                SENSOR_ID_DC_ENERGY,
                SENSOR_ID_AC_VOLTAGE,
                SENSOR_ID_AC_CURRENT,
                SENSOR_ID_AC_ENERGY,
                SENSOR_ID_ELEMENT_RESISTANCE,
            ]
            self.sensor_data = await self.api.get_measurements(sensor_ids)
        except Exception:
            #传感器数据获取失败时保留旧数据
            pass

        return self.data