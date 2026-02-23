"""Persistent storage for Suivi de Colis packages."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION
from .models import Package

_LOGGER = logging.getLogger(__name__)


class SuiviColisStore:
    """Manage package persistence via HA .storage."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
        self._packages: dict[str, Package] = {}

    @property
    def packages(self) -> dict[str, Package]:
        """Return all packages keyed by tracking number."""
        return self._packages

    @property
    def active_packages(self) -> dict[str, Package]:
        """Return non-archived packages."""
        return {k: v for k, v in self._packages.items() if not v.archived}

    async def async_load(self) -> None:
        """Load packages from storage."""
        data = await self._store.async_load()
        if data and "packages" in data:
            for pkg_data in data["packages"]:
                try:
                    pkg = Package.from_dict(pkg_data)
                    self._packages[pkg.tracking_number] = pkg
                except (KeyError, ValueError) as err:
                    _LOGGER.warning("Skipping invalid package data: %s", err)
        _LOGGER.debug("Loaded %d packages from storage", len(self._packages))

    async def async_save(self) -> None:
        """Save packages to storage."""
        data = {
            "packages": [pkg.to_dict() for pkg in self._packages.values()]
        }
        await self._store.async_save(data)

    def add_package(self, package: Package) -> None:
        """Add a package (does not persist, call async_save after)."""
        self._packages[package.tracking_number] = package

    def remove_package(self, tracking_number: str) -> Package | None:
        """Remove a package (does not persist, call async_save after)."""
        return self._packages.pop(tracking_number, None)

    def get_package(self, tracking_number: str) -> Package | None:
        """Get a package by tracking number."""
        return self._packages.get(tracking_number)

    def has_package(self, tracking_number: str) -> bool:
        """Check if a tracking number is already tracked."""
        return tracking_number in self._packages
