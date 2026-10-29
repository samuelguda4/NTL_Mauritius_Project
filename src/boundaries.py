"""Administrative boundaries filtered by ISO3 (geoBoundaries CGAZ v6, or FAO GAUL).

Each unit receives a stable identifier `unit_id = "<LEVEL>_<system:index>"`, identical on the
Earth Engine side (used for zonal statistics) and on the local side (GeoDataFrame used for maps
and exports), so that the two can always be joined.
"""
from __future__ import annotations

import logging
import unicodedata

import geopandas as gpd
import pandas as pd

from .config import DATASETS
from .gee import GEEError, ee_call

log = logging.getLogger("ntl")

# ISO3 -> FAO GAUL 2015 ADM0_NAME for the names that differ from the ISO short name.
# Used only by the deprecated GAUL 2015 fallback (GAUL 2025 carries an ISO3 field).
GAUL2015_NAMES = {
    "CIV": "Côte d'Ivoire", "COD": "Democratic Republic of the Congo", "COG": "Congo",
    "TZA": "United Republic of Tanzania", "BOL": "Bolivia", "VEN": "Venezuela",
    "IRN": "Iran  (Islamic Republic of)", "SYR": "Syrian Arab Republic", "LAO": "Lao People's Democratic Republic",
    "KOR": "Republic of Korea", "PRK": "Dem People's Rep of Korea", "MDA": "Moldova, Republic of",
    "RUS": "Russian Federation", "VNM": "Viet Nam", "GBR": "U.K. of Great Britain and Northern Ireland",
    "USA": "United States of America", "CPV": "Cape Verde", "SWZ": "Swaziland", "MKD": "The former Yugoslav Republic of Macedonia",
    "GMB": "Gambia", "LBY": "Libya", "EGY": "Egypt", "PSE": "West Bank", "TUR": "Turkey", "CZE": "Czech Republic",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _first_existing(props: list[str], candidates: list[str]) -> str | None:
    low = {p.lower(): p for p in props}
    for c in candidates:
        if c.lower() in low:
            return low[c.lower()]
    return None


def _ee_boundaries(iso3: str, level: str, source: str, country_name: str = ""):
    """Return (ee.FeatureCollection with unit_id/name/level, source label)."""
    import ee
    n = {"ADM0": 0, "ADM1": 1, "ADM2": 2}[level]
    if source == "geoboundaries":
        meta = DATASETS["geoboundaries"]
        fc = ee.FeatureCollection(meta["id"].format(level=level)).filter(ee.Filter.eq("shapeGroup", iso3))
        name_field, label = "shapeName", "geoBoundaries CGAZ v6.0.0"
    else:
        fc = ee.FeatureCollection(DATASETS["gaul2025"]["id"].format(n=n))
        try:
            props = ee_call(lambda: fc.first().propertyNames().getInfo(), "GAUL 2025 properties")
        except GEEError:
            props = []   # GAUL 2025 unavailable -> deprecated GAUL 2015 + ISO3 table below
        iso_f = _first_existing(props, ["ISO3_CODE", "iso3_code"])
        name_f = _first_existing(props, [f"GAUL{n}_NAME", f"gaul{n}_name"])
        if iso_f and name_f:
            fc, name_field, label = fc.filter(ee.Filter.eq(iso_f, iso3)), name_f, "FAO GAUL 2025"
        else:  # deprecated GAUL 2015 + ISO3 correspondence table
            fc = ee.FeatureCollection(DATASETS["gaul2015"]["id"].format(n=n))
            gname = GAUL2015_NAMES.get(iso3, country_name)
            fc = fc.filter(ee.Filter.eq("ADM0_NAME", gname))
            name_field, label = f"ADM{n}_NAME", "FAO GAUL 2015 (ISO3 table)"

    def _tag(f):
        return ee.Feature(f.geometry(), {
            "unit_id": ee.String(level + "_").cat(f.id()),
            "name": f.get(name_field), "level": level})
    return fc.map(_tag), label


def bad_name(s) -> bool:
    """True if a unit name is missing or was corrupted into question marks.

    Some geoBoundaries assets in Earth Engine store non-Latin names (e.g. Arabic) as "????"."""
    if s is None:
        return True
    s = str(s).strip()
    if not s or s.lower() in ("nan", "none"):
        return True
    return s.count("?") >= max(1, len(s.replace(" ", "")) // 2)


def _fill_names_from_gaul(gdf: gpd.GeoDataFrame, iso3: str, level: str) -> gpd.GeoDataFrame:
    """Replace corrupted names with the FAO GAUL name of the unit containing each representative point."""
    bad = gdf["name"].map(bad_name)
    if level == "ADM0" or not bad.any():
        return gdf
    try:
        import ee
        fc, label = _ee_boundaries(iso3, level, "gaul")
        light = fc.map(lambda f: f.simplify(maxError=500)).select(["name"])
        ref = ee_call(lambda: ee.data.computeFeatures(
            {"expression": light, "fileFormat": "GEOPANDAS_GEODATAFRAME"}), f"GAUL names {level}")
        ref = gpd.GeoDataFrame(ref, geometry="geometry", crs="EPSG:4326")
        ref = ref[~ref["name"].map(bad_name)].rename(columns={"name": "ref_name"})[["ref_name", "geometry"]]
        pts = gdf.loc[bad, ["geometry"]].copy()
        pts["geometry"] = pts.geometry.representative_point()
        j = gpd.sjoin(pts, ref, how="left", predicate="within")
        j = j[~j.index.duplicated(keep="first")]
        gdf = gdf.copy()
        ok = j["ref_name"].notna()
        gdf.loc[j.index[ok], "name"] = j.loc[ok, "ref_name"].values
        log.info("%s: %d corrupted names replaced from %s", level, int(ok.sum()), label)
    except Exception as e:  # noqa: BLE001
        log.warning("%s: could not repair corrupted names (%s)", level, e)
    return gdf


def get_boundaries(cfg, simplify_m: float = 200.0) -> tuple[dict, dict, dict]:
    """Fetch ADM0 + requested levels for `cfg.iso3`.

    Returns
    -------
    gdfs   : {level: GeoDataFrame[unit_id, name, level, parent_id, parent_name, geometry]}
    ee_fcs : {level: ee.FeatureCollection} (full-resolution geometry, for zonal statistics)
    meta   : {level: source label}
    """
    levels = ["ADM0"] + [lv for lv in cfg.admin_levels]
    sources = [cfg.boundary_source] + [s for s in ("geoboundaries", "gaul") if s != cfg.boundary_source]
    gdfs, fcs, meta = {}, {}, {}
    for lv in levels:
        for src in sources:
            try:
                fc, label = _ee_boundaries(cfg.iso3, lv, src, cfg.country.get("name", ""))
                n = ee_call(lambda: fc.size().getInfo(), f"boundaries {lv}")
            except GEEError as e:
                log.warning("%s boundaries via %s unavailable: %s", lv, src, e)
                continue
            if n == 0:
                log.warning("No %s unit for %s in %s", lv, cfg.iso3, src)
                continue
            light = fc.map(lambda f: f.simplify(maxError=simplify_m))
            import ee
            gdf = ee_call(lambda: ee.data.computeFeatures(
                {"expression": light, "fileFormat": "GEOPANDAS_GEODATAFRAME"}), f"geometries {lv}")
            gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs="EPSG:4326")
            gdf = gdf[["unit_id", "name", "level", "geometry"]]
            if src == "geoboundaries":
                gdf = _fill_names_from_gaul(gdf, cfg.iso3, lv)
            gdfs[lv], fcs[lv], meta[lv] = gdf, fc, label
            log.info("%s: %d units (%s)", lv, n, label)
            break
        else:
            if lv in ("ADM0", "ADM1"):
                raise GEEError(f"Could not obtain {lv} boundaries for {cfg.iso3}.")
            log.warning("Level %s dropped (no source available).", lv)
    return attach_parents(gdfs), fcs, meta


def attach_parents(gdfs: dict) -> dict:
    """Attach each ADM2 unit to the ADM1 unit containing its representative point."""
    for lv in gdfs:
        gdfs[lv] = gdfs[lv].assign(parent_id=None, parent_name=None) if "parent_id" not in gdfs[lv] else gdfs[lv]
    if "ADM2" in gdfs and "ADM1" in gdfs:
        child = gdfs["ADM2"].copy()
        pts = child.copy()
        pts["geometry"] = child.geometry.representative_point()
        parent = gdfs["ADM1"][["unit_id", "name", "geometry"]].rename(
            columns={"unit_id": "parent_id", "name": "parent_name"})
        j = gpd.sjoin(pts.drop(columns=["parent_id", "parent_name"]), parent, how="left", predicate="within")
        j = j[~j.index.duplicated(keep="first")]
        child["parent_id"] = j["parent_id"].values
        child["parent_name"] = j["parent_name"].values
        # units whose point falls outside every ADM1 polygon (coastal slivers): nearest parent
        miss = child["parent_id"].isna()
        if miss.any():
            near = gpd.sjoin_nearest(pts[miss].drop(columns=["parent_id", "parent_name"]).to_crs(3857),
                                     parent.to_crs(3857), how="left")
            near = near[~near.index.duplicated(keep="first")]
            child.loc[miss, "parent_id"] = near["parent_id"].values
            child.loc[miss, "parent_name"] = near["parent_name"].values
        gdfs["ADM2"] = child
    if "ADM1" in gdfs:
        gdfs["ADM1"] = gdfs["ADM1"].assign(parent_id="ADM0", parent_name=None)
    return gdfs


def area_km2(gdf: gpd.GeoDataFrame) -> pd.Series:
    """Area of each unit in km², computed in an equal-area projection (EPSG:6933)."""
    return gdf.to_crs(6933).area / 1e6
