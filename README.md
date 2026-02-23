# Suivi de Colis

Custom Home Assistant integration for package tracking via [17track API v2.2](https://api.17track.net).

Tracks packages from 1200+ carriers (Chronopost, Colissimo, DHL, UPS, Amazon, Cainiao...) with optional automatic detection from emails.

## Features

- **1 sensor per package** with status, location, carrier, event timeline
- **Manual add** via `suivi_colis.add_package` service
- **Auto-detect carrier** from tracking number format
- **Email IMAP** polling for automatic package discovery
- **Auto-archive** delivered packages after configurable delay
- **Dynamic icons** based on delivery status

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS
2. Install "Suivi de Colis"
3. Restart Home Assistant
4. Add integration via Settings > Integrations

### Manual

Copy `custom_components/suivi_colis/` to your `config/custom_components/` directory.

## Configuration

### Step 1 — 17track API Key

1. Créer un compte sur [api.17track.net](https://api.17track.net/register)
2. Dans le dashboard 17track, aller dans **Settings > Security > API Key**
3. Copier la clé API (commence par `XXXXXXXX...`)

Le plan gratuit donne 100 nouveaux trackings/mois avec mises à jour illimitées.

### Step 2 — IMAP (optional)

Configure an IMAP mailbox to auto-detect tracking numbers from shipping emails.

### Options

- **Auto-archive delay**: Days after delivery before archiving (default: 3, 0 = disabled)
- **Email check interval**: Minutes between IMAP checks (default: 15)

## Services

| Service | Description |
|---------|-------------|
| `suivi_colis.add_package` | Add a tracking number |
| `suivi_colis.remove_package` | Stop tracking a package |
| `suivi_colis.refresh` | Force immediate refresh |
| `suivi_colis.archive_delivered` | Archive all delivered packages |

### Example: Add a package

```yaml
service: suivi_colis.add_package
data:
  tracking_number: "XX123456789FR"
  friendly_name: "Clavier MX Keys"
  carrier: "chronopost"  # optional, auto-detected
```

## Dashboard Card

Une carte Lovelace custom est incluse et s'enregistre automatiquement au démarrage.

1. Aller sur un dashboard → **Ajouter une carte**
2. Chercher **"Suivi de Colis"** dans le picker
3. Aucune configuration nécessaire — la carte détecte automatiquement les colis

La carte affiche pour chaque colis : logo transporteur, numéro de suivi, statut coloré, dernière info et localisation. Un bouton **"+"** permet d'ajouter un colis directement depuis la carte.

## Supported Carriers

Auto-detection works for: Chronopost, Colissimo, La Poste, DHL, UPS, Amazon, Cainiao/AliExpress.

All 1200+ carriers supported by 17track work when added manually.
