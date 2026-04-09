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

# Polling interval
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)