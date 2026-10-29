"""Analysis steps of the notebook, one function per section, returning plain result dicts.

The notebook calls these functions and displays/interprets their outputs; keeping the logic
here makes it testable and reusable (e.g. in a batch run over several countries).
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from . import econometrics as eco
from . import indicators as ind
from . import shocks as sh
from . import timeseries as ts

log = logging.getLogger("ntl")


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------
LABEL = {"ADM1": "Region", "ADM2": "District"}


def unit_names(gdfs: dict) -> dict:
    """unit_id -> display name ('District (Region)' for ADM2 to disambiguate homonyms)."""
    from .boundaries import bad_name
    out = {}
    for lv, g in gdfs.items():
        k = 0
        for _, r in g.iterrows():
            nm = r["name"]
            if bad_name(nm):   # missing or "????" name (non-Latin script lost upstream)
                k += 1
                nm = f"%s {k}" % LABEL.get(lv, lv)
            nm = str(nm)
            parent = r.get("parent_name")
            if lv == "ADM2" and parent and not bad_name(parent):
                nm = f"{nm} ({parent})"
            out[r["unit_id"]] = nm
    return out


def finest_level(gdfs: dict) -> str:
    return "ADM2" if "ADM2" in gdfs and len(gdfs["ADM2"]) >= 8 else "ADM1"


def national_id(gdfs: dict) -> str:
    return gdfs["ADM0"]["unit_id"].iloc[0]


def attach_parent(df: pd.DataFrame, gdfs: dict) -> pd.DataFrame:
    if "ADM2" not in gdfs:
        return df.assign(parent_id=None)
    par = gdfs["ADM2"].set_index("unit_id")["parent_id"]
    return df.assign(parent_id=df["unit_id"].map(par))


# --------------------------------------------------------------------------------------
# Section 5 — temporal dynamics
# --------------------------------------------------------------------------------------
def dynamics(monthly: pd.DataFrame, annual: pd.DataFrame, gdfs: dict, cfg) -> dict:
    """National STL, anomalies, breaks; ADM1 seasonally adjusted series and recent growth."""
    nid = national_id(gdfs)
    nat = monthly[monthly["unit_id"] == nid].set_index("date")["sol_adj"]
    stl = ts.stl_decompose(nat, cfg.stl_period)
    anom = ts.anomalies(stl, cfg.anomaly_z, cfg.anomaly_min_effect)
    brk = ts.detect_breaks(stl["sa"], cfg.break_penalty, cfg.break_min_months)
    yoy = ts.yoy_growth(nat)
    last = stl.index.max()
    last12 = stl["sa_level"][stl.index > last - pd.DateOffset(months=12)].mean()
    prev12 = stl["sa_level"][(stl.index <= last - pd.DateOffset(months=12)) &
                             (stl.index > last - pd.DateOffset(months=24))].mean()
    adm1_stl, rows = {}, []
    for uid, g in monthly[monthly["level"] == "ADM1"].groupby("unit_id"):
        try:
            s = ts.stl_decompose(g.set_index("date")["sol_adj"], cfg.stl_period)
        except ValueError as e:
            log.info("STL not possible for %s: %s", uid, e)
            continue
        adm1_stl[uid] = s
        a = s["sa_level"][s.index > s.index.max() - pd.DateOffset(months=12)].mean()
        b = s["sa_level"][(s.index <= s.index.max() - pd.DateOffset(months=12)) &
                          (s.index > s.index.max() - pd.DateOffset(months=24))].mean()
        rows.append({"unit_id": uid, "growth_last12": a / b - 1 if b > 0 else np.nan,
                     "missing_share": float(g["sol_adj"].isna().mean())})
    coverage = monthly[monthly["unit_id"] == nid]["valid_frac"]
    nat_annual = annual[annual["level"] == "ADM0"].sort_values("year")
    return {"stl": stl, "anomalies": anom, "breaks": brk, "yoy": yoy,
            "growth_last12": float(last12 / prev12 - 1) if prev12 > 0 else np.nan,
            "last_month": last, "adm1_stl": adm1_stl, "adm1_recent": pd.DataFrame(rows),
            "national_annual": nat_annual,
            "national_trend": ind.theil_sen_growth(nat_annual["year"], nat_annual["sol"]),
            "months_excluded_share": float(nat.isna().mean()),
            "mean_valid_frac": float(coverage.mean())}


# --------------------------------------------------------------------------------------
# Section 6 — regional growth and convergence
# --------------------------------------------------------------------------------------
def regional_growth(annual: pd.DataFrame, gdfs: dict, cfg, no2: pd.DataFrame | None = None) -> dict:
    out = {"trends": {}, "concentration": {}, "class_counts": {}}
    for lv in [lv for lv in ("ADM1", "ADM2") if lv in gdfs]:
        d = annual[annual["level"] == lv]
        tr = ind.unit_trends(d, "sol", cfg.growth_threshold, cfg.alpha)
        tr_pc = ind.unit_trends(d.assign(sol_pc=d["sol"] / d["pop"].where(d["pop"] > 0)), "sol_pc",
                                cfg.growth_threshold, cfg.alpha)
        tr = tr.merge(tr_pc[["unit_id", "growth", "class"]].rename(
            columns={"growth": "growth_pc", "class": "class_pc"}), on="unit_id", how="left")
        last = d[d["year"] == d["year"].max()].set_index("unit_id")
        tr["share_last"] = tr["unit_id"].map(last["sol"] / last["sol"].sum())
        tr["sol_pc_last"] = tr["unit_id"].map(last["sol"] / last["pop"].where(last["pop"] > 0))
        out["trends"][lv] = tr
        out["class_counts"][lv] = tr["class"].value_counts().to_dict()
        out["concentration"][lv] = pd.DataFrame(
            [dict(year=y, **ind.concentration(g["sol"].values, g["unit_id"].values))
             for y, g in d.groupby("year")])
    fl = finest_level(gdfs)
    d = annual[annual["level"] == fl].copy()
    d["sol_pc"] = d["sol"] / d["pop"].where(d["pop"] > 0)
    tr = out["trends"][fl]
    y0 = d["year"].min()
    init = d[d["year"] == y0].set_index("unit_id")["sol_pc"]
    pc_tr = ind.unit_trends(d, "sol_pc", cfg.growth_threshold, cfg.alpha).set_index("unit_id")
    m = pd.DataFrame({"init": init, "g": pc_tr["growth"]}).replace([np.inf, -np.inf], np.nan).dropna()
    m = m[m["init"] > 0]
    out["beta_convergence"] = dict(ind.beta_convergence(m["init"], m["g"]), level=fl, first_year=int(y0))
    out["beta_data"] = m.reset_index().rename(columns={"index": "unit_id"})
    out["sigma_convergence"] = ind.sigma_convergence(d, "sol_pc")
    if no2 is not None and len(no2):
        last_y = int(no2["year"].max())
        x = no2[(no2["level"] == fl) & (no2["year"] == last_y)].set_index("unit_id")["no2_mean"]
        y = annual[(annual["level"] == fl) & (annual["year"] == last_y)].set_index("unit_id")["sol"]
        j = pd.concat([x, y], axis=1, join="inner").dropna()
        if len(j) >= 8:
            from scipy import stats
            rho, p = stats.spearmanr(j["no2_mean"], j["sol"])
            out["no2_corr"] = {"rho": float(rho), "p_value": float(p), "n": int(len(j)), "year": last_y}
    return out


# --------------------------------------------------------------------------------------
# Section 7 — NTL and GDP
# --------------------------------------------------------------------------------------
def ntl_gdp(annual: pd.DataFrame, monthly: pd.DataFrame, wdi: pd.DataFrame, gdfs: dict,
            long: pd.DataFrame | None = None) -> dict:
    nid = national_id(gdfs)
    nat = annual[annual["unit_id"] == nid][["year", "sol"]]
    d = nat.merge(wdi, on="year", how="left")
    out = {"table": d}
    if "gdp_const_usd" not in wdi or wdi["gdp_const_usd"].notna().sum() < 5:
        out["error"] = "World Bank GDP unavailable"
        return out
    out["levels"] = eco.elasticity(d, "sol", "gdp_const_usd", "levels")
    out["growth"] = eco.elasticity(d, "sol", "gdp_const_usd", "growth")
    if long is not None and len(long):
        ln = long[long["unit_id"] == nid][["year", "dn_sum", "source"]].merge(wdi, on="year", how="inner")
        ln["viirs"] = (ln["source"].str.startswith("VIIRS")).astype(float)
        if ln["viirs"].nunique() > 1:
            out["long"] = eco.elasticity(ln, "dn_sum", "gdp_const_usd", "levels", dummy="viirs")
        else:
            out["long"] = eco.elasticity(ln, "dn_sum", "gdp_const_usd", "levels")
        out["long_table"] = ln
    # nowcast on the monthly-derived annual series (covers the most recent year)
    am = ts.annual_from_monthly(monthly[monthly["unit_id"] == nid])
    am = am.rename(columns={"sol_adj_mean": "sol_m"})[["year", "sol_m"]].merge(wdi, on="year", how="left")
    out["nowcast"] = eco.nowcast_gdp(am, "sol_m", "gdp_const_usd")
    out["tracking"] = eco.in_sample_tracking(am, "sol_m", "gdp_const_usd")
    t = out["tracking"].dropna(subset=["dl_gdp_loo"])
    if len(t) >= 5:
        out["tracking_corr"] = float(np.corrcoef(t["dl_gdp"], t["dl_gdp_loo"])[0, 1])
        out["tracking_mae_pp"] = float(100 * np.mean(np.abs(t["dl_gdp"] - t["dl_gdp_loo"])))
    a1 = annual[annual["level"] == "ADM1"][["unit_id", "year", "sol", "pop"]]
    out["regional_gdp"] = eco.regional_gdp(a1, wdi, 1.0)
    out["regional_gdp_g05"] = eco.regional_gdp(a1, wdi, 0.5)
    return out


# --------------------------------------------------------------------------------------
# Section 8 — shocks
# --------------------------------------------------------------------------------------
def shocks(dyn: dict, cfg, daily: pd.DataFrame | None, gdfs: dict) -> dict:
    stl = dyn["stl"]
    events = sh.event_catalogue(cfg, stl.index.min(), stl.index.max())
    imp, reg = [], []
    for _, e in events.iterrows():
        r = sh.event_impact(stl, e["start"], e["end"])
        imp.append(dict(id=e["id"], label=e["label"], type=e.get("type"), start=e["start"], end=e["end"], **r))
        for uid, s in dyn["adm1_stl"].items():
            rr = sh.event_impact(s, e["start"], e["end"])
            if rr.get("computable"):
                reg.append({"event": e["id"], "unit_id": uid, "trough_pct": rr["trough_pct"],
                            "months_to_recovery": rr["months_to_recovery"], "recovered": rr["recovered"]})
    # breaks not explained by a listed event (±6 months)
    unexplained = []
    for _, b in dyn["breaks"].iterrows():
        near = events[(events["start"] - pd.DateOffset(months=6) <= b["date"]) &
                      (b["date"] <= events["end"] + pd.DateOffset(months=6))] if len(events) else []
        if len(near) == 0:
            unexplained.append(b.to_dict())
    out = {"events": events, "impacts": pd.DataFrame(imp), "regional": pd.DataFrame(reg),
           "unexplained_breaks": pd.DataFrame(unexplained), "daily": {}}
    if daily is not None and len(daily):
        nid = national_id(gdfs)
        for w in daily["window"].unique():
            try:
                out["daily"][w] = sh.daily_index(daily, nid, w)
            except Exception as e:  # noqa: BLE001
                log.info("Daily index %s unavailable: %s", w, e)
    return out


# --------------------------------------------------------------------------------------
# Section 9 — inequality and electricity access
# --------------------------------------------------------------------------------------
def inequality(annual: pd.DataFrame, gdfs: dict, cfg, wdi: pd.DataFrame | None = None) -> dict:
    fl = finest_level(gdfs)
    d = attach_parent(annual[annual["level"] == fl].copy(), gdfs)
    d["sol_pc"] = d["sol"] / d["pop"].where(d["pop"] > 0)
    rows = []
    for y, g in d.groupby("year"):
        t = (ind.theil_decomposition(g, "sol_pc", "pop", "parent_id") if fl == "ADM2"
             else {"total": ind.theil_t(g["sol_pc"], g["pop"]), "between": np.nan, "within": np.nan,
                   "between_share": np.nan})
        rows.append({"year": y, "gini": ind.gini(g["sol_pc"], g["pop"]), "theil": t["total"],
                     "theil_between": t["between"], "theil_within": t["within"],
                     "theil_between_share": t["between_share"]})
    series = pd.DataFrame(rows)
    y0, y1 = int(d["year"].min()), int(d["year"].max())
    curves = {y: ind.lorenz(d[d["year"] == y]["sol_pc"], d[d["year"] == y]["pop"]) for y in (y0, y1)}
    gini_y = {y: float(series.loc[series["year"] == y, "gini"].iloc[0]) for y in (y0, y1)}
    # Gini change with a bootstrap CI over units (paired)
    rng = np.random.default_rng(cfg.random_seed)
    a, b = d[d["year"] == y0].set_index("unit_id"), d[d["year"] == y1].set_index("unit_id")
    common = a.index.intersection(b.index)
    boots = []
    for _ in range(300):
        s = rng.choice(common, len(common), replace=True)
        boots.append(ind.gini(b.loc[s, "sol_pc"], b.loc[s, "pop"]) - ind.gini(a.loc[s, "sol_pc"], a.loc[s, "pop"]))
    dgini_ci = (float(np.nanpercentile(boots, 2.5)), float(np.nanpercentile(boots, 97.5)))
    nat = ind.add_derived(annual[annual["level"] == "ADM0"]).sort_values("year")
    dark_sens = ind.dark_population_summary(annual[annual["level"] == "ADM0"], cfg.dark_thresholds)
    out = {"level": fl, "series": series, "lorenz": curves, "gini_years": gini_y,
           "gini_change": gini_y[y1] - gini_y[y0], "gini_change_ci": dgini_ci,
           "national": nat, "dark_sensitivity": dark_sens}
    for lv in ("ADM1", "ADM2"):
        if lv in gdfs:
            x = ind.add_derived(annual[(annual["level"] == lv) & (annual["year"] == y1)])
            out[f"dark_{lv}"] = x[["unit_id", "pop", "pop_inhabited", "pop_dark", "dark_share", "sol_pc",
                                   "urban_rural_ratio"]]
    if wdi is not None and "elec_access_pct" in wdi:
        cmp_ = nat[["year", "lit_pop_share"]].merge(wdi[["year", "elec_access_pct"]], on="year").dropna()
        cmp_["ntl_access_pct"] = 100 * cmp_["lit_pop_share"]
        out["access_comparison"] = cmp_
        if len(cmp_) >= 3:
            out["access_gap_pp"] = float((cmp_["ntl_access_pct"] - cmp_["elec_access_pct"]).mean())
    return out


# --------------------------------------------------------------------------------------
# Units table for maps / dashboard
# --------------------------------------------------------------------------------------
def units_table(annual: pd.DataFrame, growth: dict, ineq: dict, gdp: dict, level: str,
                names: dict) -> pd.DataFrame:
    """One row per unit of `level` with the indicators shown on the maps."""
    y1 = int(annual["year"].max())
    a = ind.add_derived(annual[(annual["level"] == level) & (annual["year"] == y1)])
    cols = ["unit_id", "sol", "pop", "sol_pc", "lit_area_share", "pop_dark", "dark_share", "urban_rural_ratio",
            "flare_share"]
    t = a[[c for c in cols if c in a]].copy()
    tr = growth["trends"].get(level)
    if tr is not None:
        t = t.merge(tr[["unit_id", "growth", "growth_lo", "growth_hi", "p_value", "class", "growth_pc",
                        "share_last"]], on="unit_id", how="left")
    rg = gdp.get("regional_gdp")
    if level == "ADM1" and rg is not None and len(rg):
        last = rg[rg["year"] == rg["year"].max()].set_index("unit_id")
        t["gdp_est"] = t["unit_id"].map(last["gdp_est"])
        t["gdp_pc_est"] = t["unit_id"].map(last.get("gdp_pc_est"))
    t["name"] = t["unit_id"].map(names)
    t["year"] = y1
    return t
