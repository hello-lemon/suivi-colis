"""Data models for Suivi de Colis."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class PackageStatus(StrEnum):
    """Package tracking status."""

    UNKNOWN = "unknown"
    INFO_RECEIVED = "info_received"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    AVAILABLE_FOR_PICKUP = "available_for_pickup"
    DELIVERED = "delivered"
    DELIVERY_FAILURE = "delivery_failure"
    EXCEPTION = "exception"
    EXPIRED = "expired"
    NOT_FOUND = "not_found"


class PackageSource(StrEnum):
    """How the package was added."""

    MANUAL = "manual"
    EMAIL = "email"


class Carrier(StrEnum):
    """Supported carriers."""

    CHRONOPOST = "chronopost"
    COLISSIMO = "colissimo"
    LAPOSTE = "laposte"
    DHL = "dhl"
    UPS = "ups"
    AMAZON = "amazon"
    CAINIAO = "cainiao"
    UNKNOWN = "unknown"


@dataclass
class TrackingEvent:
    """A single tracking event."""

    timestamp: datetime
    description: str
    location: str = ""

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "description": self.description,
            "location": self.location,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TrackingEvent:
        """Deserialize from dict."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            description=data["description"],
            location=data.get("location", ""),
        )


@dataclass
class Package:
    """A tracked package."""

    tracking_number: str
    carrier: str = Carrier.UNKNOWN
    friendly_name: str = ""
    status: str = PackageStatus.UNKNOWN
    info_text: str = ""
    location: str = ""
    events: list[TrackingEvent] = field(default_factory=list)
    added_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime | None = None
    delivered_at: datetime | None = None
    source: str = PackageSource.MANUAL
    archived: bool = False

    @property
    def display_name(self) -> str:
        """Return friendly name or tracking number."""
        return self.friendly_name or self.tracking_number

    @property
    def last_event(self) -> TrackingEvent | None:
        """Return the most recent event."""
        return self.events[0] if self.events else None

    def to_dict(self) -> dict:
        """Serialize to dict for storage."""
        return {
            "tracking_number": self.tracking_number,
            "carrier": self.carrier,
            "friendly_name": self.friendly_name,
            "status": self.status,
            "info_text": self.info_text,
            "location": self.location,
            "events": [e.to_dict() for e in self.events],
            "added_at": self.added_at.isoformat(),
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "source": self.source,
            "archived": self.archived,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Package:
        """Deserialize from dict."""
        return cls(
            tracking_number=data["tracking_number"],
            carrier=data.get("carrier", Carrier.UNKNOWN),
            friendly_name=data.get("friendly_name", ""),
            status=data.get("status", PackageStatus.UNKNOWN),
            info_text=data.get("info_text", ""),
            location=data.get("location", ""),
            events=[TrackingEvent.from_dict(e) for e in data.get("events", [])],
            added_at=datetime.fromisoformat(data["added_at"]) if data.get("added_at") else datetime.now(),
            last_updated=datetime.fromisoformat(data["last_updated"]) if data.get("last_updated") else None,
            delivered_at=datetime.fromisoformat(data["delivered_at"]) if data.get("delivered_at") else None,
            source=data.get("source", PackageSource.MANUAL),
            archived=data.get("archived", False),
        )
