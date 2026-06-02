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

"""Automatic Lovelace dashboard creation for Elon Water Heater."""

import logging
from homeassistant.core import HomeAssistant, Event
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _lookup_entity_ids(hass: HomeAssistant, serial: str) -> dict[str, str]:
    """Return actual entity IDs from the HA entity registry by unique_id."""
    registry = er.async_get(hass)

    wanted = {
        "water_temperature":   ("sensor", f"{serial}_water_temperature"),
        "ambient_temperature": ("sensor", f"{serial}_ambient_temperature"),
        "power_source":        ("sensor", f"{serial}_power_source"),
        "heating_state":       ("sensor", f"{serial}_heating_state"),
        "ac_current":          ("sensor", f"{serial}_ac_current"),
        "grid_heat":           ("water_heater", f"{serial}_water_heater"),
    }

    result = {}
    for name, (platform, unique_id) in wanted.items():
        entity_id = registry.async_get_entity_id(platform, DOMAIN, unique_id)
        if entity_id:
            result[name] = entity_id
        else:
            device_slug = slugify(f"elon {serial}")
            result[name] = f"{platform}.{device_slug}_{name}"
            _LOGGER.warning(
                "Dashboard: entity not found for unique_id=%s, guessing %s",
                unique_id, result[name],
            )

    return result


def _build_dashboard_config(serial: str, entity_ids: dict[str, str]) -> dict:
    """Return the lovelace config dict."""
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
                        "entity": entity_ids["water_temperature"],
                        "name": "Water Temperature",
                        "min": 0,
                        "max": 80,
                        "needle": True,
                        "severity": {"green": 55, "yellow": 40, "red": 0},
                    },
                    {
                        "type": "tile",
                        "entity": entity_ids["grid_heat"],
                        "name": "Heat Now (Grid)",
                        "color": "deep-orange",
                        "icon_tap_action": {"action": "toggle"},
                    },
                    {
                        "type": "entities",
                        "title": "Status",
                        "show_header_toggle": False,
                        "entities": [
                            {"entity": entity_ids["heating_state"],       "name": "Heating State"},
                            {"entity": entity_ids["power_source"],        "name": "Power Source"},
                            {"entity": entity_ids["ac_current"],          "name": "AC Current"},
                            {"entity": entity_ids["ambient_temperature"], "name": "Ambient Temp"},
                        ],
                    },
                ],
            }
        ],
    }


async def _create_dashboard(hass: HomeAssistant, serial: str) -> None:
    """Create the dashboard using HA's lovelace runtime APIs.

    Called after EVENT_HOMEASSISTANT_STARTED so the lovelace DashboardsCollection
    and all entity registrations are fully initialised.
    """
    from homeassistant.components.lovelace import DOMAIN as LOVELACE_DOMAIN

    url_path = slugify(f"elon {serial}").replace("_", "-")
    lovelace = hass.data.get(LOVELACE_DOMAIN)

    if lovelace is None:
        _LOGGER.error("Elon dashboard: lovelace component not found in hass.data")
        return

    # LovelaceData is a dataclass — access attributes, not dict keys
    collection = getattr(lovelace, "dashboards_collection", None)
    dashboards: dict = getattr(lovelace, "dashboards", {})

    # ------------------------------------------------------------------
    # 1. Register dashboard if not already present
    # ------------------------------------------------------------------
    if url_path not in dashboards:
        if collection is None:
            _LOGGER.error("Elon: dashboards_collection attribute missing from LovelaceData")
            return
        try:
            await collection.async_create_item({
                "icon": "mdi:water-boiler",
                "mode": "storage",
                "require_admin": False,
                "show_in_sidebar": True,
                "title": f"Elon {serial}",
                "url_path": url_path,
            })
            _LOGGER.info("Elon: registered dashboard '%s' via collection API", url_path)
        except Exception:
            _LOGGER.exception("Elon: failed to register dashboard via collection")
            return

    # ------------------------------------------------------------------
    # 2. Write dashboard content via the LovelaceStorage instance
    # ------------------------------------------------------------------
    dashboards = getattr(lovelace, "dashboards", {})
    dashboard_instance = dashboards.get(url_path)

    if dashboard_instance is None:
        _LOGGER.warning("Elon: dashboard instance for '%s' not found after registration", url_path)
        return

    entity_ids = _lookup_entity_ids(hass, serial)
    config = _build_dashboard_config(serial, entity_ids)

    if hasattr(dashboard_instance, "async_save"):
        await dashboard_instance.async_save(config)
        _LOGGER.info("Elon: wrote dashboard content for '%s', entity_ids=%s", url_path, entity_ids)
    else:
        _LOGGER.warning(
            "Elon: dashboard instance for '%s' has no async_save (type=%s)",
            url_path, type(dashboard_instance),
        )


def async_schedule_dashboard_setup(hass: HomeAssistant, serial: str) -> None:
    """Schedule dashboard creation to run after HA has fully started."""

    async def _on_started(event: Event) -> None:
        await _create_dashboard(hass, serial)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_started)
