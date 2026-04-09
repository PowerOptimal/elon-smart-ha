"""Elon Water Heater integration for Home Assistant."""

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import ElonApiClient
from .coordinator import ElonDataUpdateCoordinator
from .const import DOMAIN

PLATFORMS = ["sensor", "button"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration via YAML (optional legacy method)."""
    domain_config = config.get(DOMAIN)

    if domain_config:
        serial_number = domain_config.get("serial_number")
        if serial_number:
            # Create a minimal config entry for YAML setup
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": "yaml"},
                    data={"serial_number": serial_number},
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    serial_number = entry.data["serial_number"]

    # Create aiohttp session with SSL disabled (device has no HTTPS)
    connector = aiohttp.TCPConnector(ssl=False)
    session = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=10),
        connector=connector,
    )

    try:
        # Create API client
        api = ElonApiClient(serial_number, session)

        # Create coordinator
        coordinator = ElonDataUpdateCoordinator(hass, api, serial_number, entry)

        # Initial data fetch
        await coordinator.async_config_entry_first_refresh()

        # Store coordinator
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

        # Forward to platforms
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        return True

    except Exception:
        await session.close()
        raise


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Remove coordinator
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok