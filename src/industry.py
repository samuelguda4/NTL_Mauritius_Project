"""Use case 6 — industrial zones: "where industry lights up the night".

Night-time light alone cannot tell a factory from a shopping centre. Each VIIRS pixel
(≈ 0.21 km²) is therefore scored on six independent satellite signals:

====  ==========================================================  ============================
code  criterion                                                   source
====  ==========================================================  ============================
light radiance ≥ ``rad_min`` nW·cm⁻²·sr⁻¹ (mandatory)             VIIRS VNL V2 (raw, flares kept)
ratio light / (inhabitants + 1) ≥ ``light_per_pop``               VIIRS + GHSL / WorldPop
nres  share of non-residential built-up surface ≥ ``nres_share``   GHSL BUILT-S (built_surface_nres)
no2   tropospheric NO₂ ≥ national ``no2_pct``-th percentile        Sentinel-5P TROPOMI
so2   SO₂ column ≥ national ``so2_pct``-th percentile              Sentinel-5P TROPOMI
lst   daytime land-surface temperature ≥ +``lst_delta`` K vs 5 km  MODIS MOD11A2
====  ==========================================================  ============================

Lit pixels meeting at least ``min_signals`` criteria (light included) are grouped into
*clusters* (8-connected). Each cluster gets a type (heavy industry, business park & logistics,
oil, gas & flares, isolated site to verify) and a confidence level from the number of
concordant signals. Validation computes precision and recall against an official list
(``reference``) or, failing that, OpenStreetMap ``landuse=industrial``.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .lang import LANG

log = logging.getLogger("ntl")

TYPE_LABEL = {
    "fr": {"heavy": "Industrie lourde", "logistics": "Zone d'activités et logistique",
           "hydro": "Hydrocarbures et torchères", "isolated": "Site isolé à vérifier"},
    "en": {"heavy": "Heavy industry", "logistics": "Business park & logistics",
           "hydro": "Oil, gas & flares", "isolated": "Isolated site to verify"},
}[LANG]
TYPE_COLOR = {"heavy": "#00704A", "logistics": "#3F7FC7", "hydro": "#eda100", "isolated": "#e87ba4"}
SIGNALS = ["s_light", "s_ratio", "s_nres", "s_no2", "s_so2", "s_lst"]
SIGNAL_LABEL = {
    "fr": {"s_light": "💡 lumière ≥ seuil", "s_ratio": "👤 lumière / habitant", "s_nres": "🏭 bâti non résidentiel",
           "s_no2": "🚚 NO₂ élevé", "s_so2": "⚗️ SO₂ élevé", "s_lst": "🌡️ chaleur de surface"},
    "en": {"s_light": "💡 light ≥ threshold", "s_ratio": "👤 light per inhabitant", "s_nres": "🏭 non-residential built-up",
           "s_no2": "🚚 high NO₂", "s_so2": "⚗️ high SO₂", "s_lst": "🌡️ surface heat"},
}[LANG]
CONF = {"fr": ("élevée", "moyenne", "faible"), "en": ("high", "medium", "low")}[LANG]


@dataclass
class IndustryParams:
    """Thresholds of the six signals (all documented in the notebook and the dashboard)."""
    rad_min: float = 5.0          # nW·cm⁻²·sr⁻¹ — the pixel must be clearly lit
    light_per_pop: float = 0.1    # radiance / (inhabitants + 1): much light for few residents
    nres_share: float = 0.40      # share of non-residential built-up surface
    no2_pct: int = 75             # national percentile of NO₂ (over lit pixels)
    so2_pct: int = 90             # national percentile of SO₂ (over lit pixels)
    lst_delta: float = 2.0        # K above the 5 km neighbourhood (daytime LST)
    min_signals: int = 3          # criteria met (light included) to keep a pixel
    min_pixels: int = 3           # minimum cluster size (≈ 0.6 km²)
    max_clusters: int = 400       # keep the largest clusters (Earth Engine response size)
    match_km: float = 1.5         # validation: distance to a reference site to count as a match

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------------------
# Earth Engine: signals and clusters
# --------------------------------------------------------------------------------------
def signal_image(ctx, year: int, p: IndustryParams):
    """Six binary signal bands + continuous values on the VIIRS grid (server-side)."""
    import ee
    from . import preprocessing as pp
    cfg, proj, region = ctx.cfg, ctx.proj, ctx.region
    ref, _, _ = pp.annual_vnl(year, ctx.annual_years)
    raw = pp.clean_annual(ref, None).select("rad_raw")          # flares kept: they are a type here
    pop, _ = pp.population_on_grid(year, cfg, proj)
    col = ee.ImageCollection("JRC/GHSL/P2023A/GHS_BUILT_S").filter(ee.Filter.calendarRange(2020, 2020, "year")).first()
    tot = col.select("built_surface").unmask(0).reduceResolution(ee.Reducer.sum(), maxPixels=1024).reproject(proj)
    nres = col.select("built_surface_nres").unmask(0).reduceResolution(ee.Reducer.sum(), maxPixels=1024).reproject(proj)
    nres_share = nres.divide(tot.max(1)).rename("nres_share")
    y5 = min(max(year, 2019), 2025)
    no2 = (ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_NO2").filterDate(f"{y5}-01-01", f"{y5 + 1}-01-01")
           .select("tropospheric_NO2_column_number_density").mean().resample("bilinear").reproject(proj).rename("no2"))
    so2 = (ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_SO2").filterDate(f"{y5}-01-01", f"{y5 + 1}-01-01")
           .select("SO2_column_number_density").mean().resample("bilinear").reproject(proj).rename("so2"))
    lst = (ee.ImageCollection("MODIS/061/MOD11A2").filterDate(f"{year}-01-01", f"{year + 1}-01-01")
           .select("LST_Day_1km").mean().multiply(0.02))
    lst_d = lst.subtract(lst.focalMean(5000, "circle", "meters")).reproject(proj).rename("lst_delta")
    lit = raw.gte(p.rad_min)
    pct = (no2.addBands(so2).updateMask(lit)
           .reduceRegion(ee.Reducer.percentile([p.no2_pct, p.so2_pct]), region, 1113.2, maxPixels=1e10,
                         bestEffort=True, tileScale=cfg.tile_scale))
    no2_thr = ee.Number(pct.get(f"no2_p{p.no2_pct}"))
    so2_thr = ee.Number(pct.get(f"so2_p{p.so2_pct}"))
    s = ee.Image.cat([
        lit.rename("s_light"),
        raw.divide(pop.add(1)).gte(p.light_per_pop).rename("s_ratio"),
        nres_share.gte(p.nres_share).rename("s_nres"),
        no2.gte(no2_thr).unmask(0).rename("s_no2"),
        so2.gte(so2_thr).unmask(0).rename("s_so2"),
        lst_d.gte(p.lst_delta).unmask(0).rename("s_lst"),
    ])
    count = s.reduce(ee.Reducer.sum()).rename("n_signals")
    cand = lit.And(count.gte(p.min_signals)).rename("cand")
    return s.addBands([count, cand, raw.rename("rad"), pop.rename("pop"), nres_share, no2, so2, lst_d]).clip(region)


def detect_clusters(ctx, year: int, years: list[int], p: IndustryParams | None = None) -> dict:
    """Industrial clusters as GeoJSON (client-side), one Earth Engine computation per call.

    Properties: cluster_id, pixels, area_km2, sol, pop, s_* (share of the cluster's pixels meeting
    each criterion), mean_signals, nres_share, no2, so2, lst_delta, flare_overlap, sol_<year>.
    """
    import ee
    from . import preprocessing as pp
    from .gee import ee_call
    p = p or IndustryParams()
    img = signal_image(ctx, year, p)
    cand = img.select("cand").selfMask()
    vec = (cand.addBands(cand).reduceToVectors(
        geometry=ctx.region, crs=ctx.proj, geometryType="polygon", eightConnected=True,
        labelProperty="label", reducer=ee.Reducer.count(), maxPixels=1e10, bestEffort=True)
        .filter(ee.Filter.gte("count", p.min_pixels)).sort("count", False).limit(p.max_clusters))
    flare = ctx.flare if ctx.flare is not None else ee.Image(0)
    means = img.select(SIGNALS + ["n_signals", "nres_share", "no2", "so2", "lst_delta"]).addBands(
        flare.unmask(0).rename("flare_overlap"))
    sums = [img.select("rad").rename("sol"), img.select("pop")]
    for y in years:
        ref, _, _ = pp.annual_vnl(y, ctx.annual_years)
        sums.append(pp.clean_annual(ref, None).select("rad_raw").rename(f"sol_{y}"))
    scale = 463.83
    a = means.reduceRegions(collection=vec, reducer=ee.Reducer.mean(), scale=scale, tileScale=ctx.cfg.tile_scale)
    b = ee.Image.cat(sums).reduceRegions(collection=a, reducer=ee.Reducer.sum(), scale=scale,
                                         tileScale=ctx.cfg.tile_scale)
    gj = ee_call(lambda: b.getInfo(), "grappes industrielles" if LANG == "fr" else "industrial clusters")
    for i, f in enumerate(gj.get("features", [])):
        pr = f["properties"]
        pr["cluster_id"] = f"IND-{i + 1:03d}"
        pr["pixels"] = int(pr.pop("count", 0))
        pr["area_km2"] = round(pr["pixels"] * 0.215, 3)
        pr["mean_signals"] = pr.pop("n_signals", np.nan)
        pr.pop("label", None)
    return gj


OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)
# Overpass rejects anonymous clients (HTTP 406 / 429): an identified User-Agent is required.
OVERPASS_HEADERS = {"User-Agent": "ntl-economic-analysis/2.0 (AfDB x DI4A night-lights notebook)",
                    "Accept": "application/json", "Accept-Encoding": "gzip"}


def _overpass(q: str, timeout: int, urls=OVERPASS_URLS, retries: int = 2) -> list[dict]:
    """POST one Overpass query, trying every public server with exponential back-off."""
    import time as _t
    import requests
    errors = []
    for attempt in range(retries + 1):
        for url in urls:
            try:
                r = requests.post(url, data={"data": q}, headers=OVERPASS_HEADERS, timeout=timeout + 30)
                r.raise_for_status()
                return r.json().get("elements", [])
            except Exception as ex:  # noqa: BLE001 - next server
                errors.append(f"{url.split('/')[2]}: {str(ex)[:60]}")
        if attempt < retries:
            _t.sleep(8 * (attempt + 1))   # servers overloaded (429/5xx): wait, then retry
    raise RuntimeError(" | ".join(errors[-len(urls):]))


def fetch_osm_industrial(iso2: str, timeout: int = 120, urls=OVERPASS_URLS, bbox=None, tile_deg: float = 2.5) -> pd.DataFrame:
    """OpenStreetMap ``landuse=industrial`` areas of the country (Overpass API), as points.

    Public Overpass servers often answer 429/5xx to large country-wide queries. With ``bbox``
    (w, s, e, n — e.g. ``GDFS["ADM0"].total_bounds``) the country is split into small tiles queried
    one by one (lighter, cache-friendly); every tile is retried on several servers with back-off.
    Raises only if a tile cannot be obtained at all (a partial list would bias the recall).
    """
    import math as _m
    if bbox is None:
        q = (f'[out:json][timeout:{timeout}];area["ISO3166-1"="{iso2.upper()}"][admin_level=2]->.a;'
             '(way["landuse"="industrial"](area.a);relation["landuse"="industrial"](area.a););out center tags qt;')
        tiles = [q]
    else:
        w, s, e, n = [float(x) for x in bbox]
        nx, ny = max(1, _m.ceil((e - w) / tile_deg)), max(1, _m.ceil((n - s) / tile_deg))
        tiles = []
        for i in range(nx):
            for j in range(ny):
                b = (s + j * (n - s) / ny, w + i * (e - w) / nx, s + (j + 1) * (n - s) / ny, w + (i + 1) * (e - w) / nx)
                bb = ",".join(f"{v:.4f}" for v in b)
                tiles.append(f'[out:json][timeout:{timeout}];(way["landuse"="industrial"]({bb});'
                             f'relation["landuse"="industrial"]({bb}););out center tags qt;')
    rows, seen = [], set()
    for k, q in enumerate(tiles, 1):
        try:
            els = _overpass(q, timeout, urls)
        except Exception as ex:  # noqa: BLE001
            raise RuntimeError(f"Overpass (OpenStreetMap) unavailable — tile {k}/{len(tiles)}: {ex}") from None
        for el in els:
            c = el.get("center") or {}
            key = (el.get("type"), el.get("id"))
            if "lon" in c and key not in seen:
                seen.add(key)
                rows.append({"name": (el.get("tags") or {}).get("name", ""), "lon": c["lon"], "lat": c["lat"],
                             "source": "OpenStreetMap"})
    if not rows:
        raise RuntimeError("OpenStreetMap: 0 industrial area returned")
    log.info("OpenStreetMap: %d industrial areas (%d tiles)", len(rows), len(tiles))
    return pd.DataFrame(rows, columns=["name", "lon", "lat", "source"])


def fetch_power_plants(iso3: str) -> pd.DataFrame:
    """Fallback reference from Earth Engine: WRI Global Power Plant Database (``WRI/GPPDB/v130``).

    Power plants are only *part* of industry: the list is flagged ``partial`` and the validation then
    reports the recall (share of plants found by the clusters) but not the precision.
    """
    import ee
    fc = ee.FeatureCollection("WRI/GPPDB/v130").filter(ee.Filter.eq("country", iso3.upper()))
    feats = fc.limit(5000).getInfo().get("features", [])
    rows = []
    for f in feats:
        g, p = f.get("geometry") or {}, f.get("properties") or {}
        if g.get("type") == "Point":
            rows.append({"name": p.get("name", ""), "lon": g["coordinates"][0], "lat": g["coordinates"][1],
                         "source": "WRI Global Power Plant Database", "partial": True,
                         "fuel": p.get("fuel1", ""), "capacity_mw": p.get("capacitymw")})
    if not rows:
        raise RuntimeError("WRI GPPD: no power plant for this country")
    return pd.DataFrame(rows)


def load_reference(path) -> pd.DataFrame:
    """Official list of industrial zones: CSV (lon, lat[, name]) or GeoJSON (centroids used)."""
    path = str(path)
    if path.lower().endswith((".geojson", ".json", ".gpkg", ".shp")):
        import geopandas as gpd
        g = gpd.read_file(path).to_crs(4326)
        c = g.geometry.representative_point()
        name = g["name"] if "name" in g else ""
        return pd.DataFrame({"name": name, "lon": c.x, "lat": c.y, "source": path})
    d = pd.read_csv(path)
    lon = next(c for c in d.columns if c.lower() in ("lon", "longitude", "x"))
    lat = next(c for c in d.columns if c.lower() in ("lat", "latitude", "y"))
    return pd.DataFrame({"name": d.get("name", ""), "lon": d[lon], "lat": d[lat], "source": d.get("source", path)})


# --------------------------------------------------------------------------------------
# Analysis (pandas / geopandas, no Earth Engine)
# --------------------------------------------------------------------------------------
def to_gdf(geojson: dict):
    import geopandas as gpd
    feats = (geojson or {}).get("features", [])
    if not feats:
        return gpd.GeoDataFrame({"cluster_id": []}, geometry=[], crs="EPSG:4326")
    g = gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326")
    c = g.geometry.representative_point()
    g["lon"], g["lat"] = c.x.round(5), c.y.round(5)
    return g


def classify(g, p: IndustryParams | None = None):
    """Add ``type``, ``type_label``, ``n_strong`` (signals met by ≥ 50 % of pixels) and ``confidence``."""
    g = g.copy()
    if not len(g):
        return g.assign(type=[], type_label=[], n_strong=[], confidence=[])
    pp_ = g["pop"] / g["pixels"].clip(lower=1)
    hydro = (g["flare_overlap"] >= 0.2) | ((g["s_so2"] >= 0.5) & (g["s_nres"] < 0.3) & (pp_ < 5))
    heavy = (g["s_so2"] >= 0.4) | ((g["s_no2"] >= 0.5) & (g["s_lst"] >= 0.5) & (g["s_nres"] >= 0.4))
    logi = (g["s_nres"] >= 0.5) & (g["s_ratio"] >= 0.5)
    g["type"] = np.select([hydro, heavy, logi], ["hydro", "heavy", "logistics"], "isolated")
    g["type_label"] = g["type"].map(TYPE_LABEL)
    g["n_strong"] = 1 + (g[[s for s in SIGNALS if s != "s_light"]] >= 0.5).sum(axis=1)
    g["confidence"] = np.select([g["n_strong"] >= 5, g["n_strong"] >= 4], [CONF[0], CONF[1]], CONF[2])
    return g


def assign_units(g, gdfs: dict, names: dict):
    import geopandas as gpd
    g = g.copy()
    pts = gpd.GeoDataFrame(g[["cluster_id"]], geometry=gpd.points_from_xy(g["lon"], g["lat"]), crs="EPSG:4326")
    for lv in ("ADM1", "ADM2"):
        if lv not in gdfs:
            continue
        j = gpd.sjoin(pts, gdfs[lv][["unit_id", "geometry"]], how="left", predicate="within")
        j = j[~j.index.duplicated(keep="first")]
        g[f"{lv.lower()}_id"] = j["unit_id"].values
        g[f"{lv.lower()}_name"] = g[f"{lv.lower()}_id"].map(names)
    return g


def validate(g, ref: pd.DataFrame | None, match_km: float = 1.5) -> dict:
    """Precision = share of clusters within ``match_km`` of a reference site; recall = share of
    reference sites within ``match_km`` of a cluster."""
    if ref is None or not len(ref) or not len(g):
        return {"available": False}
    import geopandas as gpd
    crs = g.estimate_utm_crs()
    a = g.to_crs(crs)
    r = gpd.GeoDataFrame(ref, geometry=gpd.points_from_xy(ref["lon"], ref["lat"]), crs="EPSG:4326").to_crs(crs)
    d_c = a.geometry.apply(lambda geom: r.distance(geom).min()) / 1000
    d_r = r.geometry.apply(lambda pt: a.distance(pt).min()) / 1000
    matched = d_c <= match_km
    by_type = (pd.DataFrame({"type": g["type"], "matched": matched.values})
               .groupby("type")["matched"].agg(["sum", "count"]).reset_index())
    by_type["precision"] = by_type["sum"] / by_type["count"]
    prec, rec = float(matched.mean()), float((d_r <= match_km).mean())
    partial = bool("partial" in ref and ref["partial"].fillna(False).astype(bool).any())
    if partial:   # e.g. power plants only: most clusters legitimately match nothing -> precision meaningless
        prec = None
    return {"available": True, "partial": partial, "source": str(ref["source"].iloc[0]) if "source" in ref else "",
            "n_clusters": int(len(g)), "n_reference": int(len(r)), "match_km": match_km,
            "precision": prec, "recall": rec,
            "f1": (2 * prec * rec / (prec + rec) if prec + rec > 0 else 0.0) if prec is not None else None,
            "matched": matched.values.tolist(), "by_type": by_type.rename(columns={"sum": "matched", "count": "n"}),
            "unmatched_reference": ref[(d_r > match_km).values].reset_index(drop=True)}


def series(g, years: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Industrial light by year: total and by type (raw radiance summed over the clusters)."""
    cols = [f"sol_{y}" for y in years if f"sol_{y}" in g]
    if not len(g) or not cols:
        return pd.DataFrame(columns=["year", "sol"]), pd.DataFrame(columns=["year", "type", "sol"])
    tot = pd.DataFrame({"year": [int(c[4:]) for c in cols], "sol": [float(g[c].sum()) for c in cols]})
    bt = g.groupby("type")[cols].sum().T
    bt.index = [int(c[4:]) for c in bt.index]
    bt = bt.rename_axis("year").reset_index().melt(id_vars="year", var_name="type", value_name="sol")
    return tot, bt


