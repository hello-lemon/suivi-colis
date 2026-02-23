/**
 * Lemon Tracker Card — Custom Lovelace card for package tracking
 * Auto-discovers sensor.lemon_tracker_* entities
 */

const CARD_VERSION = "1.0.0";

// Status config: label, color, sort order
const STATUS_CONFIG = {
  out_for_delivery: { label: "En livraison", color: "#FF9800", order: 0 },
  available_for_pickup: { label: "À retirer", color: "#9C27B0", order: 1 },
  exception: { label: "Exception", color: "#f44336", order: 2 },
  delivery_failure: { label: "Échec", color: "#f44336", order: 3 },
  in_transit: { label: "En transit", color: "#2196F3", order: 4 },
  info_received: { label: "Infos reçues", color: "#607D8B", order: 5 },
  not_found: { label: "Introuvable", color: "#9E9E9E", order: 6 },
  unknown: { label: "Inconnu", color: "#9E9E9E", order: 7 },
  expired: { label: "Expiré", color: "#795548", order: 8 },
  delivered: { label: "Livré", color: "#4CAF50", order: 9 },
};

// Carrier → favicon domain
const CARRIER_DOMAINS = {
  chronopost: "www.chronopost.fr",
  colissimo: "www.laposte.fr",
  laposte: "www.laposte.fr",
  dhl: "www.dhl.com",
  ups: "www.ups.com",
  amazon: "www.amazon.fr",
  cainiao: "global.cainiao.com",
};

class LemonTrackerCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._showForm = false;
    this._inputValue = "";
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  setConfig(config) {
    this._config = config;
  }

  getCardSize() {
    return 3;
  }

  static getConfigElement() {
    return document.createElement("lemon-tracker-card-editor");
  }

  static getStubConfig() {
    return {};
  }

  _getPackages() {
    if (!this._hass) return [];
    const packages = [];
    for (const [entityId, state] of Object.entries(this._hass.states)) {
      if (
        entityId.startsWith("sensor.lemon_tracker_") &&
        state.state !== "unavailable"
      ) {
        packages.push({
          entity_id: entityId,
          status: state.state,
          tracking_number: state.attributes.tracking_number || "",
          carrier: state.attributes.carrier || "unknown",
          friendly_name: state.attributes.friendly_name || "",
          info_text: state.attributes.info_text || "",
          location: state.attributes.location || "",
        });
      }
    }
    // Sort: active first (by order), delivered last
    packages.sort((a, b) => {
      const oa = (STATUS_CONFIG[a.status] || STATUS_CONFIG.unknown).order;
      const ob = (STATUS_CONFIG[b.status] || STATUS_CONFIG.unknown).order;
      return oa - ob;
    });
    return packages;
  }

  _getCarrierIcon(carrier) {
    const domain = CARRIER_DOMAINS[carrier];
    if (domain) {
      return `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;
    }
    return "";
  }

  _truncate(text, max = 60) {
    if (!text || text.length <= max) return text || "";
    return text.substring(0, max) + "…";
  }

  _toggleForm() {
    this._showForm = !this._showForm;
    this._inputValue = "";
    this._render();
  }

  async _addPackage() {
    const value = this._inputValue.trim();
    if (!value || !this._hass) return;
    try {
      await this._hass.callService("lemon_tracker", "add_package", {
        tracking_number: value,
      });
      this._showForm = false;
      this._inputValue = "";
      this._render();
    } catch (e) {
      console.error("Lemon Tracker: failed to add package", e);
    }
  }

  _render() {
    if (!this._hass) return;
    const packages = this._getPackages();

    this.shadowRoot.innerHTML = `
      <ha-card>
        <style>
          :host {
            --lt-bg: var(--card-background-color, var(--ha-card-background, #fff));
            --lt-text: var(--primary-text-color, #212121);
            --lt-secondary: var(--secondary-text-color, #727272);
            --lt-border: var(--divider-color, #e0e0e0);
          }
          .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px 16px 8px;
          }
          .header h2 {
            margin: 0;
            font-size: 16px;
            font-weight: 500;
            color: var(--lt-text);
          }
          .header .count {
            font-size: 13px;
            color: var(--lt-secondary);
            margin-left: 8px;
          }
          .add-btn {
            cursor: pointer;
            border: none;
            background: none;
            color: var(--primary-color, #03a9f4);
            font-size: 24px;
            line-height: 1;
            padding: 4px 8px;
            border-radius: 50%;
            transition: background 0.2s;
          }
          .add-btn:hover {
            background: var(--lt-border);
          }
          .form-row {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 0 16px 12px;
          }
          .form-row input {
            flex: 1;
            padding: 8px 12px;
            border: 1px solid var(--lt-border);
            border-radius: 8px;
            background: var(--lt-bg);
            color: var(--lt-text);
            font-size: 14px;
            outline: none;
          }
          .form-row input:focus {
            border-color: var(--primary-color, #03a9f4);
          }
          .form-row button {
            padding: 8px 14px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
          }
          .btn-ok {
            background: var(--primary-color, #03a9f4);
            color: #fff;
          }
          .btn-cancel {
            background: var(--lt-border);
            color: var(--lt-text);
          }
          .packages {
            padding: 0 16px 16px;
          }
          .package {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 10px 0;
            border-bottom: 1px solid var(--lt-border);
          }
          .package:last-child {
            border-bottom: none;
          }
          .carrier-icon {
            width: 24px;
            height: 24px;
            border-radius: 4px;
            flex-shrink: 0;
          }
          .carrier-icon-placeholder {
            width: 24px;
            height: 24px;
            border-radius: 4px;
            flex-shrink: 0;
            background: var(--lt-border);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            color: var(--lt-secondary);
          }
          .info {
            flex: 1;
            min-width: 0;
          }
          .info .name {
            font-size: 14px;
            font-weight: 500;
            color: var(--lt-text);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
          .info .tracking {
            font-size: 12px;
            color: var(--lt-secondary);
            font-family: monospace;
          }
          .info .detail {
            font-size: 12px;
            color: var(--lt-secondary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
          .chip {
            flex-shrink: 0;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            color: #fff;
            white-space: nowrap;
          }
          .empty {
            padding: 24px 16px;
            text-align: center;
            color: var(--lt-secondary);
            font-size: 14px;
          }
        </style>
        <div class="header">
          <div style="display:flex;align-items:baseline;">
            <h2>📦 Lemon Tracker</h2>
            <span class="count">${packages.length} colis</span>
          </div>
          <button class="add-btn" id="add-toggle" title="Ajouter un colis">+</button>
        </div>
        ${
          this._showForm
            ? `<div class="form-row">
            <input type="text" id="tracking-input" placeholder="Numéro de suivi…" value="${this._inputValue}" />
            <button class="btn-ok" id="btn-ok">Valider</button>
            <button class="btn-cancel" id="btn-cancel">Annuler</button>
          </div>`
            : ""
        }
        ${
          packages.length === 0
            ? `<div class="empty">Aucun colis suivi</div>`
            : `<div class="packages">${packages.map((p) => this._renderPackage(p)).join("")}</div>`
        }
      </ha-card>
    `;

    // Bind events
    this.shadowRoot.getElementById("add-toggle")?.addEventListener("click", () => this._toggleForm());
    const input = this.shadowRoot.getElementById("tracking-input");
    if (input) {
      input.addEventListener("input", (e) => (this._inputValue = e.target.value));
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") this._addPackage();
        if (e.key === "Escape") this._toggleForm();
      });
      setTimeout(() => input.focus(), 50);
    }
    this.shadowRoot.getElementById("btn-ok")?.addEventListener("click", () => this._addPackage());
    this.shadowRoot.getElementById("btn-cancel")?.addEventListener("click", () => this._toggleForm());
  }

  _renderPackage(pkg) {
    const sc = STATUS_CONFIG[pkg.status] || STATUS_CONFIG.unknown;
    const iconUrl = this._getCarrierIcon(pkg.carrier);
    const carrierLabel = pkg.carrier !== "unknown" ? pkg.carrier.charAt(0).toUpperCase() + pkg.carrier.slice(1) : "";
    const displayName = pkg.friendly_name || carrierLabel || pkg.tracking_number;
    const showTracking = pkg.friendly_name || carrierLabel;
    const infoLine = [this._truncate(pkg.info_text), pkg.location].filter(Boolean).join(" — ");

    return `
      <div class="package">
        ${
          iconUrl
            ? `<img class="carrier-icon" src="${iconUrl}" alt="${pkg.carrier}" />`
            : `<div class="carrier-icon-placeholder">?</div>`
        }
        <div class="info">
          <div class="name">${displayName}</div>
          ${showTracking ? `<div class="tracking">${pkg.tracking_number}</div>` : ""}
          ${infoLine ? `<div class="detail">${infoLine}</div>` : ""}
        </div>
        <span class="chip" style="background:${sc.color}">${sc.label}</span>
      </div>
    `;
  }
}

// Minimal editor
class LemonTrackerCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
  }
  set hass(hass) {}
  connectedCallback() {
    this.innerHTML = `<p style="padding:16px;color:var(--secondary-text-color)">Aucun paramètre requis. La carte détecte automatiquement les colis.</p>`;
  }
}

customElements.define("lemon-tracker-card", LemonTrackerCard);
customElements.define("lemon-tracker-card-editor", LemonTrackerCardEditor);

// Register in card picker
window.customCards = window.customCards || [];
window.customCards.push({
  type: "lemon-tracker-card",
  name: "Lemon Tracker",
  description: "Suivi de colis avec détection automatique",
  preview: true,
  documentationURL: "https://github.com/hellolemon/lemon-tracker",
});

console.info(
  `%c LEMON-TRACKER-CARD %c v${CARD_VERSION} `,
  "background:#FDD835;color:#000;font-weight:bold;padding:2px 6px;border-radius:4px 0 0 4px",
  "background:#333;color:#fff;padding:2px 6px;border-radius:0 4px 4px 0"
);
