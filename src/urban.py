"""Use case 8 — urbanisation signals from night-time lights.

Questions: where does the lit footprint of settlements expand, where are existing villages
newly electrified, where do new settlements appear, and does the equipment keep pace with
population growth?

Indicators per unit (region / district)
---------------------------------------
* **Lit area** (km²): VIIRS pixels above the detection threshold, every year (already in the
  annual table, ``lit_km2``) → robust annual growth (Theil–Sen on log).
* **Newly lit area** between the start and the end of the period, with *persistence* to avoid
  noise: dark in the first **two** years and lit in the last **two** years.
  - **electrified settlements**: newly lit pixels that were already inhabited at the start
    (≥ ``pop_min`` inhabitants, GHSL/WorldPop) → electrification of existing villages;
  - **new settlements**: newly lit pixels that were not inhabited → urban sprawl, new
    neighbourhoods, infrastructure.
* **Light lost**: lit in the first two years, dark in the last two (closures, conflicts…).
* **Population growth** (GHSL/WorldPop, modelled from censuses) and **urban share** (GHSL
  Degree of Urbanisation, SMOD ≥ 21).
* **Built-up growth** (GHSL BUILT-S, Sentinel-2/Landsat) — an *independent* satellite source,
  used to validate the light-based signals.

Typology (lit-area growth vs population growth, in percentage points per year)
* *Electrified urbanisation* — lit area grows faster than population;
* *Balanced growth* — both grow at a similar pace;
* *Unlit growth* — population grows faster than the lit area: equipment lags behind
  demography (informal settlements, electrification backlog);
* *Stable or declining*.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from .lang import LANG

log = logging.getLogger("ntl")
FR = LANG == "fr"

CLASS = {"fr": {"electrified": "Urbanisation électrifiée", "balanced": "Croissance équilibrée",
                "unlit": "Croissance non éclairée", "stable": "Stable ou en déclin", "na": "Indéterminé"},
         "en": {"electrified": "Electrified urbanisation", "balanced": "Balanced growth",
                "unlit": "Unlit growth", "stable": "Stable or declining", "na": "Undetermined"}}[LANG]
CLASS_COLOR = {"electrified": "#00704A", "balanced": "#3F7FC7", "unlit": "#eb6834", "stable": "#a9a8a2", "na": "#e1e0d9"}
CONF = {"fr": ("élevée", "moyenne", "faible"), "en": ("high", "medium", "low")}[LANG]
URBAN_VIS = {"settled": "f5c242", "electrified": "19c37d", "lost": "e34948"}


# --------------------------------------------------------------------------------------
# Earth Engine
# --------------------------------------------------------------------------------------
def _years(ctx):
    ys = [y for y in ctx.cfg.years if y in ctx.annual_years]
    if len(ys) < 4:
        raise RuntimeError("urbanisation: at least 4 annual composites are needed")
    return ys[0], ys[1], ys[-2], ys[-1]


def change_image(ctx):
    """Bands new, lost, electrified, settled (0/1) on the VIIRS grid, plus pop0, pop1."""
    import ee
    from . import preprocessing as pp
    cfg = ctx.cfg
    y0, y0b, y1a, y1 = _years(ctx)

    def lit(y):
        ref, _, _ = pp.annual_vnl(y, ctx.annual_years)
        return pp.clean_annual(ref, ctx.flare).select("rad").gte(cfg.noise_floor)
    l0, l0b, l1a, l1 = lit(y0), lit(y0b), lit(y1a), lit(y1)
    dark_start, lit_end = l0.Or(l0b).Not(), l1.And(l1a)
    lit_start, dark_end = l0.And(l0b), l1.Or(l1a).Not()
    new, lost = dark_start.And(lit_end), lit_start.And(dark_end)
    pop0, _ = pp.population_on_grid(y0, cfg, ctx.proj)
    pop1, _ = pp.population_on_grid(y1, cfg, ctx.proj)
    inhab0 = pop0.gte(cfg.pop_min)
    img = ee.Image.cat([new.rename("new"), lost.rename("lost"), new.And(inhab0).rename("electrified"),
                        new.And(inhab0.Not()).rename("settled"), pop0.rename("pop0"), pop1.rename("pop1")])
    return img, (y0, y1)


def _built_km2(ctx, epoch):
    import ee
    from .config import DATASETS
    col = ee.ImageCollection(DATASETS["ghsl_built"]["id"])
    b = col.filter(ee.Filter.calendarRange(epoch, epoch, "year")).first().select("built_surface")
    return b.unmask(0).reduceResolution(ee.Reducer.sum(), maxPixels=1024).reproject(ctx.proj).divide(1e6)


def urban_zonal(ctx, levels=("ADM0", "ADM1", "ADM2"), progress=print) -> pd.DataFrame:
    """Newly lit / electrified / new-settlement / lost areas and built-up change per unit."""
    import ee
    from .acquisition import _reduce, level_groups, merged_units
    from .config import DATASETS
    from .gee import fc_to_df
    cfg = ctx.cfg
    img, (y0, y1) = change_image(ctx)
    area = ee.Image.pixelArea().divide(1e6).reproject(ctx.proj)
    eps = list(range(1975, 2031, 5))
    e0 = max([e for e in eps if e <= y0], default=eps[0])
    e1 = min([e for e in eps if e >= y1], default=eps[-1])
    if e1 == e0:
        e0 = e1 - 5
    b0, b1 = _built_km2(ctx, e0), _built_km2(ctx, e1)
    built_up = b1.subtract(b0).gt(area.multiply(0.02))       # ≥ 2 % of the pixel newly built
    bands = ee.Image.cat([
        img.select("new").multiply(area).rename("new_lit_km2"),
        img.select("lost").multiply(area).rename("lost_lit_km2"),
        img.select("electrified").multiply(area).rename("electrified_km2"),
        img.select("settled").multiply(area).rename("settled_km2"),
        img.select("pop1").multiply(img.select("electrified")).rename("electrified_pop"),
        img.select("pop1").multiply(img.select("settled")).rename("settled_pop"),
        img.select("new").multiply(built_up).multiply(area).rename("new_lit_built_km2"),
        b0.rename("built0_km2"), b1.rename("built1_km2"),
    ])
    frames = []
    for grp in level_groups(levels):
        units = merged_units(ctx.fcs, grp)
        df = fc_to_df(_reduce(bands, units, DATASETS["viirs_annual_v22"]["scale"], cfg,
                              {"y0": y0, "y1": y1, "built_epoch0": e0, "built_epoch1": e1}),
                      f"urbanisation {'+'.join(grp)}")
        frames.append(df)
        progress(f"  Urbanisation [{'+'.join(grp)}] : {len(df)} unités ({y0}→{y1}, bâti GHSL {e0}→{e1})")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def change_png(ctx, out_dir: Path, bounds, dims: int = 1400) -> str:
    """PNG overlay (Web Mercator): gold = new settlement, green = electrified settlement, red = light lost."""
    import ee
    import requests
    from .gee import ee_call
    img, (y0, y1) = change_image(ctx)
    cls = (ee.Image(0).where(img.select("settled"), 1).where(img.select("electrified"), 2)
           .where(img.select("lost"), 3).selfMask().clip(ctx.region))
    vis = cls.visualize(min=1, max=3, palette=[URBAN_VIS["settled"], URBAN_VIS["electrified"], URBAN_VIS["lost"]])
    w, s, e, n = bounds
    rect = ee.Geometry.Rectangle([w, s, e, n], "EPSG:4326", False)
    url = ee_call(lambda: vis.getThumbURL({"region": rect, "dimensions": dims, "format": "png", "crs": "EPSG:3857"}),
                  "vignette urbanisation")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"urban_{y0}_{y1}.png"
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    (out_dir / name).write_bytes(r.content)
    return name


# --------------------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------------------
def classify_unit(lit_g, pop_g, gap=0.01, floor=0.01) -> str:
    if not (np.isfinite(lit_g) and np.isfinite(pop_g)):
        return "na"
    if lit_g - pop_g >= gap and lit_g >= floor:
        return "electrified"
    if pop_g - lit_g >= gap and pop_g >= floor:
        return "unlit"
    if lit_g >= floor and pop_g >= floor:
        return "balanced"
    return "stable"


def _unit_table(annual, change, level, names):
    from .indicators import theil_sen_growth
    a = annual[annual["level"] == level].sort_values("year")
    rows = []
    for uid, d in a.groupby("unit_id"):
        lg = theil_sen_growth(d["year"], d["lit_km2"]) if "lit_km2" in d else {"growth": np.nan}
        pg = theil_sen_growth(d["year"], d["pop"]) if "pop" in d else {"growth": np.nan}
        f, l = d.iloc[0], d.iloc[-1]
        us0 = f["pop_urban"] / f["pop"] if "pop_urban" in d and f["pop"] else np.nan
        us1 = l["pop_urban"] / l["pop"] if "pop_urban" in d and l["pop"] else np.nan
        rows.append({"unit_id": uid, "name": names.get(uid, uid), "level": level,
                     "lit0_km2": f.get("lit_km2"), "lit1_km2": l.get("lit_km2"),
                     "lit_growth": lg["growth"], "lit_growth_lo": lg.get("growth_lo"), "lit_growth_hi": lg.get("growth_hi"),
                     "lit_p": lg.get("p_value"), "pop0": f.get("pop"), "pop1": l.get("pop"), "pop_growth": pg["growth"],
                     "urban_share0": us0, "urban_share1": us1})
    t = pd.DataFrame(rows)
    if change is not None and len(change):
        c = change[change["level"] == level] if "level" in change else change
        keep = [k for k in ("unit_id", "new_lit_km2", "lost_lit_km2", "electrified_km2", "settled_km2", "electrified_pop",
                            "settled_pop", "new_lit_built_km2", "built0_km2", "built1_km2", "built_epoch0", "built_epoch1")
                if k in c]
        t = t.merge(c[keep], on="unit_id", how="left")
        if {"built0_km2", "built1_km2", "built_epoch0", "built_epoch1"} <= set(t.columns):
            yrs = (t["built_epoch1"] - t["built_epoch0"]).clip(lower=1)
            t["built_growth"] = (t["built1_km2"] / t["built0_km2"].replace(0, np.nan)) ** (1 / yrs) - 1
        if {"new_lit_km2", "new_lit_built_km2"} <= set(t.columns):
            t["new_lit_built_share"] = t["new_lit_built_km2"] / t["new_lit_km2"].replace(0, np.nan)
        if {"new_lit_km2", "lit0_km2"} <= set(t.columns):
            t["new_lit_share"] = t["new_lit_km2"] / t["lit0_km2"].replace(0, np.nan)
    t["gap_pp"] = 100 * (t["lit_growth"] - t["pop_growth"])
    t["class"] = [classify_unit(a_, b_) for a_, b_ in zip(t["lit_growth"], t["pop_growth"])]
    t["class_label"] = t["class"].map(CLASS)
    return t


def validate(t: pd.DataFrame) -> dict:
    """Spearman correlation, across units, between lit-area growth and GHSL built-up growth."""
    if "built_growth" not in t:
        return {"available": False}
    d = t[["lit_growth", "built_growth"]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(d) < 6:
        return {"available": False, "reason": "n < 6"}
    from scipy import stats
    rho, p = stats.spearmanr(d["lit_growth"], d["built_growth"])
    out = {"available": True, "source": "GHSL BUILT-S R2023A", "n": int(len(d)), "rho": float(rho), "p_value": float(p)}
    if "new_lit_built_share" in t:
        tot_new = t["new_lit_km2"].sum()
        out["new_lit_built_share"] = float(t["new_lit_built_km2"].sum() / tot_new) if tot_new else None
    return out


def analyse(annual: pd.DataFrame, change: pd.DataFrame | None, gdfs: dict, names: dict,
            wdi_urban: pd.DataFrame | None = None) -> dict:
    """Full use-case 8 analysis. Returns the result dict ``R["urban"]``."""
    if annual is None or "lit_km2" not in annual:
        return {"available": False, "reason": "no lit area in the annual table"}
    lvs = [lv for lv in ("ADM1", "ADM2") if lv in gdfs and (annual["level"] == lv).any()]
    finest = lvs[-1] if lvs else "ADM1"
    units = {lv: _unit_table(annual, change, lv, names) for lv in lvs}
    nat = annual[annual["level"] == "ADM0"].sort_values("year")
    series = pd.DataFrame({"year": nat["year"].astype(int), "lit_km2": nat["lit_km2"],
                           "pop": nat["pop"], "urban_share": nat["pop_urban"] / nat["pop"]})
    from .indicators import theil_sen_growth
    trend = {"lit": theil_sen_growth(series["year"], series["lit_km2"]),
             "pop": theil_sen_growth(series["year"], series["pop"])}
    totals = {}
    ch0 = change[change["level"] == "ADM0"] if change is not None and len(change) and "level" in change else None
    if ch0 is not None and len(ch0):
        r = ch0.iloc[0]
        totals = {k: float(r[k]) for k in ("new_lit_km2", "lost_lit_km2", "electrified_km2", "settled_km2",
                                           "electrified_pop", "settled_pop") if k in r}
        totals["y0"], totals["y1"] = int(r.get("y0", series["year"].min())), int(r.get("y1", series["year"].max()))
    val = validate(units[finest]) if finest in units else {"available": False}
    wdi = {}
    if wdi_urban is not None and len(wdi_urban):
        j = series.merge(wdi_urban, on="year").dropna()
        if len(j) >= 4:
            col = [c for c in wdi_urban.columns if c != "year"][0]
            wdi = {"variable": col, "n": int(len(j)), "corr": float(np.corrcoef(j["urban_share"], j[col])[0, 1]),
                   "table": j[["year", "urban_share", col]]}
    cc = units[finest]["class"].value_counts().to_dict() if finest in units else {}
    return {"available": True, "level": finest, "units": units, "series": series, "trend": trend, "totals": totals,
            "class_counts": cc, "validation": val, "wdi": wdi}


# --------------------------------------------------------------------------------------
# Messages
# --------------------------------------------------------------------------------------
def _pct(x, d=1, sign=True):
    if x is None or not np.isfinite(x):
        return "n.d." if FR else "n/a"
    s = f"{100 * x:+.{d}f}" if sign else f"{100 * x:.{d}f}"
    return (s.replace(".", ",") + " %") if FR else s + "%"


def _n(x, d=0):
    if x is None or not np.isfinite(x):
        return "n.d." if FR else "n/a"
    s = f"{x:,.{d}f}"
    return s.replace(",", " ").replace(".", ",") if FR else s


def key_messages(res: dict | None) -> list[dict]:
    if not res or not res.get("available"):
        return []
    tr, tot, cc, v = res["trend"], res.get("totals") or {}, res.get("class_counts") or {}, res.get("validation") or {}
    t = res["units"][res["level"]]
    top = t.sort_values("new_lit_km2" if "new_lit_km2" in t else "lit_growth", ascending=False).head(3)["name"].tolist()
    n = len(t)
    if FR:
        theme = "Urbanisation"
        txt = (f"La surface éclairée évolue de {_pct(tr['lit']['growth'])} par an, contre {_pct(tr['pop']['growth'])} pour la "
               f"population. Sur {n} unités {res['level']} : {cc.get('electrified', 0)} en urbanisation électrifiée, "
               f"{cc.get('balanced', 0)} en croissance équilibrée, {cc.get('unlit', 0)} en croissance non éclairée.")
        if tot:
            txt += (f" Entre {tot['y0']} et {tot['y1']}, {_n(tot.get('new_lit_km2'))} km² se sont allumés, dont "
                    f"{_n(tot.get('electrified_km2'))} km² de zones déjà habitées (≈ {_n(tot.get('electrified_pop', np.nan) / 1e3)} k "
                    f"habitants nouvellement éclairés).")
        txt += f" Plus forte extension : {', '.join(top)}."
        why = (f"corrélation de rang de {v['rho']:.2f} avec la croissance du bâti GHSL ({v['n']} unités)".replace(".", ",")
               if v.get("available") else "pas de validation par le bâti (GHSL) disponible")
    else:
        theme = "Urbanisation"
        txt = (f"The lit area changes by {_pct(tr['lit']['growth'])} per year, against {_pct(tr['pop']['growth'])} for "
               f"population. Of {n} {res['level']} units: {cc.get('electrified', 0)} show electrified urbanisation, "
               f"{cc.get('balanced', 0)} balanced growth, {cc.get('unlit', 0)} unlit growth.")
        if tot:
            txt += (f" Between {tot['y0']} and {tot['y1']}, {_n(tot.get('new_lit_km2'))} km² became lit, of which "
                    f"{_n(tot.get('electrified_km2'))} km² in already inhabited areas (≈ {_n(tot.get('electrified_pop', np.nan) / 1e3)}k "
                    f"newly lit inhabitants).")
        txt += f" Largest expansion: {', '.join(top)}."
        why = (f"rank correlation of {v['rho']:.2f} with GHSL built-up growth ({v['n']} units)"
               if v.get("available") else "no built-up (GHSL) validation available")
    conf = CONF[0] if v.get("available") and v["rho"] >= 0.7 and v["p_value"] < 0.01 else \
        CONF[1] if v.get("available") and v["rho"] >= 0.4 and v["p_value"] < 0.05 else CONF[2]
    return [{"theme": theme, "confidence": conf, "why": why, "text": txt}]


LIMITS = {
    "fr": [("Urbanisation", "La surface éclairée dépend du seuil de détection et du débordement de lumière (blooming) "
            "autour des villes ; un quartier raccordé mais peu éclairé reste invisible. La population (GHSL/WorldPop) est "
            "modélisée à partir des recensements : sa croissance n'est pas une observation indépendante, et les années "
            "entre deux millésimes sont interpolées.")],
    "en": [("Urbanisation", "The lit area depends on the detection threshold and on light blooming around cities; a "
            "connected but dimly lit neighbourhood stays invisible. Population (GHSL/WorldPop) is modelled from censuses: "
            "its growth is not an independent observation, and years between two epochs are interpolated.")],
}[LANG]


def recommendations(res: dict | None) -> list[str]:
    if not res or not res.get("available"):
        return []
    t = res["units"][res["level"]]
    unlit = t[t["class"] == "unlit"]["name"].head(4).tolist()
    if FR:
        r = ["Croiser les zones nouvellement éclairées avec les plans d'urbanisme et les registres de raccordement pour "
             "distinguer extension planifiée, habitat informel et électrification rurale."]
        if unlit:
            r.append(f"Prioriser l'équipement (réseau électrique, services) dans les unités où la population croît plus vite "
                     f"que la surface éclairée : {', '.join(unlit)}.")
    else:
        r = ["Cross newly lit areas with urban plans and grid-connection registers to tell planned expansion, informal "
             "settlements and rural electrification apart."]
        if unlit:
            r.append(f"Prioritise infrastructure (power grid, services) where population grows faster than the lit area: "
                     f"{', '.join(unlit)}.")
    return r