def analyse(geojson: dict, gdfs: dict, names: dict, annual: pd.DataFrame, wdi: pd.DataFrame | None = None,
            reference: pd.DataFrame | None = None, p: IndustryParams | None = None, cfg=None) -> dict:
    """Full use-case 6 analysis from the cluster GeoJSON. Returns the result dict ``R["industry"]``."""
    from . import indicators as ind
    p = p or IndustryParams()
    g = classify(to_gdf(geojson), p)
    if not len(g):
        return {"available": False, "params": p.to_dict(), "n": 0}
    g = assign_units(g, gdfs, names)
    years = sorted(int(c[4:]) for c in g.columns if c.startswith("sol_") and c[4:].isdigit())
    tot, bt = series(g, years)
    nat = annual[annual["level"] == "ADM0"].set_index("year")
    raw = nat["sol_raw"] if "sol_raw" in nat else nat["sol"]
    tot["share_of_national"] = tot["year"].map(lambda y: tot.loc[tot["year"] == y, "sol"].iloc[0] / raw.get(y, np.nan))
    trend = ind.theil_sen_growth(tot["year"], tot["sol"]) if len(tot) >= 4 else {}
    type_trends = {}
    for t, d in bt.groupby("type"):
        if len(d) >= 4 and d["sol"].min() > 0:
            type_trends[t] = ind.theil_sen_growth(d["year"], d["sol"])
    units = {}
    y1 = years[-1] if years else None
    for lv in ("ADM1", "ADM2"):
        col = f"{lv.lower()}_id"
        if col not in g or y1 is None:
            continue
        u = g.groupby(col).agg(n_clusters=("cluster_id", "count"), ind_sol=(f"sol_{y1}", "sum"),
                               area_km2=("area_km2", "sum")).reset_index().rename(columns={col: "unit_id"})
        a = annual[(annual["level"] == lv) & (annual["year"] == y1)].set_index("unit_id")
        araw = a["sol_raw"] if "sol_raw" in a else a["sol"]
        u["ind_share"] = u["unit_id"].map(lambda k: u.loc[u["unit_id"] == k, "ind_sol"].iloc[0] / araw.get(k, np.nan))
        u["name"] = u["unit_id"].map(names)
        units[lv] = u.sort_values("ind_sol", ascending=False).reset_index(drop=True)
    va = {}
    if wdi is not None and "industry_va_const_usd" in wdi and len(tot) >= 5:
        j = tot.merge(wdi[["year", "industry_va_const_usd"]], on="year").dropna()
        if len(j) >= 5:
            dl = np.diff(np.log(j["sol"].values))
            dv = np.diff(np.log(j["industry_va_const_usd"].values))
            from scipy import stats
            rr, pv = stats.pearsonr(dl, dv) if len(dl) >= 4 else (np.nan, np.nan)
            va = {"n": int(len(dl)), "corr_growth": float(rr), "p_value": float(pv),
                  "corr_levels": float(np.corrcoef(np.log(j["sol"]), np.log(j["industry_va_const_usd"]))[0, 1]),
                  "table": j}
    val = validate(g, reference, p.match_km)
    if val.get("available"):
        g["validated"] = val["matched"]
    counts = g["type"].value_counts().to_dict()
    return {"available": True, "params": p.to_dict(), "clusters": g, "n": int(len(g)), "years": years,
            "counts": counts, "conf_counts": g["confidence"].value_counts().to_dict(),
            "series": tot, "by_type": bt, "trend": trend, "type_trends": type_trends, "units": units,
            "industry_va": va, "validation": val,
            "top": g.sort_values(f"sol_{y1}" if y1 else "sol", ascending=False).head(15)}


