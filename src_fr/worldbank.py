"""World Bank API (World Development Indicators) — GDP, GDP per capita, electricity access.

No API key is needed. Results are returned as a tidy table (year, indicator, value) and a
wide table (one column per indicator).
"""
from __future__ import annotations

import logging
import time

import pandas as pd
import requests

from .config import WDI_INDICATORS

log = logging.getLogger("ntl")
WB_URL = "https://api.worldbank.org/v2/country/{iso3}/indicator/{ind}"


def fetch_indicator(iso3: str, indicator: str, start: int = 1990, end: int = 2030,
                    retries: int = 3, timeout: int = 60) -> pd.DataFrame:
    """One WDI indicator for one country: DataFrame[year, value]. Empty if no data."""
    params = {"format": "json", "date": f"{start}:{end}", "per_page": 500}
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(WB_URL.format(iso3=iso3, ind=indicator), params=params, timeout=timeout)
            if r.status_code == 200:
                js = r.json()
                if not isinstance(js, list) or len(js) < 2 or js[1] is None:
                    msg = js[0].get("message") if isinstance(js, list) and js and isinstance(js[0], dict) else None
                    if msg:
                        log.warning("Banque mondiale %s : %s", indicator, msg)
                    return pd.DataFrame(columns=["year", "value"])
                rows = [{"year": int(d["date"]), "value": d["value"]} for d in js[1] if d.get("value") is not None]
                return pd.DataFrame(rows, columns=["year", "value"]).sort_values("year")
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last = str(e)
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"API Banque mondiale indisponible pour {indicator} ({last})")


def fetch_wdi(iso3: str, indicators: dict[str, str] | None = None, start: int = 1990,
              end: int = 2030) -> pd.DataFrame:
    """Wide table: year + one column per indicator (short names from WDI_INDICATORS)."""
    indicators = indicators or WDI_INDICATORS
    wide = None
    for code, short in indicators.items():
        try:
            df = fetch_indicator(iso3, code, start, end).rename(columns={"value": short})
        except RuntimeError as e:
            log.warning("%s", e)
            continue
        wide = df if wide is None else wide.merge(df, on="year", how="outer")
    if wide is None:
        return pd.DataFrame(columns=["year"])
    return wide.sort_values("year").reset_index(drop=True)
