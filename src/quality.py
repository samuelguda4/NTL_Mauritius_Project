"""Quality and international standards — one quality sheet per use case, and the frameworks applied.

Night-time-light indicators are *not* official statistics. Following the practice of Eurostat and
the UK Office for National Statistics for new data sources, every output is published as an
**experimental statistic**, with its method, validation against an independent reference, its
uncertainty, its limitations and a confidence level. The project is mapped onto four reference
frameworks:

* the **UN Fundamental Principles of Official Statistics** (UN General Assembly resolution 68/261, 2014);
* the **Data Quality Assessment Framework** (DQAF, 2012): prerequisites, integrity, methodological
  soundness, accuracy and reliability, serviceability, accessibility;
* the **Generic Statistical Business Process Model** (GSBPM 5.1, UNECE 2019): which notebook section
  implements which phase of statistical production;
* the **FAIR principles** (Wilkinson et al., 2016): findable, accessible, interoperable, reusable data.

``build_quality`` returns a JSON-ready dict (also written to ``quality.json`` next to the dashboard
data) used by the notebook (section "Quality and standards"), the dashboard page "Quality" and the
GitHub repository (docs/QUALITY.md).
"""
from __future__ import annotations

import datetime as dt
import json
import math
import unicodedata
from pathlib import Path

from .lang import LANG

FR = LANG == "fr"
_t = (lambda fr, en: fr if FR else en)


def _num(x, d=2):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "n.d." if FR else "n/a"
    s = f"{x:,.{d}f}"
    return s.replace(",", " ").replace(".", ",") if FR else s


def _pct(x, d=1, sign=True):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "n.d." if FR else "n/a"
    s = f"{100 * x:+.{d}f}" if sign else f"{100 * x:.{d}f}"
    return (s.replace(".", ",") + " %") if FR else s + "%"


def _norm(s) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(s).lower()) if not unicodedata.combining(c))


def _conf(messages, *keys):
    for m in messages or []:
        t = _norm(m.get("theme", ""))
        if any(k in t for k in keys):
            return m.get("confidence"), m.get("why")
    return None, None


