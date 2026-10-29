"""Local cache of acquired tables.

Earth Engine requests are slow and quota-limited. Every acquisition step writes its tidy
result to `outputs/<ISO3>/cache/`, and the notebook re-uses it on the next run unless
`force=True`. The cache also makes the analysis sections runnable without GEE access.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

import geopandas as gpd
import pandas as pd

log = logging.getLogger("ntl")


def _path(cache_dir: Path, name: str, kind: str) -> Path:
    ext = {"df": ".csv.gz", "json": ".json", "gdf": ".geojson"}[kind]
    return Path(cache_dir) / f"{name}{ext}"


def save(cache_dir: Path, name: str, obj: Any) -> Path:
    """Save a DataFrame, GeoDataFrame or JSON-serialisable object."""
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    if isinstance(obj, gpd.GeoDataFrame):
        p = _path(cache_dir, name, "gdf")
        obj.to_file(p, driver="GeoJSON")
    elif isinstance(obj, pd.DataFrame):
        p = _path(cache_dir, name, "df")
        obj.to_csv(p, index=False)
    else:
        p = _path(cache_dir, name, "json")
        p.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return p


def load(cache_dir: Path, name: str) -> Any | None:
    """Load a cached object, or None if absent."""
    for kind in ("gdf", "df", "json"):
        p = _path(cache_dir, name, kind)
        if p.exists():
            if kind == "gdf":
                return gpd.read_file(p)
            if kind == "df":
                df = pd.read_csv(p)
                for c in ("date",):
                    if c in df.columns:
                        df[c] = pd.to_datetime(df[c])
                return df
            return json.loads(p.read_text(encoding="utf-8"))
    return None


def exists(cache_dir: Path, name: str) -> bool:
    return any(_path(cache_dir, name, k).exists() for k in ("gdf", "df", "json"))


def cached(cache_dir: Path, name: str, fn: Callable[[], Any], force: bool = False,
           required: bool = True) -> Any:
    """Return the cached object `name`, or compute it with `fn()` and cache it.

    If `fn` fails and `required` is False, logs a warning and returns None (the pipeline
    continues without this optional input, and the gap is reported in the limitations).
    """
    if not force:
        obj = load(cache_dir, name)
        if obj is not None:
            log.info("cache ✓ %s", name)
            return obj
    try:
        obj = fn()
    except Exception as e:  # noqa: BLE001
        if required:
            raise
        log.warning("Étape optionnelle « %s » non disponible : %s", name, e)
        return None
    if obj is not None:
        save(cache_dir, name, obj)
    return obj
