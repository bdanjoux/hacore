"""The DSN integration."""
from __future__ import annotations

import datetime
from datetime import timedelta
import logging

import aiohttp
import xmltodict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


class DsnApi:
    @classmethod
    async def fetch_config(cls, *args, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://eyes.nasa.gov/dsn/config.xml") as response:
                xml = await response.text()
                ret = xmltodict.parse(xml)
                return ret

    @classmethod
    async def fetch_data(cls, *args, **kwargs):
        async with aiohttp.ClientSession() as session:
            seconds = datetime.datetime.now().timestamp()
            query_string = (
                "https://eyes.nasa.gov/dsn/data/dsn.xml" + "?r=" + str(int(seconds / 5))
            )
            async with session.get(query_string) as response:
                xml = await response.text()
                ret = xmltodict.parse(xml)
                return ret


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DSN from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=DsnApi.fetch_data,
        update_interval=timedelta(seconds=60),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN] = coordinator

    entry.async_on_unload(entry.add_update_listener(update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
