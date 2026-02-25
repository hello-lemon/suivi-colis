# Suivi de Colis

Intégration Home Assistant pour le suivi de colis via l'[API 17track v2.2](https://api.17track.net).

Suivi de plus de 1200 transporteurs (Chronopost, Colissimo, DHL, UPS, Amazon, Cainiao, Colis Privé…) avec détection automatique depuis les emails.

## Fonctionnalités

- **1 capteur par colis** : statut, localisation, transporteur, historique des événements
- **Ajout manuel** via le service `suivi_colis.add_package` ou le bouton "+" de la carte
- **Sélecteur de transporteur** : choix manuel ou détection automatique
- **Détection automatique du transporteur** à partir du format du numéro de suivi, avec fallback auto-détection 17track si rejeté
- **Scan IMAP** : détection automatique des numéros de suivi depuis les emails (boîte perso ou dédiée)
- **Suppression automatique** des colis livrés après un délai configurable
- **Carte Lovelace** incluse avec historique dépliable au clic et suppression des colis livrés

## Installation

### HACS (recommandé)

1. Ajouter ce dépôt comme dépôt personnalisé dans HACS
2. Installer **Suivi de Colis**
3. Redémarrer Home Assistant
4. Ajouter l'intégration via **Paramètres → Intégrations**

### Manuelle

Copier le dossier `custom_components/suivi_colis/` dans votre répertoire `config/custom_components/`.

## Configuration

### Étape 1 — Clé API 17track

1. Créer un compte sur [api.17track.net](https://api.17track.net/register)
2. Dans le dashboard 17track, aller dans **Settings → Security → API Key**
3. Copier la clé API

Le plan gratuit donne 100 nouveaux trackings/mois avec mises à jour illimitées.

### Étape 2 — Email IMAP (optionnel)

Configurer une boîte mail IMAP pour détecter automatiquement les numéros de suivi depuis les emails de transporteurs.

Deux modes disponibles :
- **Boîte perso** (par défaut) : ne scanne que les emails provenant de transporteurs connus (Chronopost, Amazon, DHL…)
- **Boîte dédiée** : scanne tous les emails reçus et extrait les numéros de suivi. Idéal si vous transférez vos notifications de livraison vers une adresse dédiée.

### Options

- **Archivage automatique** : nombre de jours après livraison avant suppression (défaut : 2, 0 = désactivé)
- **Intervalle de vérification emails** : en minutes (défaut : 15)

## Services

| Service | Description |
|---------|-------------|
| `suivi_colis.add_package` | Ajouter un numéro de suivi |
| `suivi_colis.remove_package` | Arrêter le suivi d'un colis |
| `suivi_colis.refresh` | Forcer une mise à jour immédiate |
| `suivi_colis.archive_delivered` | Archiver tous les colis livrés |

### Exemple : ajouter un colis

```yaml
service: suivi_colis.add_package
data:
  tracking_number: "XX123456789FR"
  friendly_name: "Clavier MX Keys"
  carrier: "chronopost"  # optionnel, détecté automatiquement
```

## Carte Lovelace

La carte custom s'enregistre automatiquement au démarrage de Home Assistant.

1. Aller sur un dashboard → **Ajouter une carte**
2. Chercher **"Suivi de Colis"** dans le picker
3. Aucune configuration nécessaire

La carte affiche pour chaque colis :
- Logo du transporteur, nom, numéro de suivi
- Statut coloré et dernière info/localisation
- **Clic sur un colis** : déplie l'historique complet des événements
- **Bouton "+"** : ajouter un colis avec sélecteur de transporteur (Auto, La Poste, Chronopost, UPS, DHL, AliExpress, Colis Privé)
- **Bouton "x"** sur les colis livrés : suppression manuelle

## Transporteurs supportés

Détection automatique : Chronopost, Colissimo, La Poste, DHL, UPS, Amazon, Cainiao/AliExpress, Colis Privé.

Tous les 1200+ transporteurs supportés par 17track fonctionnent en ajout manuel.
