import { useMemo } from "react";

export default function TrendChart({ points = [], valueKey = "score", height = 150, showGrid = true, stroke = "var(--cyan)" }) {
  const data = useMemo(() => points.map((p) => Number(p[valueKey] ?? p.score ?? 0)).filter(Number.isFinite), [points, valueKey]);
  if (!data.length) return <div className="chart-empty">No historical points available.</div>;
  const min = Math.min(...data, 0);
  const max = Math.max(...data, 100);
  const range = Math.max(1, max - min);
  const width = 600;
  const pad = 18;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  const pts = data.map((v, i) => {
    const x = pad + (i / Math.max(1, data.length - 1)) * innerW;
    const y = pad + (1 - (v - min) / range) * innerH;
    return [x, y];
  });
  const path = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const area = `${path} L ${pts[pts.length - 1][0]} ${height - pad} L ${pts[0][0]} ${height - pad} Z`;
  return (
    <svg className="trend-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="trend chart">
      {showGrid && [0.25, 0.5, 0.75].map((ratio) => <line key={ratio} x1={pad} x2={width - pad} y1={pad + innerH * ratio} y2={pad + innerH * ratio} className="chart-grid" />)}
      <path d={area} fill="url(#pulseFade)" />
      <path d={path} fill="none" stroke={stroke} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      <defs><linearGradient id="pulseFade" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor={stroke} stopOpacity=".25"/><stop offset="100%" stopColor={stroke} stopOpacity="0"/></linearGradient></defs>
      <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r="4.5" fill={stroke} />
    </svg>
  );
}