def use_case_sheets(R: dict, cfg, messages=None) -> list[dict]:
    """One quality sheet per use case, filled with the run's own validation figures."""
    dyn, gro, gdp, shk, ineq = (R.get(k) or {} for k in ("dyn", "growth", "gdp", "shocks", "ineq"))
    ind, tou, urb = R.get("industry") or {}, R.get("tourism") or {}, R.get("urban") or {}
    y0, y1 = cfg.start_year, cfg.end_year
    out = []

    t = dyn.get("national_trend") or {}
    c, w = _conf(messages, "tendance", "trend")
    out.append({
        "uc": 1, "page": "time", "title": _t("Dynamiques temporelles", "Time dynamics"),
        "question": _t("L'activité accélère-t-elle ou ralentit-elle, hors effet de saison ?",
                       "Is activity accelerating or slowing down, net of seasonality?"),
        "sources": ["VIIRS VCMSLCFG (monthly)", "VIIRS VNL V2 (annual)", "Harmonised DMSP–VIIRS (Li et al., 2020)"],
        "method": _t("STL robuste (période 12) sur log(somme des lumières) ; pente de Theil–Sen et test de Mann–Kendall sur "
                     "les composites annuels ; détection d'anomalies et de ruptures.",
                     "Robust STL (period 12) on log(sum of lights); Theil–Sen slope and Mann–Kendall test on annual "
                     "composites; anomaly and break detection."),
        "validation": {"text": _t("Significativité de la tendance (Mann–Kendall) et cohérence mensuel/annuel",
                                  "Trend significance (Mann–Kendall) and monthly/annual consistency"),
                       "metric": "p-value", "value": (("< " + _num(0.0001, 4)) if (t.get("p_value") is not None and t.get("p_value") < 1e-4)
                                                       else _num(t.get("p_value"), 4))},
        "uncertainty": _t(f"IC 95 % de la croissance annuelle : {_pct(t.get('growth_lo'))} à {_pct(t.get('growth_hi'))}",
                          f"95% CI of annual growth: {_pct(t.get('growth_lo'))} to {_pct(t.get('growth_hi'))}"),
        "limits": _t("Couverture nuageuse et nuits courtes en été ; la lumière n'est pas la valeur ajoutée.",
                     "Cloud cover and short summer nights; light is not value added."),
        "status": "experimental", "confidence": c, "confidence_reason": w})

    nc = gro.get("no2_corr") or {}
    c, w = _conf(messages, "region")
    out.append({
        "uc": 2, "page": "regions", "title": _t("Croissance régionale et convergence", "Regional growth and convergence"),
        "question": _t("Quelles régions décollent, lesquelles décrochent ?", "Which regions take off, which fall behind?"),
        "sources": ["VIIRS VNL V2", "GHSL / WorldPop", "Sentinel-5P NO₂"],
        "method": _t("Croissance robuste par unité (Theil–Sen, Mann–Kendall), classes croissance/stagnation/déclin, "
                     "β- et σ-convergence, indice de Herfindahl.",
                     "Robust growth per unit (Theil–Sen, Mann–Kendall), growth/stagnation/decline classes, β- and "
                     "σ-convergence, Herfindahl index."),
        "validation": {"text": _t("Corrélation de rang avec le NO₂ troposphérique (source indépendante)",
                                  "Rank correlation with tropospheric NO₂ (independent source)"),
                       "metric": "Spearman ρ", "value": _num(nc.get("rho"))},
        "uncertainty": _t("Classe attribuée seulement si |pente| ≥ seuil et p < α ; IC de β (erreurs robustes).",
                          "Class assigned only if |slope| ≥ threshold and p < α; CI of β (robust errors)."),
        "limits": _t("Petites unités : bruit et débordement de lumière (blooming) entre voisins.",
                     "Small units: noise and light blooming between neighbours."),
        "status": "experimental", "confidence": c, "confidence_reason": w})

    lv = gdp.get("levels") or {}
    c, w = _conf(messages, "pib", "gdp")
    out.append({
        "uc": 3, "page": "time", "title": _t("Relation lumières–PIB", "Light–GDP relationship"),
        "question": _t("Peut-on estimer la croissance avant sa publication, et le PIB régional ?",
                       "Can growth be estimated before its release, and regional GDP?"),
        "sources": ["VIIRS", _t("PIB réel (Banque mondiale, WDI)", "Real GDP (World Bank, WDI)")],
        "method": _t("log(lumière) ~ log(PIB) en niveaux et en croissance, MCO avec écarts-types HAC ; prévision hors "
                     "échantillon ; PIB régional = PIB national réparti au prorata de la lumière.",
                     "log(light) ~ log(GDP) in levels and growth, OLS with HAC errors; out-of-sample nowcast; regional "
                     "GDP = national GDP allocated pro rata of light."),
        "validation": {"text": _t("Suivi hors échantillon de la croissance officielle", "Out-of-sample tracking of official growth"),
                       "metric": _t("corrélation / EAM (points)", "correlation / MAE (pp)"),
                       "value": f"{_num(gdp.get('tracking_corr'))} / {_num(gdp.get('tracking_mae_pp'), 1)}"},
        "uncertainty": _t(f"IC 95 % de l'élasticité : {_num((lv.get('ci') or [None, None])[0])} à {_num((lv.get('ci') or [None, None])[1])} ; "
                          "intervalles de prévision 80 % et 95 %.",
                          f"95% CI of the elasticity: {_num((lv.get('ci') or [None, None])[0])} to {_num((lv.get('ci') or [None, None])[1])}; "
                          "80% and 95% prediction intervals."),
        "limits": _t("Échantillon annuel court ; le PIB régional est une statistique expérimentale à confronter aux comptes régionaux.",
                     "Short annual sample; regional GDP is an experimental statistic to be checked against regional accounts."),
        "status": "experimental", "confidence": lv.get("confidence") or c, "confidence_reason": lv.get("confidence_reason") or w})

    imp = shk.get("impacts")
    row = None
    try:
        ok = imp[imp["computable"]] if imp is not None and len(imp) else None
        row = ok.sort_values("trough_pct").iloc[0] if ok is not None and len(ok) else None
    except Exception:  # noqa: BLE001
        row = None
    c, w = _conf(messages, "choc", "shock")
    out.append({
        "uc": 4, "page": "shocks", "title": _t("Chocs et résilience", "Shocks and resilience"),
        "question": _t("Quelle a été la profondeur d'un choc, et la vitesse de récupération ?", "How deep was a shock, and how fast the recovery?"),
        "sources": ["VIIRS (monthly)", "Black Marble VNP46A2 (daily)", _t("catalogue d'événements", "event catalogue")],
        "method": _t("Écart au niveau d'avant-choc sur la série désaisonnalisée ; ruptures structurelles ; indice quotidien Black Marble.",
                     "Gap to the pre-shock level on the seasonally adjusted series; structural breaks; daily Black Marble index."),
        "validation": {"text": _t("Le creux dépasse-t-il la variabilité ordinaire ?", "Does the trough exceed ordinary variability?"),
                       "metric": _t("creux (choc principal)", "trough (main shock)"),
                       "value": (f"{_num(row['trough_pct'], 1)} % — {'oui' if row['distinguishable_from_noise'] else 'non'}" if FR else
                                 f"{_num(row['trough_pct'], 1)}% — {'yes' if row['distinguishable_from_noise'] else 'no'}") if row is not None else "n/a"},
        "uncertainty": _t("Variabilité mensuelle d'avant-choc (écart-type robuste) ; ruptures inexpliquées signalées.",
                          "Pre-shock month-to-month variability (robust SD); unexplained breaks flagged."),
        "limits": _t("Les chocs touchant des activités peu éclairées (agriculture, services de jour) sont sous-estimés.",
                     "Shocks hitting poorly lit activities (agriculture, daytime services) are underestimated."),
        "status": "experimental", "confidence": c, "confidence_reason": w})

    gap = ineq.get("access_gap_pp")
    c, w = _conf(messages, "inegal", "inequal")
    out.append({
        "uc": 5, "page": "inequality", "title": _t("Inégalités et électrification", "Inequality and electrification"),
        "question": _t("Où vivent les populations privées d'électricité ?", "Where do people without electricity live?"),
        "sources": ["VIIRS VNL V2", "GHSL / WorldPop", "GHSL SMOD", _t("accès à l'électricité (WDI)", "electricity access (WDI)")],
        "method": _t("Gini et Theil pondérés par la population ; population des pixels habités sous le seuil de détection ; "
                     "sensibilité à trois seuils ; IC bootstrap de la variation du Gini.",
                     "Population-weighted Gini and Theil; population of inhabited pixels below the detection threshold; "
                     "sensitivity to three thresholds; bootstrap CI of the Gini change."),
        "validation": {"text": _t("Écart avec le taux d'accès à l'électricité de la Banque mondiale", "Gap with the World Bank electricity-access rate"),
                       "metric": _t("écart moyen (points)", "mean gap (pp)"), "value": _num(gap, 1)},
        "uncertainty": _t("Plage selon le seuil de radiance ; IC bootstrap du Gini.", "Range across radiance thresholds; bootstrap CI of the Gini."),
        "limits": _t("Proxy de l'éclairage extérieur, pas du raccordement : un foyer raccordé mais peu éclairé paraît « dans le noir ».",
                     "Proxy of outdoor lighting, not of connection: a connected but dimly lit household looks “in the dark”."),
        "status": "experimental", "confidence": c, "confidence_reason": w})

    v = (ind or {}).get("validation") or {}
    c, w = _conf(messages, "industri")
    out.append({
        "uc": 6, "page": "industry", "title": _t("Zones industrielles", "Industrial zones"),
        "question": _t("Où est l'industrie, et son activité progresse-t-elle ?", "Where is industry, and is its activity growing?"),
        "sources": ["VIIRS VNL V2", "GHSL BUILT-S", "Sentinel-5P NO₂/SO₂", "MODIS MOD11A2", "OpenStreetMap"],
        "method": _t("Concordance de six signaux par pixel (≥ 3 dont la lumière), grappes 8-connexes, typologie et confiance.",
                     "Concordance of six signals per pixel (≥ 3 including light), 8-connected clusters, typology and confidence."),
        "validation": {"text": _t(f"Comparaison avec la liste de référence ({v.get('source', 'n.d.')})",
                                  f"Comparison with the reference list ({v.get('source', 'n/a')})"),
                       "metric": (_t("rappel (centrales électriques, référence partielle)", "recall (power plants, partial reference)")
                                  if v.get("partial") else _t("précision / rappel / F1", "precision / recall / F1")),
                       "value": (_pct(v.get("recall"), 0, False) if v.get("partial") else
                                 f"{_pct(v.get('precision'), 0, False)} / {_pct(v.get('recall'), 0, False)} / {_num(v.get('f1'))}"
                                 if v.get("available") else _t("non disponible", "not available"))},
        "uncertainty": _t("Confiance par grappe selon le nombre de signaux forts ; sites isolés à vérifier.",
                          "Per-cluster confidence from the number of strong signals; isolated sites to verify."),
        "limits": _t("Résolution de Sentinel-5P (≈ 5 km) et MODIS (1 km) : les signaux qualifient un voisinage.",
                     "Sentinel-5P (≈ 5 km) and MODIS (1 km) resolution: signals describe a neighbourhood."),
        "status": "experimental", "confidence": c, "confidence_reason": w})

    v = (tou or {}).get("validation") or {}
    c, w = _conf(messages, "touris")
    out.append({
        "uc": 7, "page": "tourism", "title": _t("Tourisme saisonnier", "Seasonal tourism"),
        "question": _t("Quelles zones vivent du tourisme, et comment évolue la saison ?", "Which areas live from tourism, and how does the season evolve?"),
        "sources": ["VIIRS (monthly)", _t("nuitées ou arrivées WDI", "hotel nights or WDI arrivals")],
        "method": _t("Surcroît estival net des unités comparables de même latitude ; test unilatéral ; indice de saison base 100 ; "
                     "saisons recoupant le Ramadan signalées.",
                     "Summer excess net of comparable units at the same latitude; one-sided test; season index base 100; "
                     "seasons overlapping Ramadan flagged."),
        "validation": {"text": _t(f"Corrélation avec {v.get('label', 'les nuitées')}", f"Correlation with {v.get('label', 'hotel nights')}"),
                       "metric": "r", "value": _num(v.get("corr")) if v.get("available") else _t("non disponible", "not available")},
        "uncertainty": _t("p-valeur par unité ; années 2020–2021 exclues du classement.", "p-value per unit; 2020–2021 excluded from the classification."),
        "limits": _t("Toute activité estivale (diaspora, résidences secondaires, festivals) est captée, pas seulement le tourisme.",
                     "Any summer activity (diaspora, second homes, festivals) is captured, not only tourism."),
        "status": "experimental", "confidence": c, "confidence_reason": w})

    v = (urb or {}).get("validation") or {}
    c, w = _conf(messages, "urbanis", "lit area", "surface éclairée")
    out.append({
        "uc": 8, "page": "urban", "title": _t("Signaux d'urbanisation", "Urbanisation signals"),
        "question": _t("Où les villes s'étendent-elles, où les villages s'électrifient-ils, et où la population croît-elle sans lumière ?",
                       "Where do cities spread, where do villages get electrified, and where does population grow without light?"),
        "sources": ["VIIRS VNL V2", "GHSL GHS-POP / WorldPop", "GHSL GHS-BUILT-S R2023A", _t("population urbaine (WDI)", "urban population (WDI)")],
        "method": _t("Surface éclairée (pixels au-dessus du seuil) et population par unité ; croissances de Theil–Sen ; "
                     "pixels nouvellement éclairés (sombres deux années de suite au début, éclairés deux années de suite à la fin), "
                     "séparés entre électrification de zones habitées et nouvelles implantations ; typologie lumière/population.",
                     "Lit area (pixels above the threshold) and population per unit; Theil–Sen growth rates; newly lit pixels "
                     "(dark two years in a row at the start, lit two years in a row at the end), split between electrification "
                     "of inhabited areas and new settlements; light/population typology."),
        "validation": {"text": _t("Corrélation de rang avec la croissance de la surface bâtie GHSL (source indépendante)",
                                  "Rank correlation with GHSL built-up area growth (independent source)"),
                       "metric": "Spearman ρ", "value": _num(v.get("rho")) if v.get("available") else _t("non disponible", "not available")},
        "uncertainty": _t("Persistance exigée sur deux années pour limiter le bruit ; marge de ± 1 point entre croissances avant de classer.",
                          "Persistence required over two years to limit noise; ± 1 pp margin between growth rates before classifying."),
        "limits": _t("La lumière mesure l'éclairage extérieur, pas l'urbanisation au sens administratif ; le débordement (blooming) "
                     "élargit les villes ; la population GHSL est interpolée entre époques.",
                     "Light measures outdoor lighting, not urbanisation in the administrative sense; blooming widens cities; "
                     "GHSL population is interpolated between epochs."),
        "status": "experimental", "confidence": c, "confidence_reason": w})
    return out


