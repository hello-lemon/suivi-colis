"""Constants for Suivi de Colis."""

import re

DOMAIN = "suivi_colis"
STORAGE_KEY = "suivi_colis_packages"
STORAGE_VERSION = 1

# Config keys
CONF_API_KEY = "api_key"
CONF_IMAP_SERVER = "imap_server"
CONF_IMAP_PORT = "imap_port"
CONF_IMAP_USER = "imap_user"
CONF_IMAP_PASSWORD = "imap_password"
CONF_IMAP_FOLDER = "imap_folder"
CONF_IMAP_SSL = "imap_ssl"
CONF_IMAP_DEDICATED = "imap_dedicated"
CONF_ARCHIVE_AFTER_DAYS = "archive_after_days"
CONF_EMAIL_INTERVAL = "email_interval"

# Defaults
DEFAULT_IMAP_PORT = 993
DEFAULT_IMAP_FOLDER = "INBOX"
DEFAULT_IMAP_SSL = True
DEFAULT_ARCHIVE_AFTER_DAYS = 2
DEFAULT_EMAIL_INTERVAL = 15  # minutes
DEFAULT_UPDATE_INTERVAL = 30  # minutes

# 17track API
API_17TRACK_BASE = "https://api.17track.net/track/v2.2"
API_17TRACK_REGISTER = f"{API_17TRACK_BASE}/register"
API_17TRACK_GETTRACKINFO = f"{API_17TRACK_BASE}/gettrackinfo"
API_17TRACK_STOPTRACK = f"{API_17TRACK_BASE}/stoptrack"
API_17TRACK_GETQUOTA = f"{API_17TRACK_BASE}/getquota"
API_17TRACK_RATE_LIMIT = 3  # req/sec

# Carrier regex patterns (for manual add detection)
CARRIER_REGEX = {
    "chronopost": [
        re.compile(r"^[A-Z]{2}\d{9}FR$"),      # XX123456789FR
        re.compile(r"^\d{13}$"),                 # 13 digits
    ],
    "colissimo": [
        re.compile(r"^6[A-Z]\d{11}$"),          # 6X12345678901
        re.compile(r"^[0-9]{15}$"),             # 15 digits (Colissimo international)
    ],
    "ups": [
        re.compile(r"^1Z[A-Z0-9]{16}$"),        # 1Z + 16 chars
    ],
    "amazon": [
        re.compile(r"^TBA\d{12,}$"),            # TBA + digits
    ],
    "cainiao": [
        re.compile(r"^L[RPT][A-Z0-9]{7,9}[A-Z]{2}$"),  # LR/LP/LT...XX
        re.compile(r"^YANWEN\d+$"),
    ],
    "dhl": [
        re.compile(r"^\d{10,11}$"),             # 10-11 digits (also matches others)
        re.compile(r"^JJD\d{18}$"),             # JJD + 18 digits
        re.compile(r"^\d{3}-\d{8}$"),           # DHL Express
    ],
    "laposte": [
        re.compile(r"^[A-Z]{2}\d{9}FR$"),       # Same as Chronopost (resolved by context)
    ],
}

# Email sender to carrier mapping
EMAIL_CARRIER_MAP = {
    "noreply@chronopost.fr": "chronopost",
    "notification@chronopost.fr": "chronopost",
    "noreply@laposte.fr": "colissimo",
    "noreply@notif.laposte.fr": "colissimo",
    "noreply@dhl.com": "dhl",
    "noreply@ups.com": "ups",
    "pkginfo@ups.com": "ups",
    "shipment-tracking@amazon.fr": "amazon",
    "no-reply@amazon.fr": "amazon",
    "shipment-tracking@amazon.com": "amazon",
    "noreply@aliexpress.com": "cainiao",
    "transaction@notice.aliexpress.com": "cainiao",
}

# Email domain to carrier (fallback)
EMAIL_DOMAIN_CARRIER_MAP = {
    "chronopost.fr": "chronopost",
    "laposte.fr": "colissimo",
    "dhl.com": "dhl",
    "ups.com": "ups",
    "amazon.fr": "amazon",
    "amazon.com": "amazon",
    "aliexpress.com": "cainiao",
}

# Tracking number regex for extraction from emails
TRACKING_NUMBER_PATTERNS = [
    re.compile(r"(?:suivi|tracking|n[°o]?\s*(?:de\s+)?colis|shipment)\s*[:=]?\s*([A-Z0-9]{10,30})", re.IGNORECASE),
    re.compile(r"(?:track|suivre)[^\n]*?([A-Z0-9]{10,30})", re.IGNORECASE),
    re.compile(r"\b(1Z[A-Z0-9]{16})\b", re.IGNORECASE),           # UPS
    re.compile(r"\b(TBA\d{12,})\b", re.IGNORECASE),               # Amazon
    re.compile(r"\b([A-Z]{2}\d{9}FR)\b", re.IGNORECASE),          # Chronopost/Colissimo
    re.compile(r"\b(6[A-Z]\d{11})\b", re.IGNORECASE),             # Colissimo
    re.compile(r"\b(L[RPT][A-Z0-9]{7,9}[A-Z]{2})\b", re.IGNORECASE),  # Cainiao
    re.compile(r"\b(JJD\d{18})\b", re.IGNORECASE),                # DHL
]

# 17track carrier codes mapping
CARRIER_17TRACK_CODE = {
    "chronopost": 4031,
    "colissimo": 4036,
    "laposte": 4036,
    "dhl": 100003,
    "ups": 100002,
    "amazon": 100143,
    "cainiao": 190271,
    "colisprive": 100027,
}

# Status icon mapping
STATUS_ICONS = {
    "unknown": "mdi:package-variant",
    "info_received": "mdi:package-variant-closed",
    "in_transit": "mdi:truck-delivery",
    "out_for_delivery": "mdi:truck-fast",
    "available_for_pickup": "mdi:store-marker",
    "delivered": "mdi:package-variant-closed-check",
    "delivery_failure": "mdi:package-variant-remove",
    "exception": "mdi:alert-circle",
    "expired": "mdi:clock-alert",
    "not_found": "mdi:help-circle",
}
