"""IMAP email parser for tracking number extraction."""

from __future__ import annotations

import logging
from dataclasses import dataclass

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
    from imap_tools import MailBox, MailBoxTls

    try:
        box_class = MailBox if ssl else MailBoxTls
        with box_class(server, port) as mailbox:
            mailbox.login(user, password)
            return True
    except Exception as err:
        _LOGGER.error("IMAP connection test failed: %s", err)
        return False
