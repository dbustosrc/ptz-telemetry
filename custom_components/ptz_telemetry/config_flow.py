"""Configure one PTZ camera without reusing another integration's credentials."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.selector import selector

from .const import CONF_BAICHUAN_PORT, CONF_CHANNEL, CONF_CONNECTION, DOMAIN
from .reader import ReolinkPositionReader


class PTZTelemetryConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            if not host:
                errors[CONF_HOST] = "invalid_host"
            else:
                reader = ReolinkPositionReader(
                    host, user_input[CONF_USERNAME], user_input[CONF_PASSWORD],
                    user_input[CONF_BAICHUAN_PORT], user_input[CONF_CONNECTION], user_input[CONF_CHANNEL],
                )
                try:
                    await reader.async_open()
                except Exception:
                    errors["base"] = "cannot_connect"
                finally:
                    try:
                        await reader.async_close()
                    except Exception:
                        pass
                if not errors:
                    await self.async_set_unique_id(f"{host.casefold()}:{user_input[CONF_BAICHUAN_PORT]}:{user_input[CONF_CHANNEL]}")
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=f"PTZ telemetry {host}", data={**user_input, CONF_HOST: host})
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_BAICHUAN_PORT, default=9000): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Required(CONF_CONNECTION, default="tcp"): vol.In(("tcp", "udp")),
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): selector({"text": {"type": "password"}}),
                vol.Required(CONF_CHANNEL, default=0): vol.All(vol.Coerce(int), vol.Range(min=0)),
            }),
            errors=errors,
        )
