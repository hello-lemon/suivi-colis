"""IMAP email parser for tracking number extraction."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from .carrier_detect import detect_carrier_from_email
from .const import TRACKING_NUMBER_PATTERNS

_LOGGER = logging.getLogger(__name__)


@dataclass
class ExtractedPackage:
    """A tracking number extracted from an email."""

    tracking_number: str
    carrier: str
    friendly_name: str
    source_email: str


async def check_imap_connection(
    server: str, port: int, user: str, password: str, ssl: bool = True
) -> bool:
    """Test IMAP connection. Runs in executor."""
    from imap_tools import MailBox, MailBoxTls

    try:
        box_class = MailBox if ssl else MailBoxTls
        with box_class(server, port) as mailbox:
            mailbox.login(user, password)
            return True
    except Exception as err:
        _LOGGER.error("IMAP connection test failed: %s", err)
        return False


async def fetch_tracking_emails(
    server: str,
    port: int,
    user: str,
    password: str,
    folder: str = "INBOX",
    ssl: bool = True,
    since_hours: int = 24,
    known_numbers: set[str] | None = None,
) -> list[ExtractedPackage]:
    """Fetch and parse emails for tracking numbers. Runs in executor."""
    from imap_tools import AND, MailBox, MailBoxTls

    if known_numbers is None:
        known_numbers = set()

    results: list[ExtractedPackage] = []
    since_date = (datetime.now() - timedelta(hours=since_hours)).date()

    try:
        box_class = MailBox if ssl else MailBoxTls
        with box_class(server, port) as mailbox:
            mailbox.login(user, password, initial_folder=folder)

            for msg in mailbox.fetch(AND(date_gte=since_date), limit=50, reverse=True):
                sender = msg.from_ or ""
                carrier = detect_carrier_from_email(sender)
                if carrier == "unknown":
                    continue

                # Search in subject + body
                text = f"{msg.subject or ''}\n{msg.text or ''}\n{msg.html or ''}"
                numbers = _extract_tracking_numbers(text)

                subject = msg.subject or ""
                for number in numbers:
                    if number in known_numbers:
                        continue
                    results.append(
                        ExtractedPackage(
                            tracking_number=number,
                            carrier=carrier,
                            friendly_name=_build_friendly_name(subject, carrier),
                            source_email=sender,
                        )
                    )
                    known_numbers.add(number)

    except Exception as err:
        _LOGGER.error("IMAP fetch error: %s", err)

    return results


def _extract_tracking_numbers(text: str) -> list[str]:
    """Extract tracking numbers from text using regex patterns."""
    found: list[str] = []
    seen: set[str] = set()

    for pattern in TRACKING_NUMBER_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            number = match.group(1).upper() if match.lastindex else match.group(0).upper()
            if number not in seen and len(number) >= 10:
                seen.add(number)
                found.append(number)

    return found


def _build_friendly_name(subject: str, carrier: str) -> str:
    """Build a friendly name from email subject."""
    # Clean up common prefixes
    name = subject.strip()
    for prefix in ["Re:", "Fwd:", "TR:", "RE:", "FWD:"]:
        if name.startswith(prefix):
            name = name[len(prefix):].strip()

    # Truncate
    if len(name) > 60:
        name = name[:57] + "..."

    return name or carrier.capitalize()
