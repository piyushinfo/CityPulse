import { useEffect, useState } from "react";
import AppShell from "../components/AppShell";
import Kpi from "../components/Kpi";
import Icon from "../components/Icon";
import { getJSON, postJSON, istTime, useLiveState } from "../lib/api";

const COLUMNS = [
  ["open", "New", "alert"],
  ["acknowledged", "Acknowledged", "bell"],
  ["assigned", "Assigned", "users"],
  ["resolved", "Resolved", "shield"],
];

/** Officer workflow: every anomaly becomes a card an officer can acknowledge, assign and resolve. */
export default function Operations() {
  const { state: s } = useLiveState();
  const [board, setBoard] = useState(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(null);

  const refresh = () =>
    getJSON("/api/workflow")
      .then(setBoard)
      .catch(() => setError("Cannot reach the workflow API."));

  useEffect(() => {
    refresh();
  }, [s?.ts]);

  async function act(card, action, extra = {}) {
    setError("");
    try {
      await postJSON(`/api/workflow/${encodeURIComponent(card.id)}`, { action, by: "Control room", ...extra });
      refresh();
    } catch (e) {
      setError(`Could not ${action}: ${e.message}`);
    }
  }

  const cards = board?.cards || [];
  const m = board?.metrics;

  return (
    <AppShell active="/operations" title="Operations">
      <main className="page">
        <div className="page-hero">
          <div>
            <div className="eyebrow">OFFICER WORKFLOW</div>
            <h1>Operations board</h1>
            <p>
              Every anomaly becomes an incident card, pre-routed to the department that usually owns it.
              Acknowledge, assign and resolve; CityPulse measures how fast the city responds.
            </p>
          </div>
        </div>

        <div className="kpi-grid four">
          <Kpi icon="alert" label="Active incidents" value={m?.open_active ?? "–"} meta="signal still live, not resolved" accent="red" />
          <Kpi icon="bell" label="Time to acknowledge" value={m?.mean_minutes_to_acknowledge != null ? `${m.mean_minutes_to_acknowledge} min` : "–"} meta="mean, since card opened" accent="amber" />
          <Kpi icon="shield" label="Time to resolve" value={m?.mean_minutes_to_resolve != null ? `${m.mean_minutes_to_resolve} min` : "–"} meta="mean, since card opened" accent="green" />
          <Kpi icon="users" label="Resolved" value={m?.counts?.resolved ?? 0} meta={`${m?.counts?.cleared ?? 0} cleared on their own`} accent="purple" />
        </div>

        {error && <div className="resident-warning"><Icon name="alert" size={16} />{error}</div>}

        <div className="ops-board">
          {COLUMNS.map(([status, title, icon]) => {
            const col = cards.filter((c) => c.status === status);
            return (
              <section className="panel ops-column" key={status}>
                <div className="panel-head">
                  <div>
                    <div className="eyebrow"><Icon name={icon} size={12} /> {title.toUpperCase()}</div>
                    <h2>{col.length}</h2>
                  </div>
                </div>
                {col.length === 0 && <div className="empty-inline">Nothing here.</div>}
                {col.map((c) => (
                  <article key={c.id} className={`ops-card ${c.active ? "" : "ops-card-ended"}`}>
                    <div className="ops-card-top">
                      <span className="ops-sev" style={{ "--sev": c.peak_severity >= 0.6 ? "var(--red)" : "var(--amber)" }} />
                      <b>{c.label}</b>
                    </div>
                    <div className="ops-meta">
                      {c.zone_name} · opened {istTime(c.opened_at)}
                      {!c.active && " · signal ended"}
                    </div>
                    <p className="ops-text">{c.text}</p>
                    <div className="ops-team">
                      <Icon name="building" size={13} /> {c.assignee || c.suggested_team}
                      {!c.assignee && <span className="ops-suggested">suggested</span>}
                    </div>

                    <div className="ops-actions">
                      {(c.status === "open" || c.status === "cleared") && (
                        <button className="button ghost" onClick={() => act(c, "acknowledge")}>Acknowledge</button>
                      )}
                      {c.status !== "resolved" && (
                        <select
                          className="select"
                          value=""
                          onChange={(e) => e.target.value && act(c, "assign", { assignee: e.target.value })}
                        >
                          <option value="">Assign to…</option>
                          {(board?.teams || []).map((t) => <option key={t} value={t}>{t}</option>)}
                        </select>
                      )}
                      {c.status !== "resolved" ? (
                        <button className="button primary" onClick={() => act(c, "resolve", { note: "Resolved from control room" })}>Resolve</button>
                      ) : (
                        <button className="button ghost" onClick={() => act(c, "reopen")}>Reopen</button>
                      )}
                    </div>

                    <button className="text-link" onClick={() => setOpen(open === c.id ? null : c.id)}>
                      {open === c.id ? "Hide history" : `History (${c.history.length})`}
                    </button>
                    {open === c.id && (
                      <ul className="ops-history">
                        {c.history.map((h, i) => (
                          <li key={i}>
                            <span>{istTime(h.ts)}</span> {h.action}
                            {h.assignee && ` → ${h.assignee}`} · {h.by}
                            {h.note && <em> “{h.note}”</em>}
                          </li>
                        ))}
                      </ul>
                    )}
                  </article>
                ))}
              </section>
            );
          })}
        </div>
        <p className="footer-note">
          Cards whose signal ends before anyone acts are closed as “cleared”. Department routing is a suggestion; the officer decides.
        </p>
      </main>
    </AppShell>
  );
}
