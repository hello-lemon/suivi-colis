"""Carrier detection from tracking numbers and email senders."""

from __future__ import annotations

import re

from .const import (
    CARRIER_REGEX,
    EMAIL_CARRIER_MAP,
    EMAIL_DOMAIN_CARRIER_MAP,
)
from .models import Carrier

# Compiled regex for email extraction
EMAIL_PATTERN = re.compile(r"<([^>]+)>")


def detect_carrier_from_number(tracking_number: str) -> str:
    """Detect carrier from tracking number using regex patterns."""
    number = tracking_number.strip().upper()

    # Check each carrier's patterns
    # Order matters: more specific patterns first
    for carrier in ["ups", "amazon", "cainiao", "colissimo", "chronopost", "dhl"]:
        for pattern in CARRIER_REGEX.get(carrier, []):
            if pattern.match(number):
                return carrier

    return Carrier.UNKNOWN


def detect_carrier_from_email(sender: str) -> str:
    """Detect carrier from email sender address."""
    sender = sender.strip().lower()

    # Extract email from "Name <email>" format
    match = EMAIL_PATTERN.search(sender)
    if match:
        sender = match.group(1).lower()

    # Exact match
    if sender in EMAIL_CARRIER_MAP:
        return EMAIL_CARRIER_MAP[sender]

    # Domain match
    domain = sender.split("@")[-1] if "@" in sender else ""
    for email_domain, carrier in EMAIL_DOMAIN_CARRIER_MAP.items():
        if domain == email_domain or domain.endswith(f".{email_domain}"):
            return carrier

    return Carrier.UNKNOWN
