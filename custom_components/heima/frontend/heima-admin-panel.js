class HeimaAdminPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._snapshot = null;
    this._error = "";
    this._actionError = "";
    this._inspectionError = "";
    this._inspectionResult = null;
    this._loading = true;
    this._route = "overview";
    this._detail = null;
    this._filters = {};
    this._focusFilter = null;
    this._onHashChange = () => this._restoreRouteFromHash();
    this._refreshTimer = null;
  }

  connectedCallback() {
    this._restoreRouteFromHash();
    window.addEventListener("hashchange", this._onHashChange);
    this._render();
    this._loadSnapshot();
    this._refreshTimer = window.setInterval(() => this._loadSnapshot(), 15000);
  }

  disconnectedCallback() {
    window.removeEventListener("hashchange", this._onHashChange);
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
    this._actionError = "";
    this._inspectionError = "";
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
    this._detail = null;
    this._syncHash();
    this._render();
  }

  _setDetail(kind, id) {
    this._detail = kind && id ? { kind, id } : null;
    this._syncHash();
    this._render();
  }

  _setFilter(section, key, value) {
    const current = this._filters[section] || {};
    this._filters = {
      ...this._filters,
      [section]: {
        ...current,
        [key]: value,
      },
    };
    this._focusFilter = { section, key };
    this._render();
  }

  _restoreRouteFromHash() {
    const raw = window.location.hash.startsWith("#")
      ? window.location.hash.slice(1)
      : window.location.hash;
    const params = new URLSearchParams(raw);
    const route = params.get("route");
    if (route) this._route = route;
    const detailKind = params.get("detail");
    const detailId = params.get("id");
    this._detail = detailKind && detailId ? { kind: detailKind, id: detailId } : null;
  }

  _syncHash() {
    const params = new URLSearchParams();
    params.set("route", this._route);
    if (this._detail) {
      params.set("detail", this._detail.kind);
      params.set("id", this._detail.id);
    }
    const nextHash = `#${params.toString()}`;
    if (window.location.hash !== nextHash) {
      window.history.replaceState(null, "", nextHash);
    }
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
        button.inline {
          display: inline-block;
          width: auto;
          margin: 0;
          border: 1px solid var(--divider-color);
          background: var(--card-background-color);
          text-align: center;
        }
        button.danger {
          color: var(--error-color);
        }
        button:disabled {
          opacity: 0.55;
          cursor: progress;
        }
        .row-actions {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }
        .toolbar {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
          align-items: center;
          margin: 0 0 12px;
        }
        .toolbar input,
        .toolbar select {
          min-width: 220px;
          max-width: 100%;
          border: 1px solid var(--divider-color);
          border-radius: 6px;
          background: var(--card-background-color);
          color: var(--primary-text-color);
          padding: 8px 10px;
          font: inherit;
        }
        button.copy {
          display: inline-block;
          width: auto;
          margin: 0 0 0 4px;
          padding: 2px 6px;
          border: 1px solid var(--divider-color);
          background: var(--card-background-color);
          font-size: 11px;
          text-align: center;
        }
        .object-id {
          font-family: var(--code-font-family, monospace);
          font-size: 12px;
          overflow-wrap: anywhere;
          word-break: break-word;
          color: var(--secondary-text-color);
        }
        .detail-panel {
          margin-top: 16px;
          border: 1px solid var(--divider-color);
          border-radius: 8px;
          background: var(--card-background-color);
          padding: 14px;
        }
        .detail-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 12px;
        }
        .detail-header h2 {
          margin: 0;
        }
        .detail-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
          gap: 12px;
        }
        .detail-section {
          border-top: 1px solid var(--divider-color);
          padding-top: 12px;
          margin-top: 12px;
        }
        .kv {
          width: 100%;
          border: 0;
          background: transparent;
        }
        .kv th,
        .kv td {
          border-bottom: 1px solid var(--divider-color);
        }
        pre {
          white-space: pre-wrap;
          overflow-wrap: anywhere;
          max-width: 100%;
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
            ${this._navButton("house_state", "House State")}
            ${this._navButton("reactions", "Reactions")}
            ${this._navButton("holds", "Holds")}
            ${this._navButton("confirmations", "Confirmations")}
            ${this._navButton("notifications", "Notifications")}
            ${this._navButton("learning", "Learning")}
            ${this._navButton("proposals", "Proposals")}
            ${this._navButton("entities", "Entities")}
            ${this._navButton("health", "Health")}
          </div>
        </nav>
        <main>
          <header>
            <h1>${this._title()}</h1>
            <div class="row-actions">
              <button class="inline" data-export="copy">Copy JSON</button>
              <button class="inline" data-export="download">Download JSON</button>
              <button class="refresh" data-route="refresh">Refresh</button>
            </div>
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
    this.shadowRoot.querySelectorAll("button[data-action]").forEach((button) => {
      button.addEventListener("click", () => this._runAction(button));
    });
    this.shadowRoot.querySelectorAll("button[data-detail-kind]").forEach((button) => {
      button.addEventListener("click", () => {
        this._setDetail(
          button.getAttribute("data-detail-kind") || "",
          button.getAttribute("data-detail-id") || "",
        );
      });
    });
    this.shadowRoot.querySelectorAll("[data-filter-section]").forEach((input) => {
      input.addEventListener("input", () => {
        this._setFilter(
          input.getAttribute("data-filter-section") || "",
          input.getAttribute("data-filter-key") || "text",
          input.value || "",
        );
      });
      input.addEventListener("change", () => {
        this._setFilter(
          input.getAttribute("data-filter-section") || "",
          input.getAttribute("data-filter-key") || "text",
          input.value || "",
        );
      });
    });
    this.shadowRoot.querySelectorAll("button[data-copy-value]").forEach((button) => {
      button.addEventListener("click", () => this._copyValue(button));
    });
    this.shadowRoot.querySelectorAll("button[data-export]").forEach((button) => {
      button.addEventListener("click", () => this._exportSnapshot(button));
    });
    this.shadowRoot.querySelectorAll("button[data-inspect-why-not-now]").forEach((button) => {
      button.addEventListener("click", () => this._runWhyNotNow(button));
    });
    this._restoreFilterFocus();
  }

  _navButton(route, label) {
    const active = this._route === route ? " active" : "";
    return `<button class="${active}" data-route="${route}">${label}</button>`;
  }

  _title() {
    if (this._route === "activity") return "Runtime Activity";
    if (this._route === "house_state") return "House State";
    if (this._route === "reactions") return "Reaction Inspector";
    if (this._route === "holds") return "Manual Hold Center";
    if (this._route === "confirmations") return "Runtime Confirmation Center";
    if (this._route === "notifications") return "Notification Routing Inspector";
    if (this._route === "learning") return "Learning Monitor";
    if (this._route === "proposals") return "Proposal Backlog Inspector";
    if (this._route === "entities") return "Entity Impact";
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
    const actionError = this._actionError
      ? `<div class="card error">${this._escape(this._actionError)}</div>`
      : "";
    const inspectionError = this._inspectionError
      ? `<div class="card error">${this._escape(this._inspectionError)}</div>`
      : "";
    const body = this._bodyContent(snapshot);
    return `${actionError}${inspectionError}${body}${this._detailPanel(snapshot)}`;
  }

  _bodyContent(snapshot) {
    if (this._route === "activity") return this._activity(snapshot);
    if (this._route === "house_state") return this._houseState(snapshot);
    if (this._route === "reactions") return this._reactions(snapshot);
    if (this._route === "holds") return this._manualHolds(snapshot);
    if (this._route === "confirmations") return this._confirmations(snapshot);
    if (this._route === "notifications") return this._notifications(snapshot);
    if (this._route === "learning") return this._learning(snapshot);
    if (this._route === "proposals") return this._proposals(snapshot);
    if (this._route === "entities") return this._entities(snapshot);
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
    const allEvents = snapshot.recent_events || [];
    const events = this._filterRows("activity", allEvents);
    if (!allEvents.length) return `<div class="empty">No runtime activity in the retained window.</div>`;
    return `
      ${this._filterToolbar("activity", "Search runtime events")}
      ${this._filteredCount(events.length, allEvents.length)}
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

  _houseState(snapshot) {
    const runtime = snapshot.runtime || {};
    const house = snapshot.house_state || {};
    const resolution = house.resolution_trace || {};
    const decision = resolution.decision || {};
    const activeCandidates = house.active_candidates || [];
    const candidateRows = this._houseStateCandidateRows(house);
    const filteredRows = this._filterRows("house_state", candidateRows);
    return `
      <section class="grid">
        ${this._metric("Current State", runtime.house_state || "unknown")}
        ${this._metric("Current Reason", runtime.house_state_reason || house.winning_reason || "")}
        ${this._metric("Decision", house.decision_action || decision.action || "")}
        ${this._metric("Target State", house.decision_target_state || "")}
        ${this._metric("Winning Reason", house.winning_reason || "")}
        ${this._metric("Active Candidates", activeCandidates.length ? activeCandidates.join(", ") : "none")}
        ${this._metric("Pending Candidate", house.pending_candidate || "none")}
        ${this._metric("Resolution Path", house.resolution_path || "")}
      </section>
      ${this._filterToolbar("house_state", "Search house-state candidates")}
      ${this._filteredCount(filteredRows.length, candidateRows.length)}
      ${filteredRows.length ? this._houseStateCandidateTable(filteredRows) : `<div class="empty">No house-state candidate diagnostics in the snapshot.</div>`}
      <section class="detail-grid">
        ${this._detailSection("Resolution Decision", decision)}
        ${this._detailSection("Timers", house.timers || {})}
        ${this._detailSection("Override", house.override || {})}
      </section>
      ${this._rawDetails(house)}
    `;
  }

  _houseStateCandidateRows(house) {
    const summary = house.candidate_summary || {};
    const traces = house.candidate_trace || {};
    const names = Array.from(new Set([
      ...Object.keys(summary),
      ...Object.keys(traces),
      ...(house.active_candidates || []),
    ])).sort();
    return names.map((name) => {
      const candidateSummary = summary[name] || {};
      const trace = traces[name] || {};
      return {
        candidate: name,
        status: candidateSummary.status || candidateSummary.result || "",
        state: trace.state ?? candidateSummary.state ?? "",
        reason: trace.reason || candidateSummary.reason || "",
        since: candidateSummary.since || candidateSummary.first_seen_at || "",
        remaining_s: candidateSummary.remaining_s ?? trace.remaining_s ?? "",
        inputs: trace.inputs || candidateSummary.inputs || {},
        summary: candidateSummary,
        trace,
      };
    });
  }

  _houseStateCandidateTable(rows) {
    return `
      <table>
        <thead>
          <tr>
            <th>Candidate</th>
            <th>Status</th>
            <th>State</th>
            <th>Reason</th>
            <th>Timing</th>
            <th>Inputs</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td><strong>${this._escape(row.candidate || "")}</strong></td>
              <td><span class="status">${this._escape(row.status || "")}</span></td>
              <td>${this._escape(this._formatDetailValue(row.state))}</td>
              <td>${this._escape(row.reason || "")}</td>
              <td>${this._escape(this._houseStateTiming(row))}</td>
              <td>${this._rawDetails(row.inputs || {})}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  _houseStateTiming(row) {
    const parts = [];
    if (row.since) parts.push(`since ${row.since}`);
    if (row.remaining_s !== "") parts.push(`remaining ${this._duration(row.remaining_s)}`);
    return parts.join(", ");
  }

  _reactions(snapshot) {
    const allReactions = snapshot.reactions || [];
    const reactions = this._filterRows("reactions", allReactions);
    if (!allReactions.length) return `<div class="empty">No configured reactions in the snapshot.</div>`;
    return `
      ${this._filterToolbar("reactions", "Search reactions")}
      ${this._filteredCount(reactions.length, allReactions.length)}
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
            <th>Inspect</th>
          </tr>
        </thead>
        <tbody>
          ${reactions.map((reaction) => `
            <tr>
              <td>
                <strong>${this._escape(reaction.label || reaction.reaction_id || "")}</strong>
                ${this._copyableId(reaction.reaction_id || "")}
                ${reaction.latest_trace_id ? `<div class="object-id">trace: ${this._escape(reaction.latest_trace_id)} ${this._copyButton(reaction.latest_trace_id)}</div>` : ""}
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
              <td>${this._detailButton("reaction", reaction.reaction_id || "")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  _manualHolds(snapshot) {
    const allHolds = snapshot.manual_holds?.active_holds || [];
    const holds = this._filterRows("holds", allHolds);
    const pending = snapshot.manual_holds?.pending_applies || {};
    return `
      <section class="grid">
        ${this._metric("Active Holds", allHolds.length)}
        ${this._metric("Pending Applies", pending.total || 0)}
      </section>
      ${allHolds.length ? `${this._filterToolbar("holds", "Search holds")}${this._filteredCount(holds.length, allHolds.length)}${this._manualHoldTable(holds)}` : `<div class="empty">No active manual holds.</div>`}
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
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${holds.map((hold) => {
            const scope = this._manualHoldScopeParts(hold.scope || "");
            return `
            <tr>
              <td>${this._copyableId(hold.scope || "")}</td>
              <td>${this._escape(hold.reason || "")}</td>
              <td>${this._escape(hold.release_policy || "")}</td>
              <td>${this._duration(hold.age_s)}</td>
              <td>${this._escape(hold.source_entity || "")}</td>
              <td>${this._list(hold.affected_reaction_ids || [])}</td>
              <td>
                <div class="row-actions">
                  ${this._detailButton("manual_hold", hold.scope || "")}
                  ${scope ? this._clearHoldButton(scope, hold.scope || "") : ""}
                </div>
              </td>
            </tr>
          `;
          }).join("")}
        </tbody>
      </table>
    `;
  }

  _confirmations(snapshot) {
    const confirmations = snapshot.runtime_confirmations || {};
    const pendingAll = confirmations.pending || [];
    const completedAll = confirmations.recent_completed || [];
    const pending = this._filterRows("confirmations", pendingAll);
    const completed = this._filterRows("confirmations", completedAll);
    const reviews = confirmations.promotion_reviews || [];
    return `
      <section class="grid">
        ${this._metric("Pending", pendingAll.length)}
        ${this._metric("Recent Completed", completedAll.length)}
        ${this._metric("Stale Responses", confirmations.stale_responses || 0)}
        ${this._metric("Promotion Reviews", reviews.length)}
      </section>
      ${this._filterToolbar("confirmations", "Search confirmations")}
      ${this._filteredCount(pending.length + completed.length, pendingAll.length + completedAll.length)}
      ${pending.length ? this._confirmationTable("Pending Requests", pending) : `<div class="empty">No pending runtime confirmations.</div>`}
      ${completed.length ? this._confirmationTable("Recent Completed", completed) : ""}
      ${reviews.length ? this._promotionReviewTable(reviews) : ""}
    `;
  }

  _confirmationTable(title, requests) {
    return `
      <h2>${this._escape(title)}</h2>
      <table>
        <thead>
          <tr>
            <th>Request</th>
            <th>Reaction</th>
            <th>Status</th>
            <th>Timeout</th>
            <th>Targets</th>
            <th>Apply Result</th>
            <th>Inspect</th>
          </tr>
        </thead>
        <tbody>
          ${requests.map((request) => `
            <tr>
              <td>${this._copyableId(request.request_id || "")}</td>
              <td>${this._copyableId(request.reaction_id || "")}</td>
              <td><span class="status">${this._escape(request.status || "")}</span></td>
              <td>${this._escape(request.on_timeout || "")}</td>
              <td>${this._list(request.confirmation_targets || [])}</td>
              <td>${this._applyResult(request.apply_result)}</td>
              <td>${this._detailButton("runtime_confirmation", request.request_id || "")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  _promotionReviewTable(reviews) {
    return `
      <h2>Promotion Reviews</h2>
      <table>
        <thead>
          <tr><th>Reaction</th><th>Status</th><th>Review</th><th>Actions</th></tr>
        </thead>
        <tbody>
          ${reviews.map((review) => `
            <tr>
              <td>${this._escape(review.reaction_id || "")}</td>
              <td><span class="status">${this._escape(review.status || "")}</span></td>
              <td>${this._escape(review.review_id || review.created_at || "")}</td>
              <td>${this._promotionReviewButtons(review)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  _notifications(snapshot) {
    const notifications = snapshot.notifications || {};
    const deliveryPolicy = notifications.delivery_policy || {};
    const health = deliveryPolicy.health || {};
    const runtime = deliveryPolicy.runtime || {};
    const recentDecisions = runtime.recent_decisions || [];
    return `
      <section class="grid">
        ${this._metric("Recipients", notifications.recipient_count || 0)}
        ${this._metric("Groups", notifications.group_count || 0)}
        ${this._metric("Fallback Targets", notifications.route_count || 0)}
        ${this._metric("Actionable Routes", (notifications.actionable_routes || []).length)}
        ${this._metric("Policy Health", health.status || "unknown")}
        ${this._metric("Recent Decisions", recentDecisions.length)}
      </section>
      ${this._notificationHealth(deliveryPolicy)}
      ${this._notificationPolicyMatrix(deliveryPolicy)}
      ${this._notificationAudienceResolution(notifications)}
      ${this._notificationRecentDecisions(runtime)}
      ${this._notificationSuppressionState(runtime)}
      ${this._notificationRoutesTable(notifications)}
      ${this._notificationRecipientsTable(notifications)}
    `;
  }

  _learning(snapshot) {
    const learning = snapshot.learning || {};
    const modules = learning.learning_modules || [];
    return `
      <section class="grid">
        ${this._metric("Modules", learning.module_count || modules.length)}
        ${this._metric("Ready Modules", learning.ready_module_count || 0)}
        ${this._metric("Pending Proposals", learning.proposal_pending_count || 0)}
        ${this._metric("Total Proposals", learning.proposal_total_count || 0)}
      </section>
      ${this._objectSummary("Analyzer Failures", learning.analyzer_failures || {})}
      ${modules.length ? this._learningModulesTable(modules) : `<div class="empty">No learning modules reported.</div>`}
    `;
  }

  _learningModulesTable(modules) {
    return `
      <table>
        <thead><tr><th>Module</th><th>Status</th><th>Patterns</th><th>Diagnostics</th></tr></thead>
        <tbody>
          ${modules.map((module) => `
            <tr>
              <td>${this._escape(module.module_id || module.id || "unknown")}</td>
              <td><span class="status">${module.ready === true ? "ready" : "not ready"}</span></td>
              <td>${this._escape(module.pattern_count ?? module.slot_count ?? module.approved_patterns ?? "")}</td>
              <td>${this._rawDetails(module)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  _proposals(snapshot) {
    const proposals = snapshot.proposals || {};
    const reviewRows = proposals.review_rows || [];
    const filteredReviewRows = this._filterRows("proposals", reviewRows);
    const temporalBundles = proposals.temporal_bundles || [];
    const filteredBundles = this._filterRows("proposals", temporalBundles);
    return `
      <section class="grid">
        ${this._metric("Visible Rows", proposals.review_row_count ?? proposals.visible_pending_count ?? 0)}
        ${this._metric("Real Pending", proposals.real_pending_count ?? 0)}
        ${this._metric("Visible Pending", proposals.visible_pending_count ?? 0)}
        ${this._metric("Suppressed", proposals.suppressed_pending_count ?? 0)}
        ${this._metric("Temporal Bundles", proposals.temporal_bundle_count ?? 0)}
        ${this._metric("Stale Pending", proposals.pending_stale ?? 0)}
      </section>
      ${this._proposalCounters(proposals)}
      ${this._filterToolbar("proposals", "Search proposals")}
      ${this._filteredCount(filteredReviewRows.length + filteredBundles.length, reviewRows.length + temporalBundles.length)}
      ${this._reviewRowsTable(filteredReviewRows)}
      ${this._temporalBundlesTable(filteredBundles)}
    `;
  }

  _proposalCounters(proposals) {
    return `
      <section class="grid">
        ${this._objectCard("Pending By Type", proposals.pending_by_type || {})}
        ${this._objectCard("Visible By Type", proposals.visible_pending_by_type || {})}
        ${this._objectCard("Suppressed By Type", proposals.suppressed_pending_by_type || {})}
        ${this._objectCard("Followups", proposals.pending_by_followup_kind || {})}
      </section>
    `;
  }

  _reviewRowsTable(rows) {
    if (!rows.length) return `<div class="empty">No proposal review rows in the snapshot.</div>`;
    return `
      <h2>Review Rows</h2>
      <table>
        <thead>
          <tr><th>Type</th><th>ID</th><th>Summary</th><th>Confidence</th><th>Actions</th></tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td><span class="status">${this._escape(row.row_type || "")}</span></td>
              <td>${this._copyableId(row.bundle_id || row.proposal_id || "")}</td>
              <td>${this._proposalRowSummary(row)}</td>
              <td>${this._escape(row.confidence_avg ?? row.confidence ?? "")}</td>
              <td>
                <div class="row-actions">
                  ${this._detailButton("proposal_review_row", row.bundle_id || row.proposal_id || "")}
                  ${this._proposalReviewButtons(row)}
                </div>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  _temporalBundlesTable(bundles) {
    if (!bundles.length) return "";
    return `
      <h2>Temporal Bundles</h2>
      <table>
        <thead>
          <tr><th>Bundle</th><th>Members</th><th>State</th><th>Hours</th><th>Evidence</th></tr>
        </thead>
        <tbody>
          ${bundles.map((bundle) => `
            <tr>
              <td>${this._copyableId(bundle.bundle_id || "")}</td>
              <td>${this._escape(bundle.member_count ?? "")}</td>
              <td>${this._escape(bundle.predicted_state || "")}</td>
              <td>${this._escape(`${bundle.start_hour_bucket ?? ""}-${bundle.end_hour_bucket ?? ""}`)}</td>
              <td>${this._escape(`${bundle.support_total ?? ""}/${bundle.total_observations ?? ""}`)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  _entities(snapshot) {
    const impact = snapshot.entity_impact || {};
    const allEntities = impact.entities || [];
    const entities = this._filterRows("entities", allEntities);
    return `
      <section class="grid">
        ${this._metric("Entities", impact.entity_count ?? allEntities.length)}
        ${this._objectCard("By Domain", impact.by_domain || {})}
      </section>
      ${this._filterToolbar("entities", "Search entities")}
      ${this._filteredCount(entities.length, allEntities.length)}
      ${entities.length ? this._entityTable(entities) : `<div class="empty">No entity impact rows in the snapshot.</div>`}
    `;
  }

  _entityTable(entities) {
    return `
      <table>
        <thead>
          <tr>
            <th>Entity</th>
            <th>Domain</th>
            <th>Reactions</th>
            <th>Traces</th>
            <th>Holds</th>
            <th>Requests</th>
            <th>Policies</th>
            <th>Inspect</th>
          </tr>
        </thead>
        <tbody>
          ${entities.map((entity) => `
            <tr>
              <td>${this._copyableId(entity.entity_id || "")}</td>
              <td><span class="status">${this._escape(entity.domain || "")}</span></td>
              <td>${this._escape((entity.reaction_ids || []).length)}</td>
              <td>${this._escape((entity.trace_ids || []).length)}</td>
              <td>${this._escape((entity.hold_scopes || []).length)}</td>
              <td>${this._escape((entity.request_ids || []).length)}</td>
              <td>${this._escape((entity.policy_ids || []).length)}</td>
              <td>${this._detailButton("entity", entity.entity_id || "")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  _notificationRoutesTable(notifications) {
    const routes = notifications.resolved_routes || [];
    const unresolved = notifications.unresolved_targets || [];
    const actionable = new Set(notifications.actionable_routes || []);
    const skipped = new Set(notifications.skipped_non_actionable_routes || []);
    if (!routes.length && !unresolved.length) {
      return `<div class="empty">No fallback notification targets configured.</div>`;
    }
    return `
      <h2>Resolved Fallback Routes</h2>
      <table>
        <thead>
          <tr><th>Route</th><th>Capability</th></tr>
        </thead>
        <tbody>
          ${routes.map((route) => `
            <tr>
              <td>${this._escape(`notify.${route}`)}</td>
              <td>
                ${actionable.has(route) ? `<span class="status">supports actions</span>` : ""}
                ${skipped.has(route) ? `<span class="status">text only</span>` : ""}
              </td>
            </tr>
          `).join("")}
          ${unresolved.map((target) => `
            <tr>
              <td>${this._escape(target)}</td>
              <td><span class="status">unresolved target</span></td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  _notificationHealth(deliveryPolicy) {
    const health = deliveryPolicy.health || {};
    const issues = health.issues || [];
    return `
      <h2>Notification Health</h2>
      ${issues.length ? `
        <table>
          <thead><tr><th>Severity</th><th>Reason</th></tr></thead>
          <tbody>
            ${issues.map((issue) => `
              <tr>
                <td><span class="status">${this._escape(issue.severity || "")}</span></td>
                <td>${this._escape(issue.reason || "")}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      ` : `<div class="empty">Notification routing health is OK.</div>`}
    `;
  }

  _notificationPolicyMatrix(deliveryPolicy) {
    const effective = deliveryPolicy.effective || {};
    const policy = effective.audience_policy || {};
    const targets = effective.audience_targets || {};
    const thresholds = effective.persistence_thresholds || {};
    const aggregation = effective.aggregation || {};
    const rows = [
      ["people", "People"],
      ["house_state", "House State"],
      ["reaction", "Reaction"],
      ["occupancy_mismatch", "Occupancy Mismatch"],
      ["security_presence_mismatch", "Security Presence Mismatch"],
      ["system_config_issue", "System Config Issue"],
    ];
    return `
      <h2>Delivery Policy Matrix</h2>
      <table>
        <thead>
          <tr>
            <th>Family</th>
            <th>Push Policy</th>
            <th>Audience Targets</th>
            <th>Persistence</th>
            <th>Aggregation</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map(([family, label]) => {
            const push = policy[family]?.push || "";
            const roles = this._policyRoles(push);
            return `
              <tr>
                <td>${this._escape(label)}</td>
                <td><span class="status">${this._escape(push || "unspecified")}</span></td>
                <td>${roles.length ? roles.map((role) => `
                  <div><strong>${this._escape(role)}</strong>: ${this._list(targets[role] || [])}</div>
                `).join("") : `<span class="status">observability only</span>`}</td>
                <td>${this._notificationPersistence(family, thresholds)}</td>
                <td>${this._notificationAggregation(family, aggregation)}</td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    `;
  }

  _notificationAudienceResolution(notifications) {
    const rows = notifications.audience_resolution || [];
    const unresolved = notifications.delivery_policy?.unresolved_audience_targets || [];
    if (!rows.length && !unresolved.length) {
      return `<h2>Audience Resolution</h2><div class="empty">No audience targets configured.</div>`;
    }
    return `
      <h2>Audience Resolution</h2>
      <table>
        <thead>
          <tr>
            <th>Role</th>
            <th>Target</th>
            <th>Type</th>
            <th>Routes</th>
            <th>Capability</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td><span class="status">${this._escape(row.role || "")}</span></td>
              <td>${this._escape(row.target || "")}</td>
              <td>${this._escape(row.target_type || "")}</td>
              <td>${this._list(row.routes || [])}</td>
              <td>
                ${(row.actionable_routes || []).length ? `<div>actions: ${this._list(row.actionable_routes || [])}</div>` : ""}
                ${(row.text_only_routes || []).length ? `<div>text only: ${this._list(row.text_only_routes || [])}</div>` : ""}
                ${row.unresolved ? `<span class="status">unresolved</span>` : ""}
              </td>
            </tr>
          `).join("")}
          ${unresolved.map((row) => `
            <tr>
              <td><span class="status">${this._escape(row.role || "")}</span></td>
              <td>${this._escape(row.target || "")}</td>
              <td>missing</td>
              <td></td>
              <td><span class="status">unresolved</span></td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  _notificationRecentDecisions(runtime) {
    const rows = runtime.recent_decisions || [];
    if (!rows.length) {
      return `<h2>Last Delivery Decisions</h2><div class="empty">No notification delivery decisions recorded yet.</div>`;
    }
    return `
      <h2>Last Delivery Decisions</h2>
      <table>
        <thead>
          <tr>
            <th>Outcome</th>
            <th>Reason</th>
            <th>Family</th>
            <th>Policy</th>
            <th>Roles</th>
            <th>Targets</th>
            <th>Diagnostics</th>
          </tr>
        </thead>
        <tbody>
          ${rows.slice().reverse().slice(0, 20).map((row) => `
            <tr>
              <td><span class="status">${this._escape(row.outcome || "")}</span></td>
              <td>${this._escape(row.reason || "")}</td>
              <td>${this._escape(row.event_family || "")}</td>
              <td>${this._escape(row.push_policy || "")}</td>
              <td>${this._list(row.target_roles || [])}</td>
              <td>${this._list(row.route_targets || [])}</td>
              <td>${this._escape(this._notificationDecisionDiagnostics(row.diagnostics || {}))}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }

  _notificationSuppressionState(runtime) {
    return `
      <h2>Suppression State</h2>
      <section class="grid">
        ${this._objectCard("Decision Counts", runtime.decision_counts || {})}
        ${this._objectCard("Persistence", runtime.persistence || {})}
        ${this._objectCard("Aggregation", runtime.aggregation || {})}
        ${this._objectCard("Burst", runtime.burst || {})}
      </section>
    `;
  }

  _notificationRecipientsTable(notifications) {
    const recipients = notifications.recipients || {};
    const groups = notifications.groups || {};
    const recipientRows = Object.entries(recipients);
    const groupRows = Object.entries(groups);
    return `
      <h2>Recipients</h2>
      ${recipientRows.length ? `
        <table>
          <thead><tr><th>Recipient</th><th>Services</th></tr></thead>
          <tbody>
            ${recipientRows.map(([id, value]) => `
              <tr><td>${this._escape(id)}</td><td>${this._list(this._recipientServices(value))}</td></tr>
            `).join("")}
          </tbody>
        </table>
      ` : `<div class="empty">No recipients configured.</div>`}
      <h2>Groups</h2>
      ${groupRows.length ? `
        <table>
          <thead><tr><th>Group</th><th>Members</th></tr></thead>
          <tbody>
            ${groupRows.map(([id, members]) => `
              <tr><td>${this._escape(id)}</td><td>${this._list(Array.isArray(members) ? members : [])}</td></tr>
            `).join("")}
          </tbody>
        </table>
      ` : `<div class="empty">No groups configured.</div>`}
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

  _detailPanel(snapshot) {
    if (!this._detail) return "";
    const { kind, id } = this._detail;
    const content = this._detailContent(snapshot, kind, id);
    return `
      <section class="detail-panel">
        <div class="detail-header">
          <div>
            <h2>${this._escape(this._detailTitle(kind))}</h2>
            <div class="object-id">${this._escape(id)}</div>
          </div>
          <button class="inline" data-detail-kind="" data-detail-id="">Close</button>
        </div>
        ${content}
      </section>
    `;
  }

  _detailContent(snapshot, kind, id) {
    if (kind === "reaction") return this._reactionDetail(snapshot, id);
    if (kind === "manual_hold") return this._manualHoldDetail(snapshot, id);
    if (kind === "runtime_confirmation") return this._runtimeConfirmationDetail(snapshot, id);
    if (kind === "proposal_review_row") return this._proposalReviewRowDetail(snapshot, id);
    if (kind === "entity") return this._entityDetail(snapshot, id);
    return `<div class="empty">Unknown detail type.</div>`;
  }

  _detailTitle(kind) {
    if (kind === "reaction") return "Reaction Detail";
    if (kind === "manual_hold") return "Manual Hold Detail";
    if (kind === "runtime_confirmation") return "Runtime Confirmation Detail";
    if (kind === "proposal_review_row") return "Proposal Review Detail";
    if (kind === "entity") return "Entity Detail";
    return "Detail";
  }

  _reactionDetail(snapshot, reactionId) {
    const detail = snapshot.details?.reactions?.by_id?.[reactionId];
    if (!detail) return `<div class="empty">Reaction detail is unavailable.</div>`;
    const summary = detail.summary || {};
    return `
      <section class="detail-grid">
        ${this._detailSection("Identity", {
          label: summary.label,
          reaction_id: summary.reaction_id,
          reaction_type: summary.reaction_type,
          origin: summary.origin,
          author_kind: summary.author_kind,
          source_template_id: summary.source_template_id,
        })}
        ${this._detailSection("Status", {
          enabled: summary.enabled === false ? "false" : "true",
          muted: summary.muted === true ? "true" : "false",
          last_outcome: summary.last_outcome,
          latest_trace_id: summary.latest_trace_id,
        })}
        ${this._detailSection("Execution Policy", detail.execution_policy || {})}
      </section>
      <div class="detail-section">
        <button
          class="inline"
          data-inspect-why-not-now="${this._escape(reactionId)}"
        >Why not now?</button>
      </div>
      ${this._whyNotNowResult(reactionId)}
      ${this._linkedRows("Manual Holds", detail.linked_manual_holds || [], "scope")}
      ${this._linkedRows("Runtime Confirmations", detail.linked_runtime_confirmations || [], "request_id")}
      ${this._linkedRows("Promotion Reviews", detail.linked_promotion_reviews || [], "review_id")}
      ${this._linkedRows("Linked Proposals", detail.linked_proposals || [], "id")}
      ${this._traceSummary(detail.latest_trace)}
      ${this._rawDetails({
        configured_metadata: detail.configured_metadata || {},
        runtime_diagnostics: detail.runtime_diagnostics || {},
      })}
    `;
  }

  _manualHoldDetail(snapshot, scope) {
    const detail = snapshot.details?.manual_holds?.by_scope?.[scope];
    if (!detail) return `<div class="empty">Manual hold detail is unavailable.</div>`;
    const summary = detail.summary || {};
    return `
      <section class="detail-grid">
        ${this._detailSection("Hold", {
          scope: summary.scope,
          reason: summary.reason,
          release_policy: summary.release_policy,
          source_entity: summary.source_entity,
          age: this._duration(summary.age_s),
          expires_in: this._duration(summary.expires_in_s),
        })}
        ${this._detailSection("Links", {
          affected_reactions: (detail.affected_reaction_ids || []).join(", "),
          link_count: (detail.links || []).length,
        })}
      </section>
      ${this._rawDetails(summary)}
    `;
  }

  _runtimeConfirmationDetail(snapshot, requestId) {
    const detail = snapshot.details?.runtime_confirmations?.by_request_id?.[requestId];
    if (!detail) return `<div class="empty">Runtime confirmation detail is unavailable.</div>`;
    const summary = detail.summary || {};
    return `
      <section class="detail-grid">
        ${this._detailSection("Request", {
          request_id: summary.request_id,
          reaction_id: detail.reaction_id || summary.reaction_id,
          status_bucket: detail.status_bucket,
          status: summary.status,
          on_timeout: summary.on_timeout,
        })}
        ${this._detailSection("Delivery", {
          targets: (summary.confirmation_targets || []).join(", "),
          created_at: summary.created_at,
          expires_at: summary.expires_at,
        })}
        ${this._detailSection("Apply Result", summary.apply_result || {})}
      </section>
      ${this._rawDetails(summary)}
    `;
  }

  _proposalReviewRowDetail(snapshot, rowId) {
    const detail = snapshot.details?.proposals?.review_rows_by_id?.[rowId];
    if (!detail) return `<div class="empty">Proposal review detail is unavailable.</div>`;
    const summary = detail.summary || {};
    return `
      <section class="detail-grid">
        ${this._detailSection("Review Row", {
          row_type: summary.row_type,
          id: rowId,
          proposal_ids: (detail.proposal_ids || []).join(", "),
          predicted_state: summary.predicted_state,
          confidence: summary.confidence_avg ?? summary.confidence,
        })}
        ${this._detailSection("Evidence", {
          member_count: summary.member_count,
          support: `${summary.support_total ?? ""}/${summary.total_observations ?? ""}`,
          hour_range: `${summary.start_hour_bucket ?? ""}-${summary.end_hour_bucket ?? ""}`,
        })}
      </section>
      ${this._rawDetails(summary)}
    `;
  }

  _entityDetail(snapshot, entityId) {
    const detail = snapshot.details?.entities?.by_id?.[entityId];
    if (!detail) return `<div class="empty">Entity detail is unavailable.</div>`;
    return `
      <section class="detail-grid">
        ${this._detailSection("Entity", {
          entity_id: detail.entity_id,
          domain: detail.domain,
          reactions: (detail.reaction_ids || []).join(", "),
          traces: (detail.trace_ids || []).join(", "),
          holds: (detail.hold_scopes || []).join(", "),
          requests: (detail.request_ids || []).join(", "),
          policies: (detail.policy_ids || []).join(", "),
        })}
        ${this._detailSection("Counts", {
          apply_steps: (detail.apply_steps || []).length,
          pending_applies: (detail.pending_applies || []).length,
          source_metadata: (detail.source_metadata || []).length,
        })}
      </section>
      ${this._linkedRows("Apply Steps", detail.apply_steps || [], "step_id")}
      ${this._linkedRows("Pending Applies", detail.pending_applies || [], "step_id")}
      ${this._linkedRows("Source Metadata", detail.source_metadata || [], "kind")}
      ${this._rawDetails(detail)}
    `;
  }

  _detailSection(title, value) {
    const entries = Object.entries(value || {}).filter(([, item]) => item !== undefined);
    return `
      <div class="card">
        <div class="label">${this._escape(title)}</div>
        <table class="kv">
          <tbody>
            ${entries.length ? entries.map(([key, item]) => `
              <tr>
                <th>${this._escape(key)}</th>
                <td>${this._escape(this._formatDetailValue(item))}</td>
              </tr>
            `).join("") : `<tr><td>unavailable</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
  }

  _linkedRows(title, rows, primaryKey) {
    if (!rows.length) return "";
    return `
      <div class="detail-section">
        <h3>${this._escape(title)}</h3>
        <table>
          <tbody>
            ${rows.map((row) => `
              <tr>
                <td><span class="object-id">${this._escape(row[primaryKey] || "")}</span></td>
                <td>${this._escape(row.status || row.reason || row.type || row.row_type || "")}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  _traceSummary(trace) {
    if (!trace) return "";
    return `
      <div class="detail-section">
        <h3>Latest Trace</h3>
        ${this._detailSection("Trace", {
          trace_id: trace.trace_id,
          outcome: trace.outcome,
          reason_codes: (trace.reason_codes || []).join(", "),
          occurrence_key: trace.occurrence_key,
          timestamp: trace.timestamp,
        })}
      </div>
    `;
  }

  _whyNotNowResult(reactionId) {
    const result = this._inspectionResult;
    if (!result || result.reaction_id !== reactionId) return "";
    return `
      <div class="detail-section">
        <h3>Why Not Now</h3>
        <section class="detail-grid">
          ${this._detailSection("Focused Result", {
            outcome: result.outcome,
            reason_codes: (result.reason_codes || []).join(", "),
            generated_at: result.generated_at,
          })}
          ${this._detailSection("Input", result.input_summary || {})}
          ${this._detailSection("Policy", result.policy_result || {})}
        </section>
        ${this._linkedRows("Candidate Apply Steps", result.apply_steps || [], "step_id")}
        ${this._linkedRows("Guard Results", result.guard_results || [], "reason_code")}
        ${this._rawDetails(result)}
      </div>
    `;
  }

  _detailButton(kind, id) {
    if (!id) return "";
    return `
      <button
        class="inline"
        data-detail-kind="${this._escape(kind)}"
        data-detail-id="${this._escape(id)}"
      >Inspect</button>
    `;
  }

  _filterToolbar(section, placeholder) {
    const value = this._filters[section]?.text || "";
    return `
      <div class="toolbar">
        <input
          type="search"
          data-filter-section="${this._escape(section)}"
          data-filter-key="text"
          placeholder="${this._escape(placeholder)}"
          value="${this._escape(value)}"
        >
      </div>
    `;
  }

  _filterRows(section, rows) {
    const query = String(this._filters[section]?.text || "").trim().toLowerCase();
    if (!query) return rows;
    return rows.filter((row) => this._rowSearchText(row).includes(query));
  }

  _rowSearchText(value) {
    if (value === null || value === undefined) return "";
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
      return String(value).toLowerCase();
    }
    if (Array.isArray(value)) {
      return value.map((item) => this._rowSearchText(item)).join(" ");
    }
    if (typeof value === "object") {
      return Object.entries(value)
        .map(([key, item]) => `${key} ${this._rowSearchText(item)}`)
        .join(" ")
        .toLowerCase();
    }
    return "";
  }

  _filteredCount(filtered, total) {
    if (filtered === total) return "";
    return `<div class="empty">Showing ${this._escape(filtered)} of ${this._escape(total)} rows.</div>`;
  }

  _copyableId(value) {
    if (!value) return "";
    return `<span class="object-id">${this._escape(value)} ${this._copyButton(value)}</span>`;
  }

  _copyButton(value) {
    if (!value) return "";
    return `
      <button
        class="copy"
        data-copy-value="${this._escape(value)}"
        title="Copy value"
      >Copy</button>
    `;
  }

  async _copyValue(button) {
    const value = button.getAttribute("data-copy-value") || "";
    await this._copyText(value);
  }

  async _exportSnapshot(button) {
    const mode = button.getAttribute("data-export") || "";
    const payload = this._serializedSnapshot();
    if (!payload) return;
    if (mode === "copy") {
      await this._copyText(payload);
      return;
    }
    if (mode === "download") {
      this._downloadText(payload, this._snapshotFilename());
    }
  }

  async _runWhyNotNow(button) {
    const reactionId = button.getAttribute("data-inspect-why-not-now") || "";
    if (!reactionId || !this._hass?.callWS) return;
    this._inspectionError = "";
    button.disabled = true;
    try {
      const command =
        this._panel?.config?.whyNotNowCommand || "heima/observability/why_not_now";
      this._inspectionResult = await this._hass.callWS({
        type: command,
        reaction_id: reactionId,
      });
    } catch (err) {
      this._inspectionError = err?.message || "Unable to complete focused inspection.";
    } finally {
      button.disabled = false;
      this._render();
    }
  }

  _serializedSnapshot() {
    if (!this._snapshot) return "";
    return JSON.stringify(this._snapshot, null, 2);
  }

  async _copyText(value) {
    if (!value || !navigator.clipboard?.writeText) return;
    try {
      await navigator.clipboard.writeText(value);
    } catch (_err) {
      // Clipboard availability depends on the browser context.
    }
  }

  _downloadText(value, filename) {
    const blob = new Blob([value], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.rel = "noopener";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  _snapshotFilename() {
    const generatedAt = String(this._snapshot?.meta?.generated_at || "snapshot")
      .replaceAll(":", "")
      .replaceAll(".", "")
      .replaceAll("+", "Z");
    return `heima-observability-${generatedAt}.json`;
  }

  _restoreFilterFocus() {
    if (!this._focusFilter) return;
    const { section, key } = this._focusFilter;
    const input = Array.from(this.shadowRoot.querySelectorAll("[data-filter-section]")).find(
      (candidate) =>
        candidate.getAttribute("data-filter-section") === section &&
        candidate.getAttribute("data-filter-key") === key,
    );
    if (input && typeof input.focus === "function") {
      input.focus();
      const length = input.value.length;
      if (typeof input.setSelectionRange === "function") {
        input.setSelectionRange(length, length);
      }
    }
    this._focusFilter = null;
  }

  _formatDetailValue(value) {
    if (value === null) return "";
    if (Array.isArray(value)) return value.join(", ");
    if (typeof value === "object") return JSON.stringify(value);
    return String(value ?? "");
  }

  _metric(label, value) {
    return `
      <div class="card">
        <div class="label">${this._escape(label)}</div>
        <div class="value">${this._escape(String(value ?? ""))}</div>
      </div>
    `;
  }

  _objectSummary(title, value) {
    if (!value || !Object.keys(value).length) return "";
    return this._objectCard(title, value);
  }

  _objectCard(title, value) {
    const entries = Object.entries(value || {});
    return `
      <div class="card">
        <div class="label">${this._escape(title)}</div>
        <div>${entries.length ? entries.map(([key, count]) => `${this._escape(key)}: ${this._escape(this._compactValue(count))}`).join("<br>") : "none"}</div>
      </div>
    `;
  }

  _policyRoles(pushPolicy) {
    const policy = String(pushPolicy || "");
    const roles = [];
    if (policy.includes("admins")) roles.push("admins");
    if (policy.includes("residents")) roles.unshift("residents");
    return [...new Set(roles)];
  }

  _notificationPersistence(family, thresholds) {
    const value = thresholds?.[family];
    if (value === undefined || value === null) return "";
    return this._escape(this._duration(value));
  }

  _notificationAggregation(family, aggregation) {
    if (family === "people") {
      return this._escape(this._duration(aggregation?.presence_transition_window_s));
    }
    if (family === "occupancy_mismatch" || family === "security_presence_mismatch") {
      return this._escape(this._duration(aggregation?.mismatch_window_s));
    }
    return "";
  }

  _notificationDecisionDiagnostics(diagnostics) {
    if (!diagnostics || typeof diagnostics !== "object") return "";
    const keys = [
      "event_type",
      "pipeline_result",
      "persistence_key",
      "aggregation_key",
      "dedup_key",
      "rate_limit_key",
    ];
    return keys
      .filter((key) => diagnostics[key] !== undefined && diagnostics[key] !== null)
      .map((key) => `${key}=${this._compactValue(diagnostics[key])}`)
      .join("; ");
  }

  _compactValue(value) {
    if (value === null || value === undefined) return "";
    if (Array.isArray(value)) return value.join(", ");
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  }

  _executionPolicy(policy) {
    if (!policy || typeof policy !== "object") return "";
    const source = policy.source || "";
    const mode = policy.mode || "";
    const profile = policy.profile_id ? ` / ${policy.profile_id}` : "";
    const error = policy.config_error ? ` / ${policy.config_error}` : "";
    return this._escape(`${source}${mode ? `: ${mode}` : ""}${profile}${error}`);
  }

  _applyResult(result) {
    if (!result || typeof result !== "object") return "";
    const applied = result.applied_steps || 0;
    const blocked = result.blocked_steps || 0;
    const failed = result.failed_steps || 0;
    const skipped = result.skipped_steps || 0;
    return this._escape(`applied ${applied}, blocked ${blocked}, failed ${failed}, skipped ${skipped}`);
  }

  _proposalRowSummary(row) {
    if (row.row_type === "temporal_bundle") {
      return this._escape(
        `${row.member_count || 0} proposals, ${row.predicted_state || "unknown"}, hour ${row.start_hour_bucket ?? ""}-${row.end_hour_bucket ?? ""}`
      );
    }
    return this._escape(row.type || row.identity_key || "");
  }

  _rawDetails(value) {
    return `
      <details>
        <summary>raw</summary>
        <pre>${this._escape(JSON.stringify(value, null, 2))}</pre>
      </details>
    `;
  }

  _clearHoldButton(scope, label) {
    return `
      <button
        class="inline danger"
        data-action="clear_manual_hold"
        data-domain="${this._escape(scope.domain)}"
        data-subject-type="${this._escape(scope.subject_type)}"
        data-subject-id="${this._escape(scope.subject_id)}"
        data-label="${this._escape(label)}"
      >Clear</button>
    `;
  }

  _promotionReviewButtons(review) {
    const reactionId = String(review.reaction_id || "");
    if (!reactionId || review.status !== "pending_admin_review") {
      return "";
    }
    return `
      <button
        class="inline"
        data-action="review_runtime_promotion"
        data-reaction-id="${this._escape(reactionId)}"
        data-promotion-action="heima.promotion.approve_auto_apply"
      >Auto apply</button>
      <button
        class="inline"
        data-action="review_runtime_promotion"
        data-reaction-id="${this._escape(reactionId)}"
        data-promotion-action="heima.promotion.dismiss_not_now"
      >Not now</button>
      <button
        class="inline danger"
        data-action="review_runtime_promotion"
        data-reaction-id="${this._escape(reactionId)}"
        data-promotion-action="heima.promotion.disable_future_prompts"
      >Disable prompts</button>
      <button
        class="inline danger"
        data-action="reset_runtime_confirmation_promotion_state"
        data-reaction-id="${this._escape(reactionId)}"
      >Reset</button>
    `;
  }

  _proposalReviewButtons(row) {
    if (row.row_type === "temporal_bundle") {
      const proposalIds = Array.isArray(row.proposal_ids) ? row.proposal_ids : [];
      if (!proposalIds.length) return "";
      const encodedIds = this._escape(JSON.stringify(proposalIds));
      return `
        <button
          class="inline"
          data-action="review_proposal_batch"
          data-proposal-ids="${encodedIds}"
          data-decision="approved"
        >Accept bundle</button>
        <button
          class="inline danger"
          data-action="review_proposal_batch"
          data-proposal-ids="${encodedIds}"
          data-decision="rejected"
        >Reject bundle</button>
        <button
          class="inline danger"
          data-action="review_proposal_batch"
          data-proposal-ids="${encodedIds}"
          data-decision="rejected"
          data-dismiss-similar="true"
        >Dismiss similar</button>
      `;
    }
    const proposalId = String(row.proposal_id || "");
    if (!proposalId) return "";
    return `
      <button
        class="inline"
        data-action="review_proposal"
        data-proposal-id="${this._escape(proposalId)}"
        data-decision="approved"
      >Accept</button>
      <button
        class="inline danger"
        data-action="review_proposal"
        data-proposal-id="${this._escape(proposalId)}"
        data-decision="rejected"
      >Reject</button>
    `;
  }

  _manualHoldScopeParts(scope) {
    const parts = String(scope || "").split(":");
    if (parts.length < 3) return null;
    const [domain, subject_type, ...subjectParts] = parts;
    const subject_id = subjectParts.join(":");
    if (!domain || !subject_type || !subject_id) return null;
    return { domain, subject_type, subject_id };
  }

  async _runAction(button) {
    const action = button.getAttribute("data-action");
    if (
      ![
        "clear_manual_hold",
        "review_runtime_promotion",
        "reset_runtime_confirmation_promotion_state",
        "review_proposal",
        "review_proposal_batch",
      ].includes(action)
    ) {
      return;
    }
    const payload = this._actionPayload(button, action);
    if (!payload) return;
    const message = this._actionConfirmation(button, action);
    if (!window.confirm(message)) return;
    this._actionError = "";
    button.disabled = true;
    try {
      const command =
        this._panel?.config?.actionCommand || "heima/observability/action";
      const result = await this._hass.callWS({
        type: command,
        action,
        payload,
      });
      if (result?.snapshot) {
        this._snapshot = result.snapshot;
      } else {
        await this._loadSnapshot();
      }
    } catch (err) {
      this._actionError = err?.message || "Unable to complete Heima admin action.";
    } finally {
      button.disabled = false;
      this._render();
    }
  }

  _actionPayload(button, action) {
    if (action === "clear_manual_hold") {
      return {
        domain: button.getAttribute("data-domain") || "",
        subject_type: button.getAttribute("data-subject-type") || "",
        subject_id: button.getAttribute("data-subject-id") || "",
      };
    }
    if (action === "review_proposal") {
      return {
        proposal_id: button.getAttribute("data-proposal-id") || "",
        decision: button.getAttribute("data-decision") || "",
      };
    }
    if (action === "review_proposal_batch") {
      return {
        proposal_ids: this._jsonAttribute(button, "data-proposal-ids"),
        decision: button.getAttribute("data-decision") || "",
        dismiss_similar: button.getAttribute("data-dismiss-similar") === "true",
      };
    }
    const reactionId = button.getAttribute("data-reaction-id") || "";
    if (!reactionId) return null;
    if (action === "review_runtime_promotion") {
      return {
        reaction_id: reactionId,
        promotion_action: button.getAttribute("data-promotion-action") || "",
      };
    }
    return { reaction_id: reactionId };
  }

  _actionConfirmation(button, action) {
    if (action === "clear_manual_hold") {
      return `Clear manual hold ${button.getAttribute("data-label") || ""}?`;
    }
    const reactionId = button.getAttribute("data-reaction-id") || "";
    if (action === "reset_runtime_confirmation_promotion_state") {
      return `Reset runtime confirmation promotion state for ${reactionId}?`;
    }
    if (action === "review_proposal") {
      return `${this._decisionLabel(button.getAttribute("data-decision"))} proposal ${button.getAttribute("data-proposal-id") || ""}?`;
    }
    if (action === "review_proposal_batch") {
      const count = this._jsonAttribute(button, "data-proposal-ids").length;
      if (button.getAttribute("data-dismiss-similar") === "true") {
        return `Dismiss this bundle and similar hidden proposals (${count} visible proposal IDs)?`;
      }
      return `${this._decisionLabel(button.getAttribute("data-decision"))} proposal bundle with ${count} proposal IDs?`;
    }
    const promotionAction = button.getAttribute("data-promotion-action") || "";
    if (promotionAction === "heima.promotion.approve_auto_apply") {
      return `Promote ${reactionId} to auto apply?`;
    }
    if (promotionAction === "heima.promotion.disable_future_prompts") {
      return `Disable future promotion prompts for ${reactionId}?`;
    }
    return `Dismiss promotion prompt for ${reactionId} for now?`;
  }

  _decisionLabel(decision) {
    return decision === "approved" ? "Accept" : "Reject";
  }

  _jsonAttribute(button, attribute) {
    try {
      const value = JSON.parse(button.getAttribute(attribute) || "[]");
      return Array.isArray(value) ? value : [];
    } catch (_err) {
      return [];
    }
  }

  _recipientServices(value) {
    if (Array.isArray(value)) return value;
    if (value && typeof value === "object" && Array.isArray(value.notify_services)) {
      return value.notify_services;
    }
    return [];
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
