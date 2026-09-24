import { useEffect, useState } from "react";
import { getJSON, post } from "../lib/api";
import Icon from "./Icon";

export default function ControlPanel({ active }) {
  const [list, setList] = useState([]);
  useEffect(() => { getJSON("/api/scenarios").then((d) => setList(d.scenarios)).catch(() => {}); }, []);
  return (
    <div className="scenario-panel">
      <div className="scenario-head"><div><div className="eyebrow">SCENARIO LAB</div><h2>Reproducible civic events</h2></div>{active && <span className="scenario-running"><span className="live-pip"/> running</span>}</div>
      <div className="scenario-buttons">{list.map((s) => <button key={s.name} onClick={() => post(`/api/scenario/${s.name}`)}><span className="scenario-icon"><Icon name={s.name.includes('heat') ? 'sun' : 'cloud'} size={15}/></span><span><b>{s.title}</b><small>Start controlled scenario</small></span><Icon name="arrow" size={14}/></button>)}<button onClick={() => post("/api/scenario/reset")}><span className="scenario-icon"><Icon name="reset" size={15}/></span><span><b>Reset City</b><small>Return to normal state</small></span><Icon name="arrow" size={14}/></button></div>
      {active && <div className="scenario-progress"><div><span>{active.title}</span><b>{active.steps_done}/{active.steps_total}</b></div><div className="scenario-bar"><span style={{width:`${Math.round((active.steps_done/Math.max(1,active.steps_total))*100)}%`}}/></div></div>}
    </div>
  );
}
