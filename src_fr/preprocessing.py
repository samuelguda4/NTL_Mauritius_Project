"""Earth Engine pre-processing of night-time light images.

Each step is explicit and justified (see the notebook, section 3):

1. Cloud-free coverage (`cf_cvg`): a monthly pixel with fewer than `cf_cvg_min` cloud-free
   observations is *missing*, not dark. Missing pixels are excluded and the unit-month is
   kept only if at least `min_valid_frac` of its pixels are observed.
2. Negative values (calibration noise over dark areas) are set to 0.
3. Outliers: absolute cap (`radiance_cap`) and monthly spikes far above the pixel's annual
   median (fires, lightning, sensor glints) are replaced by that median.
4. Background: pixels with no light in the EOG annual `average_masked` composite (background
   and ephemeral lights removed by EOG) are set to 0 in the monthly composite.
5. Gas flares: very bright, uninhabited, non-built pixels (union across years), buffered by
   `flare_buffer_m` to remove the blooming halo; or an external list of flare sites.
6. DMSP: saturation (DN = 63) is quantified; blooming is limited by the DN > 7 threshold
   recommended for the harmonised series (Li et al., 2020).
"""
from __future__ import annotations

import logging

from .config import DATASETS
from .gee import ee_call

log = logging.getLogger("ntl")


# --------------------------------------------------------------------------------------
# Projections and reference images
# --------------------------------------------------------------------------------------
def viirs_projection():
    """Native projection of the VIIRS monthly composites (15 arc-seconds, EPSG:4326)."""
    import ee
    return ee.ImageCollection(DATASETS["viirs_monthly"]["id"]).first().select("avg_rad").projection()


def available_annual_years() -> dict[int, str]:
    """{year: collection id} of VNL V2 annual composites, preferring V2.2 when a year exists in both."""
    import ee
    out: dict[int, str] = {}
    for key in ("viirs_annual_v21", "viirs_annual_v22"):   # V22 last: it overrides V21
        cid = DATASETS[key]["id"]
        try:
            ts = ee_call(lambda: ee.ImageCollection(cid).aggregate_array("system:time_start").getInfo(),
                         f"années de {cid}")
        except Exception as e:  # noqa: BLE001
            log.warning("%s indisponible : %s", cid, e)
            continue
        import pandas as pd
        for y in pd.to_datetime(ts, unit="ms").year:
            out[int(y)] = cid
    return dict(sorted(out.items()))


def annual_vnl(year: int, annual_years: dict[int, str]):
    """Annual VNL V2 image for `year` (nearest available year if missing) with its product id."""
    import ee
    yr = year if year in annual_years else min(annual_years, key=lambda y: abs(y - year))
    cid = annual_years[yr]
    img = ee.ImageCollection(cid).filter(ee.Filter.calendarRange(yr, yr, "year")).first()
    return ee.Image(img).set({"ntl_product": cid, "ntl_year": yr}), yr, cid


# --------------------------------------------------------------------------------------
# Population, settlement and built-up layers aligned on the VIIRS grid
# --------------------------------------------------------------------------------------
def _nearest_epochs(year: int, epochs: list[int]) -> tuple[int, int, float]:
    lo = max([e for e in epochs if e <= year], default=epochs[0])
    hi = min([e for e in epochs if e >= year], default=epochs[-1])
    w = 0.0 if hi == lo else (year - lo) / (hi - lo)
    return lo, hi, w


def population_on_grid(year: int, cfg, proj):
    """Population count per VIIRS pixel for `year`.

    GHSL: linear interpolation between the two surrounding 5-year epochs. WorldPop: nearest
    year in 2000–2020. Aggregation uses `reduceResolution(sum)`, which is area-weighted and
    therefore preserves totals (a plain reprojection would average counts and bias them).
    """
    import ee
    if cfg.pop_source == "worldpop":
        y = min(max(year, 2000), 2020)
        col = ee.ImageCollection(DATASETS["worldpop"]["id"]).filter(ee.Filter.eq("country", cfg.iso3))
        img = col.filter(ee.Filter.eq("year", y)).mosaic().setDefaultProjection(col.first().projection())
        src_year = y
    else:
        meta = DATASETS["ghsl_pop"]
        col = ee.ImageCollection(meta["id"])
        lo, hi, w = _nearest_epochs(year, meta["epochs"])
        a = col.filter(ee.Filter.calendarRange(lo, lo, "year")).first().select("population_count")
        b = col.filter(ee.Filter.calendarRange(hi, hi, "year")).first().select("population_count")
        img = a.multiply(1 - w).add(b.multiply(w)).setDefaultProjection(a.projection())
        src_year = f"{lo}-{hi} (interp.)" if lo != hi else lo
    pop = (img.unmask(0).rename("pop")
           .reduceResolution(reducer=ee.Reducer.sum(), maxPixels=1024)
           .reproject(proj))
    return pop, src_year


