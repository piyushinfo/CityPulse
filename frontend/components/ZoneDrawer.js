import { useEffect, useState } from "react";
import { getJSON, STATUS_COLOR, istDateTime } from "../lib/api";
import StatusBadge from "./StatusBadge";
import TrendChart from "./TrendChart";
import MetricBar from "./MetricBar";
import Icon from "./Icon";

export default function ZoneDrawer({ zone, onClose }) {
  const [detail, setDetail] = useState(null);
  useEffect(() => {
    if (!zone) return;
    setDetail(null);
    getJSON(`/api/zone/${zone.id}`).then(setDetail).catch(() => {});
  }, [zone]);
  if (!zone) return null;
  const trend = detail?.history || [];
  const latest = trend[trend.length - 1];
  const previous = trend[trend.length - 2];
  const delta = latest && previous ? latest.score - previous.score : 0;
  return (
    <div className="drawer-overlay" onClick={onClose}>
      <aside className="zone-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-head"><div><div className="eyebrow">ZONE INTELLIGENCE</div><h2>{zone.name}</h2><div className="drawer-sub">{zone.flood_prone ? "Flood-sensitive zone" : "Standard zone"}</div></div><button className="close-btn" onClick={onClose}>×</button></div>
        <div className="drawer-hero">
          <div><div className="hero-score" style={{ color: STATUS_COLOR[zone.status] }}>{zone.score}</div><div className="muted-label">pulse /100</div></div>
          <div className="hero-status"><StatusBadge status={zone.status}/><div className="bpm-big">{zone.bpm} <span>BPM</span></div></div>
        </div>
        <div className="drawer-card"><div className="drawer-card-head"><span>6h pulse trend</span>{detail && <span className={delta < 0 ? "trend-down" : "trend-up"}>{delta > 0 ? `+${delta}` : delta}</span>}</div><TrendChart points={trend} valueKey="score" height={150} /></div>
        <div className="drawer-grid">
          <div className="drawer-card mini"><div className="eyebrow">NOW</div><div className="mini-value">{zone.score}/100</div><div className="muted-label">{zone.status}</div></div>
          <div className="drawer-card mini"><div className="eyebrow">NEXT HOUR</div><div className="mini-value">{detail?.forecast?.next_hour ?? "—"}</div><div className={detail?.forecast?.direction === "worse" ? "trend-down" : "trend-up"}>{detail?.forecast?.direction || "—"}</div></div>
        </div>
        {detail?.forecast && <div className="drawer-card"><div className="eyebrow">OUTLOOK</div><p className="drawer-copy">{detail.forecast.reason_en}</p></div>}
        <div className="drawer-card"><div className="drawer-card-head"><span>Active signals</span><span className="muted-label">{detail?.anomalies?.length || 0}</span></div>{detail?.anomalies?.length ? detail.anomalies.map((a) => <div className="signal-row" key={a.id}><span className="signal-dot" style={{ background: a.severity >= .6 ? "var(--red)" : "var(--amber)" }}/><div><b>{a.label}</b><small>{a.text}</small></div></div>) : <div className="empty-inline">No anomalies in this zone right now.</div>}</div>
        <div className="drawer-card"><div className="drawer-card-head"><span>Possible links</span><Icon name="link" size={15}/></div>{detail?.links?.length ? detail.links.map((l) => <div className="link-mini" key={l.id}><b>{l.first.label}</b><span>→</span><b>{l.second.label}</b><small>{l.confidence}{l.lift != null ? ` · lift ${l.lift}×` : ""}</small></div>) : <div className="empty-inline">No links detected right now.</div>}</div>
        <div className="drawer-card"><div className="eyebrow">RECENT EVENTS</div>{detail?.events?.slice(0, 8).map((e, i) => <div className="event-mini" key={i}><span>{e.ts ? istDateTime(e.ts) : "—"}</span><b>{e.subtype?.replace(/_/g, " ")}</b></div>)}</div>
      </aside>
    </div>
  );
}
