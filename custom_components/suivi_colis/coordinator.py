"""Data update coordinator for Suivi de Colis."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from functools import partial

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api_17track import Api17TrackClient, Api17TrackError, Api17TrackRateLimited
from .carrier_detect import detect_carrier_from_number
from .const import (
    CONF_ARCHIVE_AFTER_DAYS,
    CONF_EMAIL_INTERVAL,
    CONF_IMAP_FOLDER,
    CONF_IMAP_PASSWORD,
    CONF_IMAP_PORT,
    CONF_IMAP_SERVER,
    CONF_IMAP_DEDICATED,
    CONF_IMAP_SSL,
    CONF_IMAP_USER,
    DEFAULT_ARCHIVE_AFTER_DAYS,
    DEFAULT_EMAIL_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .email_parser import ExtractedPackage
from .models import Package, PackageSource, PackageStatus
from .store import SuiviColisStore

_LOGGER = logging.getLogger(__name__)


class SuiviColisCoordinator(DataUpdateCoordinator[dict[str, Package]]):
    """Coordinate updates for all tracked packages."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: Api17TrackClient,
        store: SuiviColisStore,
        config: dict,
        options: dict,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_UPDATE_INTERVAL),
        )
        self.api_client = api_client
        self.store = store
        self.config = config
        self.options = options
        self._last_email_check: datetime | None = None

    @property
    def imap_configured(self) -> bool:
        """Return True if IMAP is configured."""
        return bool(self.config.get(CONF_IMAP_SERVER))

    @property
    def archive_after_days(self) -> int:
        """Return auto-archive delay in days."""
        return self.options.get(
            CONF_ARCHIVE_AFTER_DAYS, DEFAULT_ARCHIVE_AFTER_DAYS
        )

    @property
    def email_interval_minutes(self) -> int:
        """Return email check interval in minutes."""
        return self.options.get(CONF_EMAIL_INTERVAL, DEFAULT_EMAIL_INTERVAL)

    async def _async_update_data(self) -> dict[str, Package]:
        """Fetch latest data from 17track + emails."""
        # 1. Check emails if configured and interval elapsed
        if self.imap_configured and self._should_check_email():
            await self._check_emails()
            self._last_email_check = datetime.now()

        # 2. Update active packages via 17track
        await self._update_tracking()

        # 3. Auto-remove delivered
        await self._auto_remove_delivered()

        # 4. Save to storage
        await self.store.async_save()

        return self.store.active_packages

    async def _update_tracking(self) -> None:
        """Update all active packages via 17track."""
        active = {
            k: v
            for k, v in self.store.active_packages.items()
            if v.status != PackageStatus.DELIVERED or v.last_updated is None
        }

        if not active:
            return

        numbers = list(active.keys())
        try:
            results = await self.api_client.get_track_info(numbers)
        except Api17TrackRateLimited:
            _LOGGER.warning("17track rate limited, will retry next cycle")
            return
        except Api17TrackError as err:
            _LOGGER.error("17track API error: %s", err)
            return

        now = datetime.now()
        for number, data in results.items():
            pkg = self.store.get_package(number)
            if not pkg:
                continue

            old_status = pkg.status
            pkg.status = data["status"]
            pkg.info_text = data["info_text"]
            pkg.location = data["location"]
            pkg.events = data["events"]
            pkg.last_updated = now
            # Update carrier from 17track (always trust API over local detection)
            if data.get("carrier"):
                pkg.carrier = data["carrier"]

            if pkg.status == PackageStatus.DELIVERED and old_status != PackageStatus.DELIVERED:
                pkg.delivered_at = now
                _LOGGER.info("Package %s delivered!", pkg.display_name)

    async def _check_emails(self) -> None:
        """Check IMAP for new tracking numbers."""
        known = set(self.store.packages.keys())

        try:
            extracted: list[ExtractedPackage] = await self.hass.async_add_executor_job(
                partial(
                    _run_imap_fetch,
                    server=self.config[CONF_IMAP_SERVER],
                    port=self.config[CONF_IMAP_PORT],
                    user=self.config[CONF_IMAP_USER],
                    password=self.config[CONF_IMAP_PASSWORD],
                    folder=self.config.get(CONF_IMAP_FOLDER, "INBOX"),
                    ssl=self.config.get(CONF_IMAP_SSL, True),
                    dedicated=self.config.get(CONF_IMAP_DEDICATED, False),
                    known_numbers=known,
                )
            )
        except Exception as err:
            _LOGGER.error("Email check failed: %s", err)
            return

        for item in extracted:
            await self.add_package(
                tracking_number=item.tracking_number,
                carrier=item.carrier,
                friendly_name=item.friendly_name,
                source=PackageSource.EMAIL,
            )

    def _should_check_email(self) -> bool:
        """Check if enough time has passed for email check."""
        if self._last_email_check is None:
            return True
        elapsed = datetime.now() - self._last_email_check
        return elapsed >= timedelta(minutes=self.email_interval_minutes)

    async def _auto_remove_delivered(self) -> None:
        """Remove delivered packages after configured delay."""
        if self.archive_after_days <= 0:
            return

        cutoff = datetime.now() - timedelta(days=self.archive_after_days)
        to_remove: list[str] = []
        for pkg in list(self.store.active_packages.values()):
            if (
                pkg.status == PackageStatus.DELIVERED
                and pkg.delivered_at
                and pkg.delivered_at < cutoff
            ):
                to_remove.append(pkg.tracking_number)

        for number in to_remove:
            self.store.remove_package(number)
            try:
                await self.api_client.stop_tracking(number)
            except Api17TrackError as err:
                _LOGGER.warning("Failed to stop 17track for %s: %s", number, err)
            _LOGGER.info("Auto-removed delivered package %s", number)

    async def add_package(
        self,
        tracking_number: str,
        carrier: str = "",
        friendly_name: str = "",
        source: str = PackageSource.MANUAL,
    ) -> bool:
        """Add a new package and register with 17track."""
        tracking_number = tracking_number.strip().upper()

        if self.store.has_package(tracking_number):
            _LOGGER.warning("Package %s already tracked", tracking_number)
            return False

        # Auto-detect carrier if not specified
        if not carrier or carrier == "unknown":
            carrier = detect_carrier_from_number(tracking_number)

        # Register with 17track
        try:
            registered = await self.api_client.register_package(
                tracking_number, carrier
            )
            if not registered:
                _LOGGER.error("Failed to register %s with 17track", tracking_number)
                return False
        except Api17TrackError as err:
            _LOGGER.error("17track register error for %s: %s", tracking_number, err)
            return False

        pkg = Package(
            tracking_number=tracking_number,
            carrier=carrier,
            friendly_name=friendly_name,
            source=source,
        )
        self.store.add_package(pkg)
        await self.store.async_save()

        # Trigger an immediate refresh
        await self.async_request_refresh()
        return True

    async def remove_package(self, tracking_number: str) -> bool:
        """Remove a package and stop tracking on 17track."""
        tracking_number = tracking_number.strip().upper()

        pkg = self.store.remove_package(tracking_number)
        if not pkg:
            return False

        try:
            await self.api_client.stop_tracking(tracking_number)
        except Api17TrackError as err:
            _LOGGER.warning("Failed to stop 17track for %s: %s", tracking_number, err)

        await self.store.async_save()
        await self.async_request_refresh()
        return True

    async def archive_delivered(self) -> int:
        """Archive all delivered packages. Returns count."""
        count = 0
        for pkg in list(self.store.active_packages.values()):
            if pkg.status == PackageStatus.DELIVERED:
                pkg.archived = True
                count += 1
        if count:
            await self.store.async_save()
            await self.async_request_refresh()
        return count


