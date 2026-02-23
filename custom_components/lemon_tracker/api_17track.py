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
            track = item.get("track", {})
            output[number] = self._parse_track_data(track)

        return output

    def _parse_track_data(self, track: dict) -> dict:
        """Parse 17track track data into our format."""
        latest = track.get("z0", {})  # Latest status info
        status_code = latest.get("s", 0)
        status = STATUS_17TRACK_MAP.get(status_code, PackageStatus.UNKNOWN)

        # Parse events from z1 (detailed tracking)
        events: list[TrackingEvent] = []
        for event_data in track.get("z1", []):
            try:
                ts = event_data.get("a", "")
                timestamp = datetime.fromisoformat(ts) if ts else datetime.now()
                events.append(
                    TrackingEvent(
                        timestamp=timestamp,
                        description=event_data.get("z", ""),
                        location=event_data.get("c", ""),
                    )
                )
            except (ValueError, TypeError):
                continue

        # Sort events newest first
        events.sort(key=lambda e: e.timestamp, reverse=True)

        info_text = events[0].description if events else ""
        location = events[0].location if events else ""

        return {
            "status": status,
            "info_text": info_text,
            "location": location,
            "events": events,
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