DQAF = {
    "fr": [
        ("0. Conditions préalables", "Cadre institutionnel, ressources, pertinence",
         "Projet Banque africaine de développement × Data Innovation for Africa (DI4A) ; données satellitaires gratuites ; questions de politique publique explicites pour chaque cas d'usage."),
        ("1. Garanties d'intégrité", "Professionnalisme, transparence, normes éthiques",
         "Code ouvert, méthodes documentées, paramètres et versions consignés dans le manifeste ; aucune donnée individuelle ; publication sans intervention manuelle sur les chiffres."),
        ("2. Rigueur méthodologique", "Concepts, champ, classifications, base d'enregistrement",
         "Méthodes publiées dans la littérature (Henderson et al. 2012 ; Elvidge et al. 2021 ; Román et al. 2018) ; codes ISO 3166 ; limites geoBoundaries ; WGS 84."),
        ("3. Exactitude et fiabilité", "Sources, évaluation, techniques statistiques, validation, révisions",
         "Contrôle qualité (couverture nuageuse, torchères, aberrants) ; validation de chaque cas d'usage contre une source indépendante ; intervalles de confiance ; niveau de confiance publié."),
        ("4. Utilité", "Périodicité, actualité, cohérence, politique de révision",
         "Séries mensuelles disponibles quelques semaines après le mois ; recalcul complet à chaque exécution (cache horodaté) ; cohérence vérifiée entre séries mensuelles et annuelles."),
        ("5. Accessibilité", "Données, métadonnées, assistance",
         "Tableau de bord public bilingue, fichiers ouverts (CSV, JSON, GeoJSON), manifeste de métadonnées, agent IA citant ses sources, dépôt GitHub avec citation."),
    ],
    "en": [
        ("0. Prerequisites of quality", "Institutional environment, resources, relevance",
         "African Development Bank × Data Innovation for Africa (DI4A) project; free satellite data; explicit policy question for each use case."),
        ("1. Assurances of integrity", "Professionalism, transparency, ethical standards",
         "Open code, documented methods, parameters and versions recorded in the manifest; no individual data; publication without manual intervention on figures."),
        ("2. Methodological soundness", "Concepts, scope, classification, basis for recording",
         "Methods published in the literature (Henderson et al. 2012; Elvidge et al. 2021; Román et al. 2018); ISO 3166 codes; geoBoundaries; WGS 84."),
        ("3. Accuracy and reliability", "Source data, assessment, statistical techniques, validation, revisions",
         "Quality control (cloud cover, gas flares, outliers); validation of every use case against an independent source; confidence intervals; published confidence level."),
        ("4. Serviceability", "Periodicity, timeliness, consistency, revision policy",
         "Monthly series available a few weeks after the month; full recomputation at each run (time-stamped cache); monthly/annual consistency checked."),
        ("5. Accessibility", "Data, metadata, assistance to users",
         "Public bilingual dashboard, open files (CSV, JSON, GeoJSON), metadata manifest, AI agent citing its sources, GitHub repository with citation."),
    ],
}[LANG]

