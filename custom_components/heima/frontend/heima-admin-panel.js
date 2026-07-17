class HeimaAdminPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._snapshot = null;
    this._error = "";
    this._loading = true;
    this._route = "overview";
    this._refreshTimer = null;
  }

  connectedCallback() {
    this._render();
    this._loadSnapshot();
    this._refreshTimer = window.setInterval(() => this._loadSnapshot(), 15000);
  }

  disconnectedCallback() {
    if (this._refreshTimer) {
      window.clearInterval(this._refreshTimer);
      this._refreshTimer = null;
    }
  }

  set hass(value) {
    this._hass = value;
    if (!this._snapshot && !this._loading) {
      this._loadSnapshot();
    }
  }

  set panel(value) {
    this._panel = value || {};
  }

  async _loadSnapshot() {
    if (!this._hass || typeof this._hass.callWS !== "function") {
      this._loading = false;
      this._render();
      return;
    }
    this._loading = true;
    this._error = "";
    this._render();
    try {
      const command =
        this._panel?.config?.snapshotCommand || "heima/observability/snapshot";
      this._snapshot = await this._hass.callWS({ type: command });
    } catch (err) {
      this._error = err?.message || "Unable to load Heima observability data.";
    } finally {
      this._loading = false;
      this._render();
    }
  }

  _setRoute(route) {
    this._route = route;
    this._render();
  }

  _render() {
    const snapshot = this._snapshot || {};
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          min-height: 100vh;
          color: var(--primary-text-color);
          background: var(--primary-background-color);
          font-family: var(--paper-font-body1_-_font-family, Arial, sans-serif);
        }
        .shell {
          display: grid;
          grid-template-columns: 220px minmax(0, 1fr);
          min-height: 100vh;
        }
        nav {
          border-right: 1px solid var(--divider-color);
          background: var(--card-background-color);
          padding: 16px 10px;
        }
        .brand {
          font-size: 18px;
          font-weight: 650;
          margin: 0 8px 18px;
        }
        button {
          display: block;
          width: 100%;
          border: 0;
          border-radius: 6px;
          padding: 10px 12px;
          margin: 2px 0;
          text-align: left;
          background: transparent;
          color: var(--primary-text-color);
          cursor: pointer;
          font: inherit;
        }
        button:hover,
        button.active {
          background: var(--secondary-background-color);
        }
        main {
          padding: 20px;
          min-width: 0;
        }
        header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          margin-bottom: 18px;
        }
        h1 {
          font-size: 22px;
          margin: 0;
          font-weight: 650;
        }
        .refresh {
          width: auto;
          border: 1px solid var(--divider-color);
          background: var(--card-background-color);
        }
        .grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          gap: 12px;
        }
        .card {
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          background: var(--card-background-color);
          padding: 14px;
          min-width: 0;
        }
        .label {
          color: var(--secondary-text-color);
          font-size: 12px;
          text-transform: uppercase;
          letter-spacing: 0;
          margin-bottom: 6px;
        }
        .value {
          font-size: 20px;
          font-weight: 650;
          overflow-wrap: anywhere;
        }
        table {
          width: 100%;
          border-collapse: collapse;
          background: var(--card-background-color);
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          overflow: hidden;
        }
        th,
        td {
          border-bottom: 1px solid var(--divider-color);
          padding: 9px 10px;
          text-align: left;
          vertical-align: top;
          overflow-wrap: anywhere;
        }
        th {
          color: var(--secondary-text-color);
          font-size: 12px;
          font-weight: 650;
        }
        tr:last-child td {
          border-bottom: 0;
        }
        .status {
          display: inline-block;
          border-radius: 999px;
          padding: 3px 8px;
          font-size: 12px;
          background: var(--secondary-background-color);
        }
        .error {
          border-color: var(--error-color);
          color: var(--error-color);
        }
        .empty {
          color: var(--secondary-text-color);
          padding: 16px;
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          background: var(--card-background-color);
        }
        @media (max-width: 760px) {
          .shell {
            grid-template-columns: 1fr;
          }
          nav {
            border-right: 0;
            border-bottom: 1px solid var(--divider-color);
          }
          nav .items {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(86px, 1fr));
            gap: 4px;
          }
          button {
            text-align: center;
          }
          main {
            padding: 14px;
          }
        }
      </style>
      <div class="shell">
        <nav>
          <div class="brand">Heima</div>
          <div class="items">
            ${this._navButton("overview", "Overview")}
            ${this._navButton("activity", "Runtime")}
            ${this._navButton("reactions", "Reactions")}
            ${this._navButton("holds", "Holds")}
            ${this._navButton("health", "Health")}
          </div>
        </nav>
        <main>
          <header>
            <h1>${this._title()}</h1>
            <button class="refresh" data-route="refresh">Refresh</button>
          </header>
          ${this._body(snapshot)}
        </main>
      </div>
    `;
    this.shadowRoot.querySelectorAll("button[data-route]").forEach((button) => {
      button.addEventListener("click", () => {
        const route = button.getAttribute("data-route");
        if (route === "refresh") {
          this._loadSnapshot();
        } else {
          this._setRoute(route);
        }
      });
    });
  }

  _navButton(route, label) {
    const active = this._route === route ? " active" : "";
    return `<button class="${active}" data-route="${route}">${label}</button>`;
  }

  _title() {
    if (this._route === "activity") return "Runtime Activity";
    if (this._route === "reactions") return "Reaction Inspector";
    if (this._route === "holds") return "Manual Hold Center";
    if (this._route === "health") return "Health";
    return "Overview";
  }

  _body(snapshot) {
    if (this._loading && !this._snapshot) {
      return `<div class="empty">Loading observability snapshot.</div>`;
    }
    if (this._error) {
      return `<div class="card error">${this._escape(this._error)}</div>`;
    }
    if (!snapshot.meta) {
      return `<div class="empty">No observability snapshot available.</div>`;
    }
    if (this._route === "activity") return this._activity(snapshot);
    if (this._route === "reactions") return this._reactions(snapshot);
    if (this._route === "holds") return this._manualHolds(snapshot);
    if (this._route === "health") return this._health(snapshot);
    return this._overview(snapshot);
  }

  _overview(snapshot) {
    const runtime = snapshot.runtime || {};
    const manualHolds = snapshot.manual_holds?.active_holds || [];
    const pendingConfirmations = snapshot.runtime_confirmations?.pending || [];
    const proposalRows = snapshot.proposals?.review_row_count ?? snapshot.proposals?.pending ?? 0;
    const findings = snapshot.health_findings || [];
    return `
      <section class="grid">
        ${this._metric("Engine", snapshot.health?.status || "unknown")}
        ${this._metric("House State", runtime.house_state || "unknown")}
        ${this._metric("Manual Holds", manualHolds.length)}
        ${this._metric("Confirmations", pendingConfirmations.length)}
        ${this._metric("Proposal Rows", proposalRows)}
        ${this._metric("Findings", findings.length)}
      </section>
      ${snapshot.meta?.is_partial ? `<div class="card error">Partial snapshot: ${this._escape((snapshot.meta.partial_reasons || []).join(", "))}</div>` : ""}
    `;
  }

  _activity(snapshot) {
    const events = snapshot.recent_events || [];
    if (!events.length) return `<div class="empty">No runtime activity in the retained window.</div>`;
    return `
      <table>
        <thead>
          <tr><th>Time</th><th>Category</th><th>Reason</th><th>Summary</th></tr>
        </thead>
        <tbody>
          ${events.slice().reverse().map((event) => `
            <tr>
              <td>${this._escape(this._time(event.timestamp))}</td>
              <td><span class="status">${this._escape(event.category || "")}</span></td>
              <td>${this._escape(event.reason_code || "")}</td>
              <td>${this._escape(event.summary || "")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  _health(snapshot) {
    const findings = snapshot.health_findings || [];
    const retention = snapshot.meta?.retention || {};
    return `
      <section class="grid">
        ${this._metric("Status", snapshot.health?.status || "unknown")}
        ${this._metric("Reason", snapshot.health?.reason || "")}
        ${this._metric("Retention", retention.description || "unknown")}
      </section>
      ${findings.length ? this._findingsTable(findings) : `<div class="empty">No active health findings.</div>`}
    `;
  }

  _reactions(snapshot) {
    const reactions = snapshot.reactions || [];
    if (!reactions.length) return `<div class="empty">No configured reactions in the snapshot.</div>`;
    return `
      <table>
        <thead>
          <tr>
            <th>Reaction</th>
            <th>Type</th>
            <th>Origin</th>
            <th>Status</th>
            <th>Execution Policy</th>
            <th>Last Outcome</th>
            <th>Linked Holds</th>
          </tr>
        </thead>
        <tbody>
          ${reactions.map((reaction) => `
            <tr>
              <td>
                <strong>${this._escape(reaction.label || reaction.reaction_id || "")}</strong>
                <div>${this._escape(reaction.reaction_id || "")}</div>
                ${reaction.latest_trace_id ? `<div>trace: ${this._escape(reaction.latest_trace_id)}</div>` : ""}
              </td>
              <td>${this._escape(reaction.reaction_type || "")}</td>
              <td>${this._escape(reaction.origin || "")}</td>
              <td>
                <span class="status">${reaction.enabled === false ? "disabled" : "enabled"}</span>
                ${reaction.muted ? `<span class="status">muted</span>` : ""}
              </td>
              <td>${this._executionPolicy(reaction.execution_policy)}</td>
              <td>${this._escape(reaction.last_outcome || "unknown")}</td>
              <td>${this._list(reaction.linked_manual_hold_scopes || [])}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  _manualHolds(snapshot) {
    const holds = snapshot.manual_holds?.active_holds || [];
    const pending = snapshot.manual_holds?.pending_applies || {};
    return `
      <section class="grid">
        ${this._metric("Active Holds", holds.length)}
        ${this._metric("Pending Applies", pending.total || 0)}
      </section>
      ${holds.length ? this._manualHoldTable(holds) : `<div class="empty">No active manual holds.</div>`}
    `;
  }

  _manualHoldTable(holds) {
    return `
      <table>
        <thead>
          <tr>
            <th>Scope</th>
            <th>Reason</th>
            <th>Release</th>
            <th>Age</th>
            <th>Source</th>
            <th>Affected Reactions</th>
          </tr>
        </thead>
        <tbody>
          ${holds.map((hold) => `
            <tr>
              <td>${this._escape(hold.scope || "")}</td>
              <td>${this._escape(hold.reason || "")}</td>
              <td>${this._escape(hold.release_policy || "")}</td>
              <td>${this._duration(hold.age_s)}</td>
              <td>${this._escape(hold.source_entity || "")}</td>
              <td>${this._list(hold.affected_reaction_ids || [])}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  _findingsTable(findings) {
    return `
      <table>
        <thead>
          <tr><th>Severity</th><th>Reason</th><th>Summary</th></tr>
        </thead>
        <tbody>
          ${findings.map((finding) => `
            <tr>
              <td><span class="status">${this._escape(finding.severity || "")}</span></td>
              <td>${this._escape(finding.reason_code || "")}</td>
              <td>${this._escape(finding.summary || "")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  _metric(label, value) {
    return `
      <div class="card">
        <div class="label">${this._escape(label)}</div>
        <div class="value">${this._escape(String(value ?? ""))}</div>
      </div>
    `;
  }

  _executionPolicy(policy) {
    if (!policy || typeof policy !== "object") return "";
    const source = policy.source || "";
    const mode = policy.mode || "";
    const profile = policy.profile_id ? ` / ${policy.profile_id}` : "";
    const error = policy.config_error ? ` / ${policy.config_error}` : "";
    return this._escape(`${source}${mode ? `: ${mode}` : ""}${profile}${error}`);
  }

  _list(items) {
    if (!items || !items.length) return "";
    return items.map((item) => `<span class="status">${this._escape(item)}</span>`).join(" ");
  }

  _duration(seconds) {
    const value = Number(seconds);
    if (!Number.isFinite(value)) return "";
    if (value < 60) return `${Math.round(value)}s`;
    if (value < 3600) return `${Math.round(value / 60)}m`;
    return `${Math.round(value / 3600)}h`;
  }

  _time(value) {
    if (!value) return "";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleString();
  }

  _escape(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }
}

customElements.define("heima-admin-panel", HeimaAdminPanel);