def urban_on_grid(year: int, proj):
    """1 where the GHSL Degree of Urbanisation class is urban (SMOD ≥ 21), else 0."""
    import ee
    meta = DATASETS["ghsl_smod"]
    ep = min(meta["epochs"], key=lambda e: abs(e - year))
    smod = ee.ImageCollection(meta["id"]).filter(ee.Filter.calendarRange(ep, ep, "year")).first()
    return smod.select("smod_code").gte(21).unmask(0).rename("urban").reproject(proj)


def built_fraction_on_grid(proj, epoch: int = 2020):
    """Share of each VIIRS pixel covered by buildings (GHSL BUILT-S, m² -> fraction)."""
    import ee
    col = ee.ImageCollection(DATASETS["ghsl_built"]["id"])
    b = col.filter(ee.Filter.calendarRange(epoch, epoch, "year")).first().select("built_surface")
    built_m2 = b.unmask(0).reduceResolution(ee.Reducer.sum(), maxPixels=1024).reproject(proj)
    return built_m2.divide(ee.Image.pixelArea().reproject(proj)).min(1).rename("built_frac")


# --------------------------------------------------------------------------------------
# Gas flares
# --------------------------------------------------------------------------------------
def flare_core(cfg, region, annual_imgs: list, proj, pop_img=None):
    """Candidate gas-flare pixels (1) — union over years — before any halo.

    Automatic rule: radiance ≥ flare_rad_min in any year AND population < flare_pop_max AND
    built-up fraction < 5 %. Caveat: isolated mines, ports or power plants can meet the rule;
    candidates are exported for visual review and the share of light removed is reported.
    """
    import ee
    built = built_fraction_on_grid(proj)
    pop = pop_img if pop_img is not None else ee.Image(0)
    core = ee.Image(0).reproject(proj)
    for img in annual_imgs:
        rad = ee.Image(img).select("average_masked").unmask(0)
        core = core.Or(rad.gte(cfg.flare_rad_min).And(pop.lt(cfg.flare_pop_max)).And(built.lt(0.05)))
    return core.clip(region).rename("flare_core")


def flare_polygons(core, region, max_n: int = 2000) -> dict:
    """Vectorise the candidate pixels ONCE (client-side GeoJSON), so that the flare mask used in
    every later request is a cheap painted vector instead of a recomputed raster pipeline."""
    vec = core.selfMask().reduceToVectors(geometry=region, scale=463.83, geometryType="polygon",
                                          eightConnected=True, maxPixels=1e10, bestEffort=True).limit(max_n)
    return ee_call(lambda: vec.getInfo(), "polygones des torchères")


def flare_mask_from_vectors(cfg, polygons: dict | None, proj):
    """Binary image (1 = flare + `flare_buffer_m` halo) from candidate polygons and/or the
    external point file `flare_points_csv` (lon, lat). Returns None if there is nothing to mask."""
    import ee
    feats = []
    for f in (polygons or {}).get("features", []):
        feats.append(ee.Feature(ee.Geometry(f["geometry"]).buffer(cfg.flare_buffer_m, 100)))
    if cfg.flare_points_csv:
        import pandas as pd
        pts = pd.read_csv(cfg.flare_points_csv)
        lon = next(c for c in pts.columns if c.lower() in ("lon", "longitude", "x"))
        lat = next(c for c in pts.columns if c.lower() in ("lat", "latitude", "y"))
        feats += [ee.Feature(ee.Geometry.Point([float(a), float(b)]).buffer(cfg.flare_buffer_m, 100))
                  for a, b in zip(pts[lon], pts[lat])]
    if not feats:
        return None
    return ee.Image(0).byte().paint(ee.FeatureCollection(feats), 1).reproject(proj).rename("flare")


def flare_candidates_table(polygons: dict | None):
    """Centroids (lon, lat) and size of the flare-candidate clusters, for visual review."""
    import pandas as pd
    from shapely.geometry import shape
    rows = []
    for f in (polygons or {}).get("features", []):
        g = shape(f["geometry"])
        rows.append({"lon": round(g.centroid.x, 5), "lat": round(g.centroid.y, 5),
                     "pixels": int(round(g.area / (463.83 / 111320) ** 2))})
    return pd.DataFrame(rows, columns=["lon", "lat", "pixels"])


