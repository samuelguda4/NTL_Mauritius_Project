"""Synthetic test country ``XTS`` — runs the whole notebook without Earth Engine or network.

The fixture writes, in ``outputs/XTS/cache/``, every table the acquisition steps would have
produced (same names, same columns), plus static PNG overlays, industrial clusters, a list of
reference industrial sites and a tourism-statistics file. It reproduces the patterns the eight
use cases are meant to detect, so that each analysis can be checked against a known truth:

* an urban hierarchy (a capital, ports, secondary towns) and a slowly declining region;
* seasonality (longer winter nights) and cloudy winter months;
* a COVID-19-like shock in spring 2020, followed by a recovery;
* an electrification programme (level shift) in one region in mid-2018;
* a gas flare in the desert (masked as non-economic light);
* four seaside resorts whose light rises every July–August;
* twelve industrial clusters of four types, and a reference list for validation.

Every output produced from it carries ``synthetic: true``; public publication is refused.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .lang import LANG

ISO3 = "XTS"
W, S, E, N = 8.0, 32.0, 11.6, 37.2          # bounding box (degrees)
NC, NR = 4, 6                               # district grid: 4 columns × 6 rows = 24 districts
YEARS = list(range(2014, 2026))

ADM1_NAMES = ["Alba", "Bersa", "Cedra", "Dalia", "Esmar", "Faro"]
ADM2_NAMES = ["Aven", "Brio", "Calen", "Dorsa", "Elvi", "Ferro", "Galin", "Hesta", "Ilia", "Jorvi", "Kalda",
              "Lumen", "Mira", "Noral", "Ostra", "Pelia", "Quira", "Rivo", "Selma", "Tarsi", "Ulma", "Varo",
              "Wesa", "Zelia"]
T = {
    "fr": {"dmsp": "DMSP (calibré)", "viirs": "VIIRS converti (DMSP-like)", "src": "jeu synthétique XTS",
           "flare": "Torchère (synthétique)"},
    "en": {"dmsp": "DMSP (calibrated)", "viirs": "VIIRS converted (DMSP-like)", "src": "synthetic fixture XTS",
           "flare": "Gas flare (synthetic)"},
}[LANG]


# --------------------------------------------------------------------------------------
# Geography
# --------------------------------------------------------------------------------------
def _vertices(rng):
    """Jittered vertex grid shared by neighbouring districts (consistent topology)."""
    xs = np.linspace(W, E, NC + 1)
    ys = np.linspace(S, N, NR + 1)
    V = np.zeros((NR + 1, NC + 1, 2))
    for i, y in enumerate(ys):
        for j, x in enumerate(xs):
            dx = rng.uniform(-0.16, 0.16) if 0 < j < NC else rng.uniform(-0.08, 0.08)
            dy = rng.uniform(-0.12, 0.12) if 0 < i < NR else rng.uniform(-0.06, 0.06)
            V[i, j] = (x + dx, y + dy)
    return V


def _edge(a, b, rng, k=4, amp=0.035):
    """Subdivided, slightly wiggly edge (deterministic per edge) for a natural outline."""
    seed = int(1e4 * (a[0] + 3 * a[1] + 7 * b[0] + 11 * b[1])) % (2 ** 31)
    r = np.random.default_rng(seed)
    pts = [a]
    for t in np.linspace(0, 1, k + 1)[1:-1]:
        p = a + t * (b - a)
        nrm = np.array([-(b - a)[1], (b - a)[0]])
        nrm = nrm / (np.linalg.norm(nrm) + 1e-12)
        pts.append(p + nrm * r.uniform(-amp, amp))
    return pts


def boundaries(seed: int = 7) -> dict:
    """{level: GeoDataFrame[unit_id, name, level, parent_id, parent_name, geometry]}"""
    import geopandas as gpd
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    rng = np.random.default_rng(seed)
    V = _vertices(rng)
    rows2 = []
    for i in range(NR):
        for j in range(NC):
            a, b, c, d = V[i, j], V[i, j + 1], V[i + 1, j + 1], V[i + 1, j]
            ring = _edge(a, b, rng) + _edge(b, c, rng) + _edge(c, d, rng) + _edge(d, a, rng)
            k = i * NC + j
            r1 = (i // 2) * 2 + (j // 2)                     # ADM1 = 2 × 2 districts
            rows2.append({"unit_id": f"XTS-ADM2-{k + 1:02d}", "name": ADM2_NAMES[k], "level": "ADM2",
                          "parent_id": f"XTS-ADM1-{r1 + 1:02d}", "parent_name": ADM1_NAMES[r1],
                          "row": i, "col": j, "geometry": Polygon(ring).buffer(0)})
    g2 = gpd.GeoDataFrame(rows2, crs="EPSG:4326")
    rows1 = [{"unit_id": f"XTS-ADM1-{r + 1:02d}", "name": ADM1_NAMES[r], "level": "ADM1", "parent_id": "ADM0",
              "parent_name": None, "geometry": unary_union(g2[g2["parent_id"] == f"XTS-ADM1-{r + 1:02d}"].geometry)}
             for r in range(6)]
    g1 = gpd.GeoDataFrame(rows1, crs="EPSG:4326")
    g0 = gpd.GeoDataFrame([{"unit_id": ISO3, "name": "Testland", "level": "ADM0", "parent_id": None,
                            "parent_name": None, "geometry": unary_union(g2.geometry)}], crs="EPSG:4326")
    return {"ADM0": g0, "ADM1": g1, "ADM2": g2.drop(columns=["row", "col"]), "_grid": g2}


# --------------------------------------------------------------------------------------
# District profiles (the "truth" the analyses should recover)
# --------------------------------------------------------------------------------------
def profiles(g2) -> pd.DataFrame:
    rng = np.random.default_rng(11)
    rows = []
    for _, r in g2.iterrows():
        k = int(r["unit_id"][-2:]) - 1
        i, j = int(r["row"]), int(r["col"])
        coast = j == NC - 1                                 # eastern districts are on the coast
        north = i >= NR - 2
        base = 900 * (1.9 if coast else 1.0) * (1.5 if north else 1.0) * rng.uniform(0.5, 1.4)
        pop = 120_000 * (1.8 if coast else 1.0) * (1.4 if north else 1.0) * rng.uniform(0.6, 1.5)
        if k == 21:                                         # capital (north-east)
            base, pop = 9000, 1_600_000
        if k in (19, 11):                                   # port cities
            base, pop = base * 2.6, pop * 1.9
        if i <= 1 and j <= 1:                               # southern desert interior
            base, pop = base * 0.35, pop * 0.45
        growth = rng.normal(0.035, 0.012)
        if r["parent_id"] == "XTS-ADM1-01":                 # Alba: declining region (mining closures)
            growth = rng.normal(-0.022, 0.004)
        resort = k in (3, 7, 15, 23)                        # four seaside resorts (coast)
        rows.append({"unit_id": r["unit_id"], "k": k, "base": base, "pop0": pop, "growth": growth,
                     "resort": resort, "coast": coast, "urban_share": min(0.95, 0.25 + base / 12000),
                     "dark0": 0.02 if base > 3000 else rng.uniform(0.10, 0.30),
                     "electrify": r["parent_id"] == "XTS-ADM1-03"})
    return pd.DataFrame(rows)


def _gdp_path(years=range(1990, 2026)):
    """Real GDP (constant 2015 USD) with a 2020 recession; the last year is not yet 'published'."""
    rng = np.random.default_rng(3)
    g = {}
    v = 28e9
    for y in years:
        gr = 0.032 + rng.normal(0, 0.008)
        if y == 2011:
            gr = -0.018
        if y == 2020:
            gr = -0.088
        if y == 2021:
            gr = 0.046
        v *= 1 + gr
        g[y] = v
    return g


# --------------------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------------------
def _month_factor(dates: pd.DatetimeIndex, prof, gdp, rng) -> np.ndarray:
    t = (dates.year - 2014) + (dates.month - 1) / 12
    m = dates.month.values
    f = prof["base"] * np.exp(prof["growth"] * t)
    # macro cycle linked to GDP (elasticity ~1.1 of light to GDP around its trend)
    lg = np.log(np.array([gdp[y] for y in dates.year]))
    trend = np.polyval(np.polyfit(np.arange(2014, 2026), np.log([gdp[y] for y in range(2014, 2026)]), 1), dates.year)
    f = f * np.exp(1.1 * (lg - trend))
    # physical seasonality: longer winter nights, shorter summer nights
    f = f * (1 + 0.06 * np.cos(2 * np.pi * (m - 1) / 12))
    if prof["resort"]:
        f = f * (1 + np.where(np.isin(m, [7, 8]), 0.42, np.where(np.isin(m, [6, 9]), 0.14, 0.0))
                 * np.where(dates.year == 2020, 0.25, np.where(dates.year == 2021, 0.7, 1.0)))
    covid = np.ones(len(dates))
    for (yy, mm), v in {(2020, 3): 0.93, (2020, 4): 0.80, (2020, 5): 0.82, (2020, 6): 0.90,
                        (2020, 7): 0.95, (2020, 11): 0.96, (2021, 1): 0.97}.items():
        covid[(dates.year == yy) & (dates.month == mm)] = v
    f = f * covid
    if prof["electrify"]:
        f = f * np.where(dates >= pd.Timestamp("2018-07-01"), 1.16, 1.0)
    return f * np.exp(rng.normal(0, 0.025, len(dates)))


def monthly_table(gdfs, prof, gdp) -> pd.DataFrame:
    from .boundaries import area_km2
    rng = np.random.default_rng(5)
    dates = pd.date_range("2014-01-01", "2025-12-01", freq="MS")
    a2 = dict(zip(gdfs["ADM2"]["unit_id"], area_km2(gdfs["ADM2"])))
    rows = []
    for _, p in prof.iterrows():
        true = _month_factor(dates, p, gdp, rng)
        n = int(a2[p["unit_id"]] / 0.215)
        winter = np.isin(dates.month, [12, 1, 2])
        vf = np.clip(np.where(winter, rng.uniform(0.72, 1.0, len(dates)), rng.uniform(0.9, 1.0, len(dates))), 0, 1)
        vf[(dates.year == 2016) & (dates.month == 1)] = 0.4      # a very cloudy month
        rows.append(pd.DataFrame({"unit_id": p["unit_id"], "level": "ADM2", "date": dates,
                                  "sol": true * vf, "lit": (n * (0.25 + 0.5 * p["urban_share"]) * vf).round(),
                                  "valid": (n * vf).round(), "n": n}))
    d2 = pd.concat(rows, ignore_index=True)
    par = gdfs["ADM2"].set_index("unit_id")["parent_id"]
    d1 = d2.assign(unit_id=d2["unit_id"].map(par), level="ADM1").groupby(
        ["unit_id", "level", "date"], as_index=False)[["sol", "lit", "valid", "n"]].sum()
    d0 = d2.assign(unit_id=ISO3, level="ADM0").groupby(["unit_id", "level", "date"], as_index=False)[
        ["sol", "lit", "valid", "n"]].sum()
    out = pd.concat([d0, d1, d2], ignore_index=True)
    names = {**dict(zip(gdfs["ADM1"]["unit_id"], gdfs["ADM1"]["name"])),
             **dict(zip(gdfs["ADM2"]["unit_id"], gdfs["ADM2"]["name"])), ISO3: "Testland"}
    out["name"] = out["unit_id"].map(names)
    out["annual_ref_year"] = out["date"].dt.year
    from .acquisition import finalize_monthly
    return finalize_monthly(out, 0.80)


def annual_table(gdfs, prof, monthly) -> pd.DataFrame:
    from .boundaries import area_km2
    rng = np.random.default_rng(9)
    a2 = dict(zip(gdfs["ADM2"]["unit_id"], area_km2(gdfs["ADM2"])))
    m2 = monthly[monthly["level"] == "ADM2"].copy()
    m2["year"] = m2["date"].dt.year
    true = m2.assign(t=m2["sol"] / m2["valid_frac"]).groupby(["unit_id", "year"])["t"].mean()
    rows = []
    # population growth (GHSL-like) and lit-area growth per district: the gap between the two drives use case 8
    pg = {p["unit_id"]: (0.021 if p["unit_id"] in ("XTS-ADM2-01", "XTS-ADM2-02", "XTS-ADM2-05", "XTS-ADM2-06")
                         else rng.normal(0.016, 0.006)) for _, p in prof.iterrows()}
    lr = {p["unit_id"]: (-0.012 if p["growth"] < 0 else 0.6 * p["growth"] + (0.03 if p["electrify"] else 0.0)
                         + rng.normal(0, 0.006)) for _, p in prof.iterrows()}
    for _, p in prof.iterrows():
        for y in YEARS:
            sol = float(true[(p["unit_id"], y)])
            pop = p["pop0"] * (1 + pg[p["unit_id"]]) ** (y - 2014)
            dark = max(0.005, p["dark0"] * (0.92 if not p["electrify"] or y < 2018 else 0.55) ** (y - 2014) ** 0.6)
            inh = 0.96 * pop
            us = p["urban_share"]
            flare = 420.0 if p["k"] == 1 else 0.0
            rows.append({"unit_id": p["unit_id"], "level": "ADM2", "year": y, "sol": sol, "sol_raw": sol + flare,
                         "flare_sol": flare, "area_km2": a2[p["unit_id"]],
                         "lit_km2": a2[p["unit_id"]] * min(0.9, (0.05 + 0.5 * us) * (1 + lr[p["unit_id"]]) ** (y - 2014)),
                         "pop": pop, "pop_inhabited": inh, "pop_urban": us * pop, "sol_urban": sol * min(0.97, us + 0.15),
                         "pop_dark_urban": inh * dark * 0.15, "pop_dark_rural": inh * dark * 0.85,
                         "pop_dark_0p25": inh * dark * 0.7, "pop_dark_0p5": inh * dark,
                         "pop_dark_1": inh * min(0.95, dark * 1.45)})
    d2 = pd.DataFrame(rows)
    num = [c for c in d2.columns if c not in ("unit_id", "level", "year")]
    par = gdfs["ADM2"].set_index("unit_id")["parent_id"]
    d1 = d2.assign(unit_id=d2["unit_id"].map(par), level="ADM1").groupby(["unit_id", "level", "year"],
                                                                        as_index=False)[num].sum()
    d0 = d2.assign(unit_id=ISO3, level="ADM0").groupby(["unit_id", "level", "year"], as_index=False)[num].sum()
    out = pd.concat([d0, d1, d2], ignore_index=True)
    out["product"] = "NOAA/VIIRS/DNB/ANNUAL_V22"
    out["pop_source_year"] = "GHSL " + out["year"].astype(str)
    _ = rng
    return out


def urban_table(gdfs, prof, annual) -> pd.DataFrame:
    """Use case 8: newly lit / electrified / new-settlement / lost areas and GHSL built-up change."""
    rng = np.random.default_rng(23)
    a = annual[annual["level"] == "ADM2"]
    y0, y1 = int(a["year"].min()), int(a["year"].max())
    first, last = a[a["year"] == y0].set_index("unit_id"), a[a["year"] == y1].set_index("unit_id")
    rows = []
    for _, p in prof.iterrows():
        u = p["unit_id"]
        l0, l1 = float(first.loc[u, "lit_km2"]), float(last.loc[u, "lit_km2"])
        new = max(0.0, l1 - l0) * 0.85 + abs(rng.normal(0, 0.5))
        lost = max(0.0, l0 - l1) * 0.85 + abs(rng.normal(0, 0.2))
        es = 0.75 if p["electrify"] else rng.uniform(0.25, 0.5)
        dens = float(last.loc[u, "pop"]) / max(float(last.loc[u, "area_km2"]), 1)
        b0 = float(first.loc[u, "area_km2"]) * (0.01 + 0.06 * p["urban_share"])
        lit_g = (l1 / l0) ** (1 / (y1 - y0)) - 1
        bg = max(-0.005, 0.7 * lit_g + 0.006 + rng.normal(0, 0.006))
        rows.append({"unit_id": u, "level": "ADM2", "y0": y0, "y1": y1, "built_epoch0": 2010, "built_epoch1": 2025,
                     "new_lit_km2": new, "lost_lit_km2": lost, "electrified_km2": new * es, "settled_km2": new * (1 - es),
                     "electrified_pop": new * es * dens * 0.6, "settled_pop": new * (1 - es) * dens * 0.08,
                     "new_lit_built_km2": new * float(np.clip(0.45 + 6 * lit_g + rng.normal(0, 0.05), 0.05, 0.95)),
                     "built0_km2": b0, "built1_km2": b0 * (1 + bg) ** 15})
    d2 = pd.DataFrame(rows)
    num = [c for c in d2.columns if c.endswith(("_km2", "_pop"))]
    par = gdfs["ADM2"].set_index("unit_id")["parent_id"]
    meta = {"y0": y0, "y1": y1, "built_epoch0": 2010, "built_epoch1": 2025}
    d1 = d2.assign(unit_id=d2["unit_id"].map(par)).groupby("unit_id", as_index=False)[num].sum().assign(level="ADM1", **meta)
    d0 = d2[num].sum().to_frame().T.assign(unit_id=ISO3, level="ADM0", **meta)
    return pd.concat([d0, d1, d2], ignore_index=True)


def wdi_table(gdp) -> pd.DataFrame:
    rows = []
    pop = 9.2e6
    for y in range(1990, 2025):                         # 2025 not yet published -> nowcast target
        pop *= 1.013
        rows.append({"year": y, "gdp_const_usd": gdp[y], "gdp_pc_const_usd": gdp[y] / pop,
                     "gdp_growth_pct": 100 * (gdp[y] / gdp[y - 1] - 1) if y > 1990 else np.nan,
                     "industry_va_const_usd": gdp[y] * (0.24 + 0.002 * (y - 1990) ** 0.5),
                     "elec_access_pct": min(99.6, 78 + 0.62 * (y - 1990)) if y >= 2000 else np.nan,
                     "population": pop})
    return pd.DataFrame(rows)


def long_table(annual, gdp) -> pd.DataFrame:
    rows = []
    nat = annual[annual["level"].isin(["ADM0", "ADM1"])]
    for uid, g in nat.groupby("unit_id"):
        lvl = g["level"].iloc[0]
        s14 = float(g[g["year"] == 2014]["sol"].iloc[0])
        for y in range(1992, 2026):
            if y >= 2014:
                v = float(g[g["year"] == y]["sol"].iloc[0]) / s14
            else:
                v = (gdp[y] / gdp[2014]) ** 1.25 * (1 + 0.01 * np.sin(y))
            rows.append({"unit_id": uid, "level": lvl, "year": y, "dn_sum": 52_000 * v * s14 / 30_000,
                         "source": T["dmsp"] if y <= 2013 else T["viirs"]})
    return pd.DataFrame(rows)


def dmsp_table(annual) -> pd.DataFrame:
    rows = [{"unit_id": ISO3, "level": "ADM0", "year": y, "sol_dn": 40_000 * 1.03 ** (y - 1992),
             "n_sat": 120 + 4 * (y - 1992), "n_lit": 6000 + 90 * (y - 1992)} for y in range(1992, 2014)]
    d = pd.DataFrame(rows)
    d["sat_share"] = d["n_sat"] / d["n_lit"]
    _ = annual
    return d


def daily_table(monthly) -> pd.DataFrame:
    rng = np.random.default_rng(13)
    days = pd.date_range("2019-12-01", "2020-12-31", freq="D")
    m = monthly[monthly["level"].isin(["ADM0", "ADM1"])]
    rows = []
    for uid, g in m.groupby("unit_id"):
        lvl = g["level"].iloc[0]
        base = float(g[(g["date"] >= "2019-12-01") & (g["date"] < "2020-03-01")]["sol_adj"].mean())
        prof = np.ones(len(days))
        lock = (days >= "2020-03-20") & (days <= "2020-05-31")
        prof[lock] = 0.76 + 0.12 * ((days[lock] - pd.Timestamp("2020-03-20")).days / 72) ** 2
        rec = (days > "2020-05-31") & (days <= "2020-08-31")
        prof[rec] = 0.88 + 0.10 * (days[rec] - pd.Timestamp("2020-06-01")).days / 92
        lunar = 1 + 0.05 * np.cos(2 * np.pi * (days - pd.Timestamp("2020-01-10")).days / 29.53)
        sol = base * prof * lunar * np.exp(rng.normal(0, 0.05, len(days)))
        vf = rng.uniform(0.3, 1.0, len(days))
        n = 10_000
        rows.append(pd.DataFrame({"unit_id": uid, "level": lvl, "date": days, "window": "covid19",
                                  "sol": sol * vf, "valid": (vf * n).round(), "n": n}))
    d = pd.concat(rows, ignore_index=True)
    d["valid_frac"] = d["valid"] / d["n"]
    d["sol_adj"] = np.where(d["valid_frac"] >= 0.5, d["sol"] / d["valid_frac"], np.nan)
    return d


def no2_table(annual) -> pd.DataFrame:
    rng = np.random.default_rng(17)
    d = annual[annual["year"] >= 2019][["unit_id", "level", "year", "sol", "area_km2"]].copy()
    d["no2_mean"] = 2.0e-5 + 6.0e-5 * np.sqrt(d["sol"] / d["area_km2"]) / 8 * np.where(d["year"] == 2020, 0.88, 1.0)
    d["no2_mean"] *= np.exp(rng.normal(0, 0.06, len(d)))
    return d[["unit_id", "level", "year", "no2_mean"]]


def availability() -> pd.DataFrame:
    from .config import DATASETS
    rows = [{"key": k, "id": v["id"], "status": "ok (" + T["src"] + ")", "first": v.get("start", ""),
             "last": v.get("end", "2025-12"), "n_images": 0}
            for k, v in DATASETS.items() if v["type"] == "ImageCollection" and "{" not in v["id"]]
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------
# Industrial clusters + reference sites (use case 6) and tourism statistics (use case 7)
# --------------------------------------------------------------------------------------
CLUSTERS = [  # (district k, dx, dy, type, size_km, signals)
    (21, 0.10, 0.05, "heavy", 3.0, dict(s_ratio=0.9, s_nres=0.85, s_no2=1.0, s_so2=0.9, s_lst=0.8)),
    (19, -0.05, 0.08, "heavy", 2.5, dict(s_ratio=0.8, s_nres=0.9, s_no2=1.0, s_so2=0.7, s_lst=0.9)),
    (11, 0.04, -0.06, "logistics", 2.2, dict(s_ratio=0.9, s_nres=0.95, s_no2=0.8, s_so2=0.1, s_lst=0.4)),
    (21, -0.15, -0.10, "logistics", 2.0, dict(s_ratio=0.85, s_nres=0.9, s_no2=0.9, s_so2=0.0, s_lst=0.3)),
    (17, 0.02, 0.02, "logistics", 1.6, dict(s_ratio=0.8, s_nres=0.8, s_no2=0.6, s_so2=0.0, s_lst=0.2)),
    (1, 0.05, 0.10, "hydro", 1.4, dict(s_ratio=1.0, s_nres=0.1, s_no2=0.5, s_so2=0.8, s_lst=0.9)),
    (2, -0.10, 0.05, "hydro", 1.2, dict(s_ratio=1.0, s_nres=0.2, s_no2=0.3, s_so2=0.9, s_lst=0.7)),
    (5, 0.00, 0.00, "heavy", 1.8, dict(s_ratio=0.9, s_nres=0.7, s_no2=0.7, s_so2=0.8, s_lst=0.6)),
    (9, 0.06, -0.04, "logistics", 1.3, dict(s_ratio=0.7, s_nres=0.8, s_no2=0.4, s_so2=0.0, s_lst=0.3)),
    (13, -0.04, 0.03, "isolated", 0.8, dict(s_ratio=1.0, s_nres=0.3, s_no2=0.0, s_so2=0.1, s_lst=1.0)),
    (0, 0.10, -0.08, "isolated", 0.7, dict(s_ratio=1.0, s_nres=0.0, s_no2=0.1, s_so2=0.0, s_lst=0.9)),
    (14, 0.03, 0.06, "heavy", 1.5, dict(s_ratio=0.8, s_nres=0.75, s_no2=0.9, s_so2=0.6, s_lst=0.5)),
]


def industry_clusters(gdfs, years=YEARS, annual=None) -> dict:
    """GeoJSON with the same properties as ``industry.detect_clusters`` (Earth Engine)."""
    from shapely.geometry import box, mapping
    rng = np.random.default_rng(23)
    g2 = gdfs["ADM2"].reset_index(drop=True)
    feats = []
    for c, (k, dx, dy, typ, km, sig) in enumerate(CLUSTERS):
        pt = g2.geometry.iloc[k].representative_point()
        x, y = pt.x + dx, pt.y + dy
        h = km / 111.0 / 2
        geom = box(x - h, y - h * 0.8, x + h * 1.1, y + h)
        pix = max(3, int(round(km * km / 0.215)))
        rad = {"heavy": 55, "logistics": 34, "hydro": 120, "isolated": 22}[typ] * rng.uniform(0.8, 1.2)
        gr = {"heavy": 0.028, "logistics": 0.055, "hydro": -0.01, "isolated": 0.0}[typ] + rng.normal(0, 0.01)
        props = {"cluster_id": f"IND-{c + 1:02d}", "pixels": pix, "area_km2": round(pix * 0.215, 3),
                 "sol": rad * pix, "pop": {"heavy": 900, "logistics": 1500, "hydro": 30, "isolated": 40}[typ] * pix / 10,
                 "s_light": 1.0, **sig, "nres_share": 0.15 + 0.75 * sig["s_nres"], "no2": 2.5e-5 + 7e-5 * sig["s_no2"],
                 "so2": 1e-4 + 9e-4 * sig["s_so2"], "lst_delta": 0.5 + 3.5 * sig["s_lst"],
                 "flare_overlap": 0.6 if typ == "hydro" else 0.0}
        props["mean_signals"] = 1 + sum(sig.values())
        for y in years:
            cov = 0.9 if y == 2020 else 1.0
            props[f"sol_{y}"] = props["sol"] * math.exp(gr * (y - years[-1])) * cov * rng.uniform(0.97, 1.03)
        if annual is not None:                           # keep clusters a plausible share of their district
            uid = g2["unit_id"].iloc[k]
            ds = float(annual[(annual["unit_id"] == uid) & (annual["year"] == years[-1])]["sol_raw"].iloc[0])
            fct = min(1.0, 0.35 * ds / props[f"sol_{years[-1]}"])
            for key in [f"sol_{y}" for y in years] + ["sol"]:
                props[key] *= fct
        feats.append({"type": "Feature", "geometry": mapping(geom), "properties": props})
    return {"type": "FeatureCollection", "features": feats}


def industrial_reference(clusters: dict) -> pd.DataFrame:
    """Reference list (name, lon, lat): nine of the clusters + three sites the satellite misses."""
    from shapely.geometry import shape
    rows = []
    for f in clusters["features"]:
        if f["properties"]["cluster_id"] in ("IND-10", "IND-11", "IND-07"):
            continue
        c = shape(f["geometry"]).centroid
        rows.append({"name": f"Zone industrielle {f['properties']['cluster_id'][-2:]}", "lon": c.x + 0.004,
                     "lat": c.y - 0.003, "source": T["src"]})
    for i, (x, y) in enumerate([(9.2, 34.1), (10.4, 33.2), (8.7, 36.4)]):
        rows.append({"name": f"Zone artisanale {i + 1}", "lon": x, "lat": y, "source": T["src"]})
    return pd.DataFrame(rows)


def tourism_stats(prof, monthly) -> pd.DataFrame:
    """National hotel nights (millions), driven by the resorts' true summer boost + noise."""
    rng = np.random.default_rng(29)
    rows = []
    for y in YEARS:
        f = 0.25 if y == 2020 else 0.7 if y == 2021 else 1.0
        rows.append({"year": y, "nights_millions": round(28 * f * 1.02 ** (y - 2014) * rng.uniform(0.95, 1.05), 2)})
    _ = prof, monthly
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------
# Static PNG overlays (same format as acquisition.export_pngs)
# --------------------------------------------------------------------------------------
PALETTE = ["000004", "3b0f70", "8c2981", "de4968", "fe9f6d", "fcfdbf"]


