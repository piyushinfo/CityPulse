import { useEffect, useState } from "react";
import AppShell from "../components/AppShell";
import Kpi from "../components/Kpi";
import TrendChart from "../components/TrendChart";
import Icon from "../components/Icon";
import { getJSON, istDateTime } from "../lib/api";

/** "How do you know it works?" — the 3-day history replayed through the live code and scored. */
export default function Backtest() {
  const [bt, setBt] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getJSON("/api/backtest").then(setBt).catch(() => setError("Cannot reach the backtest API."));
  }, []);

  const sm = bt?.summary;

  return (
    <AppShell active="/backtest" title="Backtest">
      <main className="page">
        <div className="page-hero">
          <div>
            <div className="eyebrow">PROOF, NOT PROMISES</div>
            <h1>How well does CityPulse work?</h1>
            <p>
              We replay the last 3 days through the exact code that runs live, then score it: did it catch every storm
              and heatwave, how fast, did it warn early, and how often did it raise alarms in calm weather?
            </p>
          </div>
        </div>

        {error && <div className="resident-warning"><Icon name="alert" size={16} />{error}</div>}
        {!bt && !error && <div className="page-center">Replaying 3 days of history…</div>}

        {sm && (
          <>
            <div className="kpi-grid four">
              <Kpi icon="alert" label="Events detected" value={sm.events_detected} meta={`mean ${sm.mean_detection_min} min after onset`} accent="green" />
              <Kpi icon="clock" label="Warned early" value={sm.events_warned_early} meta={`mean ${sm.mean_warning_lead_min} min before onset`} accent="cyan" />
              <Kpi icon="activity" label="Forecast vs “no change”" value={`${sm.forecast_improvement_pct}% better`} meta={`error ${sm.forecast_mae} vs ${sm.naive_mae} pulse points`} accent="purple" />
              <Kpi icon="bell" label="Calm-weather alerts" value={`${sm.quiet_alerts_per_day}/day`} meta={`across 8 zones, ${sm.quiet_hours_checked} quiet hours checked`} accent="amber" />
            </div>

            <div className="grid-two">
              <section className="panel">
                <div className="panel-head">
                  <div>
                    <div className="eyebrow">EVENT BY EVENT</div>
                    <h2>Storms and heatwaves in the history</h2>
                  </div>
                </div>
                <div className="bt-table">
                  <div className="bt-row bt-head">
                    <span>Event</span><span>Started</span><span>Warned</span><span>Detected</span><span>Worst zone</span>
                  </div>
                  {bt.events.map((e) => (
                    <div className="bt-row" key={e.start}>
                      <span><b>{e.label}</b></span>
                      <span>{istDateTime(e.start)}</span>
                      <span>{e.warned_before_min != null ? `${e.warned_before_min} min before` : "no"}</span>
                      <span>{e.detected_after_min != null ? `+${e.detected_after_min} min` : "missed"}</span>
                      <span>{e.worst_zone} ({e.worst_score}/100)</span>
                    </div>
                  ))}
                </div>
              </section>

              <section className="panel">
                <div className="panel-head">
                  <div>
                    <div className="eyebrow">3 DAYS</div>
                    <h2>Worst-zone pulse over time</h2>
                  </div>
                </div>
                <TrendChart points={bt.series} valueKey="worst" height={190} stroke="var(--red)" />
                <p className="chart-axis-note">Each dip is an event above; flat stretches are calm weather.</p>
              </section>
            </div>

            <section className="panel bt-method">
              <div className="panel-head">
                <div>
                  <div className="eyebrow">METHOD</div>
                  <h2>What each number means</h2>
                </div>
              </div>
              <ul>
                <li><b>Detected:</b> minutes from event onset until an affected zone (flood-prone for rain, any for heat) turned red. Checked every 5 min.</li>
                <li><b>Warned early:</b> the first time in the 2 hours before onset that the next-hour forecast said “worse” for an affected zone.</li>
                <li><b>Forecast error:</b> mean absolute difference between the predicted next-hour pulse and the actual pulse an hour later, against a naive forecast that assumes nothing changes.</li>
                <li><b>Calm-weather alerts:</b> red zones seen during normal weather (excluding 2 hours of recovery after an event), per day across all 8 zones.</li>
              </ul>
              <p className="disclaimer-line"><Icon name="shield" size={14} /> {bt.caveat}</p>
            </section>
          </>
        )}
      </main>
    </AppShell>
  );
}
