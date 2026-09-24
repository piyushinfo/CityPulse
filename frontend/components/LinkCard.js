import { useState } from "react";
import { istTime } from "../lib/api";

const CONF_STYLE = {
  "strong pattern": "bg-red-50 text-red-700 border-red-200",
  "some pattern": "bg-amber-50 text-amber-700 border-amber-200",
  "new, unverified": "bg-slate-50 text-slate-600 border-slate-200",
};

export default function LinkCard({ link, zoneName }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Possible link · {zoneName}</span>
        <span className={`text-xs px-2 py-0.5 rounded-full border ${CONF_STYLE[link.confidence]}`}>{link.confidence}</span>
      </div>
      <p className="text-sm leading-snug">
        <b>{link.first.label}</b> → <b>{link.second.label}</b>
        <span className="text-slate-500"> ({link.gap_min} min apart)</span>
      </p>
      <button onClick={() => setOpen(!open)} className="mt-2 text-xs text-blue-600 hover:underline">
        {open ? "Hide evidence" : "Why we think this"}
      </button>
      {open && (
        <div className="mt-2 text-xs text-slate-600 space-y-1">
          <p>{link.text}</p>
          <p>First signal started {istTime(link.first.start)} IST; second {istTime(link.second.start)} IST.</p>
          {link.lift != null && <p>History check: these two occurred together {link.lift}× more often than chance.</p>}
          <p className="italic">This is a possible link, not a confirmed cause. Check official sources before acting.</p>
        </div>
      )}
    </div>
  );
}
