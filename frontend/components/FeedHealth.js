import { post } from "../lib/api";
import Icon from "./Icon";

const DOT = { live: "live", stale: "stale", offline: "offline", "not connected": "not-connected" };

export default function FeedHealth({ feeds = [], controls = false }) {
  return (
    <div className="feed-health">
      <div className="panel-head compact-head"><div><div className="eyebrow">PIPELINE</div><h2>Data feed health</h2></div><span className="muted-label">{feeds.filter(f=>f.status==='live').length}/{feeds.length} live</span></div>
      <div className="feed-health-list">
        {feeds.map((f) => (
          <div key={f.name} className="feed-health-row">
            <div className={`feed-health-icon ${DOT[f.status]}`}><Icon name={f.name==='traffic'?'traffic':f.name==='weather'?'cloud':f.name==='air'||f.name==='cpcb'?'air':f.name==='power'?'power':f.name==='transit'?'bus':'message'} size={14}/></div>
            <div className="feed-health-main"><b>{f.name}</b><span>{f.source}</span></div>
            <div className="feed-health-status"><span className={`status-text ${f.status}`}>{f.status}</span>{f.age_s != null && f.status !== 'offline' && <small>{f.age_s}s</small>}</div>
            {controls && f.status !== "not connected" && <button className="feed-control-button" onClick={() => post(`/api/feeds/${f.name}/${f.status === "offline" ? "revive" : "kill"}`)}>{f.status === "offline" ? "revive" : "kill"}</button>}
          </div>
        ))}
      </div>
    </div>
  );
}