# --------------------------------------------------------------------------------------
# Key messages and figures
# --------------------------------------------------------------------------------------
def _pct(x, d=1, sign=True):
    if x is None or not np.isfinite(x):
        return "n.d." if LANG == "fr" else "n/a"
    s = f"{100 * x:+.{d}f}" if sign else f"{100 * x:.{d}f}"
    return (s.replace(".", ",") + " %") if LANG == "fr" else s + "%"


def key_messages(res: dict | None) -> list[dict]:
    if not res or not res.get("available"):
        return []
    c, n = res["counts"], res["n"]
    tr = res.get("trend") or {}
    share = res["series"]["share_of_national"].iloc[-1] if len(res["series"]) else np.nan
    v = res.get("validation", {})
    top = res["units"].get("ADM1")
    top_name = top["name"].iloc[0] if top is not None and len(top) else ""
    if LANG == "fr":
        txt = (f"{n} grappes industrielles détectées par concordance de signaux satellitaires : "
               f"{c.get('heavy', 0)} d'industrie lourde, {c.get('logistics', 0)} zones d'activités et de logistique, "
               f"{c.get('hydro', 0)} sites d'hydrocarbures et {c.get('isolated', 0)} sites isolés à vérifier. "
               f"Elles émettent {_pct(share, 1, False)} de la lumière nationale (dernière année) ; "
               f"leur lumière évolue de {_pct(tr.get('growth'))} par an. {top_name} concentre la plus forte activité industrielle.")
        why = (f"rappel {_pct(v['recall'], 0, False)} sur {v['n_reference']} centrales électriques (référence partielle : {v['source']})"
               if v.get("partial") else
               f"précision {_pct(v['precision'], 0, False)} et rappel {_pct(v['recall'], 0, False)} face à la liste de référence"
               if v.get("available") else "aucune liste de référence pour valider la détection")
        theme = "Zones industrielles"
    else:
        txt = (f"{n} industrial clusters detected from concordant satellite signals: {c.get('heavy', 0)} heavy industry, "
               f"{c.get('logistics', 0)} business parks & logistics, {c.get('hydro', 0)} oil & gas sites and "
               f"{c.get('isolated', 0)} isolated sites to verify. They emit {_pct(share, 1, False)} of national light "
               f"(latest year); their light changes by {_pct(tr.get('growth'))} per year. {top_name} has the most industrial activity.")
        why = (f"recall {_pct(v['recall'], 0, False)} on {v['n_reference']} power plants (partial reference: {v['source']})"
               if v.get("partial") else
               f"precision {_pct(v['precision'], 0, False)} and recall {_pct(v['recall'], 0, False)} against the reference list"
               if v.get("available") else "no reference list available to validate the detection")
        theme = "Industrial zones"
    score = v.get("recall", 0) if v.get("partial") else (v.get("f1") or 0)
    conf = CONF[1] if v.get("available") and score >= 0.6 else CONF[2]
    return [{"theme": theme, "confidence": conf, "why": why, "text": txt}]


