class HeimaAdminPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._snapshot = null;
    this._error = "";
    this._actionError = "";
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
    this._actionError = "";
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
            ${this._navButton("confirmations", "Confirmations")}
            ${this._navButton("notifications", "Notifications")}
            ${this._navButton("learning", "Learning")}
            ${this._navButton("proposals", "Proposals")}
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
    this.shadowRoot.querySelectorAll("button[data-action]").forEach((button) => {
      button.addEventListener("click", () => this._runAction(button));
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
    if (this._route === "confirmations") return "Runtime Confirmation Center";
    if (this._route === "notifications") return "Notification Routing Inspector";
    if (this._route === "learning") return "Learning Monitor";
    if (this._route === "proposals") return "Proposal Backlog Inspector";
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
    const body = this._bodyContent(snapshot);
    return `${actionError}${body}`;
  }

  _bodyContent(snapshot) {
    if (this._route === "activity") return this._activity(snapshot);
    if (this._route === "reactions") return this._reactions(snapshot);
    if (this._route === "holds") return this._manualHolds(snapshot);
    if (this._route === "confirmations") return this._confirmations(snapshot);
    if (this._route === "notifications") return this._notifications(snapshot);
    if (this._route === "learning") return this._learning(snapshot);
    if (this._route === "proposals") return this._proposals(snapshot);
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
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${holds.map((hold) => {
            const scope = this._manualHoldScopeParts(hold.scope || "");
            return `
            <tr>
              <td>${this._escape(hold.scope || "")}</td>
              <td>${this._escape(hold.reason || "")}</td>
              <td>${this._escape(hold.release_policy || "")}</td>
              <td>${this._duration(hold.age_s)}</td>
              <td>${this._escape(hold.source_entity || "")}</td>
              <td>${this._list(hold.affected_reaction_ids || [])}</td>
              <td>${scope ? this._clearHoldButton(scope, hold.scope || "") : ""}</td>
            </tr>
          `;
          }).join("")}
        </tbody>
      </table>
    `;
  }

  _confirmations(snapshot) {
    const confirmations = snapshot.runtime_confirmations || {};
    const pending = confirmations.pending || [];
    const completed = confirmations.recent_completed || [];
    const reviews = confirmations.promotion_reviews || [];
    return `
      <section class="grid">
        ${this._metric("Pending", pending.length)}
        ${this._metric("Recent Completed", completed.length)}
        ${this._metric("Stale Responses", confirmations.stale_responses || 0)}
        ${this._metric("Promotion Reviews", reviews.length)}
      </section>
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
          </tr>
        </thead>
        <tbody>
          ${requests.map((request) => `
            <tr>
              <td>${this._escape(request.request_id || "")}</td>
              <td>${this._escape(request.reaction_id || "")}</td>
              <td><span class="status">${this._escape(request.status || "")}</span></td>
              <td>${this._escape(request.on_timeout || "")}</td>
              <td>${this._list(request.confirmation_targets || [])}</td>
              <td>${this._applyResult(request.apply_result)}</td>
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
    return `
      <section class="grid">
        ${this._metric("Recipients", notifications.recipient_count || 0)}
        ${this._metric("Groups", notifications.group_count || 0)}
        ${this._metric("Route Targets", notifications.route_count || 0)}
        ${this._metric("Actionable Routes", (notifications.actionable_routes || []).length)}
      </section>
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
      ${this._reviewRowsTable(proposals.review_rows || [])}
      ${this._temporalBundlesTable(proposals.temporal_bundles || [])}
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
              <td>${this._escape(row.bundle_id || row.proposal_id || "")}</td>
              <td>${this._proposalRowSummary(row)}</td>
              <td>${this._escape(row.confidence_avg ?? row.confidence ?? "")}</td>
              <td>${this._proposalReviewButtons(row)}</td>
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
              <td>${this._escape(bundle.bundle_id || "")}</td>
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

  _notificationRoutesTable(notifications) {
    const routes = notifications.resolved_routes || [];
    const unresolved = notifications.unresolved_targets || [];
    const actionable = new Set(notifications.actionable_routes || []);
    const skipped = new Set(notifications.skipped_non_actionable_routes || []);
    if (!routes.length && !unresolved.length) {
      return `<div class="empty">No notification routes configured.</div>`;
    }
    return `
      <h2>Resolved Routes</h2>
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
        <div>${entries.length ? entries.map(([key, count]) => `${this._escape(key)}: ${this._escape(count)}`).join("<br>") : "none"}</div>
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
