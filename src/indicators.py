"""Indicators: growth, regional classification, concentration, convergence, inequality.

Conventions
-----------
* SoL (Sum of Lights) = sum of radiance over the pixels of a unit (an index, not energy).
* Growth rates are annual and robust: Theil–Sen slope of log(SoL) on the year, with a
  Mann–Kendall test (Kendall's tau between year and value).
* Inequality indices are population-weighted, computed on light per capita across units.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


# --------------------------------------------------------------------------------------
# Growth and classification
# --------------------------------------------------------------------------------------
def cagr(v0, v1, years):
    """Compound annual growth rate between two values (NaN if not positive)."""
    v0, v1 = np.asarray(v0, float), np.asarray(v1, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = (v1 / v0) ** (1.0 / years) - 1.0
    return np.where((v0 > 0) & (v1 > 0), r, np.nan)


def theil_sen_growth(years, values) -> dict:
    """Robust annual growth of a positive series: Theil–Sen slope on log(values).

    Returns {growth, growth_lo, growth_hi, tau, p_value, n}: growth = exp(slope) − 1 with a
    95% confidence interval, and the Mann–Kendall p-value (Kendall's tau).
    """
    x = np.asarray(years, float)
    y = np.asarray(values, float)
    m = np.isfinite(x) & np.isfinite(y) & (y > 0)
    x, y = x[m], y[m]
    if len(x) < 4:
        return {"growth": np.nan, "growth_lo": np.nan, "growth_hi": np.nan, "tau": np.nan,
                "p_value": np.nan, "n": int(len(x))}
    slope, _, lo, hi = stats.theilslopes(np.log(y), x, alpha=0.95)
    tau, p = stats.kendalltau(x, y)
    return {"growth": float(np.expm1(slope)), "growth_lo": float(np.expm1(lo)),
            "growth_hi": float(np.expm1(hi)), "tau": float(tau), "p_value": float(p), "n": int(len(x))}


def classify_growth(g: float, p: float, threshold: float = 0.01, alpha: float = 0.10) -> str:
    """'Growth' / 'Decline' if the trend exceeds ±threshold and is significant, else 'Stagnation'."""
    if not np.isfinite(g):
        return "Undetermined"
    if g >= threshold and p < alpha:
        return "Growth"
    if g <= -threshold and p < alpha:
        return "Decline"
    return "Stagnation"


def unit_trends(annual: pd.DataFrame, value: str = "sol", threshold: float = 0.01,
                alpha: float = 0.10) -> pd.DataFrame:
    """Per-unit robust growth and class from a tidy annual table [unit_id, level, year, value]."""
    rows = []
    for (uid, lv), g in annual.groupby(["unit_id", "level"]):
        g = g.sort_values("year")
        r = theil_sen_growth(g["year"], g[value])
        r.update({"unit_id": uid, "level": lv,
                  "first_year": int(g["year"].min()), "last_year": int(g["year"].max()),
                  "value_first": float(g[value].iloc[0]), "value_last": float(g[value].iloc[-1])})
        r["class"] = classify_growth(r["growth"], r["p_value"], threshold, alpha)
        rows.append(r)
    cols = ["unit_id", "level", "growth", "growth_lo", "growth_hi", "tau", "p_value", "n", "first_year",
            "last_year", "value_first", "value_last", "class"]
    return pd.DataFrame(rows, columns=cols)


# --------------------------------------------------------------------------------------
# Concentration
# --------------------------------------------------------------------------------------
def concentration(values: pd.Series, names: pd.Series | None = None) -> dict:
    """Shares of the top unit / top 10% of units, and Herfindahl–Hirschman index (0–1)."""
    v = pd.Series(values, dtype=float).clip(lower=0).dropna()
    tot = v.sum()
    if tot <= 0 or len(v) == 0:
        return {"top1_share": np.nan, "top10pct_share": np.nan, "hhi": np.nan, "top1_name": None}
    s = v.sort_values(ascending=False)
    k = max(1, int(np.ceil(0.10 * len(s))))
    top_name = None
    if names is not None:
        top_name = pd.Series(names, index=v.index).loc[s.index[0]]
    shares = s / tot
    return {"top1_share": float(shares.iloc[0]), "top10pct_share": float(shares.iloc[:k].sum()),
            "hhi": float((shares ** 2).sum()), "top1_name": top_name, "n_units": int(len(s))}


# --------------------------------------------------------------------------------------
# Inequality
# --------------------------------------------------------------------------------------
def _clean(x, w=None):
    x = np.asarray(x, float).ravel()
    w = np.ones_like(x) if w is None else np.asarray(w, float).ravel()
    m = np.isfinite(x) & np.isfinite(w) & (w > 0) & (x >= 0)
    return x[m], w[m]


def gini(x, w=None) -> float:
    """Weighted Gini coefficient (0 = equality, 1 = all light in one unit)."""
    x, w = _clean(x, w)
    if len(x) < 2 or (x * w).sum() <= 0:
        return np.nan
    o = np.argsort(x)
    x, w = x[o], w[o] / w.sum()
    cum = np.cumsum(w * x)
    cum = cum / cum[-1]
    prev = np.concatenate(([0.0], cum[:-1]))
    return float(1.0 - np.sum(w * (prev + cum)))


def lorenz(x, w=None, n: int = 101) -> tuple[np.ndarray, np.ndarray]:
    """Lorenz curve: (cumulative population share, cumulative light share) on n points."""
    x, w = _clean(x, w)
    if len(x) == 0:
        return np.array([0.0, 1.0]), np.array([0.0, 1.0])
    o = np.argsort(x)
    x, w = x[o], w[o]
    cw = np.concatenate(([0.0], np.cumsum(w) / w.sum()))
    cv = np.concatenate(([0.0], np.cumsum(x * w) / (x * w).sum()))
    q = np.linspace(0, 1, n)
    return q, np.interp(q, cw, cv)


def theil_t(x, w=None) -> float:
    """Theil T index of per-capita values x weighted by population w (0 = equality)."""
    x, w = _clean(x, w)
    if len(x) < 2:
        return np.nan
    mu = np.sum(w * x) / w.sum()
    if mu <= 0:
        return np.nan
    s = (w / w.sum()) * (x / mu)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(x > 0, s * np.log(x / mu), 0.0)
    return float(np.sum(t))


def theil_decomposition(df: pd.DataFrame, x: str, w: str, group: str) -> dict:
    """Theil T = between-group + within-group (groups = ADM1 for ADM2 units)."""
    d = df[[x, w, group]].dropna()
    d = d[(d[w] > 0) & (d[x] >= 0)]
    if len(d) < 3:
        return {"total": np.nan, "between": np.nan, "within": np.nan, "between_share": np.nan}
    total = theil_t(d[x], d[w])
    mu = np.sum(d[x] * d[w]) / d[w].sum()
    light_tot = np.sum(d[x] * d[w])
    between = within = 0.0
    for _, g in d.groupby(group):
        lg = np.sum(g[x] * g[w])
        if lg <= 0:
            continue
        mu_g = lg / g[w].sum()
        sg = lg / light_tot
        between += sg * np.log(mu_g / mu)
        within += sg * theil_t(g[x], g[w]) if len(g) > 1 else 0.0
    return {"total": float(total), "between": float(between), "within": float(within),
            "between_share": float(between / total) if total > 0 else np.nan}


# --------------------------------------------------------------------------------------
# Convergence
# --------------------------------------------------------------------------------------
def beta_convergence(initial_pc, growth) -> dict:
    """β-convergence: growth = a + β·log(initial light per capita) + ε (OLS, HC1 s.e.).

    β < 0 with a CI entirely below 0 => the least-lit units grow faster (convergence).
    """
    import statsmodels.api as sm
    x = np.log(np.asarray(initial_pc, float))
    y = np.asarray(growth, float)
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 8:
        return {"beta": np.nan, "ci": (np.nan, np.nan), "p_value": np.nan, "r2": np.nan, "n": int(m.sum())}
    res = sm.OLS(y[m], sm.add_constant(x[m])).fit(cov_type="HC1")
    lo, hi = res.conf_int()[1]
    return {"beta": float(res.params[1]), "ci": (float(lo), float(hi)), "p_value": float(res.pvalues[1]),
            "r2": float(res.rsquared), "n": int(m.sum()),
            "half_life_years": float(np.log(2) / -np.log1p(res.params[1])) if -1 < res.params[1] < 0 else np.nan}


def sigma_convergence(panel: pd.DataFrame, value: str, year: str = "year") -> pd.DataFrame:
    """σ-convergence: cross-unit standard deviation of log(value) per year (declining = convergence)."""
    d = panel[panel[value] > 0]
    out = d.groupby(year)[value].apply(lambda v: float(np.std(np.log(v), ddof=1))).rename("sigma_log")
    return out.reset_index()


# --------------------------------------------------------------------------------------
# Electricity-access proxy
# --------------------------------------------------------------------------------------
def dark_population_summary(annual: pd.DataFrame, thresholds: tuple[float, ...]) -> pd.DataFrame:
    """Share of the inhabited population living in unlit pixels, for each radiance threshold."""
    rows = []
    for _, r in annual.iterrows():
        inh = r.get("pop_inhabited", np.nan)
        for t in thresholds:
            col = "pop_dark_" + f"{t:g}".replace(".", "p")
            if col in r:
                rows.append({"unit_id": r["unit_id"], "level": r["level"], "year": r["year"],
                             "threshold": t, "pop_dark": r[col],
                             "dark_share": r[col] / inh if inh and inh > 0 else np.nan})
    return pd.DataFrame(rows)


def add_derived(annual: pd.DataFrame, area: pd.Series | None = None) -> pd.DataFrame:
    """Per-capita light, urban/rural split, lit share of population, flare share."""
    d = annual.copy()
    with np.errstate(divide="ignore", invalid="ignore"):
        d["sol_pc"] = d["sol"] / d["pop"].where(d["pop"] > 0)
        d["lit_area_share"] = d["lit_km2"] / d["area_km2"].where(d["area_km2"] > 0)
        if "pop_urban" in d:
            d["pop_rural"] = d["pop"] - d["pop_urban"]
            d["sol_rural"] = d["sol"] - d["sol_urban"]
            d["sol_pc_urban"] = d["sol_urban"] / d["pop_urban"].where(d["pop_urban"] > 0)
            d["sol_pc_rural"] = d["sol_rural"] / d["pop_rural"].where(d["pop_rural"] > 0)
            d["urban_rural_ratio"] = d["sol_pc_urban"] / d["sol_pc_rural"].where(d["sol_pc_rural"] > 0)
        nf_col = [c for c in d.columns if c.startswith("pop_dark_") and c[9:10].isdigit()]
        if "pop_dark_urban" in d and "pop_inhabited" in d:
            d["pop_dark"] = d["pop_dark_urban"] + d["pop_dark_rural"]
            d["dark_share"] = d["pop_dark"] / d["pop_inhabited"].where(d["pop_inhabited"] > 0)
            d["lit_pop_share"] = 1 - d["dark_share"]
        elif nf_col:
            d["pop_dark"] = d[nf_col[0]]
        if "flare_sol" in d:
            d["flare_share"] = d["flare_sol"] / d["sol_raw"].where(d["sol_raw"] > 0)
    return d
