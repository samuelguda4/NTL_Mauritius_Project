"""Bilingual dashboard (FR / EN).

The notebook runs the analysis once, in its own language. To publish the dashboard in both
languages, the results dictionary is translated (categorical labels and short reasons only — all
numbers are unchanged) and the other-language text modules (`src_fr` / `src_en`, shipped with the
notebook) write their own key messages, KPI labels and data files under `dashboard/<lang>/`.
"""
from __future__ import annotations

import copy
import logging
import re
import shutil
from pathlib import Path

import pandas as pd

log = logging.getLogger("ntl")

# exact-match categorical values (classes, confidence levels, event types, sources, directions)
FR_EN = {
    "Croissance": "Growth", "Stagnation": "Stagnation", "Déclin": "Decline", "Indéterminé": "Undetermined",
    "élevée": "high", "moyenne": "medium", "faible": "low",
    "hausse": "up", "baisse": "down",
    "pandémie": "pandemic", "conflit": "conflict", "catastrophe": "disaster", "autre": "other",
    "catalogue générique": "generic catalogue", "utilisateur": "user",
    "moins de 5 observations": "fewer than 5 observations",
    "moins de 6 années de recouvrement": "fewer than 6 years of overlap",
    "moins de 6 mois avant l'événement": "fewer than 6 months before the event",
    "pas de données pendant l'événement": "no data during the event",
    "PIB Banque mondiale indisponible": "World Bank GDP unavailable",
    "Industrie lourde": "Heavy industry", "Zone d'activités et logistique": "Business park & logistics",
    "Hydrocarbures et torchères": "Oil, gas & flares", "Site isolé à vérifier": "Isolated site to verify",
    "Zone touristique": "Tourist zone", "Non touristique": "Not touristic",
    "Urbanisation électrifiée": "Electrified urbanisation", "Croissance équilibrée": "Balanced growth",
    "Croissance non éclairée": "Unlit growth", "Stable ou en déclin": "Stable or declining",
    "Dates indicatives : les mesures de restriction varient selon les pays.":
        "Indicative dates: restriction measures vary across countries.",
}
EN_FR = {v: k for k, v in FR_EN.items()}

_NUM = r"(-?[0-9]+(?:[.,][0-9]+)?)"
# templated reasons (econometrics._confidence); numbers are re-formatted for the target language
PATTERNS = [
    ("seulement {0} observations", "only {0} observations"),
    ("n = {0}, p < 0,01, IC étroit", "n = {0}, p < 0.01, narrow CI"),
    ("relation nette mais seulement {0} années", "clear relationship but only {0} years"),
    ("n = {0}, significatif mais IC large ({1})", "n = {0}, significant but wide CI ({1})"),
    ("n = {0}, non significatif (p = {1})", "n = {0}, not significant (p = {1})"),
    ("Pic de violence ({0} décès)", "Violence peak ({0} deaths)"),
]


def _rx(t: str) -> re.Pattern:
    s = re.escape(t).replace(r"\{0\}", _NUM).replace(r"\{1\}", _NUM)
    return re.compile("^" + s + "$")


def _tr_str(s: str, to: str) -> str:
    table = FR_EN if to == "en" else EN_FR
    if s in table:
        return table[s]
    for fr, en in PATTERNS:
        src, dst = (fr, en) if to == "en" else (en, fr)
        m = _rx(src).match(s)
        if m:
            nums = [g.replace(",", ".") if to == "en" else g.replace(".", ",") for g in m.groups()]
            return dst.format(*nums)
    return s


def translate(obj, to: str, _seen=None):
    """Deep copy of `obj` with categorical strings translated to `to` ("fr" | "en")."""
    if isinstance(obj, str):
        return _tr_str(obj, to)
    if isinstance(obj, dict):
        return {translate(k, to) if isinstance(k, str) else k: translate(v, to) for k, v in obj.items()}
    if isinstance(obj, list):
        return [translate(v, to) for v in obj]
    if isinstance(obj, tuple):
        return tuple(translate(v, to) for v in obj)
    if isinstance(obj, pd.DataFrame):
        d = obj.copy()
        for c in d.columns:
            if d[c].dtype == object or pd.api.types.is_string_dtype(d[c]):
                d[c] = d[c].map(lambda v: _tr_str(v, to) if isinstance(v, str) else v)
        return d
    if isinstance(obj, pd.Series):
        txt = obj.dtype == object or pd.api.types.is_string_dtype(obj)
        return obj.map(lambda v: _tr_str(v, to) if isinstance(v, str) else v) if txt else obj.copy()
    return obj   # numbers, arrays, config objects, timestamps…


def export_other_language(lang: str, cfg, gdfs, R, annual, monthly, names, manifest, rasters, raster_src,
                          root: str | Path, synthetic: bool = False) -> Path | None:
    """Write the dashboard in the other language under <dashboard_dir>/<other>/ (site + data).

    `lang` is the notebook language; `root` the project root holding src_<other>/ and dashboard_<other>/.
    Returns the other-language country data directory, or None if the other-language modules are missing.
    """
    import importlib
    other = "en" if lang == "fr" else "fr"
    root = Path(root)
    if not (root / f"src_{other}").exists() or not (root / f"dashboard_{other}").exists():
        log.warning("Other-language modules missing (src_%s / dashboard_%s): single-language dashboard.", other, other)
        return None
    M2 = importlib.import_module(f"src_{other}.messages")
    X2 = importlib.import_module(f"src_{other}.export")
    R2 = translate({k: v for k, v in R.items() if k != "cfg"}, other)
    R2["cfg"] = R["cfg"]
    country = cfg.country.get("name") if other == "en" else (cfg.country.get("name_fr") or cfg.country.get("name"))
    msgs = M2.key_messages(R2, country, names)
    recs = M2.recommendations(R2)
    site = Path(cfg.dashboard_dir) / other
    site.mkdir(parents=True, exist_ok=True)
    for item in (root / f"dashboard_{other}").iterdir():   # static site (index.html, assets/)
        if item.name == "data":
            continue
        dst = site / item.name
        if item.is_dir():
            shutil.copytree(item, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dst)
    vend = Path(cfg.dashboard_dir) / "assets" / "vendor"
    if vend.exists():                                       # share downloaded libraries (plotly)
        shutil.copytree(vend, site / "assets" / "vendor", dirs_exist_ok=True)
    cfg2 = copy.copy(cfg)
    cfg2.dashboard_dir = str(site)
    out = X2.export_dashboard(cfg2, gdfs, R2, annual, monthly, names, msgs, recs, M2.LIMITS, manifest,
                              rasters, raster_src, synthetic=synthetic)
    log.info("Dashboard (%s) written to %s", other, site)
    return out
