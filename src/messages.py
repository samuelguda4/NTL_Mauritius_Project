"""Automatic key messages, each with a confidence level and its justification.

Messages are generated from the results — no sentence is written in advance for a given
country. Each message dict: {theme, text, confidence ('high'|'medium'|'low'), why}.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _pct(x, d=1, sign=True):
    if x is None or not np.isfinite(x):
        return "n/a"
    s = f"{100 * x:+.{d}f}" if sign else f"{100 * x:.{d}f}"
    return s + "%"


def _num(x, d=0):
    if x is None or not np.isfinite(x):
        return "n/a"
    return f"{x:,.{d}f}"


def _f(x, d=2):
    """English decimal formatting (point), with a typographic minus sign."""
    if x is None or not np.isfinite(x):
        return "n/a"
    return f"{x:.{d}f}".replace("-", "−")


def _conf_trend(p, n):
    if n < 6:
        return "low", f"only {n} years"
    if p < 0.01:
        return "high", f"significant trend (p < 0.01; n = {n})"
    if p < 0.10:
        return "medium", f"trend significant at the 10% level (p = {_f(p)})"
    return "low", f"trend not significant (p = {_f(p)})"


def key_messages(R: dict, country: str, names: dict) -> list[dict]:
    """5–7 messages from the results dict R (keys: dyn, growth, gdp, shocks, ineq, cfg)."""
    msgs = []
    dyn, gr, gdp, shk, ineq, cfg = (R.get(k) for k in ("dyn", "growth", "gdp", "shocks", "ineq", "cfg"))

    # 1. national trend
    if dyn:
        t = dyn["national_trend"]
        conf, why = _conf_trend(t["p_value"], t["n"])
        y = dyn["national_annual"]["year"]
        msgs.append({"theme": "National trend", "confidence": conf, "why": why, "text": (
            f"Between {int(y.min())} and {int(y.max())}, night-time light in {country} changed by "
            f"{_pct(t['growth'])} per year (95% CI: {_pct(t['growth_lo'])} to {_pct(t['growth_hi'])}). "
            f"Over the last 12 months, the seasonally adjusted level is {_pct(dyn['growth_last12'])} "
            f"relative to the previous 12 months.")})

    # 2. regional dynamics and concentration
    if gr:
        lv = "ADM2" if "ADM2" in gr["trends"] else "ADM1"
        cc = gr["class_counts"][lv]
        n = sum(cc.values())
        conc = gr["concentration"]["ADM1"].iloc[-1] if "ADM1" in gr["concentration"] else None
        top = names.get(conc["top1_name"], conc["top1_name"]) if conc is not None else "n/a"
        msgs.append({"theme": "Regions", "confidence": "medium" if n >= 10 else "low",
                     "why": f"classification of {n} units, threshold ±{100 * cfg.growth_threshold:.0f}%/yr and p < {_f(cfg.alpha)}",
                     "text": (f"Of {n} {lv} units, {cc.get('Growth', 0)} show significant growth, "
                              f"{cc.get('Stagnation', 0)} are stagnating and {cc.get('Decline', 0)} are declining. "
                              f"Light remains concentrated: {top} accounts for "
                              f"{_pct(conc['top1_share'], 0, False) if conc is not None else 'n/a'} of national light.")})
        b = gr.get("beta_convergence", {})
        if np.isfinite(b.get("beta", np.nan)):
            lo, hi = b["ci"]
            verdict = ("converges: the least-lit units are catching up" if hi < 0 else
                       "diverges: already well-lit units are growing faster" if lo > 0 else
                       "shows neither statistically established convergence nor divergence")
            msgs.append({"theme": "Convergence", "confidence": "medium" if (hi < 0 or lo > 0) else "low",
                         "why": f"β = {_f(b['beta'], 3)} [{_f(lo, 3)}; {_f(hi, 3)}], n = {b['n']}",
                         "text": f"Across {b['level']} units, light per capita {verdict}."})

    # 3. GDP link
    if gdp and "levels" in gdp and np.isfinite(gdp["levels"].get("beta", np.nan)):
        L, G = gdp["levels"], gdp.get("growth", {})
        txt = (f"The elasticity of light with respect to real GDP is {_f(L['beta'])} in levels "
               f"(95% CI: {_f(L['ci'][0])} to {_f(L['ci'][1])}, R² = {_f(L['r2'])}, {L['n']} years)")
        if np.isfinite(G.get("beta", np.nan)):
            txt += f" and {_f(G['beta'])} in growth rates (CI: {_f(G['ci'][0])} to {_f(G['ci'][1])})"
        txt += ". "
        if "tracking_corr" in gdp:
            txt += (f"Out of sample, light growth tracks GDP growth with a correlation of "
                    f"{_f(gdp['tracking_corr'])} (mean absolute error: {_f(gdp['tracking_mae_pp'], 1)} percentage points of growth).")
        msgs.append({"theme": "Link with GDP", "confidence": L["confidence"], "why": L["confidence_reason"],
                     "text": txt})
        nc = gdp.get("nowcast", {}).get("estimates")
        if nc is not None and len(nc):
            r = nc.iloc[-1]
            msgs.append({"theme": "Recent estimate", "confidence": "low",
                         "why": "extrapolation of a model estimated on few years; wide prediction interval",
                         "text": (f"Lights suggest real GDP growth of {_pct(r['growth_est'])} in "
                                  f"{int(r['year'])} (a year not yet published by the World Bank), "
                                  f"80% interval: {_num(r['lo80'] / 1e9, 1)} – {_num(r['hi80'] / 1e9, 1)} constant USD bn.")})

    # 4. shocks
    if shk is not None and len(shk.get("impacts", [])):
        imp = shk["impacts"]
        imp = imp[imp.get("computable", False) == True]  # noqa: E712
        if len(imp):
            r = imp.loc[imp["trough_pct"].idxmin()]
            rec = (f"return to the pre-shock level after {int(r['months_to_recovery'])} months"
                   if r["recovered"] else "no return to the pre-shock level by the end of the data")
            msgs.append({"theme": "Shocks", "confidence": "medium" if r["distinguishable_from_noise"] else "low",
                         "why": "trough compared with pre-shock month-to-month variability",
                         "text": (f"The most pronounced shock in the seasonally adjusted series is “{r['label']}”: "
                                  f"trough of {_pct(r['trough_pct'] / 100)} ({pd.Timestamp(r['trough_date']):%m/%Y}), {rec}.")})

    # 5. inequality and dark population
    if ineq:
        s = ineq["series"]
        lo, hi = ineq["gini_change_ci"]
        sig = "significant increase" if lo > 0 else "significant decrease" if hi < 0 else "no significant change"
        g1 = s.iloc[-1]
        nat = ineq["national"].iloc[-1]
        txt = (f"The Gini coefficient of light per capita ({ineq['level']}) is {_f(g1['gini'])} in {int(g1['year'])} "
               f"({sig} since {int(s.iloc[0]['year'])}). ")
        if "pop_dark" in nat and np.isfinite(nat["pop_dark"]):
            txt += (f"About {_num(nat['pop_dark'] / 1e6, 2)} million people live in inhabited areas "
                    f"with no detectable light ({_pct(nat['dark_share'], 0, False)} of the inhabited population).")
        sens = ineq["dark_sensitivity"]
        sens = sens[sens["year"] == sens["year"].max()]
        rng_txt = (f"from {_num(sens['pop_dark'].min() / 1e6, 2)} to {_num(sens['pop_dark'].max() / 1e6, 2)} M "
                   f"depending on the threshold") if len(sens) else ""
        msgs.append({"theme": "Inequality and access", "confidence": "medium",
                     "why": f"sensitive to the radiance threshold ({rng_txt}); a proxy for outdoor lighting, not for grid connection",
                     "text": txt})
    from . import industry as _ind, tourism as _tou, urban as _urb
    msgs += (_ind.key_messages(R.get("industry")) + _tou.key_messages(R.get("tourism"))
             + _urb.key_messages(R.get("urban")))
    return msgs[:10]


def recommendations(R: dict) -> list[str]:
    """Generic, result-conditioned recommendations."""
    rec = ["Use night-time lights as a leading and subnational indicator, as a complement to — never a "
           "replacement for — the national accounts."]
    gdp = R.get("gdp") or {}
    if gdp.get("levels", {}).get("confidence") == "low":
        rec.append("Do not disseminate light-based GDP estimates: the NTL–GDP relationship is not "
                   "established with sufficient confidence over this period.")
    else:
        rec.append("Publish regional GDP estimates as experimental statistics, with intervals "
                   "and a methodological note, after comparison with available regional accounts.")
    ineq = R.get("ineq") or {}
    if "access_gap_pp" in ineq:
        rec.append(f"Cross-check the map of populations “in the dark” against grid-connection registers: the average "
                   f"gap with the World Bank access rate is {ineq['access_gap_pp']:+.0f} percentage points.")
    shk = R.get("shocks") or {}
    if len(shk.get("unexplained_breaks", [])):
        rec.append("Document breaks detected without an associated event (sensor change, outage, "
                   "local event) before any economic interpretation.")
    rec.append("Update the dashboard every quarter (monthly VIIRS series) and every year "
               "(annual VNL composites).")
    from . import industry as _ind, tourism as _tou, urban as _urb
    rec[-1:-1] = (_ind.recommendations(R.get("industry")) + _tou.recommendations(R.get("tourism"))
                  + _urb.recommendations(R.get("urban")))
    return rec


LIMITS = [
    ("What lights measure", "Upward radiance emitted around 01:30: agriculture, daytime trade, "
     "poorly lit services and the rural informal economy are poorly captured."),
    ("Saturation and blooming", "DMSP saturates in city centres (DN 63) and “blooms” beyond lit areas; VIIRS is "
     "much better, but blooming still inflates the lit area of cities."),
    ("Gas flares and isolated sites", "The automatic mask may remove isolated mines, ports or power plants, and "
     "miss small flares; candidates are exported for verification."),
    ("Clouds, seasons, moon", "Cloudy months are only partially observed; STL removes average seasonality "
     "but not an abnormal season (snow, late monsoon)."),
    ("Product breaks", "DMSP and VIIRS are not directly comparable: the harmonised long series "
     "(Li et al., 2020) is a modelled product, to be read for trends only."),
    ("NTL–GDP elasticity", "Estimated on 10 to 30 annual observations: wide intervals, possible instability, "
     "a non-causal relationship that varies with the level of development."),
    ("Access to electricity", "“Inhabited without light” ≠ “not connected”: a connected household with low "
     "consumption is invisible; the indicator depends strongly on the radiance threshold and the population data."),
    ("Administrative boundaries", "geoBoundaries/GAUL may differ from official boundaries; small ADM2 units "
     "are sensitive to light spilling over from neighbouring units."),
]


from .industry import LIMITS as _L6  # noqa: E402
from .tourism import LIMITS as _L7  # noqa: E402
from .urban import LIMITS as _L8  # noqa: E402
LIMITS = LIMITS + _L6 + _L7 + _L8
