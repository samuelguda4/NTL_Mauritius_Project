"""Zonal statistics from Earth Engine -> tidy pandas tables.

Every function returns a long ("tidy") DataFrame with at least `unit_id`, `level` and a
time key (`date` or `year`). Requests are chunked by year so that each Earth Engine call
stays well below the time-out and memory limits.

Output tables
-------------
monthly     : unit_id, level, name, date, sol, lit, valid, n, valid_frac, sol_adj
annual      : unit_id, level, name, year, sol, sol_raw, lit_km2, area_km2, pop, pop_inhabited,
              pop_dark_<t>, pop_urban, sol_urban, pop_dark_urban, pop_dark_rural, flare_sol,
              product, pop_source_year
dmsp        : unit_id, level, year, sol_dn, n_sat, n_lit, sat_share
long        : unit_id, level, year, dn_sum, source        (harmonised DMSP-like series)
daily       : unit_id, level, date, window, sol, valid, n, valid_frac, sol_adj
no2         : unit_id, level, year, no2_mean
landcover   : unit_id, level, tree_share, crop_share, built_share, ...
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from . import preprocessing as pp
from .config import DATASETS
from .gee import ee_call, fc_to_df

log = logging.getLogger("ntl")


def _thr_name(t: float) -> str:
    return "pop_dark_" + f"{t:g}".replace(".", "p")


def merged_units(fcs: dict, levels: tuple[str, ...] = ("ADM0", "ADM1", "ADM2")):
    """Merge the FeatureCollections of several levels into one (one reduceRegions per image)."""
    import ee
    out = None
    for lv in levels:
        if lv in fcs:
            out = fcs[lv] if out is None else out.merge(fcs[lv])
    return ee.FeatureCollection(out)


def _reduce(img, units, scale, cfg, props: dict | None = None, reducer=None):
    import ee
    red = reducer or ee.Reducer.sum()
    out = img.reduceRegions(collection=units, reducer=red, scale=scale, tileScale=cfg.tile_scale)
    props = props or {}
    return out.map(lambda f: ee.Feature(None, f.toDictionary()).set(props))


# --------------------------------------------------------------------------------------
# Context shared by all steps
# --------------------------------------------------------------------------------------
class GEEContext:
    """Objects re-used by every acquisition step (projection, region, flare mask...)."""

    def __init__(self, cfg, fcs: dict):
        import ee
        self.cfg, self.fcs = cfg, fcs
        # simplified outline (500 m) for clipping and thumbnails: much cheaper than the full coastline
        self.region = fcs["ADM0"].geometry().simplify(500)
        self.proj = pp.viirs_projection()
        self.annual_years = pp.available_annual_years()
        if not self.annual_years:
            raise RuntimeError("Aucun composite annuel VNL V2 disponible dans Earth Engine.")
        self.flare, self.flare_polys = None, None
        self._ee = ee

    def build_flare_mask(self):
        """Detect flare candidates once (union over the study period), vectorise them, and keep a
        cheap painted mask for all later requests. Returns the candidate polygons (GeoJSON)."""
        polys = None
        if self.cfg.flare_mode == "auto":
            yrs = [y for y in self.cfg.years if y in self.annual_years] or list(self.annual_years)[-3:]
            imgs = [pp.annual_vnl(y, self.annual_years)[0] for y in yrs]
            pop, _ = pp.population_on_grid(yrs[-1], self.cfg, self.proj)
            core = pp.flare_core(self.cfg, self.region, imgs, self.proj, pop)
            polys = pp.flare_polygons(core, self.region)
        if self.cfg.flare_mode != "off":
            self.flare = pp.flare_mask_from_vectors(self.cfg, polys, self.proj)
        self.flare_polys = polys
        return polys


# --------------------------------------------------------------------------------------
# VIIRS monthly
# --------------------------------------------------------------------------------------
def level_groups(levels) -> list[tuple[str, ...]]:
    """ADM0+ADM1 in one request, ADM2 (often hundreds of units) in its own request."""
    small = tuple(lv for lv in levels if lv in ("ADM0", "ADM1"))
    return [g for g in (small, tuple(lv for lv in levels if lv == "ADM2")) if g]


def monthly_zonal(ctx: GEEContext, levels=("ADM0", "ADM1", "ADM2"), progress=print) -> pd.DataFrame:
    """Monthly Sum of Lights per unit after cleaning (cf_cvg, negatives, spikes, background, flares)."""
    frames = [_monthly_zonal(ctx, grp, progress) for grp in level_groups(levels)]
    out = pd.concat([f for f in frames if len(f)], ignore_index=True) if frames else pd.DataFrame()
    return finalize_monthly(out, ctx.cfg.min_valid_frac)


def _monthly_zonal(ctx: GEEContext, levels, progress=print) -> pd.DataFrame:
    import ee
    cfg = ctx.cfg
    units = merged_units(ctx.fcs, levels)
    frames = []
    vm = DATASETS["viirs_monthly"]
    for y in cfg.years:
        ref, ref_y, _ = pp.annual_vnl(y, ctx.annual_years)
        col = ee.ImageCollection(vm["id"]).filterDate(f"{y}-01-01", f"{y + 1}-01-01")

        def per_image(img, ref=ref):
            c = pp.clean_monthly(img, cfg, ref, ctx.flare)
            return _reduce(c, units, vm["scale"], cfg, {"date": img.date().format("YYYY-MM-01")})
        df = fc_to_df(col.map(per_image).flatten(), f"VIIRS mensuel {y}")
        if len(df):
            df["annual_ref_year"] = ref_y
            frames.append(df)
        progress(f"  VIIRS mensuel {y} [{'+'.join(levels)}] : {len(df)} lignes (masque annuel {ref_y})")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def finalize_monthly(df: pd.DataFrame, min_valid_frac: float) -> pd.DataFrame:
    """Compute the valid share and the coverage-adjusted SoL (NaN when coverage is too low)."""
    if df.empty:
        return df
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["valid_frac"] = df["valid"] / df["n"].replace(0, np.nan)
    df["sol_adj"] = np.where(df["valid_frac"] >= min_valid_frac,
                             df["sol"] / df["valid_frac"].clip(lower=1e-9), np.nan)
    return df.sort_values(["level", "unit_id", "date"]).reset_index(drop=True)


# --------------------------------------------------------------------------------------
# VIIRS annual (VNL V2) + population, electricity-access proxy, urban/rural split
# --------------------------------------------------------------------------------------
def annual_zonal(ctx: GEEContext, levels=("ADM0", "ADM1", "ADM2"), progress=print) -> pd.DataFrame:
    """Annual indicators per unit (see module docstring for the columns)."""
    import ee
    cfg = ctx.cfg
    units = merged_units(ctx.fcs, levels)
    area = ee.Image.pixelArea().divide(1e6).reproject(ctx.proj)
    frames = []
    for y in cfg.years:
        if y not in ctx.annual_years:
            progress(f"  VNL annuel {y} : non publié — année ignorée (la série mensuelle la couvre)")
            continue
        ref, _, cid = pp.annual_vnl(y, ctx.annual_years)
        a = pp.clean_annual(ref, ctx.flare)
        rad, raw = a.select("rad"), a.select("rad_raw")
        pop, pop_src = pp.population_on_grid(y, cfg, ctx.proj)
        urban = pp.urban_on_grid(y, ctx.proj)
        inhab = pop.gte(cfg.pop_min)
        dark_nf = rad.lt(cfg.noise_floor)
        bands = [
            rad.rename("sol"), raw.rename("sol_raw"),
            rad.gte(cfg.noise_floor).multiply(area).rename("lit_km2"), area.rename("area_km2"),
            pop.rename("pop"), pop.multiply(inhab).rename("pop_inhabited"),
            pop.multiply(urban).rename("pop_urban"), rad.multiply(urban).rename("sol_urban"),
            pop.multiply(inhab).multiply(dark_nf).multiply(urban).rename("pop_dark_urban"),
            pop.multiply(inhab).multiply(dark_nf).multiply(urban.Not()).rename("pop_dark_rural"),
        ]
        for t in cfg.dark_thresholds:
            bands.append(pop.multiply(inhab).multiply(rad.lt(t)).rename(_thr_name(t)))
        if ctx.flare is not None:
            bands.append(raw.multiply(ctx.flare).rename("flare_sol"))
        img = ee.Image.cat(bands)
        df = fc_to_df(_reduce(img, units, DATASETS["viirs_annual_v22"]["scale"], cfg, {"year": y}),
                      f"VNL annuel {y}")
        df["product"], df["pop_source_year"] = cid, str(pop_src)
        frames.append(df)
        progress(f"  VNL annuel {y} : {len(df)} unités ({cid.split('/')[-1]}, population {pop_src})")
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if "flare_sol" not in out.columns and len(out):
        out["flare_sol"] = 0.0
    return out


# --------------------------------------------------------------------------------------
# DMSP-OLS (1992–2013): saturation diagnostics and raw long series
# --------------------------------------------------------------------------------------
def dmsp_zonal(ctx: GEEContext, levels=("ADM0", "ADM1"), years=range(1992, 2014), progress=print) -> pd.DataFrame:
    import ee
    cfg = ctx.cfg
    units = merged_units(ctx.fcs, levels)
    frames = []
    for y in years:
        dn = pp.dmsp_year(y)
        if ctx.flare is not None:
            dn = dn.addBands(dn.select("dn").where(ctx.flare, 0), overwrite=True)
        img = ee.Image.cat([dn.select("dn").rename("sol_dn"), dn.select("sat").rename("n_sat"),
                            dn.select("dn").gt(0).rename("n_lit")])
        df = fc_to_df(_reduce(img, units, DATASETS["dmsp"]["scale"], cfg, {"year": y}), f"DMSP {y}")
        frames.append(df)
    progress(f"  DMSP-OLS : {len(frames)} années")
    out = pd.concat(frames, ignore_index=True)
    out["sat_share"] = out["n_sat"] / out["n_lit"].replace(0, np.nan)
    return out


def harmonized_zonal(ctx: GEEContext, levels=("ADM0", "ADM1"), progress=print) -> pd.DataFrame:
    """Harmonised DMSP-like series (Li et al., 2020), DN > dmsp_min_dn, 1992 → last year."""
    import ee
    cfg = ctx.cfg
    units = merged_units(ctx.fcs, levels)
    frames = []
    for key in ("harmonized_dmsp", "harmonized_viirs"):
        cid = DATASETS[key]["id"]
        avail = pp.harmonized_years(key)
        yrs = [y for y in sorted(avail) if cfg.long_start_year <= y <= cfg.end_year
               and (y <= 2013 if key == "harmonized_dmsp" else y >= 2014)]
        for y in yrs:
            dn = pp.harmonized_year(key, avail[y])
            dn = dn.where(dn.lte(cfg.dmsp_min_dn), 0)
            if ctx.flare is not None:
                dn = dn.where(ctx.flare, 0)
            # single-band image: name the reducer output explicitly (otherwise it is called "sum")
            df = fc_to_df(_reduce(dn, units, 926.6, cfg, {"year": y}, ee.Reducer.sum().setOutputs(["dn_sum"])),
                          f"harmonisé {y}")
            df["source"] = "DMSP (calibré)" if key == "harmonized_dmsp" else "VIIRS converti (DMSP-like)"
            frames.append(df)
        progress(f"  {cid.split('/')[-1]} : {len(yrs)} années")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# --------------------------------------------------------------------------------------
# Black Marble daily windows (shocks)
# --------------------------------------------------------------------------------------
def default_daily_windows(cfg) -> list[dict]:
    """COVID-19 window (if inside the study period) + user-defined windows."""
    w = []
    if cfg.start_year <= 2020 <= cfg.end_year:
        w.append({"id": "covid19", "label": "COVID-19", "start": "2019-12-01", "end": "2020-12-31"})
    return w + list(cfg.daily_windows)


def daily_zonal(ctx: GEEContext, windows: list[dict], levels=("ADM0", "ADM1"), chunk_days: int = 92,
                gap_filled: bool = False, progress=print) -> pd.DataFrame:
    """Daily Black Marble SoL over lit pixels, with quality masks, for each window."""
    import ee
    cfg = ctx.cfg
    units = merged_units(ctx.fcs, levels)
    bm = DATASETS["black_marble_daily"]
    frames = []
    for w in windows:
        y0 = pd.Timestamp(w["start"]).year - 1
        ref, _, _ = pp.annual_vnl(y0, ctx.annual_years)
        lit = pp.clean_annual(ref, ctx.flare).select("rad").gte(cfg.noise_floor)
        for s in pd.date_range(w["start"], w["end"], freq=f"{chunk_days}D"):
            e = min(s + pd.Timedelta(days=chunk_days), pd.Timestamp(w["end"]) + pd.Timedelta(days=1))
            col = ee.ImageCollection(bm["id"]).filterDate(s.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d"))

            def per_image(img, lit=lit):
                c = pp.clean_black_marble(img, lit, gap_filled)
                return _reduce(c, units, bm["scale"], cfg, {"date": img.date().format("YYYY-MM-dd")})
            df = fc_to_df(col.map(per_image).flatten(), f"Black Marble {s.date()}")
            if len(df):
                df["window"] = w["id"]
                frames.append(df)
        progress(f"  Black Marble — fenêtre {w['label']} ({w['start']} → {w['end']})")
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if len(out):
        out["date"] = pd.to_datetime(out["date"])
        out["valid_frac"] = out["valid"] / out["n"].replace(0, np.nan)
        out["sol_adj"] = np.where(out["valid_frac"] >= 0.5, out["sol"] / out["valid_frac"].clip(lower=1e-9), np.nan)
    return out


# --------------------------------------------------------------------------------------
# Complementary indicators: NO2 and land cover
# --------------------------------------------------------------------------------------
def no2_zonal(ctx: GEEContext, levels=("ADM0", "ADM1", "ADM2"), progress=print) -> pd.DataFrame:
    """Annual mean tropospheric NO2 column (Sentinel-5P), complete years from 2019."""
    import ee
    cfg = ctx.cfg
    units = merged_units(ctx.fcs, levels)
    meta = DATASETS["no2"]
    frames = []
    for y in [y for y in cfg.years if y >= 2019]:
        img = (ee.ImageCollection(meta["id"]).filterDate(f"{y}-01-01", f"{y + 1}-01-01")
               .select(meta["bands"][0]).mean().rename("no2_mean"))
        frames.append(fc_to_df(_reduce(img, units, meta["scale"], cfg, {"year": y},
                                       ee.Reducer.mean().setOutputs(["no2_mean"])), f"NO2 {y}"))
    progress(f"  NO₂ Sentinel-5P : {len(frames)} années")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def landcover_zonal(ctx: GEEContext, levels=("ADM0", "ADM1", "ADM2")) -> pd.DataFrame:
    """Shares of ESA WorldCover 2021 classes per unit (computed at 100 m)."""
    import ee
    units = merged_units(ctx.fcs, levels)
    m = ee.ImageCollection(DATASETS["worldcover"]["id"]).first().select("Map")
    img = ee.Image.cat([m.eq(10).rename("tree_share"), m.eq(30).Or(m.eq(20)).rename("grass_shrub_share"),
                        m.eq(40).rename("crop_share"), m.eq(50).rename("built_share"),
                        m.eq(60).rename("bare_share"), m.eq(80).rename("water_share")])
    # class fractions computed from the 10 m pixels (mean of indicators), not from the 100 m
    # pyramid level, which for a categorical layer would over-represent the dominant class
    img = img.reduceResolution(ee.Reducer.mean(), maxPixels=128).reproject(m.projection().atScale(100))
    return fc_to_df(_reduce(img, units, 100, ctx.cfg, {}, ee.Reducer.mean()), "WorldCover")


# --------------------------------------------------------------------------------------
# Images for interactive maps and static PNG exports
# --------------------------------------------------------------------------------------
NTL_VIS = {"min": -1.0, "max": 2.0, "palette": ["000004", "3b0f70", "8c2981", "de4968", "fe9f6d", "fcfdbf"]}


def annual_image(ctx: GEEContext, year: int):
    """Cleaned annual radiance (flares removed), clipped to the country, unlit pixels masked."""
    ref, _, _ = pp.annual_vnl(year, ctx.annual_years)
    rad = pp.clean_annual(ref, ctx.flare).select("rad").clip(ctx.region)
    return rad.updateMask(rad.gte(ctx.cfg.noise_floor))


def annual_collection(ctx: GEEContext, years: list[int]):
    """ImageCollection of log10 radiance, one image per year (for geemap time slider)."""
    import ee
    imgs = []
    for y in years:
        if y in ctx.annual_years:
            imgs.append(annual_image(ctx, y).log10().set(
                {"system:time_start": ee.Date.fromYMD(y, 7, 1).millis(), "label": str(y)}))
    return ee.ImageCollection(imgs)


def dark_inhabited_image(ctx: GEEContext, year: int):
    """1 = inhabited and lit, 2 = inhabited and unlit ("in the dark"); masked elsewhere."""
    rad = annual_image(ctx, year).unmask(0)
    pop, _ = pp.population_on_grid(year, ctx.cfg, ctx.proj)
    inhab = pop.gte(ctx.cfg.pop_min)
    cls = inhab.multiply(rad.lt(ctx.cfg.noise_floor).add(1))
    return cls.updateMask(cls.gt(0)).clip(ctx.region).rename("dark")


def export_pngs(ctx: GEEContext, years: list[int], out_dir: Path, dims: int = 1400,
                progress=print) -> dict:
    """Download static PNG overlays (Web Mercator) for the dashboard.

    GEE tile URLs expire after a few hours: the dashboard therefore embeds PNG files whose
    geographic bounds are stored in the returned index (MapLibre image sources).
    """
    import ee
    import requests
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    b = ee_call(lambda: ctx.region.bounds().coordinates().getInfo(), "emprise du pays")[0]
    xs, ys = [p[0] for p in b], [p[1] for p in b]
    west, south, east, north = min(xs), min(ys), max(xs), max(ys)
    rect = ee.Geometry.Rectangle([west, south, east, north], "EPSG:4326", False)
    index = {"bounds": [west, south, east, north], "ntl": {}, "dark": {}}

    def _dl(img, path):
        url = ee_call(lambda: img.getThumbURL({"region": rect, "dimensions": dims, "format": "png",
                                               "crs": "EPSG:3857"}), f"vignette {path.name}")
        r = requests.get(url, timeout=300)
        r.raise_for_status()
        path.write_bytes(r.content)

    for y in years:
        if y not in ctx.annual_years:
            continue
        p = out_dir / f"ntl_{y}.png"
        _dl(annual_image(ctx, y).log10().visualize(**NTL_VIS), p)
        index["ntl"][str(y)] = p.name
        progress(f"  PNG NTL {y}")
    last = max(y for y in years if y in ctx.annual_years)
    p = out_dir / f"dark_{last}.png"
    _dl(dark_inhabited_image(ctx, last).visualize(min=1, max=2, palette=["f5c242", "d7263d"]), p)
    index["dark"][str(last)] = p.name
    return index
