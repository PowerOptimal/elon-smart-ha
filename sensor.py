"""Sensors for Elon Water Heater."""

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, UnitOfElectricCurrent, UnitOfElectricPotential, UnitOfResistance, UnitOfEnergy
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SENSOR_ID_WATER_TEMP,
    SENSOR_ID_AMBIENT_TEMP,
    SENSOR_ID_AC_CURRENT,
    SENSOR_RESOLUTIONS,
    POWER_SOURCE_NAMES,
    PowerSource,
    HEATING_CURRENT_THRESHOLD,
)
from .coordinator import ElonDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        WaterTemperatureSensor(coordinator),
        AmbientTemperatureSensor(coordinator),
        PowerSourceSensor(coordinator),
        HeatingStateSensor(coordinator),
        ACCurrentSensor(coordinator),
    ]

    async_add_entities(sensors)


class ElonSensor(SensorEntity):
    """Base sensor for Elon Water Heater."""

    def __init__(self, coordinator: ElonDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.serial_number)},
            "name": f"Elon {coordinator.serial_number}",
            "manufacturer": "Elon",
            "model": "Smart Water Heater",
        }

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.coordinator.async_add_listener(self._handle_update)

    @callback
    def _handle_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class WaterTemperatureSensor(ElonSensor):
    """Water temperature sensor."""

    _attr_name = "Water Temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> float | None:
        """Return water temperature."""
        data = self.coordinator.data
        if not data:
            return None
        temp = data.get("waterTemperature")
        return round(temp, 1) if temp is not None else None


class AmbientTemperatureSensor(ElonSensor):
    """Ambient temperature sensor."""

    _attr_name = "Ambient Temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> float | None:
        """Return ambient temperature."""
        sensors = self.coordinator.sensor_data
        raw = sensors.get(SENSOR_ID_AMBIENT_TEMP)
        if raw is None:
            return None
        resolution = SENSOR_RESOLUTIONS[SENSOR_ID_AMBIENT_TEMP]
        return round(raw * resolution, 1)


class PowerSourceSensor(ElonSensor):
    """Power source sensor."""

    _attr_name = "Power Source"

    @property
    def native_value(self) -> str | None:
        """Return power source."""
        data = self.coordinator.data
        if not data:
            return None
        source = data.get("powerSource")
        return POWER_SOURCE_NAMES.get(source, "Unknown")


class HeatingStateSensor(ElonSensor):
    """Heating state sensor (derived from power source and AC current)."""

    _attr_name = "Heating State"

    @property
    def native_value(self) -> str | None:
        """Return heating state."""
        data = self.coordinator.data
        sensors = self.coordinator.sensor_data

        if not data:
            return None

        power_source = data.get("powerSource")
        ac_current_raw = sensors.get(SENSOR_ID_AC_CURRENT, 0)
        ac_current = ac_current_raw * SENSOR_RESOLUTIONS[SENSOR_ID_AC_CURRENT]

        # If AC current > threshold, actively heating from grid
        if power_source == PowerSource.AC_GRID and ac_current > HEATING_CURRENT_THRESHOLD:
            return "Heating"

        # DC Solar power source means DC heating (even if current is low)
        if power_source == PowerSource.DC_SOLAR:
            return "Solar"

        if power_source == PowerSource.AC_GRID:
            return "Grid (Idle)"

        if power_source == PowerSource.DISCONNECTED:
            return "Disconnected"

        return "Unknown"


class ACCurrentSensor(ElonSensor):
    """AC RMS Current sensor."""

    _attr_name = "AC Current"
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    @property
    def native_value(self) -> float | None:
        """Return AC current."""
        sensors = self.coordinator.sensor_data
        raw = sensors.get(SENSOR_ID_AC_CURRENT)
        if raw is None:
            return None
        resolution = SENSOR_RESOLUTIONS[SENSOR_ID_AC_CURRENT]
        return round(raw * resolution, 3)