def _rgb(hexs):
    return np.array([[int(h[i:i + 2], 16) for i in (0, 2, 4)] for h in hexs], float)


def _colorize(v, vmin, vmax, palette):
    p = _rgb(palette)
    t = np.clip((v - vmin) / (vmax - vmin), 0, 1) * (len(p) - 1)
    i = np.minimum(np.floor(t).astype(int), len(p) - 2)
    f = (t - i)[..., None]
    return p[i] * (1 - f) + p[i + 1] * f


def rasters(gdfs, prof, out_dir: Path, clusters: dict, dims: int = 900) -> dict:
    from matplotlib.path import Path as MPath
    from PIL import Image
    w, s, e, n = [float(v) for v in gdfs["ADM0"].total_bounds]
    ny = int(dims * (n - s) / (e - w))
    xs = np.linspace(w, e, dims)
    ys = np.linspace(n, s, ny)
    X, Y = np.meshgrid(xs, ys)
    geom = gdfs["ADM0"].geometry.iloc[0]
    poly = geom if geom.geom_type == "Polygon" else max(geom.geoms, key=lambda g: g.area)
    inside = MPath(np.asarray(poly.exterior.coords)).contains_points(np.c_[X.ravel(), Y.ravel()]).reshape(X.shape)
    g2 = gdfs["ADM2"].reset_index(drop=True)
    rng = np.random.default_rng(31)
    blobs = []          # (x, y, peak radiance, core radius in degrees, growth)
    towns = []
    for _, p in prof.iterrows():
        c0 = g2.geometry.iloc[p["k"]].representative_point()
        jx, jy = (0, 0) if p["base"] > 5000 else (rng.uniform(-0.22, 0.22), rng.uniform(-0.18, 0.18))
        cx_, cy_ = c0.x + jx, c0.y + jy
        c = type("P", (), {"x": cx_, "y": cy_})
        towns.append((c.x, c.y, p["base"], p["growth"]))
        blobs.append((c.x, c.y, 18 + 140 * (p["base"] / 9000) ** 0.8, 0.010 + 0.022 * (p["base"] / 9000) ** 0.5, p["growth"]))
        for _ in range(int(4 + p["base"] / 600)):            # suburbs and villages around each town
            r, a = abs(rng.normal(0, 0.10 + 0.08 * (p["base"] / 9000) ** 0.5)), rng.uniform(0, 2 * np.pi)
            blobs.append((c.x + r * np.cos(a), c.y + r * np.sin(a), rng.uniform(2, 10), rng.uniform(0.004, 0.009), p["growth"]))
    towns.sort(key=lambda t: -t[2])
    for (ax, ay, ab, ag) in towns[:12]:                       # road corridors between the larger towns
        bx, by, bb, bg = min((t for t in towns if t[:2] != (ax, ay)), key=lambda t: (t[0] - ax) ** 2 + (t[1] - ay) ** 2)
        for t in np.linspace(0.08, 0.92, 9):
            blobs.append((ax + t * (bx - ax) + rng.normal(0, 0.01), ay + t * (by - ay) + rng.normal(0, 0.01),
                          rng.uniform(1.5, 5), 0.004, ag))
    for _ in range(260):                                      # scattered rural settlements
        x, y = rng.uniform(w, e), rng.uniform(s, n)
        wgt = 0.3 + 0.7 * ((x - w) / (e - w)) * (0.4 + 0.6 * (y - s) / (n - s))
        if rng.uniform() < wgt:
            blobs.append((x, y, rng.uniform(0.8, 3.5), 0.004, 0.04))
    from shapely.geometry import shape
    for f in clusters["features"]:
        c = shape(f["geometry"]).centroid
        blobs.append((c.x, c.y, 30 + f["properties"]["sol"] / f["properties"]["pixels"], 0.007, 0.03))
    blobs.append((8.965, 32.815, 400, 0.004, 0.0))           # the gas flare
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    index = {"bounds": [w, s, e, n], "ntl": {}, "dark": {}}
    Rs = {}
    for y in YEARS:
        R = np.zeros_like(X)
        for (cx, cy, amp, sd, g) in blobs:
            d2 = ((X - cx) ** 2 + (Y - cy) ** 2) / sd ** 2
            R += amp * math.exp(g * (y - 2014)) / (1 + d2) ** 1.6
        R = np.where(inside, R, 0)
        lg = np.log10(np.maximum(R, 1e-6))
        rgb = _colorize(lg, -1.0, 2.0, PALETTE)
        alpha = np.where(R >= 0.5, 235, 0)
        img = np.dstack([rgb, alpha]).astype(np.uint8)
        Image.fromarray(img, "RGBA").save(out_dir / f"ntl_{y}.png", optimize=True)
        index["ntl"][str(y)] = f"ntl_{y}.png"
        if y in (YEARS[0], YEARS[1], YEARS[-2], YEARS[-1]):
            Rs[y] = R
    # inhabited areas lit (gold) / unlit (red)
    P = np.zeros_like(X)
    for (cx, cy, amp, sd, g) in blobs:
        P += amp / (1 + ((X - cx) ** 2 + (Y - cy) ** 2) / (sd * 2.2) ** 2) ** 1.3
    for _ in range(420):                                      # villages with no detectable light
        x, y = rng.uniform(w, e), rng.uniform(s, n)
        if rng.uniform() < 0.85 - 0.6 * (x - w) / (e - w):
            P += rng.uniform(5, 12) / (1 + ((X - x) ** 2 + (Y - y) ** 2) / 0.016 ** 2) ** 1.3
    inhab = inside & (P > 4.0)
    lit = inhab & (R >= 0.5)
    img = np.zeros(X.shape + (4,), np.uint8)
    img[lit] = (245, 194, 66, 230)
    img[inhab & ~lit] = (215, 38, 61, 230)
    Image.fromarray(img, "RGBA").save(out_dir / f"dark_{YEARS[-1]}.png", optimize=True)
    index["dark"][str(YEARS[-1])] = f"dark_{YEARS[-1]}.png"
    # use case 8: newly lit (gold = new settlement, green = electrified settlement) and light lost (red)
    T = 0.5
    dark_start = (Rs[YEARS[0]] < T) & (Rs[YEARS[1]] < T)
    lit_end = (Rs[YEARS[-1]] >= T) & (Rs[YEARS[-2]] >= T)
    new, lost = inside & dark_start & lit_end, inside & (Rs[YEARS[0]] >= T) & (Rs[YEARS[1]] >= T) & (Rs[YEARS[-1]] < T) & (Rs[YEARS[-2]] < T)
    img = np.zeros(X.shape + (4,), np.uint8)
    img[new & ~inhab] = (245, 194, 66, 235)
    img[new & inhab] = (25, 195, 125, 235)
    img[lost] = (227, 73, 72, 235)
    name = f"urban_{YEARS[0]}_{YEARS[-1]}.png"
    Image.fromarray(img, "RGBA").save(out_dir / name, optimize=True)
    index["urban"] = {f"{YEARS[0]}-{YEARS[-1]}": name}
    return index


