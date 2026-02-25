"""IMAP email parser for tracking number extraction."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime as dt, timedelta as td

from .carrier_detect import detect_carrier_from_email, detect_carrier_from_number
from .const import TRACKING_NUMBER_PATTERNS

_LOGGER = logging.getLogger(__name__)


@dataclass
class ExtractedPackage:
    """A tracking number extracted from an email."""

    tracking_number: str
    carrier: str
    friendly_name: str
    source_email: str


def check_imap_connection(
    server: str, port: int, user: str, password: str, ssl: bool = True
) -> bool:
    """Test IMAP connection. Runs in executor."""
    from imap_tools import MailBox

    try:
        with MailBox(server, port, starttls=not ssl) as mailbox:
            mailbox.login(user, password)
            return True
    except Exception as err:
        _LOGGER.error("IMAP connection test failed: %s", err)
        return False


def run_imap_fetch(
    server: str,
    port: int,
    user: str,
    password: str,
    folder: str,
    ssl: bool,
    dedicated: bool,
    known_numbers: set[str],
) -> list[ExtractedPackage]:
    """Fetch emails and extract tracking numbers. Runs in executor."""
    from imap_tools import AND, MailBox

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

                # Extract tracking numbers — limit to 50KB to avoid performance issues
                text = f"{subject}\n{msg.text or ''}\n{msg.html or ''}"[:50000]
                found: set[str] = set()
                for pattern in TRACKING_NUMBER_PATTERNS:
                    for match in pattern.finditer(text):
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
