# Lemon Tracker

Custom Home Assistant integration for package tracking via [17track API v2.2](https://api.17track.net).

Tracks packages from 1200+ carriers (Chronopost, Colissimo, DHL, UPS, Amazon, Cainiao...) with optional automatic detection from emails.

## Features

- **1 sensor per package** with status, location, carrier, event timeline
- **Manual add** via `lemon_tracker.add_package` service
- **Auto-detect carrier** from tracking number format
- **Email IMAP** polling for automatic package discovery
- **Auto-archive** delivered packages after configurable delay
- **Dynamic icons** based on delivery status

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS
2. Install "Lemon Tracker"
3. Restart Home Assistant
4. Add integration via Settings > Integrations

### Manual

Copy `custom_components/lemon_tracker/` to your `config/custom_components/` directory.

## Configuration

### Step 1 — 17track API Key

Get a free API key at [api.17track.net](https://api.17track.net). Free tier: 100 new trackings/month, unlimited updates.

### Step 2 — IMAP (optional)

Configure an IMAP mailbox to auto-detect tracking numbers from shipping emails.

### Options

- **Auto-archive delay**: Days after delivery before archiving (default: 3, 0 = disabled)
- **Email check interval**: Minutes between IMAP checks (default: 15)

## Services

| Service | Description |
|---------|-------------|
| `lemon_tracker.add_package` | Add a tracking number |
| `lemon_tracker.remove_package` | Stop tracking a package |
| `lemon_tracker.refresh` | Force immediate refresh |
| `lemon_tracker.archive_delivered` | Archive all delivered packages |

### Example: Add a package

```yaml
service: lemon_tracker.add_package
data:
  tracking_number: "XX123456789FR"
  friendly_name: "Clavier MX Keys"
  carrier: "chronopost"  # optional, auto-detected
```

## Dashboard Card

Markdown card template to list all active packages:

```yaml
type: markdown
title: Colis en cours
content: >
  {% set trackers = states.sensor | selectattr('entity_id', 'match', 'sensor.lemon_tracker_') | list %}
  {% if trackers | length == 0 %}
  Aucun colis en cours de suivi.
  {% else %}
  {% for s in trackers %}
  {% set icon = '📦' %}
  {% if s.state == 'in_transit' %}{% set icon = '🚚' %}
  {% elif s.state == 'delivered' %}{% set icon = '✅' %}
  {% elif s.state == 'out_for_delivery' %}{% set icon = '🏃' %}
  {% elif s.state == 'exception' %}{% set icon = '⚠️' %}
  {% elif s.state == 'available_for_pickup' %}{% set icon = '🏪' %}
  {% endif %}
  {{ icon }} **{{ s.attributes.friendly_name or s.name }}** — {{ s.attributes.carrier | upper }}
  {{ s.attributes.info_text }}
  {% if s.attributes.location %}📍 {{ s.attributes.location }}{% endif %}
  `{{ s.attributes.tracking_number }}`
  {% endfor %}
  {% endif %}
```

## Supported Carriers

Auto-detection works for: Chronopost, Colissimo, La Poste, DHL, UPS, Amazon, Cainiao/AliExpress.

All 1200+ carriers supported by 17track work when added manually.
