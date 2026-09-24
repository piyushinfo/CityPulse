import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import AppShell from "../components/AppShell";
import StatusBadge from "../components/StatusBadge";
import Heartbeat from "../components/Heartbeat";
import TrendChart from "../components/TrendChart";
import MetricBar from "../components/MetricBar";
import ZoneDrawer from "../components/ZoneDrawer";
import Icon from "../components/Icon";
import ControlPanel from "../components/ControlPanel";
import FeedHealth from "../components/FeedHealth";
import Ticker from "../components/Ticker";
import { getJSON, useLiveState, STATUS_COLOR, istDateTime, istTime } from "../lib/api";

const MapLoading = () => <div className="map-loading" />;
const CityMap = dynamic(() => import("../components/CityMap"), { ssr: false, loading: MapLoading });
const CityMap3D = dynamic(() => import("../components/CityMap3D"), { ssr: false, loading: MapLoading });

function Section({ eyebrow, title, action, children, className = "" }) {
  return <section className={`panel ${className}`}><div className="panel-head"> <div><div className="eyebrow">{eyebrow}</div><h2>{title}</h2></div>{action}</div>{children}</section>;
}

function Kpi({ icon, label, value, meta, accent = "cyan" }) {
  return <div className={`kpi-card kpi-${accent}`}><div className="kpi-top"><span className="kpi-icon"><Icon name={icon} size={17}/></span><span>{label}</span></div><div className="kpi-value">{value}</div><div className="kpi-meta">{meta}</div></div>;
}

