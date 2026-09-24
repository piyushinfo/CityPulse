import { useEffect, useRef, useState } from "react";

export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const WS_URL = API.replace(/^http/, "ws") + "/ws";

export async function getJSON(path) {
  const r = await fetch(API + path);
  if (!r.ok) throw new Error(path + " " + r.status);
  return r.json();
}

export async function post(path) {
  const r = await fetch(API + path, { method: "POST" });
  return r.json();
}

export async function postJSON(path, body) {
  const r = await fetch(API + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(path + " " + r.status);
  return r.json();
}

export const STATUS_COLOR = { calm: "#16a34a", watch: "#f59e0b", alert: "#dc2626" };

export function istTime(iso) {
  return new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit" });
}
export function istDateTime(iso) {
  return new Date(iso).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** Live state over WebSocket; falls back to polling /api/state if the socket drops. */
export function useLiveState() {
  const [state, setState] = useState(null);
  const [conn, setConn] = useState("connecting");
  const wsRef = useRef(null);

  useEffect(() => {
    let closed = false;
    let retry;
    let poll;

    const startPolling = () => {
      if (poll) return;
      poll = setInterval(() => getJSON("/api/state").then(setState).catch(() => setConn("offline")), 5000);
    };
    const stopPolling = () => { clearInterval(poll); poll = null; };

    const connect = () => {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      ws.onopen = () => { setConn("live"); stopPolling(); };
      ws.onmessage = (m) => setState(JSON.parse(m.data));
      ws.onclose = () => {
        if (closed) return;
        setConn("polling");
        startPolling();
        retry = setTimeout(connect, 3000);
      };
      ws.onerror = () => ws.close();
    };

    getJSON("/api/state").then(setState).catch(() => setConn("offline"));
    connect();
    return () => { closed = true; clearTimeout(retry); stopPolling(); wsRef.current && wsRef.current.close(); };
  }, []);

  return { state, conn };
}