GSBPM = {
    "fr": [("1. Spécifier les besoins", "1", "Questions de politique publique des huit cas d'usage"),
           ("2. Concevoir", "1–2", "Choix des sources, des indicateurs et des seuils"),
           ("3. Construire", "2", "Pipeline paramétré par ISO3, code embarqué, tests sur jeu synthétique"),
           ("4. Collecter", "3", "Earth Engine, Banque mondiale, OpenStreetMap — avec cache"),
           ("5. Traiter", "3", "Nuages, torchères, aberrants, harmonisation, contrôle qualité"),
           ("6. Analyser", "4–12", "Huit cas d'usage, validation, incertitude, interprétation"),
           ("7. Diffuser", "15–18", "Tableau de bord, images, agent IA, dépôt GitHub"),
           ("8. Évaluer", "13–14", "Fiches qualité, niveaux de confiance, limites, recommandations")],
    "en": [("1. Specify needs", "1", "Policy questions of the eight use cases"),
           ("2. Design", "1–2", "Choice of sources, indicators and thresholds"),
           ("3. Build", "2", "ISO3-driven pipeline, embedded code, tests on a synthetic dataset"),
           ("4. Collect", "3", "Earth Engine, World Bank, OpenStreetMap — with caching"),
           ("5. Process", "3", "Clouds, gas flares, outliers, harmonisation, quality control"),
           ("6. Analyse", "4–12", "Eight use cases, validation, uncertainty, interpretation"),
           ("7. Disseminate", "15–18", "Dashboard, images, AI agent, GitHub repository"),
           ("8. Evaluate", "13–14", "Quality sheets, confidence levels, limitations, recommendations")],
}[LANG]