def _run_imap_fetch(
    server: str,
    port: int,
    user: str,
    password: str,
    folder: str,
    ssl: bool,
    dedicated: bool,
    known_numbers: set[str],
) -> list[ExtractedPackage]:
    """Synchronous wrapper for IMAP fetch (runs in executor)."""
    from imap_tools import AND, MailBox
    from datetime import datetime as dt, timedelta as td
    import re

    from .carrier_detect import detect_carrier_from_email, detect_carrier_from_number
    from .const import TRACKING_NUMBER_PATTERNS

    results: list[ExtractedPackage] = []
    since_date = (dt.now() - td(hours=24)).date()

    try:
        with MailBox(server, port, starttls=not ssl) as mailbox:
            mailbox.login(user, password, initial_folder=folder)

            for msg in mailbox.fetch(AND(date_gte=since_date), limit=50, reverse=True):
                sender = msg.from_ or ""
                subject = msg.subject or ""

                carrier_from_email = detect_carrier_from_email(sender)
                # Personal mailbox: only process known carrier senders
                if not dedicated and carrier_from_email == "unknown":
                    continue

                # Extract tracking numbers — subject first, then body
                text = f"{subject}\n{msg.text or ''}\n{msg.html or ''}"
                found: set[str] = set()
                for pattern in TRACKING_NUMBER_PATTERNS:
                    for match in re.finditer(pattern, text, re.IGNORECASE):
                        number = (
                            match.group(1).upper()
                            if match.lastindex
                            else match.group(0).upper()
                        )
                        if len(number) >= 10:
                            found.add(number)

                name = subject.strip()[:60]

                for number in found:
                    if number not in known_numbers:
                        # Determine carrier: from email sender, or from tracking number format
                        carrier = carrier_from_email
                        if carrier == "unknown":
                            carrier = detect_carrier_from_number(number)
                        results.append(
                            ExtractedPackage(
                                tracking_number=number,
                                carrier=carrier,
                                friendly_name=name or carrier.capitalize(),
                                source_email=sender,
                            )
                        )
                        known_numbers.add(number)

                # Mark as seen in dedicated mode
                if dedicated and found:
                    mailbox.flag(msg.uid, [r'\Seen'], True)

    except Exception as err:
        _LOGGER.error("IMAP fetch error: %s", err)

    return results
