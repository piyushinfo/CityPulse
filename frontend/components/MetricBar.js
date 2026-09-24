export default function MetricBar({ label, value, suffix = "", icon, muted = false }) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div className="metric-row">
      <div className="metric-label"><span>{icon}</span>{label}</div>
      <div className="metric-track"><span style={{ width: `${pct}%` }} /></div>
      <div className={`metric-value ${muted ? "muted" : ""}`}>{value}{suffix}</div>
    </div>
  );
}