# --------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------
def write_fixture(cache_dir: str | Path) -> dict:
    """Write every cached table of the synthetic country. Returns {name: path}."""
    from . import cache
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    gdfs = boundaries()
    prof = profiles(gdfs.pop("_grid"))
    gdp = _gdp_path()
    monthly = monthly_table(gdfs, prof, gdp)
    annual = annual_table(gdfs, prof, monthly)
    clusters = industry_clusters(gdfs, annual=annual)
    files = {}
    for lv, g in gdfs.items():
        files[f"boundaries_{lv}"] = cache.save(cache_dir, f"boundaries_{lv}", g)
    tables = {
        "boundary_meta": {lv: "synthétique (XTS)" if LANG == "fr" else "synthetic (XTS)" for lv in gdfs},
        "availability": availability(), "monthly": monthly, "annual": annual,
        "long": long_table(annual, gdp), "dmsp": dmsp_table(annual), "daily": daily_table(monthly),
        "no2": no2_table(annual), "wdi": wdi_table(gdp),
        "flare_polygons": {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"label": T["flare"]},
                           "geometry": {"type": "Polygon", "coordinates": [[[8.95, 32.80], [8.98, 32.80], [8.98, 32.83],
                                                                            [8.95, 32.83], [8.95, 32.80]]]}}]},
        "industry_clusters": clusters,
        "industrial_reference": industrial_reference(clusters),
        "tourism_stats": tourism_stats(prof, monthly),
        "urban": urban_table(gdfs, prof, annual),
        "wdi_urban": pd.DataFrame({"year": YEARS[:-1], "urban_pct": [68.0 + 0.45 * i for i in range(len(YEARS) - 1)]}),
    }
    for k, v in tables.items():
        files[k] = cache.save(cache_dir, k, v)
    idx = rasters(gdfs, prof, cache_dir / "rasters", clusters)
    files["rasters_index"] = cache.save(cache_dir, "rasters_index", idx)
    (cache_dir / "truth.json").write_text(json.dumps({
        "resorts": prof[prof["resort"]]["unit_id"].tolist(), "declining_region": "XTS-ADM1-01",
        "electrification": {"region": "XTS-ADM1-03", "date": "2018-07"}, "covid_trough": "2020-04",
        "clusters": {c[0]: c[3] for c in CLUSTERS}}, indent=1), encoding="utf-8")
    return files
