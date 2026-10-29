"""Static exports for the dashboard (no dependency on Earth Engine at viewing time).

Layout written under `<dashboard_dir>/data/`:

    countries.json                  index of the countries available on the site
    <ISO3>/meta.json                country, period, datasets, versions, parameters, rasters
    <ISO3>/summary.json             KPIs, key messages, recommendations, limits
    <ISO3>/adm1.geojson, adm2.geojson   simplified boundaries + indicators
    <ISO3>/monthly_national.csv     observed / seasonally adjusted / trend
    <ISO3>/monthly_adm1.csv         seasonally adjusted level per ADM1
    <ISO3>/annual_units.csv         annual indicators per unit and year
    <ISO3>/regions.csv              one row per unit (latest year) — map and ranking table
    <ISO3>/gdp.json, shocks.json, inequality.json
    <ISO3>/rasters/*.png            static overlays (Web Mercator) with bounds in meta.json
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import logging
import shutil
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd


def _clean(o: Any) -> Any:
    """Make an object JSON-safe: NaN/inf -> None, numpy -> python, timestamps -> ISO strings."""
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, pd.DataFrame):
        return _clean(o.to_dict(orient="records"))
    if isinstance(o, pd.Series):
        return _clean(o.tolist())
    if isinstance(o, np.ndarray):
        return _clean(o.tolist())
    if isinstance(o, (pd.Timestamp, _dt.date, _dt.datetime)):
        return o.strftime("%Y-%m-%d")
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return None if not math.isfinite(f) else round(f, 6)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if o is pd.NaT:
        return None
    return o


def _fr(x: float, d: int = 2) -> str:
    return "n.d." if x is None or not np.isfinite(x) else f"{x:.{d}f}".replace("-", "−").replace(".", ",")


def write_json(path: Path, obj: Any) -> Path:
    path.write_text(json.dumps(_clean(obj), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return path


def simplify_gdf(gdf: gpd.GeoDataFrame, max_kb: int = 600) -> gpd.GeoDataFrame:
    """Simplify progressively until the GeoJSON is below `max_kb` (keeps topology)."""
    import shapely
    g = gdf.copy()
    span = max(g.total_bounds[2] - g.total_bounds[0], g.total_bounds[3] - g.total_bounds[1])
    tol = span / 4000
    for _ in range(12):
        s = g.copy()
        s["geometry"] = shapely.set_precision(g.geometry.simplify(tol, preserve_topology=True).values, 1e-4)
        s = s[~s.geometry.is_empty]
        if len(s.to_json(drop_id=True)) / 1024 <= max_kb:
            return s
        tol *= 1.7
    return s


def _df_records(df: pd.DataFrame | None, cols: list[str] | None = None) -> list:
    if df is None or len(df) == 0:
        return []
    d = df[[c for c in (cols or df.columns) if c in df.columns]].copy()
    return _clean(d)


PLOTLY_URL = "https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"


def _download(url: str, path: Path, timeout: int = 60) -> bool:
    """Best-effort download (flag, vendored library). Never fatal: the site has fallbacks."""
    try:
        import requests
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
        return True
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger("ntl").warning("download failed %s (%s)", url, e)
        return False


def site_assets(site_dir: Path, out: Path, iso2: str) -> None:
    """Country flag (flagcdn.com, public domain) next to the data, and a local copy of Plotly so the
    published site does not depend on a CDN (the page falls back to the CDN if this copy is missing)."""
    if iso2:
        _download(f"https://flagcdn.com/{iso2.lower()}.svg", out / "flag.svg", timeout=20)
    vend = Path(site_dir) / "assets" / "vendor" / "plotly.min.js"
    if not vend.exists():
        _download(PLOTLY_URL, vend)


def export_dashboard(cfg, gdfs: dict, R: dict, annual: pd.DataFrame, monthly: pd.DataFrame,
                     names: dict, messages: list[dict], recs: list[str], limits: list,
                     manifest: dict, rasters: dict | None = None, raster_src: Path | None = None,
                     synthetic: bool = False) -> Path:
    """Write every static file needed by the dashboard. Returns the country data directory."""
    root = Path(cfg.dashboard_dir) / "data"
    out = root / cfg.iso3
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    dyn, gr, gdp, shk, ineq = R["dyn"], R["growth"], R["gdp"], R["shocks"], R["ineq"]
    y0, y1 = int(annual["year"].min()), int(annual["year"].max())

    # ---- boundaries + indicators -----------------------------------------------------------
    from .pipeline import units_table
    regions = []
    for lv in ("ADM1", "ADM2"):
        if lv not in gdfs:
            continue
        t = units_table(annual, gr, ineq, gdp, lv, names)
        t["level"] = lv
        regions.append(t)
        g = simplify_gdf(gdfs[lv][["unit_id", "parent_name", "geometry"]]).merge(t, on="unit_id", how="left")
        num = g.select_dtypes("number").columns
        g[num] = g[num].astype(float).round(6)
        (out / f"{lv.lower()}.geojson").write_text(g.to_json(drop_id=True, na="null"), encoding="utf-8")
    regions = pd.concat(regions, ignore_index=True)
    regions.to_csv(out / "regions.csv", index=False, float_format="%.6g")
    adm0 = simplify_gdf(gdfs["ADM0"][["unit_id", "name", "geometry"]], 300)
    (out / "adm0.geojson").write_text(adm0.to_json(drop_id=True), encoding="utf-8")

    # ---- time series ---------------------------------------------------------------------
    stl = dyn["stl"].copy()
    stl["anomaly"] = stl.index.isin(dyn["anomalies"].index)
    stl.index.name = "date"
    stl[["obs", "sa_level", "trend_level", "anomaly"]].rename(
        columns={"sa_level": "sa", "trend_level": "trend"}).reset_index().to_csv(
        out / "monthly_national.csv", index=False, float_format="%.6g", date_format="%Y-%m-%d")
    rows = []
    for uid, s in dyn["adm1_stl"].items():
        rows.append(pd.DataFrame({"date": s.index, "unit_id": uid, "sa": s["sa_level"].values}))
    if rows:
        pd.concat(rows).to_csv(out / "monthly_adm1.csv", index=False, float_format="%.6g", date_format="%Y-%m-%d")
    from .indicators import add_derived
    au = add_derived(annual)
    au["name"] = au["unit_id"].map(names)
    keep = ["unit_id", "level", "name", "year", "sol", "pop", "sol_pc", "lit_km2", "lit_area_share",
            "pop_dark", "dark_share", "urban_rural_ratio", "flare_share"]
    au[[c for c in keep if c in au]].to_csv(out / "annual_units.csv", index=False, float_format="%.6g")

    # ---- GDP -----------------------------------------------------------------------------------
    def _el(e):
        if not e or not np.isfinite(e.get("beta", np.nan)):
            return None
        return {k: e[k] for k in ("spec", "beta", "ci", "p_value", "r2", "n", "years", "confidence",
                                  "confidence_reason", "diagnostics", "dummy_coef") if k in e} | {
            "points": _df_records(e["data"], ["year", "lx", "ly", "fitted", "resid"])}
    nc = gdp.get("nowcast", {})
    write_json(out / "gdp.json", {
        "available": "levels" in gdp,
        "table": _df_records(gdp.get("table"), ["year", "sol", "gdp_const_usd", "gdp_growth_pct",
                                                 "gdp_pc_const_usd", "population"]),
        "levels": _el(gdp.get("levels")), "growth": _el(gdp.get("growth")), "long": _el(gdp.get("long")),
        "nowcast": {"gamma": nc.get("gamma"), "gamma_ci": nc.get("gamma_ci"), "r2": nc.get("r2"),
                    "last_official_year": nc.get("last_official_year"),
                    "estimates": _df_records(nc.get("estimates"))},
        "tracking": _df_records(gdp.get("tracking"), ["year", "dl_gdp", "dl_ntl", "dl_gdp_loo"]),
        "tracking_corr": gdp.get("tracking_corr"), "tracking_mae_pp": gdp.get("tracking_mae_pp"),
        "regional": _df_records(gdp.get("regional_gdp"), ["unit_id", "year", "share", "gdp_est", "gdp_pc_est"]),
    })

    # ---- shocks --------------------------------------------------------------------------------
    an = dyn["anomalies"].reset_index().rename(columns={"index": "date"})
    write_json(out / "shocks.json", {
        "events": _df_records(shk["events"]), "impacts": _df_records(shk["impacts"]),
        "regional": _df_records(shk["regional"]), "breaks": _df_records(dyn["breaks"]),
        "unexplained_breaks": _df_records(shk["unexplained_breaks"]),
        "anomalies": _df_records(an, ["date", "obs", "z", "direction"]),
        "daily": {w: _df_records(d.rename_axis("date").reset_index(),
                                 ["date", "index", "index_smooth", "valid_frac"]) for w, d in shk["daily"].items()},
    })

    # ---- growth: concentration and convergence --------------------------------------------
    b = gr.get("beta_convergence", {})
    write_json(out / "growth.json", {
        "concentration": {lv: _df_records(df) for lv, df in gr["concentration"].items()},
        "class_counts": gr["class_counts"],
        "beta": {k: b.get(k) for k in ("beta", "ci", "p_value", "r2", "n", "level", "first_year", "half_life_years")},
        "beta_data": _df_records(gr.get("beta_data"), ["unit_id", "init", "g"]),
        "sigma": _df_records(gr.get("sigma_convergence")),
        "no2_corr": gr.get("no2_corr"),
    })

    # ---- inequality ------------------------------------------------------------------------------
    nat = ineq["national"]
    write_json(out / "inequality.json", {
        "level": ineq["level"], "series": _df_records(ineq["series"]),
        "lorenz": {str(y): {"q": q, "l": l} for y, (q, l) in ineq["lorenz"].items()},
        "gini_years": ineq["gini_years"], "gini_change": ineq["gini_change"],
        "gini_change_ci": ineq["gini_change_ci"],
        "national": _df_records(nat, ["year", "pop", "pop_inhabited", "pop_dark", "dark_share", "lit_pop_share",
                                      "sol_pc_urban", "sol_pc_rural", "urban_rural_ratio"]),
        "dark_sensitivity": _df_records(ineq["dark_sensitivity"]),
        "access_comparison": _df_records(ineq.get("access_comparison")),
        "access_gap_pp": ineq.get("access_gap_pp"),
    })

    # ---- rasters ---------------------------------------------------------------------------------
    rindex = None
    if rasters and raster_src:
        (out / "rasters").mkdir()
        for f in Path(raster_src).glob("*.png"):
            shutil.copy(f, out / "rasters" / f.name)
        rindex = rasters

    # ---- summary & KPIs -----------------------------------------------------------------------
    natr = ineq["national"].iloc[-1]
    t = dyn["national_trend"]
    conc = gr["concentration"]["ADM1"].iloc[-1]
    kpis = [
        {"id": "growth", "label": "Croissance annuelle de la lumière", "value": t["growth"], "fmt": "pct",
         "sub": f"{y0}–{y1}, pente robuste (Theil–Sen)"},
        {"id": "last12", "label": "12 derniers mois vs 12 précédents", "value": dyn["growth_last12"], "fmt": "pct",
         "sub": f"série désaisonnalisée, jusqu'à {dyn['last_month']:%m/%Y}"},
        {"id": "elasticity", "label": "Élasticité lumière–PIB",
         "value": gdp["levels"]["beta"] if "levels" in gdp else None, "fmt": "num2",
         "sub": (f"IC 95 % {_fr(gdp['levels']['ci'][0])} à {_fr(gdp['levels']['ci'][1])} · confiance "
                 f"{gdp['levels']['confidence']}") if "levels" in gdp else "PIB indisponible"},
        {"id": "gini", "label": "Gini de la lumière par habitant", "value": ineq["series"]["gini"].iloc[-1],
         "fmt": "num2", "sub": f"unités {ineq['level']}, {y1}"},
        {"id": "dark", "label": "Personnes dans le noir", "value": natr.get("pop_dark"), "fmt": "people",
         "sub": f"{100 * natr.get('dark_share', np.nan):.0f} % de la population habitée, {y1}"},
        {"id": "top1", "label": "Part de la 1ʳᵉ région", "value": conc["top1_share"], "fmt": "pct0",
         "sub": f"{names.get(conc['top1_name'], '')}, {y1}"},
    ]
    write_json(out / "summary.json", {"kpis": kpis, "messages": messages, "recommendations": recs,
                                      "limits": [{"title": a, "text": b} for a, b in limits]})

    # ---- meta & index ------------------------------------------------------------------------------
    # country flag (flag.png + flag.svg) from the cache — downloaded once, fictional for the test country
    try:
        from .flags import ensure_flag
        for k, p in ensure_flag(cfg, synthetic).items():
            if p is not None:
                shutil.copy2(p, out / f"flag.{k}")
    except Exception as e:  # noqa: BLE001 - never fatal
        logging.getLogger("ntl").warning("flag: %s", e)
    site_assets(Path(cfg.dashboard_dir), out, "" if (out / "flag.svg").exists() else cfg.country.get("iso2", ""))
    meta = {"iso3": cfg.iso3, "iso2": cfg.country.get("iso2", ""), "name": cfg.country.get("name_fr") or cfg.country.get("name"),
            "name_en": cfg.country.get("name"), "period": [y0, y1],
            "monthly_period": [dyn["stl"].index.min(), dyn["stl"].index.max()],
            "generated_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "synthetic": bool(synthetic), "levels": [lv for lv in ("ADM1", "ADM2") if lv in gdfs],
            "rasters": rindex, "files": sorted(p.name for p in out.iterdir() if p.is_file()),
            **manifest}
    write_json(out / "meta.json", meta)
    from .extensions import export_extensions
    export_extensions(out, R, names)
    meta["files"] = sorted(p.name for p in out.iterdir() if p.is_file())
    write_json(out / "meta.json", meta)
    idx_path = root / "countries.json"
    idx = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else []
    idx = [c for c in idx if c.get("iso3") != cfg.iso3]
    idx.append({"iso3": cfg.iso3, "name": meta["name"], "period": [y0, y1], "updated": meta["generated_at"],
                "synthetic": bool(synthetic)})
    write_json(idx_path, sorted(idx, key=lambda c: c["name"]))
    return out
