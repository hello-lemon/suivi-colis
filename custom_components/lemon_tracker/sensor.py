"""Sensor platform for Lemon Tracker."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATUS_ICONS
from .coordinator import LemonTrackerCoordinator
from .models import Package

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lemon Tracker sensors from config entry."""
    coordinator: LemonTrackerCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Track which sensors exist
    tracked: set[str] = set()

    @callback
    def _async_add_new_sensors() -> None:
        """Add sensors for newly discovered packages."""
        new_entities: list[LemonTrackerSensor] = []

        for tracking_number, package in coordinator.store.active_packages.items():
            if tracking_number not in tracked:
                tracked.add(tracking_number)
                new_entities.append(
                    LemonTrackerSensor(coordinator, package, entry)
                )

        # Remove archived from tracking set
        active_numbers = set(coordinator.store.active_packages.keys())
        archived = tracked - active_numbers
        for number in archived:
            tracked.discard(number)

        if new_entities:
            async_add_entities(new_entities)

    # Add existing packages
    _async_add_new_sensors()

    # Listen for new packages on each update
    entry.async_on_unload(
        coordinator.async_add_listener(_async_add_new_sensors)
    )


class LemonTrackerSensor(CoordinatorEntity[LemonTrackerCoordinator], SensorEntity):
    """Sensor for a single tracked package."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LemonTrackerCoordinator,
        package: Package,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._tracking_number = package.tracking_number
        self._attr_unique_id = f"{DOMAIN}_{package.tracking_number}"
        self._attr_translation_key = "package"

    @property
    def _package(self) -> Package | None:
        """Get the current package data."""
        return self.coordinator.store.get_package(self._tracking_number)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._package is not None and not self._package.archived

    @property
    def name(self) -> str:
        """Return the display name."""
        pkg = self._package
        if pkg:
            return pkg.display_name
        return self._tracking_number

    @property
    def native_value(self) -> str | None:
        """Return the package status."""
        pkg = self._package
        return pkg.status if pkg else None

    @property
    def icon(self) -> str:
        """Return icon based on status."""
        pkg = self._package
        status = pkg.status if pkg else "unknown"
        return STATUS_ICONS.get(status, "mdi:package-variant")

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes."""
        pkg = self._package
        if not pkg:
            return {}

        attrs = {
            "tracking_number": pkg.tracking_number,
            "carrier": pkg.carrier,
            "friendly_name": pkg.friendly_name,
            "info_text": pkg.info_text,
            "location": pkg.location,
            "source": pkg.source,
            "added_at": pkg.added_at.isoformat() if pkg.added_at else None,
            "last_updated": pkg.last_updated.isoformat() if pkg.last_updated else None,
            "delivered_at": pkg.delivered_at.isoformat() if pkg.delivered_at else None,
            "events_count": len(pkg.events),
        }

        if pkg.last_event:
            attrs["last_event"] = pkg.last_event.description
            attrs["last_event_time"] = pkg.last_event.timestamp.isoformat()
            attrs["last_event_location"] = pkg.last_event.location

        return attrs

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when removed."""
        _LOGGER.debug("Removing sensor for %s", self._tracking_number)
