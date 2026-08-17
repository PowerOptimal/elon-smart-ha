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

# Config entry keys
CONF_SERIAL_NUMBER = "serial_number"
CONF_HOST = "host"

# The device advertises itself as an instance named ``ELON-<serial>`` under the
# generic HTTP service type.  There are no TXT records; the serial has to be
# taken from the instance name.
ZEROCONF_TYPE = "_http._tcp.local."
ZEROCONF_NAME_PREFIX = "elon-"

# How long to wait for an mDNS response when resolving the device address.
ZEROCONF_RESOLVE_TIMEOUT_MS = 3000

# API Endpoints
ENDPOINT_DEVICE_STATUS = "V1/DeviceStatus/Query"
ENDPOINT_MEASUREMENTS = "V1/CurrentMeasurements/Query"
ENDPOINT_FORCE_REHEAT = "V1/Thermostat/ForceReheat"
ENDPOINT_CANCEL_HEATING = "V1/Thermostat/CancelGridHeating"

# Sensor IDs.  Sensor 9 (element resistance) is documented in the protocol but
# is not implemented by the firmware -- requesting it returns an entry with
# ``sensorId: 0`` -- so it is deliberately absent here.
SENSOR_ID_WATER_TEMP = 1
SENSOR_ID_AMBIENT_TEMP = 2
SENSOR_ID_DC_VOLTAGE = 3
SENSOR_ID_DC_CURRENT = 4
SENSOR_ID_DC_ENERGY = 5
SENSOR_ID_AC_VOLTAGE = 6
SENSOR_ID_AC_CURRENT = 7
SENSOR_ID_AC_ENERGY = 8

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
}

# Sensors actually fetched each poll.  Water temperature is read from the
# DeviceStatus payload rather than sensor 1 -- the two sources refresh on
# different cadences and disagree slightly, so we keep a single source.  The
# energy counters (5, 8) are not polled until the savings feature needs them;
# the measurement query is the slow call in each refresh.
POLLED_SENSOR_IDS = [
    SENSOR_ID_AMBIENT_TEMP,
    SENSOR_ID_DC_VOLTAGE,
    SENSOR_ID_DC_CURRENT,
    SENSOR_ID_AC_VOLTAGE,
    SENSOR_ID_AC_CURRENT,
]

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

# Delay before the follow-up refresh after a user action, in seconds.  The
# device switches power source within about ten seconds of ForceReheat or
# CancelGridHeating, so this lands just after the real transition.
ACTION_SETTLE_DELAY = 15