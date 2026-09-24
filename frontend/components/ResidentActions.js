import { useEffect, useRef, useState } from "react";
import Icon from "./Icon";
import { postJSON } from "../lib/api";

const CATS = [
  ["waterlogging", "Waterlogging", "जलभराव"],
  ["power_cut", "Power cut", "बिजली कटौती"],
  ["traffic_signal", "Signal not working", "सिग्नल बंद"],
  ["pothole", "Pothole", "गड्ढा"],
  ["streetlight", "Streetlight out", "स्ट्रीटलाइट बंद"],
  ["garbage", "Garbage", "कचरा"],
  ["noise", "Noise", "शोर"],
];

const T = {
  en: {
    report: "REPORT AN ISSUE", reportHelp: "Tap what you see. No name, no exact location: we only count it for your area.",
    sent: (t) => `Thank you. Report ${t} added to your area's signal.`, again: "You already reported this recently.",
    fail: "Could not send the report. Please try again.",
    alerts: "ALERTS FOR MY AREA", on: "Alerts on", off: "Turn on alerts", listen: "Read aloud",
    alertsHelp: "Get a notification on this device when your area turns red or is likely to get worse. Works while this page is open.",
    blocked: "Notifications are blocked in your browser settings.",
    title: "CityPulse alert",
  },
  hi: {
    report: "समस्या बताएं", reportHelp: "जो दिख रहा है उस पर टैप करें। न नाम, न सटीक जगह: हम इसे सिर्फ़ आपके इलाके में गिनते हैं।",
    sent: (t) => `धन्यवाद। रिपोर्ट ${t} आपके इलाके में जोड़ दी गई है।`, again: "आप यह हाल ही में बता चुके हैं।",
    fail: "रिपोर्ट नहीं भेजी जा सकी। कृपया फिर कोशिश करें।",
    alerts: "मेरे इलाके के अलर्ट", on: "अलर्ट चालू हैं", off: "अलर्ट चालू करें", listen: "सुनें",
    alertsHelp: "जब आपके इलाके में स्थिति खराब हो या बिगड़ने की संभावना हो, तो इस डिवाइस पर सूचना पाएं। यह पेज खुला रहने पर काम करता है।",
    blocked: "आपके ब्राउज़र में सूचनाएं बंद हैं।",
    title: "CityPulse अलर्ट",
  },
};

/** Resident actions: report an issue, opt in to area alerts, and hear the status read aloud. */
export default function ResidentActions({ zoneId, zone, forecast, lang = "en" }) {
  const t = T[lang];
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [alertsOn, setAlertsOn] = useState(false);
  const last = useRef({ status: null, direction: null });

  // restore the opt-in
  useEffect(() => {
    try {
      setAlertsOn(localStorage.getItem("cp_alerts") === "1" && Notification.permission === "granted");
    } catch {
      /* no Notification support */
    }
  }, []);

  // notify on transitions only (not every refresh)
  useEffect(() => {
    if (!zone) return;
    const prev = last.current;
    const becameAlert = zone.status === "alert" && prev.status && prev.status !== "alert";
    const turningWorse = forecast?.direction === "worse" && prev.direction && prev.direction !== "worse";
    if (alertsOn && (becameAlert || turningWorse)) {
      try {
        new Notification(t.title, { body: zone.resident?.[lang] || "", tag: `cp-${zoneId}` });
      } catch {
        /* ignore */
      }
    }
    last.current = { status: zone.status, direction: forecast?.direction };
  }, [zone?.status, forecast?.direction, alertsOn]);

  useEffect(() => {
    last.current = { status: null, direction: null }; // changing area should not fire an alert
    setMsg("");
  }, [zoneId]);

  async function report(category) {
    setBusy(true);
    setMsg("");
    try {
      const r = await postJSON("/api/report", { zone_id: zoneId, category });
      setMsg(r.ticket ? t.sent(r.ticket) : t.fail);
    } catch (e) {
      setMsg(String(e.message).endsWith("429") ? t.again : t.fail);
    } finally {
      setBusy(false);
    }
  }

  async function toggleAlerts() {
    if (alertsOn) {
      setAlertsOn(false);
      localStorage.setItem("cp_alerts", "0");
      return;
    }
    if (typeof Notification === "undefined") return setMsg(t.blocked);
    const p = await Notification.requestPermission();
    if (p !== "granted") return setMsg(t.blocked);
    setAlertsOn(true);
    localStorage.setItem("cp_alerts", "1");
  }

  function speak() {
    if (!zone || typeof speechSynthesis === "undefined") return;
    const u = new SpeechSynthesisUtterance(`${zone.resident?.[lang] || ""} ${(zone.resident?.[`tips_${lang}`] || []).join(" ")}`);
    u.lang = lang === "hi" ? "hi-IN" : "en-IN";
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
  }

  return (
    <>
      <section className="resident-card">
        <div className="eyebrow">{t.report}</div>
        <p>{t.reportHelp}</p>
        <div className="report-grid">
          {CATS.map(([id, en, hi]) => (
            <button key={id} className="report-chip" disabled={busy} onClick={() => report(id)}>
              {lang === "hi" ? hi : en}
            </button>
          ))}
        </div>
        {msg && <div className="report-msg">{msg}</div>}
      </section>

      <section className="resident-card">
        <div className="eyebrow">{t.alerts}</div>
        <p>{t.alertsHelp}</p>
        <div className="report-grid">
          <button className={`report-chip ${alertsOn ? "report-chip-on" : ""}`} onClick={toggleAlerts}>
            <Icon name="bell" size={14} /> {alertsOn ? t.on : t.off}
          </button>
          <button className="report-chip" onClick={speak}>
            <Icon name="message" size={14} /> {t.listen}
          </button>
        </div>
      </section>
    </>
  );
}