# --------------------------------------------------------------------------------------
# VIIRS monthly cleaning
# --------------------------------------------------------------------------------------
def clean_monthly(img, cfg, annual_ref, flare=None):
    """Return a 4-band image ready for zonal sums: sol, lit, valid, n.

    sol   : cleaned radiance on valid pixels (0 elsewhere)
    lit   : 1 if valid and radiance ≥ noise_floor
    valid : 1 if the pixel has ≥ cf_cvg_min cloud-free observations
    n     : 1 everywhere (pixel count, for the valid share)
    """
    import ee
    rad = img.select("avg_rad").unmask(0)
    valid = img.select("cf_cvg").unmask(0).gte(cfg.cf_cvg_min)
    rad = rad.max(0).min(cfg.radiance_cap)                       # 2. negatives, 3a. cap
    med = annual_ref.select("median_masked").unmask(0)
    spike = rad.gt(med.add(1).multiply(cfg.spike_factor))        # 3b. spikes
    rad = rad.where(spike, med)
    rad = rad.multiply(annual_ref.select("average_masked").unmask(0).gt(0))  # 4. background
    if flare is not None:
        rad = rad.where(flare, 0)                                # 5. gas flares
    rad = rad.multiply(valid)                                    # 1. cloud-free coverage
    return ee.Image.cat([
        rad.rename("sol"),
        rad.gte(cfg.noise_floor).And(valid).rename("lit"),
        valid.rename("valid"),
        ee.Image(1).rename("n"),
    ]).set("system:time_start", img.get("system:time_start"))


def clean_annual(img, flare=None):
    """Annual VNL: average_masked, negatives to 0, gas flares removed. Bands: rad, rad_raw."""
    raw = img.select("average_masked").unmask(0).max(0)
    rad = raw.where(flare, 0) if flare is not None else raw
    return rad.rename("rad").addBands(raw.rename("rad_raw"))


# --------------------------------------------------------------------------------------
# DMSP and harmonised series
# --------------------------------------------------------------------------------------
def dmsp_year(year: int):
    """DMSP-OLS stable lights for `year`: band `dn` = mean of the satellites when two flew,
    band `sat` = 1 where ANY satellite is saturated (DN 63; a mean would hide saturation)."""
    import ee
    col = ee.ImageCollection(DATASETS["dmsp"]["id"]).filter(ee.Filter.calendarRange(year, year, "year"))
    proj = col.first().select("stable_lights").projection()
    sl = col.select("stable_lights")
    return ee.Image.cat([sl.mean().rename("dn"), sl.max().gte(63).rename("sat")]).setDefaultProjection(proj)


def harmonized_years(key: str) -> dict[int, str]:
    """{year: system:index} of a harmonised collection. Uses system:time_start when present,
    otherwise parses a 4-digit year from system:index (community assets are not always dated)."""
    import re
    import ee
    import pandas as pd
    col = ee.ImageCollection(DATASETS[key]["id"])
    ids, ts = ee_call(lambda: (col.aggregate_array("system:index").getInfo(),
                               col.aggregate_array("system:time_start").getInfo()), f"années {key}")
    if ts and len(ts) == len(ids):
        return {int(y): i for y, i in zip(pd.to_datetime(ts, unit="ms").year, ids)}
    out = {}
    for i in ids:
        m = re.search(r"(19|20)\d{2}", i)
        if m:
            out[int(m.group(0))] = i
    return out


def harmonized_year(key: str, index: str):
    """Li et al. (2020) harmonised DMSP-like image (first band, whatever its name) by system:index."""
    import ee
    col = ee.ImageCollection(DATASETS[key]["id"])
    return ee.Image(col.filter(ee.Filter.eq("system:index", index)).first()).select([0]).rename("dn")


# --------------------------------------------------------------------------------------
# Black Marble daily (VNP46A2)
# --------------------------------------------------------------------------------------
def clean_black_marble(img, lit_mask, gap_filled: bool = False):
    """Daily Black Marble with quality masks.

    Kept: Mandatory_Quality_Flag ∈ {0, 1} (high quality), cloud confidence bits 6–7 ∈ {0, 1}
    (confident/probably clear), no snow. Restricted to pixels lit in the annual composite to
    reduce noise. Bands: sol, valid, n (over the lit mask).
    """
    import ee
    band = "Gap_Filled_DNB_BRDF_Corrected_NTL" if gap_filled else "DNB_BRDF_Corrected_NTL"
    ntl = img.select(band)
    q = img.select("Mandatory_Quality_Flag").unmask(255)
    cloud = img.select("QF_Cloud_Mask").unmask(0).rightShift(6).bitwiseAnd(3)
    snow = img.select("Snow_Flag").unmask(0)
    valid = ntl.mask().And(ntl.unmask(0).lt(65535))
    # gap-filled values replace precisely the poor-quality retrievals: do not filter them out by QA
    good = (valid.And(snow.eq(0)) if gap_filled else q.lte(1).And(cloud.lte(1)).And(snow.eq(0)).And(valid))
    good = good.And(lit_mask)
    val = ntl.unmask(0).max(0).multiply(good)
    return ee.Image.cat([val.rename("sol"), good.rename("valid"), lit_mask.rename("n")]).set(
        "system:time_start", img.get("system:time_start"))
