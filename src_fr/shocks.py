"""Shocks: event catalogue, impact and recovery measured on the seasonally adjusted series.

Events come from three sources, all optional except the first:
* a generic catalogue (COVID-19, which hit every country — dates of restrictions vary);
* events supplied by the user in `cfg.custom_events` (conflicts, disasters, energy crises,
  electrification programmes…), e.g. {"label": "Cyclone X", "start": "2019-03", "end": "2019-05",
  "type": "catastrophe"};
* an optional file exported from ACLED or EM-DAT (`cfg.events_csv`), aggregated by month.

Data-driven breaks (timeseries.detect_breaks) complement the catalogue: they find shocks
nobody listed, and they show which listed events left no visible trace in the lights.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

GENERIC_EVENTS = [
    {"id": "covid19", "label": "COVID-19", "type": "pandémie", "start": "2020-03-01", "end": "2021-06-30",
     "note": "Dates indicatives : les mesures de restriction varient selon les pays."},
]


def event_catalogue(cfg, first: pd.Timestamp, last: pd.Timestamp) -> pd.DataFrame:
    """Events overlapping the study period (generic + user + optional file)."""
    ev = [dict(e, source="catalogue générique") for e in GENERIC_EVENTS]
    for i, e in enumerate(cfg.custom_events):
        ev.append({"id": e.get("id", f"user{i + 1}"), "label": e["label"], "type": e.get("type", "autre"),
                   "start": e["start"], "end": e.get("end", e["start"]), "note": e.get("note", ""),
                   "source": e.get("source", "utilisateur")})
    if getattr(cfg, "events_csv", None):
        ev += load_events_file(cfg.events_csv)
    df = pd.DataFrame(ev)
    if df.empty:
        return df
    df["start"], df["end"] = pd.to_datetime(df["start"]), pd.to_datetime(df["end"])
    return df[(df["end"] >= first) & (df["start"] <= last)].reset_index(drop=True)


def load_events_file(path: str, top: int = 5) -> list[dict]:
    """Read an ACLED or EM-DAT export and keep the `top` most severe months/events.

    ACLED: columns event_date, fatalities → monthly fatalities; the months above the 95th
    percentile become events. EM-DAT: columns 'Start Year', 'Start Month', 'Disaster Type',
    'Total Deaths' or 'Total Affected'.
    """
    p = str(path)
    df = pd.read_excel(p) if p.endswith((".xlsx", ".xls")) else pd.read_csv(p)
    cols = {c.lower(): c for c in df.columns}
    out = []
    if "event_date" in cols and "fatalities" in cols:
        d = df.assign(m=pd.to_datetime(df[cols["event_date"]]).dt.to_period("M").dt.to_timestamp())
        g = d.groupby("m")[cols["fatalities"]].sum()
        thr = g.quantile(0.95)
        for m, v in g[g >= thr].nlargest(top).items():
            out.append({"id": f"acled_{m:%Y%m}", "label": f"Pic de violence ({int(v)} décès)", "type": "conflit",
                        "start": m, "end": m + pd.offsets.MonthEnd(0), "note": "ACLED", "source": "ACLED"})
    elif "start year" in cols:
        sev = cols.get("total affected") or cols.get("total deaths")
        d = df.copy()
        d["_m"] = d[cols.get("start month", cols["start year"])].fillna(1).astype(int)
        d["_d"] = pd.to_datetime(dict(year=d[cols["start year"]].astype(int), month=d["_m"].clip(1, 12), day=1))
        d = d.sort_values(sev, ascending=False).head(top) if sev else d.head(top)
        for _, r in d.iterrows():
            out.append({"id": f"emdat_{r['_d']:%Y%m}", "label": str(r.get(cols.get("disaster type", ""), "Catastrophe")),
                        "type": "catastrophe", "start": r["_d"], "end": r["_d"] + pd.offsets.MonthEnd(2),
                        "note": "EM-DAT", "source": "EM-DAT"})
    return out


def event_impact(stl: pd.DataFrame, start, end, pre_months: int = 12, horizon: int = 36) -> dict:
    """Impact of an event on the seasonally adjusted level and time to recovery.

    * baseline  : mean of the SA log-level over the `pre_months` before the start;
    * counterfactual : linear trend of the 24 pre-event months, extrapolated;
    * trough    : minimum SA level between start and end+6 months, in % of the baseline;
    * gap_vs_trend : mean deviation from the counterfactual during the event window;
    * recovery  : first month after the trough when the SA level is back to the baseline
                  (None if not recovered within `horizon` months or by the end of data).
    """
    sa = stl["sa"]
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    pre = sa[(sa.index < start) & (sa.index >= start - pd.DateOffset(months=pre_months))]
    if len(pre) < 6:
        return {"computable": False, "reason": "moins de 6 mois avant l'événement"}
    base = pre.mean()
    win = sa[(sa.index >= start) & (sa.index <= end + pd.DateOffset(months=6))]
    if len(win) == 0:
        return {"computable": False, "reason": "pas de données pendant l'événement"}
    trough_date = win.idxmin()
    trough_pct = float(100 * np.expm1(win.min() - base))
    pre24 = sa[(sa.index < start) & (sa.index >= start - pd.DateOffset(months=24))]
    t = np.arange(len(pre24))
    gap = np.nan
    if len(pre24) >= 12:
        b, a = np.polyfit(t, pre24.values, 1)
        during = sa[(sa.index >= start) & (sa.index <= end)]
        tt = np.arange(len(pre24), len(pre24) + len(during))
        gap = float(100 * np.mean(np.expm1(during.values - (a + b * tt)))) if len(during) else np.nan
    after = sa[(sa.index > trough_date) & (sa.index <= trough_date + pd.DateOffset(months=horizon))]
    rec = after[after >= base]
    rec_date = rec.index[0] if len(rec) else None
    months = (rec_date.year - start.year) * 12 + rec_date.month - start.month if rec_date is not None else None
    sig = abs(trough_pct) > 2 * 100 * float(np.std(pre.diff().dropna()) or np.nan)
    return {"computable": True, "baseline_level": float(np.exp(base)), "trough_date": trough_date,
            "trough_pct": trough_pct, "gap_vs_trend_pct": gap, "recovery_date": rec_date,
            "months_to_recovery": months, "recovered": rec_date is not None,
            "distinguishable_from_noise": bool(sig)}


def daily_index(daily: pd.DataFrame, unit_id: str, window: str, baseline_days: int = 60,
                roll: int = 7) -> pd.DataFrame:
    """Daily Black Marble index (100 = median of the first `baseline_days` of the window).

    A 7-day rolling median absorbs the lunar cycle residuals and cloudy days.
    """
    d = daily[(daily["unit_id"] == unit_id) & (daily["window"] == window)].sort_values("date")
    s = d.set_index("date")["sol_adj"]
    base = s.iloc[:baseline_days].median()
    out = pd.DataFrame({"raw": s, "index": 100 * s / base})
    out["index_smooth"] = out["index"].rolling(roll, min_periods=max(2, roll // 2), center=True).median()
    out["valid_frac"] = d.set_index("date")["valid_frac"]
    return out
