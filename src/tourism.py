"""Use case 7 — summer tourism: "the season seen from the sky".

For each district and each year, the **summer excess** is the log-ratio of light in the peak
months (July–August in the northern hemisphere, December–January in the southern one) to light
in the shoulder months of the same year (April–May and October–November, or their southern
equivalents). Physical effects (short summer nights, stray light, vegetation) also move this
ratio, so the median excess of *comparable* units — same latitude band, excluding the most
seasonal ones — is subtracted. What remains, the **net excess**, is the tourist inflow.

A unit is a **tourist zone** if its median net excess is ≥ ``min_excess`` (+10 %) and is
statistically positive over at least ``min_summers`` summers. A **season index** (base 100 in
``base_year``) follows the strength of each summer — the 2020 collapse and the recovery are
visible. Summers when Ramadan overlaps the peak or shoulder months are flagged (night-time
activity changes during Ramadan). With a file of hotel nights or arrivals, the indicator is
validated by correlation. No extra Earth Engine request is needed: the monthly VIIRS table of
use case 1 is reused.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .lang import LANG

# First day of Ramadan (Gregorian, astronomical estimates; ±1 day depending on the country)
RAMADAN_START = {
    2012: "2012-07-20", 2013: "2013-07-09", 2014: "2014-06-28", 2015: "2015-06-18", 2016: "2016-06-06",
    2017: "2017-05-27", 2018: "2018-05-16", 2019: "2019-05-06", 2020: "2020-04-24", 2021: "2021-04-13",
    2022: "2022-04-02", 2023: "2023-03-23", 2024: "2024-03-11", 2025: "2025-03-01", 2026: "2026-02-18",
    2027: "2027-02-08", 2028: "2028-01-28", 2029: "2029-01-16", 2030: "2030-01-06",
}
CLASS = {"fr": {"tourist": "Zone touristique", "none": "Non touristique", "na": "Indéterminé"},
         "en": {"tourist": "Tourist zone", "none": "Not touristic", "na": "Undetermined"}}[LANG]
CONF = {"fr": ("élevée", "moyenne", "faible"), "en": ("high", "medium", "low")}[LANG]
MONTHS = {"fr": ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."],
          "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]}[LANG]


@dataclass
class TourismParams:
    peak_months: tuple[int, ...] | None = None       # None -> from the hemisphere of the country
    shoulder_months: tuple[int, ...] | None = None
    min_excess: float = 0.10       # net summer excess (+10 %) to be called a tourist zone
    min_summers: int = 3           # summers with data needed
    alpha: float = 0.10            # significance of the net excess (one-sided t-test)
    lat_band: float = 1.0          # degrees: comparable units are within ± lat_band
    exclude_quantile: float = 0.75  # comparables exclude units above this quantile of excess
    base_year: int = 2019          # season index = 100 in this year

    def to_dict(self) -> dict:
        d = asdict(self)
        d["peak_months"] = list(d["peak_months"] or [])
        d["shoulder_months"] = list(d["shoulder_months"] or [])
        return d


def season_months(lat: float, p: TourismParams) -> tuple[tuple[int, ...], tuple[int, ...]]:
    if p.peak_months and p.shoulder_months:
        return tuple(p.peak_months), tuple(p.shoulder_months)
    if lat >= 0:
        return (7, 8), (4, 5, 10, 11)
    return (12, 1), (3, 4, 9, 10)


def ramadan_overlap(years, months: tuple[int, ...]) -> pd.DataFrame:
    """For each year, number of Ramadan days falling in ``months``."""
    rows = []
    for y in years:
        s = RAMADAN_START.get(int(y))
        if not s:
            rows.append({"year": int(y), "ramadan_days": np.nan})
            continue
        d = pd.date_range(s, periods=30, freq="D")
        rows.append({"year": int(y), "ramadan_start": s, "ramadan_days": int(np.isin(d.month, months).sum())})
    return pd.DataFrame(rows)


def unit_latitudes(gdfs: dict, level: str) -> pd.Series:
    g = gdfs[level]
    return pd.Series(g.geometry.representative_point().y.values, index=g["unit_id"].values)


def summer_excess(monthly: pd.DataFrame, level: str, peak, shoulder) -> pd.DataFrame:
    """unit × year table: mean light of peak and shoulder months and their log-ratio."""
    d = monthly[(monthly["level"] == level)].dropna(subset=["sol_adj"]).copy()
    d = d[d["sol_adj"] > 0]
    d["year"] = d["date"].dt.year
    d["month"] = d["date"].dt.month
    # southern summer straddles the new year: December belongs to the following summer
    if 12 in peak and 1 in peak:
        d.loc[d["month"] == 12, "year"] += 1
    pk = d[d["month"].isin(peak)].groupby(["unit_id", "year"])["sol_adj"].agg(["mean", "count"])
    sh = d[d["month"].isin(shoulder)].groupby(["unit_id", "year"])["sol_adj"].agg(["mean", "count"])
    t = pk.join(sh, lsuffix="_peak", rsuffix="_shoulder", how="inner").reset_index()
    t = t[(t["count_peak"] >= 1) & (t["count_shoulder"] >= 2)]
    t["excess"] = np.log(t["mean_peak"] / t["mean_shoulder"])
    return t.rename(columns={"mean_peak": "peak", "mean_shoulder": "shoulder"})


def comparable_reference(panel: pd.DataFrame, lat: pd.Series, p: TourismParams) -> pd.DataFrame:
    """Median excess of comparable units (same latitude band, not among the most seasonal)."""
    med = panel.groupby("unit_id")["excess"].median()
    cut = med.quantile(p.exclude_quantile)
    pool = med[med <= cut].index
    rows = []
    for (u, y), g in panel.groupby(["unit_id", "year"]):
        la = lat.get(u, np.nan)
        cand = [v for v in pool if v != u and abs(lat.get(v, np.inf) - la) <= p.lat_band]
        if len(cand) < 3:                                 # widen the band for isolated latitudes
            cand = [v for v in pool if v != u]
        ref = panel[(panel["year"] == y) & (panel["unit_id"].isin(cand))]["excess"]
        rows.append({"unit_id": u, "year": y, "ref": float(ref.median()) if len(ref) else np.nan,
                     "n_comparables": int(len(ref))})
    out = panel.merge(pd.DataFrame(rows), on=["unit_id", "year"], how="left")
    out["net"] = out["excess"] - out["ref"]
    return out


def classify(panel: pd.DataFrame, p: TourismParams, exclude_years=(2020, 2021)) -> pd.DataFrame:
    """Median net excess per unit, one-sided t-test, class and confidence.

    Pandemic summers are excluded from the classification (not from the season index): a
    resort is a resort even when tourists cannot travel.
    """
    from scipy import stats
    rows = []
    for u, g in panel.groupby("unit_id"):
        x = g[~g["year"].isin(exclude_years)]["net"].dropna()
        n = int(len(x))
        med = float(x.median()) if n else np.nan
        if n >= 2 and x.std(ddof=1) > 0:
            tt = stats.ttest_1samp(x, 0.0)
            pv = float(tt.pvalue / 2 if tt.statistic > 0 else 1 - tt.pvalue / 2)
        else:
            pv = np.nan
        gain = float(np.expm1(med)) if np.isfinite(med) else np.nan
        if n < p.min_summers:
            cls = "na"
        elif gain >= p.min_excess and pv < p.alpha:
            cls = "tourist"
        else:
            cls = "none"
        conf = (CONF[0] if (cls == "tourist" and pv < 0.01 and n >= 6) else
                CONF[1] if (cls == "tourist" and n >= p.min_summers) else CONF[2])
        rows.append({"unit_id": u, "n_summers": n, "excess_median": float(g["excess"].median()),
                     "ref_median": float(g["ref"].median()), "net_median": med, "net_gain": gain,
                     "p_value": pv, "class": cls, "class_label": CLASS[cls], "confidence": conf})
    return pd.DataFrame(rows)


def season_index(panel: pd.DataFrame, units: list[str], base_year: int) -> pd.DataFrame:
    """Strength of each summer in the tourist zones: mean net gain, as an index (base_year = 100)."""
    d = panel[panel["unit_id"].isin(units)].copy()
    if not len(d):
        return pd.DataFrame(columns=["year", "net_gain", "index"])
    d["gain"] = np.expm1(d["net"])
    # tourist light: peak-month light above what comparable units would show
    d["tourist_light"] = d["peak"] - d["shoulder"] * np.exp(d["ref"])
    s = d.groupby("year").agg(net_gain=("gain", "mean"), tourist_light=("tourist_light", "sum"),
                              n_units=("unit_id", "nunique")).reset_index()
    by = base_year if base_year in set(s["year"]) else int(s["year"].min())
    base = float(s.loc[s["year"] == by, "tourist_light"].iloc[0])
    s["index"] = 100 * s["tourist_light"] / base if base > 0 else np.nan
    s["base_year"] = by
    return s


def monthly_profile(monthly: pd.DataFrame, level: str, units_t: list[str]) -> pd.DataFrame:
    """Average seasonal profile (each unit-year normalised by its annual mean): tourist vs other units."""
    d = monthly[monthly["level"] == level].dropna(subset=["sol_adj"]).copy()
    d["year"] = d["date"].dt.year
    d = d[~d["year"].isin([2020, 2021])]
    d["rel"] = d["sol_adj"] / d.groupby(["unit_id", "year"])["sol_adj"].transform("mean")
    d["group"] = np.where(d["unit_id"].isin(units_t), "tourist", "other")
    out = d.groupby(["group", d["date"].dt.month])["rel"].mean().unstack(0).reset_index()
    return out.rename(columns={"date": "month"})


VAR_LABEL = {
    "fr": {"nights_millions": "les nuitées", "arrivals_millions": "les arrivées de touristes internationaux (WDI)"},
    "en": {"nights_millions": "hotel nights", "arrivals_millions": "international tourist arrivals (WDI)"},
}[LANG]


def validate(index: pd.DataFrame, stats_df: pd.DataFrame | None) -> dict:
    """Correlation between the season index and hotel nights / arrivals (levels and growth)."""
    if stats_df is None or not len(stats_df) or not len(index):
        return {"available": False}
    col = next((c for c in stats_df.columns if c != "year"), None)
    j = index.merge(stats_df[["year", col]], on="year").dropna()
    if len(j) < 4:
        return {"available": False, "reason": "n < 4"}
    from scipy import stats
    r, pv = stats.pearsonr(j["index"], j[col])
    out = {"available": True, "variable": col, "label": VAR_LABEL.get(col, col), "n": int(len(j)), "corr": float(r), "p_value": float(pv),
           "table": j[["year", "index", col]]}
    if len(j) >= 5:
        g1, g2 = np.diff(np.log(j["index"].clip(lower=1e-6))), np.diff(np.log(j[col].clip(lower=1e-9)))
        out["corr_growth"] = float(np.corrcoef(g1, g2)[0, 1])
    return out


def analyse(monthly: pd.DataFrame, gdfs: dict, names: dict, level: str | None = None,
            stats_df: pd.DataFrame | None = None, p: TourismParams | None = None) -> dict:
    """Full use-case 7 analysis. Returns the result dict ``R["tourism"]``."""
    p = p or TourismParams()
    level = level or ("ADM2" if "ADM2" in gdfs and len(gdfs["ADM2"]) >= 8 else "ADM1")
    lat = unit_latitudes(gdfs, level)
    country_lat = float(gdfs["ADM0"].geometry.representative_point().y.iloc[0])
    peak, shoulder = season_months(country_lat, p)
    panel = summer_excess(monthly, level, peak, shoulder)
    if panel["unit_id"].nunique() < 5:
        return {"available": False, "level": level, "params": p.to_dict(), "reason": "fewer than 5 units"}
    panel = comparable_reference(panel, lat, p)
    units = classify(panel, p)
    units["name"] = units["unit_id"].map(names)
    units["lat"] = units["unit_id"].map(lat)
    units = units.sort_values("net_median", ascending=False).reset_index(drop=True)
    tz = units[units["class"] == "tourist"]["unit_id"].tolist()
    idx = season_index(panel, tz, p.base_year)
    ram = ramadan_overlap(sorted(panel["year"].unique()), tuple(peak) + tuple(shoulder))
    if len(idx):
        idx = idx.merge(ram[["year", "ramadan_days"]], on="year", how="left")
    prof = monthly_profile(monthly, level, tz)
    val = validate(idx, stats_df)
    pd_ = p.to_dict()
    pd_["peak_months"], pd_["shoulder_months"] = list(peak), list(shoulder)
    return {"available": True, "level": level, "params": pd_, "panel": panel, "units": units,
            "tourist_units": tz, "n_tourist": len(tz), "n_units": int(len(units)), "index": idx,
            "ramadan": ram, "profile": prof, "validation": val}


# --------------------------------------------------------------------------------------
# Key message
# --------------------------------------------------------------------------------------
def _pct(x, d=0, sign=True):
    if x is None or not np.isfinite(x):
        return "n.d." if LANG == "fr" else "n/a"
    s = f"{100 * x:+.{d}f}" if sign else f"{100 * x:.{d}f}"
    return (s.replace(".", ",") + " %") if LANG == "fr" else s + "%"


def key_messages(res: dict | None) -> list[dict]:
    if not res or not res.get("available"):
        return []
    u = res["units"]
    t = u[u["class"] == "tourist"]
    idx = res["index"]
    v = res["validation"]
    names = ", ".join(t["name"].head(4).astype(str))
    y20 = idx[idx["year"] == 2020]["index"]
    last = idx.iloc[-1] if len(idx) else None
    if LANG == "fr":
        theme = "Tourisme estival"
        if len(t):
            txt = (f"{len(t)} unités sur {res['n_units']} ont un surcroît de lumière estival net d'au moins "
                   f"{_pct(res['params']['min_excess'], 0, False)} : {names}. Le surcroît net médian atteint "
                   f"{_pct(t['net_gain'].max())} dans la zone la plus touristique.")
            if len(y20) and last is not None:
                txt += (f" L'indice de saison (base 100 = {int(idx['base_year'].iloc[0])}) tombe à "
                        f"{y20.iloc[0]:.0f} en 2020 et vaut {last['index']:.0f} en {int(last['year'])}.")
        else:
            txt = "Aucune unité ne montre de surcroît estival net significatif : pas de saison touristique visible depuis l'espace."
        why = (f"corrélation de {v['corr']:.2f} avec {v.get('label', 'les nuitées')} ({v['n']} années)".replace(".", ",")
               if v.get("available") else "aucune statistique de nuitées pour valider l'indicateur")
    else:
        theme = "Summer tourism"
        if len(t):
            txt = (f"{len(t)} of {res['n_units']} units show a net summer light excess of at least "
                   f"{_pct(res['params']['min_excess'], 0, False)}: {names}. The median net excess reaches "
                   f"{_pct(t['net_gain'].max())} in the most touristic zone.")
            if len(y20) and last is not None:
                txt += (f" The season index (base 100 = {int(idx['base_year'].iloc[0])}) falls to "
                        f"{y20.iloc[0]:.0f} in 2020 and stands at {last['index']:.0f} in {int(last['year'])}.")
        else:
            txt = "No unit shows a significant net summer excess: no tourist season visible from space."
        why = (f"correlation of {v['corr']:.2f} with {v.get('label', 'hotel nights')} ({v['n']} years)" if v.get("available")
               else "no hotel-night statistics to validate the indicator")
    conf = (CONF[0] if v.get("available") and v["corr"] >= 0.8 else CONF[1] if v.get("available") and v["corr"] >= 0.5
            else CONF[2])
    return [{"theme": theme, "confidence": conf, "why": why, "text": txt}]


LIMITS = {
    "fr": [("Tourisme estival", "Le surcroît estival mesure toute hausse de lumière en été (résidences secondaires, "
            "diaspora, fêtes, chantiers), pas seulement le tourisme ; aux hautes latitudes, les nuits d'été très courtes "
            "réduisent les observations VIIRS. Le Ramadan modifie l'activité nocturne : les étés concernés sont signalés.")],
    "en": [("Summer tourism", "The summer excess captures any rise in summer light (second homes, diaspora visits, "
            "festivals, construction), not only tourism; at high latitudes, very short summer nights reduce VIIRS "
            "observations. Ramadan changes night-time activity: the summers concerned are flagged.")],
}[LANG]


def recommendations(res: dict | None) -> list[str]:
    if not res or not res.get("available") or not res.get("n_tourist"):
        return []
    if LANG == "fr":
        return ["Publier l'indice de saison touristique dès la fin de l'été (données VIIRS disponibles en quelques "
                "semaines), avant les statistiques de nuitées, et l'étalonner chaque année sur celles-ci."]
    return ["Publish the tourist season index right after the summer (VIIRS data are available within weeks), ahead "
            "of hotel-night statistics, and recalibrate it on them every year."]
