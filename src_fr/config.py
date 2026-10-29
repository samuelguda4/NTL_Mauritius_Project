"""Run configuration, ISO3 validation and dataset registry.

Every country-specific value is derived from the ISO3 code at run time: nothing in this
package is hard-coded for a given country.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------------------
# Dataset registry — IDs checked against the Earth Engine catalogue (Oct. 2026).
# `start`/`end` are the documented availability bounds; the code re-checks the actual
# availability at run time with gee.check_availability().
# --------------------------------------------------------------------------------------
DATASETS: dict[str, dict[str, Any]] = {
    "viirs_monthly": {
        "id": "NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG",
        "type": "ImageCollection", "bands": ["avg_rad", "cf_cvg"], "start": "2014-01",
        "scale": 463.83, "unit": "nW·cm⁻²·sr⁻¹",
        "citation": "Elvidge et al. (2017), VIIRS night-time lights, Int. J. Remote Sensing 38(21).",
        "note": "Stray-light corrected monthly composite (VCMSLCFG).",
    },
    "viirs_annual_v21": {
        "id": "NOAA/VIIRS/DNB/ANNUAL_V21", "type": "ImageCollection",
        "bands": ["average_masked", "cf_cvg"], "start": "2013", "end": "2021", "scale": 463.83,
        "citation": "Elvidge et al. (2021), Annual time series of global VIIRS nighttime lights "
                    "derived from monthly averages: 2012 to 2019, Remote Sensing 13(5).",
    },
    "viirs_annual_v22": {
        "id": "NOAA/VIIRS/DNB/ANNUAL_V22", "type": "ImageCollection",
        "bands": ["average_masked", "cf_cvg"], "start": "2022", "scale": 463.83,
        "citation": "Elvidge et al. (2021) — VNL V2.2.",
    },
    "dmsp": {
        "id": "NOAA/DMSP-OLS/NIGHTTIME_LIGHTS", "type": "ImageCollection",
        "bands": ["stable_lights", "cf_cvg"], "start": "1992", "end": "2013", "scale": 927.67,
        "citation": "NOAA NGDC, DMSP-OLS Nighttime Lights Time Series Version 4.",
    },
    "harmonized_dmsp": {
        "id": "projects/sat-io/open-datasets/Harmonized_NTL/dmsp", "type": "ImageCollection",
        "start": "1992", "end": "2013", "scale": 1000,
        "citation": "Li, X., Zhou, Y., Zhao, M., Zhao, X. (2020). A harmonized global nighttime "
                    "light dataset 1992–2018. Scientific Data 7, 168.",
    },
    "harmonized_viirs": {
        "id": "projects/sat-io/open-datasets/Harmonized_NTL/viirs", "type": "ImageCollection",
        "start": "2014", "scale": 1000, "citation": "Li et al. (2020), DMSP-like VIIRS.",
    },
    "black_marble_daily": {
        "id": "NASA/VIIRS/002/VNP46A2", "type": "ImageCollection",
        "bands": ["DNB_BRDF_Corrected_NTL", "Gap_Filled_DNB_BRDF_Corrected_NTL",
                  "Mandatory_Quality_Flag", "QF_Cloud_Mask", "Snow_Flag"],
        "start": "2012-01-19", "scale": 500,
        "citation": "Román, M. O. et al. (2018). NASA's Black Marble nighttime lights product "
                    "suite. Remote Sensing of Environment 210.",
    },
    "geoboundaries": {
        "id": "WM/geoLab/geoBoundaries/600/{level}", "type": "FeatureCollection",
        "iso_field": "shapeGroup", "name_field": "shapeName", "id_field": "shapeID",
        "citation": "Runfola, D. et al. (2020). geoBoundaries. PLoS ONE 15(4). CC BY 4.0.",
    },
    "gaul2025": {
        "id": "FAO/GAUL/2025/level{n}", "type": "FeatureCollection", "iso_field": "ISO3_CODE",
        "citation": "FAO GAUL 2025.",
    },
    "gaul2015": {
        "id": "FAO/GAUL/2015/level{n}", "type": "FeatureCollection", "iso_field": None,
        "citation": "FAO GAUL 2015 (deprecated, fallback only, matched through an ISO3 table).",
    },
    "ghsl_pop": {
        "id": "JRC/GHSL/P2023A/GHS_POP", "type": "ImageCollection", "bands": ["population_count"],
        "epochs": list(range(1975, 2031, 5)), "scale": 100,
        "citation": "Schiavina, M. et al. (2023). GHS-POP R2023A. European Commission, JRC.",
    },
    "ghsl_smod": {
        "id": "JRC/GHSL/P2023A/GHS_SMOD_V2-0", "type": "ImageCollection", "bands": ["smod_code"],
        "epochs": list(range(1975, 2031, 5)), "scale": 1000,
        "citation": "Schiavina, M. et al. (2023). GHS-SMOD R2023A (Degree of Urbanisation).",
    },
    "ghsl_built": {
        "id": "JRC/GHSL/P2023A/GHS_BUILT_S", "type": "ImageCollection",
        "bands": ["built_surface"], "scale": 100,
        "citation": "Pesaresi, M. et al. (2023). GHS-BUILT-S R2023A.",
    },
    "worldpop": {
        "id": "WorldPop/GP/100m/pop", "type": "ImageCollection", "bands": ["population"],
        "start": "2000", "end": "2020", "scale": 92.77,
        "citation": "WorldPop (2018). Global High Resolution Population Denominators. CC BY 4.0.",
    },
    "worldcover": {
        "id": "ESA/WorldCover/v200", "type": "ImageCollection", "bands": ["Map"], "year": 2021,
        "scale": 10, "citation": "Zanaga, D. et al. (2022). ESA WorldCover 10 m 2021 v200.",
    },
    "no2": {
        "id": "COPERNICUS/S5P/OFFL/L3_NO2", "type": "ImageCollection",
        "bands": ["tropospheric_NO2_column_number_density"], "start": "2018-07",
        "scale": 1113.2, "unit": "mol/m²",
        "citation": "Copernicus Sentinel-5P (ESA), TROPOMI Level 3 NO2.",
    },
}

WDI_INDICATORS: dict[str, str] = {
    "NY.GDP.MKTP.KD": "gdp_const_usd",          # GDP, constant 2015 USD
    "NY.GDP.PCAP.KD": "gdp_pc_const_usd",       # GDP per capita, constant 2015 USD
    "NY.GDP.MKTP.KD.ZG": "gdp_growth_pct",      # real GDP growth, %
    "NV.IND.TOTL.KD": "industry_va_const_usd",  # industry value added, constant USD
    "EG.ELC.ACCS.ZS": "elec_access_pct",        # access to electricity, % of population
    "EG.ELC.ACCS.UR.ZS": "elec_access_urban_pct",
    "EG.ELC.ACCS.RU.ZS": "elec_access_rural_pct",
    "SP.POP.TOTL": "population",
}


class ConfigError(ValueError):
    """Raised for an invalid run configuration (e.g. unknown ISO3)."""


def validate_iso3(iso3: str) -> dict[str, str]:
    """Validate an ISO 3166-1 alpha-3 code and return {'iso3', 'iso2', 'name', 'name_fr'}.

    Uses `pycountry` when installed (offline). Raises ConfigError with a helpful message
    otherwise (e.g. a close match such as 'TUN' for 'TUNISIA').
    """
    if not isinstance(iso3, str) or len(iso3.strip()) != 3 or not iso3.strip().isalpha():
        raise ConfigError(f"ISO3 invalide : {iso3!r}. Attendu : trois lettres, ex. 'TUN', 'SEN', 'KEN'.")
    code = iso3.strip().upper()
    if code.startswith("X") and code[1:] in ("TS", "XX"):
        # ISO 3166 user-assigned range (XAA–XZZ): reserved here for the synthetic test fixture
        return {"iso3": code, "iso2": "XT", "name": "Testland (synthetic)", "name_fr": "Pays test (synthétique)"}
    try:
        import pycountry
    except ImportError:  # pragma: no cover - degraded mode
        return {"iso3": code, "iso2": "", "name": code, "name_fr": code}
    c = pycountry.countries.get(alpha_3=code)
    if c is None:
        try:
            guesses = [g.alpha_3 for g in pycountry.countries.search_fuzzy(code)][:3]
        except LookupError:
            guesses = []
        hint = f" Vouliez-vous dire : {', '.join(guesses)} ?" if guesses else ""
        raise ConfigError(f"Code ISO3 inconnu : {code!r}.{hint}")
    name = getattr(c, "common_name", None) or c.name
    name_fr = name
    try:
        import gettext
        fr = gettext.translation("iso3166-1", pycountry.LOCALES_DIR, languages=["fr"])
        name_fr = fr.gettext(c.name)
    except Exception:  # noqa: BLE001 - translation is cosmetic
        pass
    return {"iso3": code, "iso2": c.alpha_2, "name": name, "name_fr": name_fr}


@dataclass
class NTLConfig:
    """All parameters of a run. Only `iso3` is mandatory.

    Thresholds are not neutral: each one is documented in the notebook and exported in the
    dashboard's methodology page so that results can be reproduced and discussed.
    """

    iso3: str
    start_year: int = 2014                 # first full year of VIIRS monthly data
    end_year: int | None = None            # None -> last complete year available in GEE
    long_start_year: int = 1992            # harmonised DMSP–VIIRS long series
    admin_levels: tuple[str, ...] = ("ADM1", "ADM2")
    boundary_source: str = "geoboundaries"  # "geoboundaries" | "gaul"
    gee_project: str | None = None          # Google Cloud project for Earth Engine

    # --- pre-processing ------------------------------------------------------------------
    cf_cvg_min: int = 2              # min. cloud-free observations for a monthly pixel
    min_valid_frac: float = 0.80     # min. share of a unit's pixels observed in a month
    noise_floor: float = 0.5         # nW·cm⁻²·sr⁻¹ below which a pixel is "unlit"
    radiance_cap: float = 1000.0     # absolute cap on monthly radiance (fires, flares, glints)
    spike_factor: float = 5.0        # monthly value > factor × annual median -> spike
    flare_mode: str = "auto"         # "auto" | "points" | "off"
    flare_rad_min: float = 50.0      # radiance of a flare candidate (very bright)
    flare_pop_max: float = 5.0       # max. inhabitants in the pixel for a flare candidate
    flare_buffer_m: float = 2000.0   # halo removed around a flare (blooming)
    flare_points_csv: str | None = None  # optional lon/lat file (e.g. EOG VIIRS Nightfire)
    dmsp_min_dn: int = 7             # Li et al. (2020) recommend DN > 7 on the harmonised data

    # --- population & electricity access ----------------------------------------------------
    pop_source: str = "ghsl"         # "ghsl" (1975–2030, 5-yr epochs) | "worldpop" (2000–2020)
    pop_min: float = 5.0             # inhabitants per VIIRS pixel (~0.21 km²) to be "inhabited"
    dark_thresholds: tuple[float, ...] = (0.25, 0.5, 1.0)  # sensitivity of the dark population

    # --- time series & shocks -------------------------------------------------------------
    stl_period: int = 12
    anomaly_z: float = 3.5               # robust z-score of the STL residual
    anomaly_min_effect: float = 0.05     # and at least a 5 % deviation
    break_min_months: int = 12           # min. segment length around a structural break
    break_penalty: float | None = None   # None -> BIC-like default
    growth_threshold: float = 0.01       # ±1 %/yr: below this, a region "stagnates"
    alpha: float = 0.10                  # significance level for trends
    custom_events: list[dict[str, Any]] = field(default_factory=list)
    daily_windows: list[dict[str, Any]] = field(default_factory=list)  # Black Marble windows
    events_csv: str | None = None        # optional ACLED / EM-DAT export (date, label, ...)

    # --- outputs -------------------------------------------------------------------------
    output_dir: str = "outputs"
    dashboard_dir: str = "dashboard"
    tile_scale: int = 4
    random_seed: int = 42

    # filled by resolve()
    country: dict[str, str] = field(default_factory=dict)

    def resolve(self) -> "NTLConfig":
        """Validate parameters and fill derived values (country name, end year)."""
        self.country = validate_iso3(self.iso3)
        self.iso3 = self.country["iso3"]
        this_year = _dt.date.today().year
        if self.end_year is None:
            self.end_year = this_year - 1
        if not (2012 <= self.start_year <= self.end_year <= this_year):
            raise ConfigError(
                f"Période invalide : {self.start_year}–{self.end_year}. VIIRS couvre 2012 → aujourd'hui.")
        bad = [lv for lv in self.admin_levels if lv not in ("ADM1", "ADM2")]
        if bad:
            raise ConfigError(f"Niveaux administratifs non gérés : {bad}. Utiliser ADM1 et/ou ADM2.")
        if self.boundary_source not in ("geoboundaries", "gaul"):
            raise ConfigError("boundary_source doit valoir 'geoboundaries' ou 'gaul'.")
        if self.pop_source not in ("ghsl", "worldpop"):
            raise ConfigError("pop_source doit valoir 'ghsl' ou 'worldpop'.")
        if self.flare_mode not in ("auto", "points", "off"):
            raise ConfigError("flare_mode doit valoir 'auto', 'points' ou 'off'.")
        return self

    # --- paths ---------------------------------------------------------------------------
    @property
    def out(self) -> Path:
        p = Path(self.output_dir) / self.iso3
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def cache_dir(self) -> Path:
        p = self.out / "cache"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def fig_dir(self) -> Path:
        p = self.out / "figures"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def years(self) -> list[int]:
        return list(range(self.start_year, int(self.end_year) + 1))

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["admin_levels"] = list(self.admin_levels)
        d["dark_thresholds"] = list(self.dark_thresholds)
        return d


def package_versions(names: tuple[str, ...] = (
        "numpy", "pandas", "scipy", "statsmodels", "geopandas", "shapely", "plotly", "folium",
        "earthengine-api", "geemap", "ruptures", "requests")) -> dict[str, str]:
    """Return installed versions of the key packages (for the reproducibility manifest)."""
    from importlib import metadata
    out = {}
    for n in names:
        try:
            out[n] = metadata.version(n)
        except metadata.PackageNotFoundError:
            out[n] = "non installé"
    import platform
    out["python"] = platform.python_version()
    return out
