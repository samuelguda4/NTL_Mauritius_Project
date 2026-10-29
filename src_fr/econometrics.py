"""NTL–GDP relationship: elasticity with diagnostics, GDP nowcast, regional GDP estimation.

Specifications
--------------
1. Levels   : log(NTL_t) = a + β·log(GDP_t) + ε_t            (β = elasticity of lights to GDP)
2. Growth   : Δlog(NTL_t) = a + β·Δlog(GDP_t) + ε_t           (robust to common trends / spurious
                                                              regression between two trending series)
3. Long run : levels on the harmonised DMSP-like series, with a dummy for the VIIRS-converted years.

Standard errors are HAC (Newey–West) because residuals of annual macro series are serially
correlated. With 10–30 annual observations, intervals are wide: this is reported, not hidden.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _fit(y, X, hac_lags: int = 1):
    import statsmodels.api as sm
    X = sm.add_constant(X, has_constant="add")
    ols = sm.OLS(y, X).fit()
    hac = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags})
    return ols, hac


def diagnostics(ols) -> dict:
    """Durbin–Watson, Breusch–Pagan, Jarque–Bera and (if n ≥ 12) Ramsey RESET."""
    from statsmodels.stats.diagnostic import het_breuschpagan
    from statsmodels.stats.stattools import durbin_watson, jarque_bera
    out = {"durbin_watson": float(durbin_watson(ols.resid))}
    try:
        _, bp_p, _, _ = het_breuschpagan(ols.resid, ols.model.exog)
        out["breusch_pagan_p"] = float(bp_p)
    except Exception:  # noqa: BLE001
        out["breusch_pagan_p"] = np.nan
    jb, jb_p, _, _ = jarque_bera(ols.resid)
    out["jarque_bera_p"] = float(jb_p)
    if ols.nobs >= 12:
        try:
            from statsmodels.stats.diagnostic import linear_reset
            out["reset_p"] = float(linear_reset(ols, power=2, use_f=True).pvalue)
        except Exception:  # noqa: BLE001
            out["reset_p"] = np.nan
    return out


def _confidence(n: int, p: float, ci_width: float, r2: float) -> tuple[str, str]:
    """Qualitative confidence level for an elasticity estimate, with its reason."""
    if n < 8 or not np.isfinite(p):
        return "faible", f"seulement {n} observations"
    if p < 0.01 and ci_width < 1.0 and r2 >= 0.6 and n >= 15:
        return "élevée", f"n = {n}, p < 0,01, IC étroit"
    if p < 0.01 and ci_width < 1.0 and r2 >= 0.6:
        return "moyenne", f"relation nette mais seulement {n} années"
    if p < 0.10:
        return "moyenne", f"n = {n}, significatif mais IC large ({ci_width:.2f})"
    return "faible", f"n = {n}, non significatif (p = {p:.2f})"


def elasticity(df: pd.DataFrame, ntl: str = "sol", gdp: str = "gdp_const_usd", spec: str = "levels",
               dummy: str | None = None, hac_lags: int = 1) -> dict:
    """Estimate β in log(NTL) ~ log(GDP) (spec='levels') or in growth rates (spec='growth').

    Returns a dict with beta, 95 % CI (HAC), p-value, R², n, diagnostics, confidence, and a
    DataFrame of fitted values/residuals for plotting.
    """
    d = df[["year", ntl, gdp] + ([dummy] if dummy else [])].dropna().sort_values("year")
    d = d[(d[ntl] > 0) & (d[gdp] > 0)].copy()
    d["ly"], d["lx"] = np.log(d[ntl]), np.log(d[gdp])
    if spec == "growth":
        d["ly"], d["lx"] = d["ly"].diff(), d["lx"].diff()
        d = d.dropna(subset=["ly", "lx"])
    if len(d) < 5:
        return {"spec": spec, "n": int(len(d)), "beta": np.nan, "error": "moins de 5 observations"}
    X = d[["lx"] + ([dummy] if dummy else [])].astype(float)
    ols, hac = _fit(d["ly"].values, X.values, hac_lags)
    lo, hi = hac.conf_int()[1]
    beta, p = float(hac.params[1]), float(hac.pvalues[1])
    conf, why = _confidence(int(ols.nobs), p, float(hi - lo), float(ols.rsquared))
    d["fitted"] = ols.fittedvalues
    d["resid"] = ols.resid
    return {"spec": spec, "beta": beta, "ci": (float(lo), float(hi)), "p_value": p,
            "r2": float(ols.rsquared), "n": int(ols.nobs), "alpha": float(hac.params[0]),
            "dummy_coef": float(hac.params[2]) if dummy else None,
            "diagnostics": diagnostics(ols), "confidence": conf, "confidence_reason": why,
            "years": (int(d["year"].min()), int(d["year"].max())), "data": d}


def nowcast_gdp(df: pd.DataFrame, ntl: str = "sol", gdp: str = "gdp_const_usd") -> dict:
    """Estimate GDP for the years where NTL is observed but official GDP is not yet published.

    Model (growth rates): Δlog(GDP_t) = a + γ·Δlog(NTL_t) + ε_t, fitted on the overlap. Each
    missing year is chained from the last known GDP; the 80 % and 95 % prediction intervals
    are propagated by summing the variances of successive steps (conservative).
    """
    import statsmodels.api as sm
    d = df[["year", ntl, gdp]].sort_values("year").copy()
    d["dl_ntl"] = np.log(d[ntl].where(d[ntl] > 0)).diff()
    d["dl_gdp"] = np.log(d[gdp].where(d[gdp] > 0)).diff()
    fit_d = d.dropna(subset=["dl_ntl", "dl_gdp"])
    if len(fit_d) < 6:
        return {"n": int(len(fit_d)), "estimates": pd.DataFrame(), "error": "moins de 6 années de recouvrement"}
    res = sm.OLS(fit_d["dl_gdp"], sm.add_constant(fit_d["dl_ntl"])).fit()
    last_gdp_year = int(d.dropna(subset=[gdp])["year"].max())
    todo = d[(d["year"] > last_gdp_year) & d["dl_ntl"].notna()]
    rows, level, var = [], float(d.loc[d["year"] == last_gdp_year, gdp].iloc[0]), 0.0
    for _, r in todo.iterrows():
        pr = res.get_prediction(np.array([[1.0, r["dl_ntl"]]])).summary_frame(alpha=0.05)
        mean, se = float(pr["mean"].iloc[0]), float(pr["obs_ci_upper"].iloc[0] - pr["mean"].iloc[0]) / 1.96
        level *= np.exp(mean)
        var += se ** 2
        sd = np.sqrt(var)
        rows.append({"year": int(r["year"]), "gdp_est": level, "growth_est": float(np.expm1(mean)),
                     "lo95": level * np.exp(-1.96 * sd), "hi95": level * np.exp(1.96 * sd),
                     "lo80": level * np.exp(-1.2816 * sd), "hi80": level * np.exp(1.2816 * sd)})
    return {"gamma": float(res.params.iloc[1]), "gamma_ci": tuple(map(float, res.conf_int().iloc[1])),
            "r2": float(res.rsquared), "n": int(res.nobs), "last_official_year": last_gdp_year,
            "estimates": pd.DataFrame(rows)}


def in_sample_tracking(df: pd.DataFrame, ntl: str = "sol", gdp: str = "gdp_const_usd") -> pd.DataFrame:
    """Leave-one-out predictions of GDP growth from NTL growth (honest measure of tracking skill)."""
    import statsmodels.api as sm
    d = df[["year", ntl, gdp]].sort_values("year").copy()
    d["dl_ntl"] = np.log(d[ntl].where(d[ntl] > 0)).diff()
    d["dl_gdp"] = np.log(d[gdp].where(d[gdp] > 0)).diff()
    d = d.dropna(subset=["dl_ntl", "dl_gdp"]).reset_index(drop=True)
    preds = []
    for i in range(len(d)):
        tr = d.drop(index=i)
        if len(tr) < 5:
            preds.append(np.nan)
            continue
        m = sm.OLS(tr["dl_gdp"], sm.add_constant(tr["dl_ntl"])).fit()
        preds.append(float(m.params.iloc[0] + m.params.iloc[1] * d.loc[i, "dl_ntl"]))
    d["dl_gdp_loo"] = preds
    return d


def regional_gdp(units: pd.DataFrame, national: pd.DataFrame, gamma: float = 1.0,
                 value: str = "sol", gdp: str = "gdp_const_usd") -> pd.DataFrame:
    """Experimental regional GDP: national GDP allocated in proportion to SoL_i^γ.

    γ = 1 is the plain light-share allocation; γ < 1 (typical GDP-to-light elasticity in the
    literature) gives more weight to dimly lit regions. Totals always add up to national GDP.
    The output is an *estimate* to be labelled as experimental and validated against any
    regional accounts available.
    """
    d = units.merge(national[["year", gdp]], on="year", how="inner")
    d = d[d[value] > 0].copy()
    d["w"] = d[value] ** gamma
    d["share"] = d["w"] / d.groupby("year")["w"].transform("sum")
    d["gdp_est"] = d["share"] * d[gdp]
    if "pop" in d:
        d["gdp_pc_est"] = d["gdp_est"] / d["pop"].where(d["pop"] > 0)
    return d.drop(columns=["w"])
