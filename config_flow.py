"""Config flow for Elon Water Heater."""

import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN

DATA_SCHEMA = vol.Schema({
    vol.Required("serial_number"): str,
})


class ElonWaterHeaterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elon Water Heater."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            serial = user_input.get("serial_number", "").strip()

            if not serial:
                errors["serial_number"] = "required"
            elif not serial.replace("-", "").replace("_", "").isalnum():
                errors["serial_number"] = "invalid"

            if not errors:
                # Store the serial and create the entry
                return self.async_create_entry(
                    title=f"Elon Water Heater ({serial})",
                    data={"serial_number": serial},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_yaml(self, user_input=None):
        """Handle YAML configuration."""
        return await self.async_step_user(user_input)