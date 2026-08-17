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

"""Shared entity base for the Elon Water Heater integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ElonData, ElonDataUpdateCoordinator


class ElonEntity(CoordinatorEntity[ElonDataUpdateCoordinator]):
    """Base for every Elon entity.

    Deriving from :class:`CoordinatorEntity` gives availability tied to
    ``last_update_success`` and listener registration that is torn down on
    unload.  The previous hand-rolled base classes tied availability to
    "we have ever received data", which meant a device that lost power stayed
    online in the UI forever, and they discarded the unsubscribe callback so
    listeners accumulated on every reload.
    """

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: ElonDataUpdateCoordinator, unique_id_suffix: str
    ) -> None:
        """Initialise the entity.

        Args:
            coordinator: The shared data coordinator.
            unique_id_suffix: Stable per-entity suffix.  These must not change
                between releases or users lose history and automations.
        """
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_number}_{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.serial_number)},
            name=f"Elon {coordinator.serial_number}",
            manufacturer="Elon",
            model="Smart Water Heater",
            serial_number=coordinator.serial_number,
        )

    @property
    def elon_data(self) -> ElonData | None:
        """The most recent device snapshot, if any."""
        return self.coordinator.data
