"""Resident mode: one short, template-based message per zone in English and Hindi, plus practical tips.
No LLM here on purpose: every word is predictable, translatable and checkable."""
from ..analysis.anomaly import signal_key
from ..zones import zone_name

SHORT = {  # signal -> (English, Hindi)
    "weather:heavy_rain": ("heavy rain", "भारी बारिश"),
    "weather:heatwave": ("extreme heat", "भीषण गर्मी"),
    "air:pm25": ("poor air quality", "खराब हवा"),
    "power:outage": ("a power cut", "बिजली कटौती"),
    "transit:delays": ("buses running late", "बसें देरी से चल रही हैं"),
    "traffic:congestion": ("heavy traffic", "भारी ट्रैफिक"),
    "complaint:waterlogging": ("waterlogging reported", "जलभराव की शिकायतें"),
    "complaint:power_cut": ("many power-cut reports", "बिजली कटौती की कई शिकायतें"),
    "complaint:traffic_signal": ("traffic signals reported down", "ट्रैफिक सिग्नल बंद होने की शिकायतें"),
    "complaint:garbage": ("more garbage reports", "कचरे की शिकायतें बढ़ीं"),
    "complaint:streetlight": ("streetlights reported out", "स्ट्रीटलाइट बंद होने की शिकायतें"),
    "complaint:noise": ("more noise reports", "शोर की शिकायतें बढ़ीं"),
    "complaint:pothole": ("more pothole reports", "गड्ढों की शिकायतें बढ़ीं"),
}

TIPS = {  # signal -> (English, Hindi)
    "complaint:waterlogging": ("Avoid underpasses and low-lying roads.", "अंडरपास और निचली सड़कों से बचें।"),
    "weather:heavy_rain": ("Avoid underpasses and low-lying roads.", "अंडरपास और निचली सड़कों से बचें।"),
    "power:outage": ("Keep your phone charged.", "अपना फ़ोन चार्ज रखें।"),
    "complaint:power_cut": ("Keep your phone charged.", "अपना फ़ोन चार्ज रखें।"),
    "weather:heatwave": ("Stay indoors 12-4 pm and keep drinking water.", "दोपहर 12 से 4 बजे तक घर में रहें और पानी पीते रहें।"),
    "air:pm25": ("Cut down outdoor exercise; wear a mask if you are sensitive.", "बाहर व्यायाम कम करें; संवेदनशील हों तो मास्क पहनें।"),
    "transit:delays": ("Leave early; buses are running late.", "जल्दी निकलें; बसें देरी से चल रही हैं।"),
    "traffic:congestion": ("Allow extra travel time.", "यात्रा के लिए अतिरिक्त समय रखें।"),
    "complaint:traffic_signal": ("Drive slowly at junctions.", "चौराहों पर धीमे चलें।"),
}

STATUS = {"calm": ("All normal", "सब सामान्य"), "watch": ("Be alert", "सतर्क रहें"),
          "alert": ("Needs attention", "ध्यान दें")}
NEXT = {"worse": ("likely to get worse", "हालात बिगड़ सकते हैं"),
        "steady": ("likely to stay about the same", "लगभग ऐसे ही रहने की संभावना"),
        "better": ("likely to improve", "सुधार की संभावना")}


def _join(items, word):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + f" {word} " + items[-1]


def resident_message(zone, anomalies, fc):
    zid = zone["id"]
    mine = sorted([a for a in anomalies if a.zone_id in (zid, "city")], key=lambda a: -a.severity)
    sigs = []
    for a in mine:
        k = signal_key(a)
        if k in SHORT and k not in sigs:
            sigs.append(k)
    name_en, name_hi = zone_name(zid), zone_name(zid, "hi")
    st_en, st_hi = STATUS[zone["status"]]
    if not sigs:
        en, hi = f"All normal in {name_en} right now.", f"{name_hi} में अभी सब सामान्य है।"
    else:
        top = sigs[:3]
        en = f"{st_en}: {_join([SHORT[k][0] for k in top], 'and')} in {name_en}."
        hi = f"{st_hi}: {name_hi} में {_join([SHORT[k][1] for k in top], 'और')}।"
    if fc:
        n_en, n_hi = NEXT[fc["direction"]]
        en += f" Next hour: {n_en}."
        hi += f" अगले एक घंटे में: {n_hi}।"
    tips_en, tips_hi = [], []
    for k in sigs:
        if k in TIPS and TIPS[k][0] not in tips_en:
            tips_en.append(TIPS[k][0])
            tips_hi.append(TIPS[k][1])
    return {"en": en, "hi": hi, "tips_en": tips_en[:3], "tips_hi": tips_hi[:3]}