FAIR = {
    "fr": [("Trouvable (Findable)", "Dépôt GitHub public avec description, mots-clés et CITATION.cff ; manifeste de métadonnées ; identifiant pérenne possible (DOI Zenodo)."),
           ("Accessible", "HTTPS public sans authentification ; formats ouverts ; code et données sous licence explicite."),
           ("Interopérable (Interoperable)", "CSV, JSON, GeoJSON (WGS 84) ; codes ISO 3166 ; identifiants d'unités stables ; vocabulaire des indicateurs documenté."),
           ("Réutilisable (Reusable)", "Provenance (sources, versions, paramètres), licences, méthodes et limites publiées avec les résultats.")],
    "en": [("Findable", "Public GitHub repository with description, topics and CITATION.cff; metadata manifest; persistent identifier possible (Zenodo DOI)."),
           ("Accessible", "Public HTTPS without authentication; open formats; code and data under an explicit licence."),
           ("Interoperable", "CSV, JSON, GeoJSON (WGS 84); ISO 3166 codes; stable unit identifiers; documented indicator vocabulary."),
           ("Reusable", "Provenance (sources, versions, parameters), licences, methods and limitations published with the results.")],
}[LANG]

UN_PRINCIPLES = {
    "fr": [("Pertinence et impartialité", "Indicateurs utiles aux décideurs, diffusés à tous en même temps."),
           ("Normes professionnelles", "Méthodes scientifiques publiées, choix fondés sur des critères techniques."),
           ("Responsabilité et transparence", "Sources, méthodes et procédures documentées."),
           ("Prévention des mauvais usages", "Niveaux de confiance, limites et étiquette « expérimental » sur chaque résultat."),
           ("Efficacité", "Données satellitaires gratuites, pipeline reproductible."),
           ("Confidentialité", "Aucune donnée individuelle : agrégats territoriaux uniquement."),
           ("Normes internationales", "DQAF, GSBPM, FAIR, ISO 3166."),
           ("Coopération", "Code ouvert, réutilisable par tous les instituts statistiques.")],
    "en": [("Relevance and impartiality", "Indicators useful to decision-makers, released to everyone at the same time."),
           ("Professional standards", "Published scientific methods, choices based on technical criteria."),
           ("Accountability and transparency", "Sources, methods and procedures documented."),
           ("Prevention of misuse", "Confidence levels, limitations and an “experimental” label on every output."),
           ("Cost-effectiveness", "Free satellite data, reproducible pipeline."),
           ("Confidentiality", "No individual data: territorial aggregates only."),
           ("International standards", "DQAF, GSBPM, FAIR, ISO 3166."),
           ("Cooperation", "Open code, reusable by every statistical office.")],
}[LANG]


