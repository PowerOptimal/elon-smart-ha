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

"""Constants for the Elon Water Heater integration."""

from datetime import timedelta

DOMAIN = "elon_water_heater"

# Device hostname format
HOSTNAME_FORMAT = "ELON-{serial}.local"
BASE_URL = "http://{host}/{endpoint}"

# API Endpoints
ENDPOINT_DEVICE_STATUS = "V1/DeviceStatus/Query"
ENDPOINT_MEASUREMENTS = "V1/CurrentMeasurements/Query"
ENDPOINT_FORCE_REHEAT = "V1/Thermostat/ForceReheat"
ENDPOINT_CANCEL_HEATING = "V1/Thermostat/CancelGridHeating"

# Sensor IDs
SENSOR_ID_WATER_TEMP = 1
SENSOR_ID_AMBIENT_TEMP = 2
SENSOR_ID_DC_VOLTAGE = 3
SENSOR_ID_DC_CURRENT = 4
SENSOR_ID_DC_ENERGY = 5
SENSOR_ID_AC_VOLTAGE = 6
SENSOR_ID_AC_CURRENT = 7
SENSOR_ID_AC_ENERGY = 8
SENSOR_ID_ELEMENT_RESISTANCE = 9

# Sensor resolutions (multiply raw value by this)
SENSOR_RESOLUTIONS = {
    SENSOR_ID_WATER_TEMP: 0.1,
    SENSOR_ID_AMBIENT_TEMP: 0.1,
    SENSOR_ID_DC_VOLTAGE: 0.1,
    SENSOR_ID_DC_CURRENT: 0.001,
    SENSOR_ID_DC_ENERGY: 1,
    SENSOR_ID_AC_VOLTAGE: 0.1,
    SENSOR_ID_AC_CURRENT: 0.001,
    SENSOR_ID_AC_ENERGY: 1,
    SENSOR_ID_ELEMENT_RESISTANCE: 0.1,
}

SENSOR_UNITS = {
    SENSOR_ID_WATER_TEMP: "°C",
    SENSOR_ID_AMBIENT_TEMP: "°C",
    SENSOR_ID_DC_VOLTAGE: "V",
    SENSOR_ID_DC_CURRENT: "A",
    SENSOR_ID_DC_ENERGY: "Wh",
    SENSOR_ID_AC_VOLTAGE: "V",
    SENSOR_ID_AC_CURRENT: "A",
    SENSOR_ID_AC_ENERGY: "Wh",
    SENSOR_ID_ELEMENT_RESISTANCE: "Ω",
}

# Power source enum
class PowerSource:
    """Power source enumeration."""

    UNKNOWN = 0
    DC_SOLAR = 1
    AC_GRID = 2
    DISCONNECTED = 3

POWER_SOURCE_NAMES = {
    PowerSource.UNKNOWN: "Unknown",
    PowerSource.DC_SOLAR: "DC Solar",
    PowerSource.AC_GRID: "AC Grid",
    PowerSource.DISCONNECTED: "Disconnected",
}

# Heating state
HEATING_CURRENT_THRESHOLD = 2.0  # Amps

# Polling interval.  The device's measurement query takes ~5 s; polling every
# 60 s leaves comfortable headroom for the two sequential calls per refresh
# (status + sensors) without flooding the device.
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)

# HTTP timeout for an individual request to the device.  The measurement query
# can take ~5 s under load; 30 s gives a generous safety margin so transient
# slowness doesn't drop sensor data.
DEVICE_HTTP_TIMEOUT = 30