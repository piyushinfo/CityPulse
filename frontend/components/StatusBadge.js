import { STATUS_COLOR } from "../lib/api";

const LABEL = { calm: "CALM", watch: "WATCH", alert: "ALERT" };

export default function StatusBadge({ status = "calm", compact = false }) {
  const color = STATUS_COLOR[status] || STATUS_COLOR.calm;
  return (
    <span className={`status-badge ${compact ? "status-badge-compact" : ""}`} style={{ "--status": color }}>
      <span className="status-dot" /> {LABEL[status] || status}
    </span>
  );
}
