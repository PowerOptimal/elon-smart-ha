"""Switch platform for Elon Water Heater."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    PowerSource,
    HEATING_CURRENT_THRESHOLD,
    SENSOR_ID_AC_CURRENT,
    SENSOR_RESOLUTIONS,
)
from .coordinator import ElonDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ElonGridHeatSwitch(coordinator)])


class ElonGridHeatSwitch(SwitchEntity):
    """Switch to trigger or cancel grid heating.

    Exposed as a Matter-compatible switch so it can be controlled via Siri /
    HomePod.  On = heating from grid; Off = cancel / not heating.
    """

    _attr_has_entity_name = True
    _attr_name = "Grid Heating"
    _attr_icon = "mdi:radiator"

    def __init__(self, coordinator: ElonDataUpdateCoordinator) -> None:
        """Initialise the switch."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.serial_number}_grid_heat"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.serial_number)},
            "name": f"Elon {coordinator.serial_number}",
            "manufacturer": "Elon",
            "model": "Smart Water Heater",
        }

    async def async_added_to_hass(self) -> None:
        """Register coordinator callback."""
        self.coordinator.async_add_listener(self._handle_update)

    @callback
    def _handle_update(self) -> None:
        """Push updated state to HA."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Available when coordinator has data."""
        return self.coordinator.data is not None

    @property
    def is_on(self) -> bool:
        """True when a forced reheat is active or the device is heating from grid.

        reheatTime > 0 means a forced reheat has been scheduled/is running.
        As a secondary check, powerSource==AC_GRID with AC current above threshold
        also counts, for cases where the device is heating without a forced request.
        """
        data = self.coordinator.data
        if not data:
            return False

        # Forced reheat indicator from device status (most reliable)
        if data.get("reheatTime", 0) > 0:
            return True

        # Fallback: actively drawing grid power above heating threshold
        sensors = self.coordinator.sensor_data
        power_source = data.get("powerSource")
        ac_current_raw = sensors.get(SENSOR_ID_AC_CURRENT, 0)
        ac_current = ac_current_raw * SENSOR_RESOLUTIONS[SENSOR_ID_AC_CURRENT]

        return (
            power_source == PowerSource.AC_GRID
            and ac_current > HEATING_CURRENT_THRESHOLD
        )

    @property
    def icon(self) -> str:
        """Radiator icon, filled when heating."""
        return "mdi:radiator" if self.is_on else "mdi:radiator-off"

    async def async_turn_on(self, **kwargs) -> None:
        """Request immediate grid heating."""
        await self.coordinator.api.force_reheat()
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Cancel the forced heat cycle."""
        await self.coordinator.api.cancel_grid_heating()
        await self.coordinator.async_refresh()
