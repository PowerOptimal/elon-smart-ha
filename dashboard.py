"""Automatic Lovelace dashboard creation for Elon Water Heater."""

import logging
import uuid
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

_DASHBOARDS_STORE_KEY = "lovelace_dashboards"
_STORE_VERSION = 1


def _entity_id(platform: str, serial: str, suffix: str) -> str:
    """Build the entity ID HA will assign given our unique_id naming."""
    # With _attr_has_entity_name=True, device name is "Elon {serial}" and
    # entity name is e.g. "Water Temperature", so HA slugifies the combo.
    device_slug = slugify(f"elon {serial}")
    return f"{platform}.{device_slug}_{suffix}"


def _build_dashboard_config(serial: str) -> dict:
    """Return the lovelace config dict with real entity IDs."""
    water_temp   = _entity_id("sensor", serial, "water_temperature")
    ambient_temp = _entity_id("sensor", serial, "ambient_temperature")
    power_source = _entity_id("sensor", serial, "power_source")
    heating_state = _entity_id("sensor", serial, "heating_state")
    ac_current   = _entity_id("sensor", serial, "ac_current")
    grid_heat    = _entity_id("switch", serial, "grid_heating")

    return {
        "title": f"Elon {serial}",
        "views": [
            {
                "title": "Water Heater",
                "path": "overview",
                "icon": "mdi:water-boiler",
                "cards": [
                    {
                        "type": "gauge",
                        "entity": water_temp,
                        "name": "Water Temperature",
                        "min": 0,
                        "max": 80,
                        "needle": True,
                        "severity": {
                            "green": 55,
                            "yellow": 40,
                            "red": 0,
                        },
                    },
                    {
                        "type": "tile",
                        "entity": grid_heat,
                        "name": "Heat Now (Grid)",
                        "color": "deep-orange",
                        "icon_tap_action": {"action": "toggle"},
                    },
                    {
                        "type": "entities",
                        "title": "Status",
                        "show_header_toggle": False,
                        "entities": [
                            {"entity": heating_state, "name": "Heating State"},
                            {"entity": power_source,  "name": "Power Source"},
                            {"entity": ac_current,    "name": "AC Current"},
                            {"entity": ambient_temp,  "name": "Ambient Temp"},
                        ],
                    },
                ],
            }
        ],
    }


async def async_setup_dashboard(hass: HomeAssistant, serial: str) -> None:
    """Create the Elon dashboard in Lovelace storage if not already present.

    Safe to call on every startup — skips creation if the dashboard already
    exists so user edits are not overwritten.
    """
    url_path = slugify(f"elon {serial}").replace("_", "-")
    dashboard_store_key = f"lovelace.{url_path}"

    # ------------------------------------------------------------------
    # 1. Register the dashboard in the dashboards collection
    # ------------------------------------------------------------------
    dashboards_store = Store(
        hass, _STORE_VERSION, _DASHBOARDS_STORE_KEY
    )
    # HA's StorageCollection stores items under the key "items"
    dashboards_data = await dashboards_store.async_load() or {"items": []}

    existing_paths = {d.get("url_path") for d in dashboards_data.get("items", [])}

    if url_path not in existing_paths:
        dashboards_data.setdefault("items", []).append(
            {
                "icon": "mdi:water-boiler",
                "id": uuid.uuid4().hex,
                "mode": "storage",
                "require_admin": False,
                "show_in_sidebar": True,
                "title": f"Elon {serial}",
                "url_path": url_path,
            }
        )
        await dashboards_store.async_save(dashboards_data)
        _LOGGER.info("Elon: registered Lovelace dashboard '%s'", url_path)

    # ------------------------------------------------------------------
    # 2. Write the dashboard content (only if it doesn't exist yet)
    # ------------------------------------------------------------------
    content_store = Store(
        hass, _STORE_VERSION, dashboard_store_key
    )
    if not await content_store.async_load():
        await content_store.async_save({"config": _build_dashboard_config(serial)})
        _LOGGER.info("Elon: created Lovelace dashboard content for '%s'", url_path)