def build_quality(R: dict, cfg, out_dir: str | Path | None = None, messages=None, version: str = "2.1.0") -> dict:
    """Quality sheets + frameworks; written to ``out_dir/quality.json`` when ``out_dir`` is given."""
    q = {
        "version": version, "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "country": cfg.country.get("name_fr" if FR else "name") or cfg.country.get("name"),
        "period": [cfg.start_year, cfg.end_year], "lang": LANG,
        "statement": _t("Les indicateurs issus des lumières nocturnes sont des statistiques expérimentales : ils complètent les "
                        "statistiques officielles sans les remplacer. Chaque résultat est publié avec sa méthode, sa validation, "
                        "son incertitude, ses limites et un niveau de confiance.",
                        "Night-time-light indicators are experimental statistics: they complement official statistics and do "
                        "not replace them. Every output is published with its method, validation, uncertainty, limitations "
                        "and a confidence level."),
        "use_cases": use_case_sheets(R, cfg, messages),
        "dqaf": [{"dimension": a, "practice": b, "evidence": c} for a, b, c in DQAF],
        "gsbpm": [{"phase": a, "notebook_sections": b, "what": c} for a, b, c in GSBPM],
        "fair": [{"principle": a, "how": b} for a, b in FAIR],
        "un_principles": [{"principle": a, "how": b} for a, b in UN_PRINCIPLES],
        "experimental": [_t("Toutes les séries et cartes dérivées des lumières nocturnes", "All series and maps derived from night-time lights"),
                         _t("PIB régional estimé et estimation de croissance de l'année non publiée", "Estimated regional GDP and growth estimate for the unpublished year"),
                         _t("Population « dans le noir » (proxy de l'accès à l'électricité)", "Population “in the dark” (proxy of electricity access)"),
                         _t("Grappes industrielles et indice de saison touristique", "Industrial clusters and tourist season index")],
        "references": [
            "United Nations (2014). Fundamental Principles of Official Statistics. A/RES/68/261.",
            "Data Quality Assessment Framework (DQAF, 2012) — generic framework.",
            "UNECE (2019). Generic Statistical Business Process Model, GSBPM v5.1.",
            "Wilkinson, M. D. et al. (2016). The FAIR Guiding Principles for scientific data management and stewardship. Scientific Data 3.",
            "Eurostat (2021). Experimental statistics — European Statistical System guidelines.",
        ],
    }
    if out_dir is not None:
        p = Path(out_dir) / "quality.json"
        p.write_text(json.dumps(q, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return q


def quality_markdown(q: dict) -> str:
    """Markdown rendering (notebook display and docs/QUALITY.md)."""
    c = lambda x: str(x if x is not None else "–").replace("|", "\\|")  # noqa: E731 - table-safe cell
    L = [f"> {q['statement']}", ""]
    hd = _t("| Cas d'usage | Validation | Valeur | Incertitude | Statut | Confiance |",
            "| Use case | Validation | Value | Uncertainty | Status | Confidence |")
    L += [hd, "|---|---|---|---|---|---|"]
    for u in q["use_cases"]:
        v = u["validation"]
        L.append(f"| **{u['uc']}. {c(u['title'])}** | {c(v['text'])} ({c(v['metric'])}) | {c(v['value'])} | {c(u['uncertainty'])} | "
                 f"{_t('expérimental', 'experimental')} | {u.get('confidence') or '–'} |")
    L += ["", f"**{_t('Cadre DQAF', 'DQAF')}**", "", _t("| Dimension | Pratique | Mise en œuvre |", "| Dimension | Practice | Implementation |"), "|---|---|---|"]
    L += [f"| {c(d['dimension'])} | {c(d['practice'])} | {c(d['evidence'])} |" for d in q["dqaf"]]
    L += ["", f"**GSBPM**", "", _t("| Phase | Sections | Contenu |", "| Phase | Sections | Content |"), "|---|---|---|"]
    L += [f"| {c(g['phase'])} | {c(g['notebook_sections'])} | {c(g['what'])} |" for g in q["gsbpm"]]
    L += ["", "**FAIR**", ""] + [f"- **{f['principle']}** — {f['how']}" for f in q["fair"]]
    return "\n".join(L)
