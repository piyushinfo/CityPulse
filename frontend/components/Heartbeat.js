import { STATUS_COLOR } from "../lib/api";

/** One ECG beat drawn in a 100-wide box; spike height grows with stress. */
function beat(x0, amp) {
  const b = 20;
  return `L${x0 + 30} ${b} L${x0 + 35} ${b - 3} L${x0 + 40} ${b} L${x0 + 46} ${b} L${x0 + 49} ${b + 4 * amp} ` +
    `L${x0 + 53} ${b - 17 * amp} L${x0 + 57} ${b + 9 * amp} L${x0 + 61} ${b} L${x0 + 72} ${b} L${x0 + 80} ${b - 5} L${x0 + 88} ${b} L${x0 + 100} ${b}`;
}

export default function Heartbeat({ bpm = 60, status = "calm", height = 40, width = 160 }) {
  const amp = status === "alert" ? 1.1 : status === "watch" ? 0.85 : 0.65;
  const beats = 4; // 2 visible + 2 copies for the seamless loop
  let d = "M0 20 ";
  for (let i = 0; i < beats; i++) d += beat(i * 100, amp) + " ";
  const secondsPerBeat = 60 / Math.max(40, bpm);
  return (
    <div style={{ width, height, overflow: "hidden" }} aria-label={`${bpm} beats per minute, ${status}`}>
      <svg viewBox="0 0 400 40" preserveAspectRatio="none" className="ecg-track"
        style={{ width: width * 2, height, animationDuration: `${secondsPerBeat * 2}s` }}>
        <path d={d} fill="none" stroke={STATUS_COLOR[status]} strokeWidth="2.2" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      </svg>
    </div>
  );
}