def map_layer(res: dict):
    """GeoDataFrame ready for folium / the dashboard (one polygon per cluster)."""
    g = res["clusters"].copy()
    y1 = res["years"][-1]
    keep = ["cluster_id", "type", "type_label", "confidence", "n_strong", "pixels", "area_km2", "lon", "lat",
            f"sol_{y1}", "adm1_name", "adm2_name", "validated", *SIGNALS, "nres_share", "lst_delta", "geometry"]
    return g[[c for c in keep if c in g]].rename(columns={f"sol_{y1}": "sol_last"})


LIMITS = {
    "fr": [("Zones industrielles", "La détection repose sur des seuils : une centrale, un port ou un grand centre "
            "commercial peut cumuler les signaux ; une usine peu éclairée ou sans émissions visibles échappe à la "
            "détection. Sentinel-5P (≈ 5 km) et MODIS (1 km) sont plus grossiers que VIIRS : les signaux NO₂/SO₂/chaleur "
            "qualifient un voisinage, pas un bâtiment.")],
    "en": [("Industrial zones", "Detection relies on thresholds: a power plant, a port or a large shopping centre can "
            "meet the signals; a dimly lit factory without visible emissions is missed. Sentinel-5P (≈ 5 km) and MODIS "
            "(1 km) are coarser than VIIRS: NO₂/SO₂/heat signals describe a neighbourhood, not a building.")],
}[LANG]


def recommendations(res: dict | None) -> list[str]:
    if not res or not res.get("available"):
        return []
    n_iso = res["counts"].get("isolated", 0)
    if LANG == "fr":
        r = [f"Faire vérifier sur imagerie haute résolution les {n_iso} sites isolés et compléter le registre officiel "
             "des zones industrielles, qui sert de référence de validation."] if n_iso else []
        r.append("Suivre la lumière des grappes industrielles chaque mois comme indicateur avancé de la production "
                 "industrielle, en la confrontant à l'indice de production industrielle lorsqu'il existe.")
    else:
        r = [f"Have the {n_iso} isolated sites checked on high-resolution imagery and complete the official register "
             "of industrial zones used as the validation reference."] if n_iso else []
        r.append("Monitor the light of industrial clusters monthly as a leading indicator of industrial output, and "
                 "compare it with the industrial production index where one exists.")
    return r