export default function Dashboard() {
  const { state: live, conn } = useLiveState();
  const [zones, setZones] = useState(null);
  const [selected, setSelected] = useState(null);
  const [showControls, setShowControls] = useState(false);
  const [view3d, setView3d] = useState(false);
  const [analytics, setAnalytics] = useState(null);

  useEffect(() => { getJSON("/api/zones").then(setZones).catch(() => {}); }, []);
  useEffect(() => { let id; const load=()=>getJSON("/api/analytics?hours=6&interval_min=15").then(setAnalytics).catch(()=>{}); load(); id=setInterval(load,30000); return ()=>clearInterval(id); }, []);

  const s = live;
  const zoneById = useMemo(() => Object.fromEntries((zones?.zones || []).map((z) => [z.id, z])), [zones]);
  if (!s || !zones) return <AppShell title="Command Center"><div className="page page-center">{conn === "offline" ? "Cannot reach the CityPulse API. Is the backend running on port 8000?" : "Taking the city's pulse…"}</div></AppShell>;

  const sortedZones = [...s.zones].sort((a, b) => a.score - b.score);
  const activeAlerts = s.alerts?.length || 0;
  const nonCalm = s.zones.filter(z => z.status !== "calm").length;
  const liveFeeds = s.feeds.filter(f => f.status === "live").length;
  const worsening = (s.forecast || []).filter(f => f.direction === "worse").sort((a, b) => a.next_hour - b.next_hour);
  const cityHistory = analytics?.points || [];
  const category = analytics?.category_breakdown || {};

  return (
    <AppShell active="/" title="Command Center">
      <main className="page">
        <div className="page-hero">
          <div><div className="eyebrow">JAIPUR · LIVE CITY STATUS</div><h1>The city's pulse, explained.</h1><p>One view across weather, air, traffic, transit, complaints and power.</p></div>
          <div className="hero-actions"><span className="timestamp"><span className="live-pip"/>Updated {istTime(s.ts)} IST</span><button className="button ghost" onClick={() => setShowControls(v => !v)}><Icon name="settings" size={15}/> Scenario Lab</button></div>
        </div>

        <div className="kpi-grid">
          <Kpi icon="activity" label="City pulse" value={`${s.city.score}/100`} meta={`${s.city.bpm} BPM · ${s.city.status === "calm" ? "calm" : s.city.status === "watch" ? "watch" : "needs attention"}`} accent={s.city.status === "alert" ? "red" : s.city.status === "watch" ? "amber" : "cyan"}/>
          <Kpi icon="alert" label="Active anomalies" value={s.anomalies.length} meta={`${nonCalm} zones not calm`} accent="red"/>
          <Kpi icon="link" label="Possible links" value={s.links.length} meta="association, not causation" accent="purple"/>
          <Kpi icon="wind" label="Next hour" value={worsening.length ? worsening[0].next_hour : s.city.score} meta={worsening.length ? "some zones may worsen" : "no significant worsening"} accent="amber"/>
          <Kpi icon="database" label="Data health" value={`${liveFeeds}/${s.feeds.length}`} meta="required feeds live" accent="green"/>
        </div>

        {showControls && <div className="control-grid"><ControlPanel active={s.scenario}/><FeedHealth feeds={s.feeds} controls/></div>}

        <div className="grid-main">
          <Section eyebrow="CITY MAP" title="Live civic heatmap" className="map-panel" action={<div className="segmented"><button className={!view3d ? "active" : ""} onClick={() => setView3d(false)}>2D</button><button className={view3d ? "active" : ""} onClick={() => setView3d(true)}>3D</button></div>}>
            <div className="map-wrap">
              {view3d ? <CityMap3D zones={zones.zones} zoneStates={s.zones} selected={selected} onSelect={setSelected} center={zones.center}/> : <CityMap zones={zones.zones} zoneStates={s.zones} selected={selected} onSelect={setSelected} center={zones.center}/>} 
              <div className="map-legend"><div><span className="legend-dot calm"/>Calm</div><div><span className="legend-dot watch"/>Watch</div><div><span className="legend-dot alert"/>Alert</div></div>
              {selected && <div className="map-selected"><span>{zoneById[selected]?.name}</span><button onClick={() => setSelected(null)}>×</button></div>}
            </div>
          </Section>

          <Section eyebrow="ZONE EXPLORER" title="What needs attention?" action={<span className="count-chip">{s.zones.length} zones</span>}>
            <div className="zone-list">
              {sortedZones.map((z, idx) => <button className={`zone-row ${selected === z.id ? "selected" : ""}`} key={z.id} onClick={() => setSelected(z.id)}>
                <div className="zone-rank">{String(idx + 1).padStart(2, "0")}</div><div className="zone-name-block"><strong>{z.name}</strong><span>{z.status} · {z.bpm} BPM</span></div><div className="zone-score" style={{color: STATUS_COLOR[z.status]}}>{z.score}</div><Heartbeat bpm={z.bpm} status={z.status} width={88} height={26}/><Icon name="chevron" size={15}/>
              </button>)}
            </div>
          </Section>
        </div>

        <div className="grid-two">
          <Section eyebrow="CITY STORY" title="Why the pulse looks this way" action={<StatusBadge status={s.city.status} compact/>}>
            <div className="story-card"><div className="story-score" style={{color: STATUS_COLOR[s.city.status]}}>{s.city.score}</div><Heartbeat bpm={s.city.bpm} status={s.city.status} width={250} height={52}/><p>{s.summary.text}</p><div className="grounded-badge"><Icon name={s.summary.source === "llm" ? "cpu" : "shield"} size={14}/>{s.summary.source === "llm" ? "AI summary · grounded + validated" : "Rule-based summary · deterministic"}</div></div>
            <div className="breakdown-list"> <MetricBar label="Weather" value={Math.min(100, (category.weather || 0) * 25)} icon="☁"/><MetricBar label="Traffic" value={Math.min(100, (category.traffic || 0) * 25)} icon="↗"/><MetricBar label="Complaints" value={Math.min(100, (category.complaint || 0) * 25)} icon="•"/><MetricBar label="Transit" value={Math.min(100, (category.transit || 0) * 25)} icon="□"/><MetricBar label="Power" value={Math.min(100, (category.power || 0) * 25)} icon="ϟ"/><MetricBar label="Air" value={Math.min(100, (category.air || 0) * 25)} icon="~"/></div>
          </Section>

          <Section eyebrow="TREND INTELLIGENCE" title="City pulse · last 6 hours" action={<span className="muted-label">15-minute samples</span>}>
            <TrendChart points={cityHistory.map(p => ({ score: p.city_score }))} valueKey="score" height={190}/>
            <div className="trend-footer"><div><span>Current</span><b>{s.city.score}</b></div><div><span>6h low</span><b>{cityHistory.length ? Math.min(...cityHistory.map(p => p.city_score)) : "—"}</b></div><div><span>6h high</span><b>{cityHistory.length ? Math.max(...cityHistory.map(p => p.city_score)) : "—"}</b></div><div><span>Worst zone</span><b>{zoneById[s.city.worst_zone]?.name || s.city.worst_zone}</b></div></div>
          </Section>
        </div>

        <div className="grid-three">
          <Section eyebrow="INCIDENT CENTER" title="Active signals" action={<a className="text-link" href="/incidents">View all →</a>}>
            {s.anomalies.length ? <div className="signal-list">{s.anomalies.slice(0, 6).map(a => <div className="signal-item" key={a.id}><span className="severity-bar" style={{height: `${25 + a.severity * 60}px`}}/><div><b>{a.label}</b><span>{a.text}</span></div><small>{a.kind === "spike" ? `${a.z}σ` : "threshold"}</small></div>)}</div> : <div className="empty-state">No unusual readings right now.</div>}
          </Section>
          <Section eyebrow="POSSIBLE LINKS" title="Signals moving together" action={<a className="text-link" href="/correlations">Explore →</a>}>
            {s.links.length ? s.links.slice(0, 4).map(l => <div className="link-row" key={l.id}><div className="link-chain"><span>{l.first.label}</span><Icon name="arrow" size={14}/><span>{l.second.label}</span></div><small>{l.confidence}{l.lift != null ? ` · ${l.lift}×` : ""}</small></div>) : <div className="empty-state">No connected issues detected right now.</div>}
            <div className="disclaimer-line"><Icon name="shield" size={13}/> Possible association, not confirmed causation.</div>
          </Section>
          <Section eyebrow="NEXT HOUR" title="Where things may change" action={<a className="text-link" href="/forecast">Forecast →</a>}>
            {worsening.length ? worsening.slice(0, 4).map(f => <div className="forecast-row" key={f.zone_id}><div><b>{zoneById[f.zone_id]?.name || f.zone_id}</b><span>{f.reason_en}</span></div><strong>{f.now} → {f.next_hour}</strong></div>) : <div className="empty-state">No zone is expected to worsen significantly.</div>}
          </Section>
        </div>

        <div className="grid-two">
          <Section eyebrow="AGENT ALERTS" title="What needs an operator" action={<a className="text-link" href="/incidents">Alert center →</a>}>
            {activeAlerts ? <div className="alert-list">{s.alerts.slice(0, 5).map((a, i) => <div className="alert-row" key={i}><span className="alert-icon"><Icon name="bell" size={15}/></span><div><b>{a.message}</b><span>{istDateTime(a.ts)} IST</span></div></div>)}</div> : <div className="empty-state">No active agent alerts. Monitoring is on.</div>}
          </Section>
          <Section eyebrow="LIVE FEED" title="Latest civic events" action={<span className="muted-label">15 latest</span>}><Ticker items={s.ticker}/></Section>
        </div>
        <div className="footer-note"><Icon name="shield" size={14}/> CityPulse never treats associations as confirmed causes. Public/simulated data can be delayed; feed health is shown explicitly.</div>
      </main>
      <ZoneDrawer zone={selected ? zoneById[selected] : null} onClose={() => setSelected(null)}/>
    </AppShell>
  );
}
