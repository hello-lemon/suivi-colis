"""Suivi de Colis — Package tracking integration for Home Assistant."""

from __future__ import annotations

import logging
from pathlib import Path

import aiohttp
import voluptuous as vol
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .api_17track import Api17TrackClient
from .const import DOMAIN, CONF_API_KEY
from .coordinator import SuiviColisCoordinator
from .store import SuiviColisStore

_LOGGER = logging.getLogger(__name__)

CARD_JS_URL = "/suivi_colis/suivi-colis-card.js"
CARD_JS_VERSION = "1.0.1"

PLATFORMS = ["sensor"]

SERVICE_ADD_PACKAGE = "add_package"
SERVICE_REMOVE_PACKAGE = "remove_package"
SERVICE_REFRESH = "refresh"
SERVICE_ARCHIVE_DELIVERED = "archive_delivered"

ADD_PACKAGE_SCHEMA = vol.Schema(
    {
        vol.Required("tracking_number"): cv.string,
        vol.Optional("friendly_name", default=""): cv.string,
        vol.Optional("carrier", default=""): cv.string,
    }
)

REMOVE_PACKAGE_SCHEMA = vol.Schema(
    {
        vol.Required("tracking_number"): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Suivi de Colis — register static files and Lovelace resource."""
    # Serve www/ folder at /suivi_colis/
    www_path = Path(__file__).parent / "www"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_JS_URL, str(www_path / "suivi-colis-card.js"), cache_headers=False)]
    )

    # Register Lovelace resource after HA is fully started (resources not ready earlier)
    url = f"{CARD_JS_URL}?v={CARD_JS_VERSION}"

    async def _register_on_start(event: Event) -> None:
        await _async_register_lovelace_resource(hass, url)

    if hass.is_running:
        await _async_register_lovelace_resource(hass, url)
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _register_on_start)

    return True


async def _async_register_lovelace_resource(hass: HomeAssistant, url: str) -> None:
    """Register the card JS as a Lovelace resource if not already present."""
    try:
        lovelace_data = hass.data.get("lovelace")
        if lovelace_data is None:
            _LOGGER.warning("Lovelace not available, add resource manually: %s", url)
            return

        # lovelace_data can be a dict or object with resources attribute
        resources = None
        if isinstance(lovelace_data, dict):
            resources = lovelace_data.get("resources")
        elif hasattr(lovelace_data, "resources"):
            resources = lovelace_data.resources

        if resources is None:
            _LOGGER.warning("Lovelace resources not available (YAML mode?), add manually: %s", url)
            return

        # Clean up old lemon_tracker resources and check if already registered
        found = False
        for item in resources.async_items():
            item_url = item.get("url", "")
            # Remove legacy lemon_tracker resource
            if "/lemon_tracker/" in item_url or "lemon-tracker-card" in item_url:
                await resources.async_delete_item(item["id"])
                _LOGGER.info("Removed legacy lemon_tracker resource: %s", item_url)
                continue
            # Check if current resource already exists
            if item_url.startswith(CARD_JS_URL):
                if item_url != url:
                    await resources.async_update_item(
                        item["id"], {"url": url}
                    )
                    _LOGGER.info("Updated Suivi de Colis card resource to %s", url)
                found = True

        if not found:
            await resources.async_create_item({"res_type": "module", "url": url})
            _LOGGER.info("Registered Suivi de Colis card resource: %s", url)
    except Exception as err:
        _LOGGER.error("Could not auto-register Lovelace resource: %s — add manually: %s", err, url)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Suivi de Colis from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create HTTP session and API client
    session = aiohttp.ClientSession()
    api_client = Api17TrackClient(session, entry.data[CONF_API_KEY])

    # Load stored packages
    store = SuiviColisStore(hass)
    await store.async_load()

    # Create coordinator
    coordinator = SuiviColisCoordinator(
        hass,
        api_client=api_client,
        store=store,
        config=dict(entry.data),
        options=dict(entry.options),
    )

    # Listen for option updates
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    # Store references
    hass.data[DOMAIN][entry.entry_id] = coordinator
    hass.data[DOMAIN]["session"] = session

    # Initial refresh
    await coordinator.async_config_entry_first_refresh()

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    _register_services(hass, coordinator)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        session = hass.data[DOMAIN].pop("session", None)
        if session:
            await session.close()

        # Remove services if no entries left
        remaining = [
            e for e in hass.config_entries.async_entries(DOMAIN)
            if e.entry_id != entry.entry_id
        ]
        if not remaining:
            for service in [
                SERVICE_ADD_PACKAGE,
                SERVICE_REMOVE_PACKAGE,
                SERVICE_REFRESH,
                SERVICE_ARCHIVE_DELIVERED,
            ]:
                hass.services.async_remove(DOMAIN, service)

    return unload_ok


async def _async_options_updated(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options update."""
    coordinator: SuiviColisCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.options = dict(entry.options)


def _register_services(
    hass: HomeAssistant, coordinator: SuiviColisCoordinator
) -> None:
    """Register integration services."""

    async def handle_add_package(call: ServiceCall) -> None:
        tracking_number = call.data["tracking_number"]
        friendly_name = call.data.get("friendly_name", "")
        carrier = call.data.get("carrier", "")
        result = await coordinator.add_package(
            tracking_number=tracking_number,
            carrier=carrier,
            friendly_name=friendly_name,
        )
        if result:
            _LOGGER.info("Added package %s", tracking_number)
        else:
            _LOGGER.warning("Failed to add package %s", tracking_number)

    async def handle_remove_package(call: ServiceCall) -> None:
        tracking_number = call.data["tracking_number"]
        result = await coordinator.remove_package(tracking_number)
        if result:
            _LOGGER.info("Removed package %s", tracking_number)
        else:
            _LOGGER.warning("Package %s not found", tracking_number)

    async def handle_refresh(call: ServiceCall) -> None:
        await coordinator.async_request_refresh()

    async def handle_archive_delivered(call: ServiceCall) -> None:
        count = await coordinator.archive_delivered()
        _LOGGER.info("Archived %d delivered packages", count)

    if not hass.services.has_service(DOMAIN, SERVICE_ADD_PACKAGE):
        hass.services.async_register(
            DOMAIN, SERVICE_ADD_PACKAGE, handle_add_package, schema=ADD_PACKAGE_SCHEMA
        )
        hass.services.async_register(
            DOMAIN, SERVICE_REMOVE_PACKAGE, handle_remove_package, schema=REMOVE_PACKAGE_SCHEMA
        )
        hass.services.async_register(
            DOMAIN, SERVICE_REFRESH, handle_refresh
        )
        hass.services.async_register(
            DOMAIN, SERVICE_ARCHIVE_DELIVERED, handle_archive_delivered
        )
