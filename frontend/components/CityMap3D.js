import { useEffect, useMemo, useState } from "react";
import DeckGL from "@deck.gl/react";
import { PolygonLayer, BitmapLayer } from "@deck.gl/layers";
import { TileLayer } from "@deck.gl/geo-layers";
import { useTheme } from "../lib/theme";

const RGB = { calm: [22, 163, 74], watch: [245, 158, 11], alert: [220, 38, 38] };

/** 3D city: each zone is an extruded hexagon. Height = stress, colour = status,
 *  and it "breathes" at the zone's heart rate. Loaded with next/dynamic (ssr:false). */
export default function CityMap3D({ zones, zoneStates, selected, onSelect, center }) {
  const { isLight } = useTheme();
  const [t, setT] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setT(performance.now() / 1000), 60);
    return () => clearInterval(id);
  }, []);

  const data = useMemo(() => {
    const byId = Object.fromEntries((zoneStates || []).map((z) => [z.id, z]));
    return zones.map((z) => ({ ...z, st: byId[z.id] || { status: "calm", score: 100, bpm: 60 } }));
  }, [zones, zoneStates]);

  const layers = [
    new TileLayer({
      id: "basemap",
      data: isLight ? "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png" : "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
      minZoom: 0, maxZoom: 19, tileSize: 256,
      renderSubLayers: (props) => {
        const [[west, south], [east, north]] = props.tile.boundingBox;
        return new BitmapLayer(props, { data: null, image: props.data, bounds: [west, south, east, north] });
      },
    }),
    new PolygonLayer({
      id: "zones",
      data,
      pickable: true,
      extruded: true,
      wireframe: true,
      getPolygon: (d) => d.polygon.map(([lat, lon]) => [lon, lat]),
      getElevation: (d) => (200 + (100 - d.st.score) * 30) * (1 + 0.06 * Math.sin(t * 2 * Math.PI * (d.st.bpm / 60))),
      getFillColor: (d) => [...RGB[d.st.status], d.id === selected ? 235 : 170],
      getLineColor: [255, 255, 255],
      updateTriggers: { getElevation: [t, data], getFillColor: [data, selected], data: [isLight] },
      onClick: ({ object }) => object && onSelect(selected === object.id ? null : object.id),
    }),
  ];

  return (
    <div style={{ position: "relative", height: "100%", minHeight: 380, borderRadius: 12, overflow: "hidden" }}>
      <DeckGL
        initialViewState={{ longitude: center[1], latitude: center[0], zoom: 11, pitch: 50, bearing: -15 }}
        controller={true}
        layers={layers}
        getTooltip={({ object }) => object && `${object.name}\nPulse ${object.st.score}/100 · ${object.st.bpm} bpm`}
      />
    </div>
  );
}
