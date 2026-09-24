import Icon from "./Icon";

/** KPI tile in the same style as the Overview page. accent: cyan | green | amber | red | purple */
export default function Kpi({ icon = "activity", label, value, meta, accent = "cyan" }) {
  return (
    <div className={`kpi-card kpi-${accent}`}>
      <div className="kpi-top">
        <span className="kpi-icon">
          <Icon name={icon} size={17} />
        </span>
        <span>{label}</span>
      </div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-meta">{meta}</div>
    </div>
  );
}
