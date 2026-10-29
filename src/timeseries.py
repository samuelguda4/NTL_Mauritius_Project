"""Monthly series: STL seasonal adjustment, structural breaks, anomalies.

Work in logs: the seasonal swing of night-time lights is multiplicative (a 15 % winter
increase is 15 % whatever the level), so STL is applied to log(SoL).
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger("ntl")


def regularize_monthly(s: pd.Series, max_gap: int = 3) -> tuple[pd.Series, pd.Series]:
    """Put a series on a complete monthly index and fill short gaps by log-linear interpolation.

    Returns (filled series, boolean Series 'was_filled'). Gaps longer than `max_gap` months
    remain NaN (and the STL is then run on the longest complete stretch).
    """
    s = s.copy()
    s.index = pd.to_datetime(s.index).to_period("M").to_timestamp()
    s = s[~s.index.duplicated()].sort_index()
    idx = pd.date_range(s.index.min(), s.index.max(), freq="MS")
    s = s.reindex(idx)
    filled = s.isna()
    logv = np.log(s.where(s > 0))
    # length of each run of missing values: only runs of <= max_gap months are interpolated
    # (pandas' `limit` would partially fill longer gaps, inventing data inside an outage)
    miss = logv.isna()
    run_id = (miss != miss.shift()).cumsum()
    run_len = miss.groupby(run_id).transform("sum")
    interp = logv.interpolate(limit_area="inside")
    logv = logv.where(~miss, interp.where(run_len <= max_gap))
    out = np.exp(logv)
    return out, filled & out.notna()


def stl_decompose(s: pd.Series, period: int = 12, robust: bool = True) -> pd.DataFrame:
    """STL on log(series). Returns DataFrame[obs, log, trend, seasonal, resid, sa, sa_level].

    `sa` is the seasonally adjusted log series (trend + residual); `sa_level` = exp(sa).
    Requires at least 2 full periods of data.
    """
    from statsmodels.tsa.seasonal import STL
    s, _ = regularize_monthly(s)
    s = s.dropna()
    if len(s) < 2 * period + 1:
        raise ValueError(f"Series too short for STL ({len(s)} months, minimum {2 * period + 1}).")
    s = s.asfreq("MS")
    if s.isna().any():  # long gap: keep the longest complete stretch
        grp = s.isna().cumsum()
        best = s.groupby(grp).apply(lambda x: x.notna().sum()).idxmax()
        s = s[grp == best].dropna().asfreq("MS")
    y = np.log(s.clip(lower=1e-9))
    res = STL(y, period=period, robust=robust).fit()
    out = pd.DataFrame({"obs": s, "log": y, "trend": res.trend, "seasonal": res.seasonal,
                        "resid": res.resid})
    out["sa"] = out["trend"] + out["resid"]
    out["sa_level"] = np.exp(out["sa"])
    out["trend_level"] = np.exp(out["trend"])
    return out


def robust_z(x: pd.Series) -> pd.Series:
    """Robust z-score using the median and the MAD (×1.4826)."""
    med = np.nanmedian(x)
    mad = np.nanmedian(np.abs(x - med))
    sigma = 1.4826 * mad if mad > 0 else np.nanstd(x)
    return (x - med) / (sigma if sigma and sigma > 0 else np.nan)


def anomalies(stl: pd.DataFrame, z: float = 3.5, min_effect: float = 0.05) -> pd.DataFrame:
    """Months whose STL residual is extreme: |robust z| ≥ z AND |deviation| ≥ min_effect.

    The second condition keeps only economically meaningful deviations (≥ 5% by default):
    on a smooth national series the MAD is tiny and a 1 % blip can have a large z-score.
    """
    zz = robust_z(stl["resid"])
    out = stl.assign(z=zz)
    out = out[(np.abs(out["z"]) >= z) & (np.abs(np.expm1(out["resid"])) >= min_effect)]
    return out[["obs", "resid", "z"]].assign(direction=np.where(out["z"] > 0, "up", "down"))


def _seg_cost(y: np.ndarray, a: int, b: int) -> float:
    """Residual sum of squares of a linear trend fitted on y[a:b]."""
    seg = y[a:b]
    t = np.arange(len(seg), dtype=float)
    if len(seg) < 3:
        return 0.0
    A = np.c_[np.ones_like(t), t]
    coef, *_ = np.linalg.lstsq(A, seg, rcond=None)
    r = seg - A @ coef
    return float(r @ r)


def _seg_fit(y: np.ndarray, a: int, b: int) -> tuple[float, float]:
    t = np.arange(b - a, dtype=float)
    c = np.polyfit(t, y[a:b], 1)
    return float(c[1]), float(c[0])   # intercept, slope


def detect_breaks(sa: pd.Series, penalty: float | None = None, min_size: int = 12,
                  max_breaks: int = 4) -> pd.DataFrame:
    """Structural breaks in the seasonally adjusted log series, by binary segmentation with a
    piecewise-LINEAR cost (a break = a jump in level and/or a change of slope).

    A piecewise-constant model would cut any trending series into a staircase of spurious
    "breaks"; the linear cost avoids that. The default penalty is BIC-like:
    3 parameters × σ² × log(n) × 2, with σ the robust noise level estimated from the
    second differences (insensitive to the trend). A break needs `min_size` months on each side.

    Returns DataFrame[date, jump_pct, slope_before_pct_yr, slope_after_pct_yr, level_before,
    level_after, change_pct] where jump_pct is the level jump at the break between the two
    fitted segments, and change_pct the change between segment means.
    """
    cols = ["date", "jump_pct", "slope_before_pct_yr", "slope_after_pct_yr", "level_before", "level_after",
            "change_pct"]
    s = sa.dropna()
    y = s.values.astype(float)
    n = len(y)
    if n < 2 * min_size + 1:
        return pd.DataFrame(columns=cols)
    d2 = np.diff(y, 2)
    sigma = 1.4826 * np.median(np.abs(d2 - np.median(d2))) / np.sqrt(6)
    sigma = sigma if sigma > 0 else np.std(np.diff(y))
    pen = penalty if penalty is not None else 2 * 3 * sigma ** 2 * np.log(n)
    segs, bks = [(0, n)], []
    for _ in range(max_breaks):
        best = None
        for (a, b) in segs:
            base = _seg_cost(y, a, b)
            for k in range(a + min_size, b - min_size + 1):
                gain = base - _seg_cost(y, a, k) - _seg_cost(y, k, b)
                if best is None or gain > best[0]:
                    best = (gain, k, (a, b))
        if best is None or best[0] < pen:
            break
        _, k, ab = best
        segs.remove(ab)
        segs += [(ab[0], k), (k, ab[1])]
        bks.append(k)
    bks = sorted(bks)
    edges = [0] + bks + [n]
    rows = []
    for i, k in enumerate(bks):
        a, b = edges[i], edges[i + 2]
        i0, s0 = _seg_fit(y, a, k)
        i1, s1 = _seg_fit(y, k, b)
        end_before = i0 + s0 * (k - a)          # left segment extrapolated to the break month
        jump = i1 - end_before
        m0, m1 = y[a:k].mean(), y[k:b].mean()
        rows.append({"date": s.index[k], "jump_pct": float(100 * np.expm1(jump)),
                     "slope_before_pct_yr": float(100 * np.expm1(12 * s0)),
                     "slope_after_pct_yr": float(100 * np.expm1(12 * s1)),
                     "level_before": float(np.exp(m0)), "level_after": float(np.exp(m1)),
                     "change_pct": float(100 * np.expm1(m1 - m0))})
    return pd.DataFrame(rows, columns=cols)


def yoy_growth(s: pd.Series) -> pd.Series:
    """Year-on-year growth (same month of the previous year): immune to seasonality."""
    s, _ = regularize_monthly(s)
    return s / s.shift(12) - 1


def annual_from_monthly(df: pd.DataFrame, value: str = "sol_adj", min_months: int = 10) -> pd.DataFrame:
    """Annual mean of a monthly tidy table, per unit; years with < min_months observations dropped."""
    d = df.dropna(subset=[value]).copy()
    d["year"] = d["date"].dt.year
    g = d.groupby(["unit_id", "level", "year"])[value].agg(["mean", "count"]).reset_index()
    g = g[g["count"] >= min_months].rename(columns={"mean": f"{value}_mean", "count": "n_months"})
    return g
