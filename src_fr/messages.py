"""Automatic key messages, each with a confidence level and its justification.

Messages are generated from the results — no sentence is written in advance for a given
country. Each message dict: {theme, text, confidence ('élevée'|'moyenne'|'faible'), why}.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _pct(x, d=1, sign=True):
    if x is None or not np.isfinite(x):
        return "n.d."
    s = f"{100 * x:+.{d}f}" if sign else f"{100 * x:.{d}f}"
    return s.replace(".", ",") + " %"


def _num(x, d=0):
    if x is None or not np.isfinite(x):
        return "n.d."
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def _f(x, d=2):
    """French decimal formatting (comma)."""
    if x is None or not np.isfinite(x):
        return "n.d."
    return f"{x:.{d}f}".replace("-", "−").replace(".", ",")


def _conf_trend(p, n):
    if n < 6:
        return "faible", f"{n} années seulement"
    if p < 0.01:
        return "élevée", f"tendance significative (p < 0,01 ; n = {n})"
    if p < 0.10:
        return "moyenne", f"tendance significative au seuil de 10 % (p = {_f(p)})"
    return "faible", f"tendance non significative (p = {_f(p)})"


def key_messages(R: dict, country: str, names: dict) -> list[dict]:
    """5–7 messages from the results dict R (keys: dyn, growth, gdp, shocks, ineq, cfg)."""
    msgs = []
    dyn, gr, gdp, shk, ineq, cfg = (R.get(k) for k in ("dyn", "growth", "gdp", "shocks", "ineq", "cfg"))

    # 1. national trend
    if dyn:
        t = dyn["national_trend"]
        conf, why = _conf_trend(t["p_value"], t["n"])
        y = dyn["national_annual"]["year"]
        msgs.append({"theme": "Tendance nationale", "confidence": conf, "why": why, "text": (
            f"Entre {int(y.min())} et {int(y.max())}, la lumière nocturne de {country} a évolué de "
            f"{_pct(t['growth'])} par an (IC 95 % : {_pct(t['growth_lo'])} à {_pct(t['growth_hi'])}). "
            f"Sur les 12 derniers mois, le niveau désaisonnalisé est {_pct(dyn['growth_last12'])} "
            f"par rapport aux 12 mois précédents.")})

    # 2. regional dynamics and concentration
    if gr:
        lv = "ADM2" if "ADM2" in gr["trends"] else "ADM1"
        cc = gr["class_counts"][lv]
        n = sum(cc.values())
        conc = gr["concentration"]["ADM1"].iloc[-1] if "ADM1" in gr["concentration"] else None
        top = names.get(conc["top1_name"], conc["top1_name"]) if conc is not None else "n.d."
        msgs.append({"theme": "Régions", "confidence": "moyenne" if n >= 10 else "faible",
                     "why": f"classement sur {n} unités, seuil ±{100 * cfg.growth_threshold:.0f} %/an et p < {_f(cfg.alpha)}",
                     "text": (f"Sur {n} unités {lv}, {cc.get('Croissance', 0)} sont en croissance significative, "
                              f"{cc.get('Stagnation', 0)} stagnent et {cc.get('Déclin', 0)} déclinent. "
                              f"L'activité lumineuse reste concentrée : {top} concentre "
                              f"{_pct(conc['top1_share'], 0, False) if conc is not None else 'n.d.'} de la lumière nationale.")})
        b = gr.get("beta_convergence", {})
        if np.isfinite(b.get("beta", np.nan)):
            lo, hi = b["ci"]
            verdict = ("converge : les unités les moins éclairées rattrapent leur retard" if hi < 0 else
                       "diverge : les unités déjà éclairées croissent plus vite" if lo > 0 else
                       "ne montre ni convergence ni divergence statistiquement établie")
            msgs.append({"theme": "Convergence", "confidence": "moyenne" if (hi < 0 or lo > 0) else "faible",
                         "why": f"β = {_f(b['beta'], 3)} [{_f(lo, 3)} ; {_f(hi, 3)}], n = {b['n']}",
                         "text": f"Entre unités {b['level']}, la lumière par habitant {verdict}."})

    # 3. GDP link
    if gdp and "levels" in gdp and np.isfinite(gdp["levels"].get("beta", np.nan)):
        L, G = gdp["levels"], gdp.get("growth", {})
        txt = (f"L'élasticité de la lumière au PIB réel est de {_f(L['beta'])} en niveaux "
               f"(IC 95 % : {_f(L['ci'][0])} à {_f(L['ci'][1])}, R² = {_f(L['r2'])}, {L['n']} années)")
        if np.isfinite(G.get("beta", np.nan)):
            txt += f" et de {_f(G['beta'])} en taux de croissance (IC : {_f(G['ci'][0])} à {_f(G['ci'][1])})"
        txt += ". "
        if "tracking_corr" in gdp:
            txt += (f"Hors échantillon, la croissance des lumières suit celle du PIB avec une corrélation de "
                    f"{_f(gdp['tracking_corr'])} (erreur absolue moyenne : {_f(gdp['tracking_mae_pp'], 1)} point de croissance).")
        msgs.append({"theme": "Lien avec le PIB", "confidence": L["confidence"], "why": L["confidence_reason"],
                     "text": txt})
        nc = gdp.get("nowcast", {}).get("estimates")
        if nc is not None and len(nc):
            r = nc.iloc[-1]
            msgs.append({"theme": "Estimation récente", "confidence": "faible",
                         "why": "extrapolation d'un modèle estimé sur peu d'années ; intervalle de prévision large",
                         "text": (f"Les lumières suggèrent une croissance du PIB réel de {_pct(r['growth_est'])} en "
                                  f"{int(r['year'])} (année non encore publiée par la Banque mondiale), "
                                  f"intervalle à 80 % : {_num(r['lo80'] / 1e9, 1)} – {_num(r['hi80'] / 1e9, 1)} Md USD constants.")})

    # 4. shocks
    if shk is not None and len(shk.get("impacts", [])):
        imp = shk["impacts"]
        imp = imp[imp.get("computable", False) == True]  # noqa: E712
        if len(imp):
            r = imp.loc[imp["trough_pct"].idxmin()]
            rec = (f"retour au niveau d'avant-choc après {int(r['months_to_recovery'])} mois"
                   if r["recovered"] else "pas de retour au niveau d'avant-choc à la fin des données")
            msgs.append({"theme": "Chocs", "confidence": "moyenne" if r["distinguishable_from_noise"] else "faible",
                         "why": "creux comparé à la variabilité mensuelle d'avant-choc",
                         "text": (f"Le choc le plus marqué dans la série désaisonnalisée est « {r['label']} » : "
                                  f"creux de {_pct(r['trough_pct'] / 100)} ({pd.Timestamp(r['trough_date']):%m/%Y}), {rec}.")})

    # 5. inequality and dark population
    if ineq:
        s = ineq["series"]
        lo, hi = ineq["gini_change_ci"]
        sig = "hausse significative" if lo > 0 else "baisse significative" if hi < 0 else "évolution non significative"
        g1 = s.iloc[-1]
        nat = ineq["national"].iloc[-1]
        txt = (f"Le Gini de la lumière par habitant ({ineq['level']}) vaut {_f(g1['gini'])} en {int(g1['year'])} "
               f"({sig} depuis {int(s.iloc[0]['year'])}). ")
        if "pop_dark" in nat and np.isfinite(nat["pop_dark"]):
            txt += (f"Environ {_num(nat['pop_dark'] / 1e6, 2)} million(s) de personnes vivent dans des zones habitées "
                    f"sans lumière détectable ({_pct(nat['dark_share'], 0, False)} de la population habitée).")
        sens = ineq["dark_sensitivity"]
        sens = sens[sens["year"] == sens["year"].max()]
        rng_txt = (f"de {_num(sens['pop_dark'].min() / 1e6, 2)} à {_num(sens['pop_dark'].max() / 1e6, 2)} M "
                   f"selon le seuil") if len(sens) else ""
        msgs.append({"theme": "Inégalités et accès", "confidence": "moyenne",
                     "why": f"sensible au seuil de radiance ({rng_txt}) ; proxy d'éclairage extérieur, pas de raccordement",
                     "text": txt})
    from . import industry as _ind, tourism as _tou, urban as _urb
    msgs += (_ind.key_messages(R.get("industry")) + _tou.key_messages(R.get("tourism"))
             + _urb.key_messages(R.get("urban")))
    return msgs[:10]


def recommendations(R: dict) -> list[str]:
    """Generic, result-conditioned recommendations."""
    rec = ["Utiliser les lumières comme indicateur avancé et infranational, en complément — jamais en "
           "remplacement — des comptes nationaux."]
    gdp = R.get("gdp") or {}
    if gdp.get("levels", {}).get("confidence") == "faible":
        rec.append("Ne pas diffuser d'estimation de PIB fondée sur les lumières : le lien NTL–PIB n'est pas "
                   "établi avec une confiance suffisante sur cette période.")
    else:
        rec.append("Publier les estimations régionales de PIB comme statistiques expérimentales, avec intervalle "
                   "et note méthodologique, après comparaison avec les comptes régionaux disponibles.")
    ineq = R.get("ineq") or {}
    if "access_gap_pp" in ineq:
        rec.append(f"Croiser la carte des populations « dans le noir » avec les registres de raccordement : l'écart "
                   f"moyen avec le taux d'accès de la Banque mondiale est de {ineq['access_gap_pp']:+.0f} points.")
    shk = R.get("shocks") or {}
    if len(shk.get("unexplained_breaks", [])):
        rec.append("Documenter les ruptures détectées sans événement associé (changement de capteur, panne, "
                   "événement local) avant toute interprétation économique.")
    rec.append("Mettre à jour le tableau de bord chaque trimestre (série mensuelle VIIRS) et chaque année "
               "(composites annuels VNL).")
    from . import industry as _ind, tourism as _tou, urban as _urb
    rec[-1:-1] = (_ind.recommendations(R.get("industry")) + _tou.recommendations(R.get("tourism"))
                  + _urb.recommendations(R.get("urban")))
    return rec


LIMITS = [
    ("Ce que mesurent les lumières", "Radiance émise vers le haut vers 01 h 30 : l'agriculture, le commerce de "
     "jour, les services peu éclairés et l'économie informelle rurale sont mal captés."),
    ("Saturation et débordement", "DMSP sature au centre des villes (DN 63) et « déborde » (blooming) ; VIIRS est "
     "bien meilleur mais le débordement gonfle encore la surface éclairée des villes."),
    ("Torchères et sites isolés", "Le masque automatique peut retirer des mines, ports ou centrales isolés, et "
     "manquer de petites torchères ; les candidats sont exportés pour vérification."),
    ("Nuages, saisons, lune", "Les mois nuageux sont partiellement observés ; la STL retire la saisonnalité "
     "moyenne mais pas une saison anormale (neige, mousson tardive)."),
    ("Ruptures de produit", "DMSP et VIIRS ne sont pas directement comparables : la série longue harmonisée "
     "(Li et al., 2020) est un produit modélisé, à lire en tendance seulement."),
    ("Élasticité NTL–PIB", "Estimée sur 10 à 30 points annuels : intervalles larges, instabilité possible, "
     "relation non causale et variable selon le niveau de développement."),
    ("Accès à l'électricité", "« Habité sans lumière » ≠ « non raccordé » : un foyer raccordé à faible "
     "consommation est invisible ; l'indicateur dépend fortement du seuil de radiance et de la population."),
    ("Limites administratives", "geoBoundaries/GAUL peuvent différer des limites officielles ; les petites unités "
     "ADM2 sont sensibles au débordement de la lumière des voisines."),
]


from .industry import LIMITS as _L6  # noqa: E402
from .tourism import LIMITS as _L7  # noqa: E402
from .urban import LIMITS as _L8  # noqa: E402
LIMITS = LIMITS + _L6 + _L7 + _L8
