"""17track API v2.2 client."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import aiohttp

from .const import (
    API_17TRACK_GETQUOTA,
    API_17TRACK_GETTRACKINFO,
    API_17TRACK_REGISTER,
    API_17TRACK_STOPTRACK,
    CARRIER_17TRACK_CODE,
    STATUS_17TRACK_MAP,
)
from .models import Package, PackageStatus, TrackingEvent

_LOGGER = logging.getLogger(__name__)

# Reverse mapping: 17track carrier code -> our carrier name
CARRIER_17TRACK_REVERSE = {
    4031: "chronopost",
    4036: "colissimo",
    100003: "dhl",
    100002: "ups",
    100143: "amazon",
    190271: "cainiao",
    # Common La Poste variants
    4015: "laposte",
    4016: "colissimo",
}


def _normalize_carrier_name(name: str) -> str:
    """Normalize a carrier name from 17track to our format."""
    name_lower = name.lower()
    for keyword, carrier in {
        "chronopost": "chronopost",
        "colissimo": "colissimo",
        "la poste": "colissimo",
        "laposte": "colissimo",
        "dhl": "dhl",
        "ups": "ups",
        "amazon": "amazon",
        "cainiao": "cainiao",
        "aliexpress": "cainiao",
        "yanwen": "cainiao",
    }.items():
        if keyword in name_lower:
            return carrier
    return name_lower


class Api17TrackError(Exception):
    """Base exception for 17track API errors."""


class Api17TrackRateLimited(Api17TrackError):
    """Rate limited by 17track."""


class Api17TrackQuotaExceeded(Api17TrackError):
    """Monthly quota exceeded."""


class Api17TrackClient:
    """Client for 17track API v2.2."""

    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        """Initialize."""
        self._session = session
        self._api_key = api_key
        self._last_request_time: float = 0
        self._rate_lock = asyncio.Lock()

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "17token": self._api_key,
            "Content-Type": "application/json",
        }

    async def _rate_limit(self) -> None:
        """Enforce 3 req/sec rate limit."""
        async with self._rate_lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < 0.34:  # ~3 req/sec
                await asyncio.sleep(0.34 - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()

    async def _request(self, url: str, data: dict[str, Any]) -> dict[str, Any]:
        """Make a rate-limited request to 17track API."""
        await self._rate_limit()

        try:
            async with self._session.post(
                url, json=data, headers=self._headers
            ) as resp:
                if resp.status == 429:
                    raise Api17TrackRateLimited("Rate limited by 17track")
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as err:
            raise Api17TrackError(f"Request failed: {err}") from err

    async def validate_api_key(self) -> dict[str, Any]:
        """Validate API key by checking quota. Returns quota info."""
        result = await self._request(API_17TRACK_GETQUOTA, {})
        if result.get("code") != 0:
            raise Api17TrackError(
                f"Invalid API key: {result.get('message', 'Unknown error')}"
            )
        return result.get("data", {})

    async def register_package(self, tracking_number: str, carrier: str = "") -> bool:
        """Register a tracking number. Consumes 1 quota."""
        item: dict[str, Any] = {"number": tracking_number}
        carrier_code = CARRIER_17TRACK_CODE.get(carrier)
        if carrier_code:
            item["carrier"] = carrier_code

        result = await self._request(API_17TRACK_REGISTER, [item])
        code = result.get("code", -1)

        if code == 0:
            accepted = result.get("data", {}).get("accepted", [])
            rejected = result.get("data", {}).get("rejected", [])
            if accepted:
                _LOGGER.debug("Registered %s on 17track", tracking_number)
                return True
            if rejected:
                error = rejected[0].get("error", {})
                error_code = error.get("code", -1)
                # -18019901 = already registered, that's fine
                if error_code == -18019901:
                    _LOGGER.debug("%s already registered on 17track", tracking_number)
                    return True
                error_msg = error.get("message", "Unknown")
                _LOGGER.warning(
                    "17track rejected %s: %s", tracking_number, error_msg
                )
                return False

        if code == -18010014:
            raise Api17TrackQuotaExceeded("Monthly quota exceeded")

        _LOGGER.error("17track register error: %s", result)
        return False

    async def get_track_info(self, tracking_numbers: list[str]) -> dict[str, dict]:
        """Get tracking info for registered numbers. Free after register."""
        if not tracking_numbers:
            return {}

        items = [{"number": n} for n in tracking_numbers]
        result = await self._request(API_17TRACK_GETTRACKINFO, items)

        if result.get("code") != 0:
            _LOGGER.error("17track gettrackinfo error: %s", result)
            return {}

        data = result.get("data", {})
        accepted = data.get("accepted", [])
        output: dict[str, dict] = {}

        for item in accepted:
            number = item.get("number", "")
            track_info = item.get("track_info", {})
            output[number] = self._parse_track_data(track_info)

        return output

    def _parse_track_data(self, track_info: dict) -> dict:
        """Parse 17track v2.2 track_info into our format."""
        # Status mapping from 17track v2.2 string statuses
        status_map = {
            "NotFound": PackageStatus.NOT_FOUND,
            "InfoReceived": PackageStatus.INFO_RECEIVED,
            "InTransit": PackageStatus.IN_TRANSIT,
            "OutForDelivery": PackageStatus.OUT_FOR_DELIVERY,
            "AvailableForPickup": PackageStatus.AVAILABLE_FOR_PICKUP,
            "Delivered": PackageStatus.DELIVERED,
            "DeliveryFailure": PackageStatus.DELIVERY_FAILURE,
            "Exception": PackageStatus.EXCEPTION,
            "Expired": PackageStatus.EXPIRED,
        }

        # Parse latest status
        latest_status = track_info.get("latest_status", {})
        status_str = latest_status.get("status", "NotFound")
        status = status_map.get(status_str, PackageStatus.UNKNOWN)

        # Parse events from all providers
        events: list[TrackingEvent] = []
        tracking = track_info.get("tracking", {})
        for provider in tracking.get("providers", []):
            for event_data in provider.get("events", []):
                try:
                    ts = event_data.get("time_iso", "")
                    timestamp = datetime.fromisoformat(ts) if ts else datetime.now()
                    location = event_data.get("location") or ""
                    if not location:
                        addr = event_data.get("address", {})
                        parts = [
                            addr.get("city") or "",
                            addr.get("state") or "",
                            addr.get("country") or "",
                        ]
                        location = ", ".join(p for p in parts if p)
                    events.append(
                        TrackingEvent(
                            timestamp=timestamp,
                            description=event_data.get("description", ""),
                            location=location,
                        )
                    )
                except (ValueError, TypeError):
                    continue

        # Sort events newest first
        events.sort(key=lambda e: e.timestamp, reverse=True)

        # Latest event info
        latest_event = track_info.get("latest_event", {})
        info_text = latest_event.get("description", "")
        if not info_text and events:
            info_text = events[0].description
        location = latest_event.get("location") or ""
        if not location and events:
            location = events[0].location

        # Carrier detection — try multiple fields
        carrier = ""

        # 1. From tracking providers (most reliable)
        for provider in tracking.get("providers", []):
            provider_info = provider.get("provider", {})
            carrier_code = provider_info.get("key")
            if carrier_code and not carrier:
                carrier = CARRIER_17TRACK_REVERSE.get(carrier_code, "")
            if not carrier:
                carrier_name = provider_info.get("name", "")
                if carrier_name:
                    carrier = _normalize_carrier_name(carrier_name)

        # 2. From misc_info.service_type (fallback)
        if not carrier:
            svc = track_info.get("misc_info", {}).get("service_type", "")
            if svc:
                carrier = _normalize_carrier_name(svc)

        # 3. From misc_info.carrier_code
        if not carrier:
            code = track_info.get("misc_info", {}).get("carrier_code")
            if code:
                carrier = CARRIER_17TRACK_REVERSE.get(code, "")

        return {
            "status": status,
            "info_text": info_text,
            "location": location,
            "events": events,
            "carrier": carrier,
        }

    async def stop_tracking(self, tracking_number: str) -> bool:
        """Stop tracking a number (archive)."""
        result = await self._request(
            API_17TRACK_STOPTRACK, [{"number": tracking_number}]
        )
        return result.get("code") == 0

    async def get_quota(self) -> dict[str, Any]:
        """Get current quota usage."""
        result = await self._request(API_17TRACK_GETQUOTA, {})
        return result.get("data", {})
