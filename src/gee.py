"""Earth Engine helpers: authentication, robust calls, availability checks.

All Earth Engine calls of the package go through `ee_call()`, which retries on transient
errors (quota, concurrency, time-out) with exponential back-off and turns the cryptic
server messages into actionable messages.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Callable

import pandas as pd

log = logging.getLogger("ntl")

_TRANSIENT = ("Too many concurrent aggregations", "Too Many Requests", "429", "Quota exceeded",
              "rate limit", "503", "502", "Internal error", "Connection reset", "Read timed out")
_MEMORY = ("User memory limit exceeded", "Output of image computation is too large", "Computation timed out")


class GEEError(RuntimeError):
    """Earth Engine error with an explanatory message."""


def init_gee(project: str | None = None, interactive: bool = True) -> str:
    """Initialise Earth Engine and return the project ID used.

    Order: explicit `project` → env. var. EE_PROJECT / GOOGLE_CLOUD_PROJECT → interactive
    prompt. If no credentials are stored, launches `ee.Authenticate()` (opens Google's page;
    on Colab it uses the Colab auth flow).
    """
    try:
        import ee
    except ImportError as e:  # pragma: no cover
        raise GEEError("earthengine-api is not installed: pip install earthengine-api") from e

    project = project or os.environ.get("EE_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project and interactive:
        project = input("ID of the Google Cloud project registered for Earth Engine: ").strip() or None
    if not project:
        raise GEEError("No Earth Engine project. Set CONFIG.gee_project or the EE_PROJECT variable.")
    try:
        ee.Initialize(project=project)
    except Exception:  # noqa: BLE001 - not authenticated yet
        if not interactive:
            raise GEEError("Earth Engine is not authenticated. Run `earthengine authenticate`.")
        ee.Authenticate()
        ee.Initialize(project=project)
    # tiny round-trip to make sure the project is registered for EE
    try:
        ee.Number(1).getInfo()
    except Exception as e:  # noqa: BLE001
        raise GEEError(
            f"Project '{project}' cannot be used with Earth Engine: {e}\n"
            "→ Check that it is registered at https://code.earthengine.google.com/register") from e
    log.info("Earth Engine initialised (project %s)", project)
    return project


def is_initialized() -> bool:
    """True if Earth Engine is initialised in this session."""
    try:
        import ee
        ee.Number(0).getInfo()
        return True
    except Exception:  # noqa: BLE001
        return False


def ee_call(fn: Callable[[], Any], what: str = "Earth Engine request", retries: int = 5,
            base_wait: float = 4.0) -> Any:
    """Run `fn()` with retries on transient errors.

    Memory errors are not retried as-is: they are re-raised as GEEError with advice (increase
    `tile_scale`, reduce the number of units or months per request).
    """
    last: Exception | None = None
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            last = e
            if any(k.lower() in msg.lower() for k in _MEMORY):
                raise GEEError(
                    f"{what}: Earth Engine memory or time limit exceeded. Increase `tile_scale` "
                    "(e.g. 8 or 16), shorten the period, or process ADM2 separately (admin_levels=('ADM1',)).") from e
            if any(k.lower() in msg.lower() for k in _TRANSIENT) and attempt < retries - 1:
                wait = base_wait * (2 ** attempt)
                log.warning("%s: transient error (%s). Retrying in %.0f s…", what, msg[:120], wait)
                time.sleep(wait)
                continue
            if "not found" in msg.lower() or "does not exist" in msg.lower():
                raise GEEError(f"{what}: dataset not found — {msg}") from e
            if "permission" in msg.lower() or "403" in msg:
                raise GEEError(f"{what}: access denied — check the GEE project and its permissions. {msg}") from e
            raise GEEError(f"{what}: {msg}") from e
    raise GEEError(f"{what}: failed after {retries} attempts — {last}")


def fc_to_df(fc, what: str = "table", page_size: int = 2000) -> pd.DataFrame:
    """Convert an ee.FeatureCollection (without geometry) to a pandas DataFrame.

    Uses `ee.data.computeFeatures(..., fileFormat='PANDAS_DATAFRAME')`, which pages through
    results and is not subject to the 5 000-element limit of getInfo().
    """
    import ee

    def _run():
        return ee.data.computeFeatures({"expression": fc, "fileFormat": "PANDAS_DATAFRAME",
                                        "pageSize": page_size})
    df = ee_call(_run, what)
    if "geo" in df.columns:
        df = df.drop(columns=["geo"])
    return pd.DataFrame(df)


def collection_date_range(collection_id: str) -> tuple[str | None, str | None, int]:
    """Return (first date, last date, number of images) of an ImageCollection."""
    import ee
    col = ee.ImageCollection(collection_id)

    def _run():
        r = col.reduceColumns(ee.Reducer.minMax(), ["system:time_start"]).getInfo()
        n = col.size().getInfo()
        return r, n
    r, n = ee_call(_run, f"availability of {collection_id}")
    if not n:
        return None, None, 0
    f = pd.to_datetime(r["min"], unit="ms").strftime("%Y-%m-%d")
    t = pd.to_datetime(r["max"], unit="ms").strftime("%Y-%m-%d")
    return f, t, int(n)


def check_availability(datasets: dict[str, dict[str, Any]], keys: list[str] | None = None) -> pd.DataFrame:
    """Check that each dataset ID exists and report its actual temporal coverage.

    Returns a table (key, id, status, first, last, n_images) that is written to the
    reproducibility manifest. Missing datasets are reported, not fatal: the pipeline
    degrades gracefully (e.g. no long-run series if the harmonised data are unavailable).
    """
    import ee
    rows = []
    for k in keys or list(datasets):
        meta = datasets[k]
        if meta["type"] != "ImageCollection" or "{" in meta["id"]:
            continue
        try:
            f, t, n = collection_date_range(meta["id"])
            rows.append({"key": k, "id": meta["id"], "status": "ok" if n else "empty",
                         "first": f, "last": t, "n_images": n})
        except GEEError as e:
            rows.append({"key": k, "id": meta["id"], "status": f"unavailable: {str(e)[:90]}",
                         "first": None, "last": None, "n_images": 0})
    _ = ee  # keep import for side effects / clarity
    return pd.DataFrame(rows)


def last_complete_year(collection_id: str = "NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG") -> int:
    """Last calendar year with 12 monthly images in the VIIRS monthly collection."""
    import ee
    col = ee.ImageCollection(collection_id)
    hist = ee_call(lambda: col.aggregate_array("system:time_start").getInfo(), "last complete year")
    s = pd.Series(pd.to_datetime(hist, unit="ms")).dt.year.value_counts()
    full = s[s >= 12]
    return int(full.index.max()) if len(full) else int(s.index.max()) - 1
