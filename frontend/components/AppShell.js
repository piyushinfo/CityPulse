import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useLiveState, istTime } from "../lib/api";
import Icon from "./Icon";
import { useTheme } from "../lib/theme";

const NAV = [
  ["/", "Overview", "grid"],
  ["/zones", "Zone Explorer", "map"],
  ["/incidents", "Incident Center", "alert"],
  ["/operations", "Operations", "users"],
  ["/analytics", "Analytics", "chart"],
  ["/correlations", "Correlation Lab", "link"],
  ["/forecast", "Forecast", "activity"],
  ["/replay", "Replay", "clock"],
  ["/feeds", "Data Feeds", "database"],
  ["/copilot", "AI Copilot", "cpu"],
  ["/backtest", "Backtest", "shield"],
];

export default function AppShell({ children, active = "/", title = "CityPulse" }) {
  const { state, conn } = useLiveState();
  const { theme, toggleTheme } = useTheme();
  const [search, setSearch] = useState("");
  const [openSearch, setOpenSearch] = useState(false);
  const [mobile, setMobile] = useState(false);
  const feedCount = useMemo(() => {
    if (!state?.feeds) return { live: 0, total: 0 };
    return { live: state.feeds.filter((f) => f.status === "live").length, total: state.feeds.length };
  }, [state]);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpenSearch(true); }
      if (e.key === "Escape") { setOpenSearch(false); setSearch(""); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const results = NAV.filter(([, label]) => label.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobile ? "sidebar-open" : ""}`}>
        <div className="brand-block">
          <div className="brand-mark"><span className="brand-heart">♥</span><span /></div>
          <div><div className="brand-name">CITY<span>PULSE</span></div><div className="brand-sub">JAIPUR CIVIC INTELLIGENCE</div></div>
        </div>
        <button className="mobile-close" onClick={() => setMobile(false)}>×</button>
        <div className="sidebar-label">COMMAND</div>
        <nav className="nav-list">
          {NAV.map(([href, label, icon]) => (
            <Link key={href} href={href} className={`nav-item ${active === href ? "nav-item-active" : ""}`} onClick={() => setMobile(false)}>
              <Icon name={icon} size={17} /> <span>{label}</span>
            </Link>
          ))}
        </nav>
        <div className="sidebar-label">PUBLIC</div>
        <Link href="/resident" className="nav-item" onClick={() => setMobile(false)}><Icon name="users" size={17}/><span>Resident View</span></Link>
        <Link href="/explain" className="nav-item" onClick={() => setMobile(false)}><Icon name="shield" size={17}/><span>Explainability</span></Link>
        <div className="sidebar-bottom">
          <div className="system-card">
            <div className="system-head"><span className={`live-pip ${conn === "live" ? "" : "warn"}`} />{conn === "live" ? "Backend connected" : `Backend ${conn}`}</div>
            <div className="system-meta">{feedCount.live}/{feedCount.total} feeds live</div>
            {state?.ts && <div className="system-meta">Updated {istTime(state.ts)} IST</div>}
          </div>
        </div>
      </aside>
      {mobile && <div className="sidebar-overlay" onClick={() => setMobile(false)} />}
      <div className="main-shell">
        <header className="topbar">
          <div className="topbar-left"><button className="mobile-menu" onClick={() => setMobile(true)}>☰</button><div><div className="topbar-title">{title}</div><div className="topbar-kicker">Live civic health intelligence</div></div></div>
          <div className="topbar-actions">
            <button className="search-pill" onClick={() => setOpenSearch(true)}><Icon name="search" size={16}/><span>Search CityPulse</span><kbd>Ctrl K</kbd></button>
            <Link href="/resident" className="icon-link" title="Resident view"><Icon name="users" size={18}/></Link>
            <Link href="/explain" className="icon-link" title="Explainability"><Icon name="shield" size={18}/></Link>
            <button className="theme-toggle" type="button" onClick={toggleTheme} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`} title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}>
              <Icon name={theme === "dark" ? "sun" : "moon"} size={16}/>
              <span>{theme === "dark" ? "Light" : "Dark"}</span>
            </button>
            <span className={`live-chip ${conn === "live" ? "live" : "warn"}`}><span className="live-pip" />{conn === "live" ? "LIVE" : conn.toUpperCase()}</span>
          </div>
        </header>
        {children}
      </div>
      {openSearch && (
        <div className="modal-backdrop" onClick={() => setOpenSearch(false)}>
          <div className="search-modal" onClick={(e) => e.stopPropagation()}>
            <div className="search-modal-head"><Icon name="search" size={18}/><input autoFocus value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Go to a CityPulse section…"/><span>ESC</span></div>
            <div className="search-results">{results.map(([href, label, icon]) => <Link key={href} href={href} onClick={() => setOpenSearch(false)}><Icon name={icon}/><span>{label}</span><Icon name="chevron" size={16}/></Link>)}{!results.length && <div className="search-empty">No matching section.</div>}</div>
          </div>
        </div>
      )}
    </div>
  );
}
