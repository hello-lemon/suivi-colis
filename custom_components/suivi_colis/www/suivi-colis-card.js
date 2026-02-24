/**
 * Suivi de Colis Card — Custom Lovelace card for package tracking
 * Auto-discovers Suivi de Colis entities by tracking_number attribute
 */

const CARD_VERSION = "1.1.0";

// Status config: label, color, sort order
const STATUS_CONFIG = {
  out_for_delivery: { label: "En livraison", color: "#FF9800", order: 0 },
  available_for_pickup: { label: "A retirer", color: "#9C27B0", order: 1 },
  exception: { label: "Exception", color: "#f44336", order: 2 },
  delivery_failure: { label: "Echec", color: "#f44336", order: 3 },
  in_transit: { label: "En transit", color: "#2196F3", order: 4 },
  info_received: { label: "Infos recues", color: "#607D8B", order: 5 },
  not_found: { label: "Introuvable", color: "#9E9E9E", order: 6 },
  unknown: { label: "Inconnu", color: "#9E9E9E", order: 7 },
  expired: { label: "Expire", color: "#795548", order: 8 },
  delivered: { label: "Livre", color: "#4CAF50", order: 9 },
};

// Carrier options for the dropdown
const CARRIER_OPTIONS = [
  { value: "", label: "Auto" },
  { value: "colissimo", label: "La Poste / Colissimo" },
  { value: "chronopost", label: "Chronopost" },
  { value: "ups", label: "UPS" },
  { value: "dhl", label: "DHL" },
  { value: "cainiao", label: "AliExpress / Cainiao" },
  { value: "colisprive", label: "Colis Prive" },
];

// Carrier -> favicon domain
const CARRIER_DOMAINS = {
  chronopost: "www.chronopost.fr",
  colissimo: "www.laposte.fr",
  laposte: "www.laposte.fr",
  dhl: "www.dhl.com",
  ups: "www.ups.com",
  amazon: "www.amazon.fr",
  cainiao: "global.cainiao.com",
  colisprive: "www.colisprive.fr",
};

class SuiviColisCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._showForm = false;
    this._inputValue = "";
    this._carrierValue = "";
    this._rendered = false;
  }

  set hass(hass) {
    this._hass = hass;
    if (this._rendered && this._showForm) {
      this._updatePackagesOnly();
    } else {
      this._render();
    }
  }

  setConfig(config) {
    this._config = config;
  }

  getCardSize() {
    return 3;
  }

  static getConfigElement() {
    return document.createElement("suivi-colis-card-editor");
  }

  static getStubConfig() {
    return {};
  }

  _getPackages() {
    if (!this._hass) return [];
    const packages = [];
    for (const [entityId, state] of Object.entries(this._hass.states)) {
      if (
        entityId.startsWith("sensor.") &&
        state.attributes.tracking_number &&
        state.attributes.carrier !== undefined &&
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
    return text.substring(0, max) + "\u2026";
  }

  _toggleForm() {
    this._showForm = !this._showForm;
    this._inputValue = "";
    this._carrierValue = "";
    this._render();
  }

  async _addPackage() {
    const value = this._inputValue.trim();
    if (!value || !this._hass) return;
    const data = { tracking_number: value };
    if (this._carrierValue) {
      data.carrier = this._carrierValue;
    }
    try {
      await this._hass.callService("suivi_colis", "add_package", data);
      this._showForm = false;
      this._inputValue = "";
      this._carrierValue = "";
      this._render();
    } catch (e) {
      console.error("Suivi de Colis: failed to add package", e);
    }
  }

  async _removePackage(trackingNumber) {
    if (!this._hass) return;
    // Optimistic: hide immediately
    const el = this.shadowRoot.querySelector(`.package[data-tracking="${trackingNumber}"]`);
    if (el) el.style.display = "none";
    try {
      await this._hass.callService("suivi_colis", "remove_package", {
        tracking_number: trackingNumber,
      });
    } catch (e) {
      console.error("Suivi de Colis: failed to remove package", e);
      if (el) el.style.display = "";
    }
  }

  _updatePackagesOnly() {
    const container = this.shadowRoot.querySelector(".packages");
    const emptyEl = this.shadowRoot.querySelector(".empty");
    const packages = this._getPackages();

    const countEl = this.shadowRoot.querySelector(".count");
    if (countEl) countEl.textContent = `${packages.length} colis`;

    if (packages.length === 0) {
      if (container) container.remove();
      if (!emptyEl) {
        const card = this.shadowRoot.querySelector("ha-card");
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = "Aucun colis suivi";
        card.appendChild(empty);
      }
    } else {
      if (emptyEl) emptyEl.remove();
      if (container) {
        container.innerHTML = packages.map((p) => this._renderPackage(p)).join("");
        this._bindPackageEvents();
      }
    }
  }

  _render() {
    if (!this._hass) return;
    const packages = this._getPackages();

    const carrierOptionsHtml = CARRIER_OPTIONS.map(
      (o) => `<option value="${o.value}"${o.value === this._carrierValue ? " selected" : ""}>${o.label}</option>`
    ).join("");

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
          .form-area {
            padding: 0 16px 12px;
          }
          .form-row {
            display: flex;
            align-items: center;
            gap: 8px;
          }
          .form-row input, .form-row select {
            padding: 8px 12px;
            border: 1px solid var(--lt-border);
            border-radius: 8px;
            background: var(--lt-bg);
            color: var(--lt-text);
            font-size: 14px;
            outline: none;
          }
          .form-row input {
            flex: 1;
          }
          .form-row select {
            min-width: 80px;
            max-width: 160px;
          }
          .form-row input:focus, .form-row select:focus {
            border-color: var(--primary-color, #03a9f4);
          }
          .form-buttons {
            display: flex;
            gap: 8px;
            margin-top: 8px;
          }
          .form-buttons button {
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
            align-items: flex-start;
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
            margin-top: 2px;
          }
          .carrier-icon-placeholder {
            width: 24px;
            height: 24px;
            border-radius: 4px;
            flex-shrink: 0;
            margin-top: 2px;
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
            margin-top: 2px;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            color: #fff;
            white-space: nowrap;
          }
          .remove-btn {
            flex-shrink: 0;
            margin-top: 2px;
            cursor: pointer;
            border: none;
            background: none;
            color: var(--lt-secondary);
            font-size: 16px;
            padding: 2px 4px;
            border-radius: 4px;
            opacity: 0.5;
            transition: opacity 0.2s, color 0.2s;
          }
          .remove-btn:hover {
            opacity: 1;
            color: #f44336;
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
            <h2>Suivi de Colis</h2>
            <span class="count">${packages.length} colis</span>
          </div>
          <button class="add-btn" id="add-toggle" title="Ajouter un colis">+</button>
        </div>
        ${
          this._showForm
            ? `<div class="form-area">
            <div class="form-row">
              <input type="text" id="tracking-input" placeholder="Numero de suivi..." />
              <select id="carrier-select">${carrierOptionsHtml}</select>
            </div>
            <div class="form-buttons">
              <button class="btn-ok" id="btn-ok">Valider</button>
              <button class="btn-cancel" id="btn-cancel">Annuler</button>
            </div>
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

    this._rendered = true;

    // Bind header events
    this.shadowRoot.getElementById("add-toggle")?.addEventListener("click", () => this._toggleForm());

    // Bind form events
    const input = this.shadowRoot.getElementById("tracking-input");
    if (input) {
      input.value = this._inputValue;
      input.addEventListener("input", (e) => (this._inputValue = e.target.value));
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") this._addPackage();
        if (e.key === "Escape") this._toggleForm();
      });
      setTimeout(() => input.focus(), 50);
    }
    const select = this.shadowRoot.getElementById("carrier-select");
    if (select) {
      select.addEventListener("change", (e) => (this._carrierValue = e.target.value));
    }
    this.shadowRoot.getElementById("btn-ok")?.addEventListener("click", () => this._addPackage());
    this.shadowRoot.getElementById("btn-cancel")?.addEventListener("click", () => this._toggleForm());

    // Bind package remove buttons
    this._bindPackageEvents();
  }

  _bindPackageEvents() {
    this.shadowRoot.querySelectorAll(".remove-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const tracking = e.currentTarget.dataset.tracking;
        if (tracking) this._removePackage(tracking);
      });
    });
  }

  _renderPackage(pkg) {
    const sc = STATUS_CONFIG[pkg.status] || STATUS_CONFIG.unknown;
    const iconUrl = this._getCarrierIcon(pkg.carrier);
    const carrierLabel = pkg.carrier !== "unknown" ? pkg.carrier.charAt(0).toUpperCase() + pkg.carrier.slice(1) : "";

    const displayName = carrierLabel || pkg.tracking_number;
    const showTracking = displayName !== pkg.tracking_number;

    const infoLine = [this._truncate(pkg.info_text), pkg.location].filter(Boolean).join(" \u2014 ");
    const isDelivered = pkg.status === "delivered";

    return `
      <div class="package" data-tracking="${pkg.tracking_number}">
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
        ${isDelivered ? `<button class="remove-btn" data-tracking="${pkg.tracking_number}" title="Supprimer">\u2715</button>` : ""}
      </div>
    `;
  }
}

// Minimal editor
class SuiviColisCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
  }
  set hass(hass) {}
  connectedCallback() {
    this.innerHTML = `<p style="padding:16px;color:var(--secondary-text-color)">Aucun parametre requis. La carte detecte automatiquement les colis.</p>`;
  }
}

customElements.define("suivi-colis-card", SuiviColisCard);
customElements.define("suivi-colis-card-editor", SuiviColisCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "suivi-colis-card",
  name: "Suivi de Colis",
  description: "Suivi de colis avec detection automatique",
  preview: true,
  documentationURL: "https://github.com/hello-lemon/suivi-colis",
});

console.info(
  `%c SUIVI-DE-COLIS %c v${CARD_VERSION} `,
  "background:#FDD835;color:#000;font-weight:bold;padding:2px 6px;border-radius:4px 0 0 4px",
  "background:#333;color:#fff;padding:2px 6px;border-radius:0 4px 4px 0"
);
