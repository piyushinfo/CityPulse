import { MapContainer, TileLayer, Polygon, CircleMarker, Tooltip } from "react-leaflet";
import { useEffect, useState } from "react";
import { STATUS_COLOR } from "../lib/api";
import { useTheme } from "../lib/theme";

/** Loaded with next/dynamic (ssr:false) because Leaflet needs window. */
export default function CityMap({ zones, zoneStates, selected, onSelect, center }) {
  const { isLight } = useTheme();
  const [tiles, setTiles] = useState(false);
  useEffect(() => setTiles(isLight), [isLight]);
  const byId = Object.fromEntries((zoneStates || []).map((z) => [z.id, z]));
  return (
    <MapContainer center={center} zoom={11} scrollWheelZoom={false} style={{ height: "100%", minHeight: 380 }}>
      <TileLayer
        attribution='&copy; OpenStreetMap contributors &copy; CARTO'
        url={tiles ? "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" : "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"}
      />
      {zones.map((z) => {
        const st = byId[z.id] || { status: "calm", score: 100, bpm: 60 };
        const color = STATUS_COLOR[st.status];
        return (
          <Polygon key={z.id + st.status + (selected === z.id)} positions={z.polygon}
            pathOptions={{ color, weight: selected === z.id ? 3 : 1.2, fillColor: color, fillOpacity: st.status === "calm" ? 0.12 : 0.28 }}
            eventHandlers={{ click: () => onSelect(selected === z.id ? null : z.id) }}>
            <Tooltip direction="top" sticky>
              <b>{z.name}</b><br />Pulse {st.score}/100 · {st.bpm} bpm · {st.status}
            </Tooltip>
          </Polygon>
        );
      })}
      {zones.map((z) => {
        const st = byId[z.id];
        if (!st || st.status === "calm") return null;
        return (
          <CircleMarker key={"c" + z.id + st.bpm} center={z.center} radius={6 + (100 - st.score) / 7}
            pathOptions={{ color: STATUS_COLOR[st.status], fillOpacity: 0.6, weight: 1 }} />
        );
      })}
    </MapContainer>
  );
}
