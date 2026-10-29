"""Showcase GitHub repository (``main`` branch) generated from the run: README EN/FR, docs, assets.

    from src import repo
    REPO_DIR = repo.build_repo(cfg, ROOT, ROOT / "outputs" / "repo_main", SITE_URL, REPO_URL,
                               {"fr": OUT, "en": OUT_EN}, notebook_path=repo.notebook_from_colab(...),
                               synthetic=SYNTHETIC_TEST)

The tree is meant to be pushed as-is to the default branch (``publish_dashboard(..., repo_dir=REPO_DIR)``);
the site itself stays on ``gh-pages``. Everything is written from the exported files of the run
(summary.json, agent_context.json, media.json, quality.json when present), in both languages
whatever the notebook language: ``README.md`` (English) and ``README.fr.md`` (French).

Nothing secret is ever written: notebooks are stripped of outputs and of metadata, and every
text file is scanned for token-like strings (which are redacted).
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
import re
import shutil
from pathlib import Path
from urllib.parse import quote

log = logging.getLogger("ntl")

VERSION = "2.1.0"
SECRET_RX = re.compile(r"(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|gsk_[A-Za-z0-9]{20,}|"
                       r"AIza[0-9A-Za-z_\-]{30,}|sk-[A-Za-z0-9]{20,})")
UC_PAGE = {1: "time", 2: "regions", 3: "time", 4: "shocks", 5: "inequality", 6: "industry", 7: "tourism", 8: "urban"}
THEME_UC = {"National trend": 1, "Tendance nationale": 1, "Regions": 2, "Régions": 2, "Link with GDP": 3,
            "Lien avec le PIB": 3, "Shocks": 4, "Chocs": 4, "Inequality and access": 5, "Inégalités et accès": 5,
            "Industrial zones": 6, "Zones industrielles": 6, "Summer tourism": 7, "Tourisme estival": 7}
UC_ICON = {1: "📈", 2: "🗺️", 3: "💹", 4: "⚡", 5: "⚖️", 6: "🏭", 7: "🏖️", 8: "🏙️"}

# --------------------------------------------------------------------------------------
# Texts (both languages are always written)
# --------------------------------------------------------------------------------------
TX = {
    "en": {
        "lang_switch": "<b>English</b> · <a href=\"README.fr.md\">Français</a>",
        "title": "Night-time lights: eight use cases",
        "pitch": "Turning satellite night-time lights into evidence for <b>{country}</b> — <b>eight use cases</b> for "
                 "statistics and public policy: economic dynamics, regional growth, GDP nowcasting, shocks and "
                 "resilience, inequality and electrification, industrial zones, seasonal tourism, urbanisation — with a "
                 "<b>public dashboard</b> and an <b>AI agent</b> that answers only from the published figures.",
        "cta": "Open the live dashboard", "colab": "Run the notebook in Colab",
        "synthetic": "**Synthetic test data.** Every figure, map and animation in this repository was produced from "
                     "the fictitious country *{country}* to test the pipeline end to end. None of them is a real statistic.",
        "tl_title": "{years} years of night lights in {sec}",
        "glance": "At a glance", "glance_sub": "Key figures of the run, {a}–{b}. Each comes with its confidence level "
                                              "and method on the dashboard.",
        "shock": "A shock, seen from space",
        "ucs": "Eight use cases", "ucs_sub": "Each card opens the matching page of the live dashboard.",
        "question": "Question", "finding": "Finding", "open": "Open the page →",
        "ai_card": "AI agent", "ai_card_q": "Ask the results in plain language — every number is cited.",
        "tour": "The dashboard", "tour_sub": "Bilingual (FR/EN), works offline-first from static files, light & dark "
                                            "themes, mobile-ready.",
        "screens": "Screenshots",
        "agent": "The AI agent",
        "agent_txt": [
            "**Grounded.** The agent only answers from the numbered facts exported with the dashboard "
            "(`agent_context.json`, F01, F02…): the same facts in the notebook and on the website.",
            "**Cited.** Every quantitative sentence cites its fact, e.g. `[F12]`; citations link to the dashboard page "
            "they come from, and unknown citations are removed.",
            "**A real agent with six tools.** It plans, calls tools by *function calling* and chains several steps: "
            "🔎 `search_facts`, 🏆 `rank_units`, 📍 `unit_profile`, ⚖️ `compare_units`, 📈 `make_chart` (charts drawn in "
            "the conversation) and 🗺️ `map_action` (it drives the dashboard map: year, swipe comparison, zoom, layers). "
            "Each step is shown; tool results are cited as `[D2]`.",
            "**Briefs in one click.** Policy brief, country profile or parliamentary answer — structured, sourced, "
            "exportable as Markdown or PDF.",
            "**Your choice of model.** Groq (`openai/gpt-oss-120b` by default), Google Gemini or a local Ollama model, "
            "with streamed answers; without any model, an offline planner runs the same tools.",
            "**Guard-rails.** Read-only tools, at most five tool calls per question, data never treated as "
            "instructions (prompt-injection resistant), rate limiting.",
            "**Keys stay with you.** On the website, a visitor's API key stays in their own browser and is sent only "
            "to the chosen provider; in the notebook keys come from Colab Secrets. No key is ever published.",
        ],
        "arch": "How it works",
        "quick": "Quick start",
        "quick_steps": [
            "**Open the notebook in Colab** — [{nb}]({colab}).",
            "**Set the country** — in section 2, `ISO3 = \"TUN\"` (any ISO 3166-1 alpha-3 code) and the period; "
            "`SYNTHETIC_TEST = True` runs everything without Earth Engine.",
            "**Run all** — *Runtime → Run all*. The dashboard is exported to `dashboard/` and, with `PUBLISH = True`, "
            "published to GitHub Pages in one call.",
        ],
        "secrets": "Keys and tokens go in **Colab Secrets** (🔑 icon): `GITHUB_TOKEN` (fine-grained, this repository "
                   "only: *Contents*, *Pages* — plus *Administration* to create the repository and set its "
                   "description), and optionally `GROQ_API_KEY` or `GEMINI_API_KEY`. An Earth Engine Cloud project is "
                   "needed for real countries.",
        "sources": "Data sources",
        "src_cols": ["Dataset", "Provider · Earth Engine ID", "Used for", "Reference"],
        "method": "Methodology & quality standards",
        "method_txt": "Full methodology: [docs/methodology.md](docs/methodology.md) · quality report: "
                      "[docs/QUALITY.md](docs/QUALITY.md).",
        "std": [
            "**UN Fundamental Principles of Official Statistics** — relevance, impartiality, professional standards, "
            "transparency of sources and methods, open access to the results.",
            "**Data Quality Assessment Framework (DQAF)** — integrity, methodological soundness, accuracy and "
            "reliability, serviceability, accessibility.",
            "**GSBPM** — every notebook section maps to a phase of the Generic Statistical Business Process Model.",
            "**FAIR** — findable (stable URLs, citation file), accessible (open formats), interoperable (CSV, JSON, "
            "GeoJSON), reusable (licence, provenance in `manifest.json`).",
            "**Experimental statistics** — night-light estimates complement, and never replace, official "
            "statistics; they are labelled *experimental* with their uncertainty.",
        ],
        "q_cols": ["Use case", "Status", "Confidence", "Validation"],
        "experimental": "Experimental", "official": "Official input",
        "struct": "Repository structure",
        "security": "Security",
        "security_txt": [
            "Tokens and API keys are **never** written to disk, printed, logged, committed or published; "
            "publication uses the GitHub REST API with an in-memory token and redacts every error message.",
            "Use a **fine-grained token** limited to this repository, with an expiry date; revoke it when it is no longer needed.",
            "Every file is scanned for token patterns before each push; the publication is cancelled if one is found.",
            "The site is static (no server, no database); the AI assistant runs in the visitor's browser.",
        ],
        "cite": "How to cite", "cite_txt": "See [`CITATION.cff`](CITATION.cff) (GitHub shows a *Cite this repository* "
                                           "button), or:",
        "license": "License",
        "license_txt": "© AfDB-DI4A (African Development Bank — Data Innovation for Africa). **Any reuse of the results, "
                       "maps, charts or images must state the source: “Source: AfDB-DI4A”.** "
                       "Code: [MIT](LICENSE). Derived data and images follow the licence of each source dataset "
                       "(for example, EOG VIIRS products, GHSL, WorldPop, geoBoundaries and World Bank WDI are "
                       "distributed under CC BY 4.0, OpenStreetMap under ODbL) — see each source's licence before reuse.",
        "ack": "Acknowledgements",
        "ack_txt": "Developed by the **African Development Bank (AfDB)** and **Data Innovation for Africa (DI4A)**. "
                   "Night-time lights by the Earth Observation Group (Payne Institute, "
                   "Colorado School of Mines) and NASA Black Marble, processed with Google Earth Engine.",
        "footer": "Generated by the notebook on {date} · version {v}",
        "q": {1: "How fast is economic activity growing, and what happened over the last 12 months?",
              2: "Which regions are pulling ahead, and which are falling behind?",
              3: "Can lights estimate GDP growth before it is published — and regional GDP?",
              4: "How deep was the shock, and how long did the recovery take?",
              5: "Who lives in the dark, and is activity becoming more evenly spread?",
              6: "Where are the industrial zones, and are they growing?",
              7: "Which areas live from summer tourism, and how strong was each season?",
              8: "Where do cities spread and villages light up — and where does population grow without light?"},
        "t": {1: "Temporal dynamics", 2: "Regional growth", 3: "Lights and GDP", 4: "Economic shocks",
              5: "Inequality & access", 6: "Industrial zones", 7: "Summer tourism", 8: "Urbanisation"},
        "uc": "Use case",
    },
    "fr": {
        "lang_switch": "<a href=\"README.md\">English</a> · <b>Français</b>",
        "title": "Lumières nocturnes : huit cas d'usage",
        "pitch": "Transformer les lumières nocturnes observées par satellite en éclairages pour <b>{country}</b> — "
                 "<b>huit cas d'usage</b> au service des statistiques et des politiques publiques : dynamiques "
                 "économiques, croissance régionale, prévision du PIB, chocs et résilience, inégalités et "
                 "électrification, zones industrielles, tourisme saisonnier, urbanisation — avec un <b>tableau de bord public</b> et "
                 "un <b>agent IA</b> qui ne répond qu'à partir des chiffres publiés.",
        "cta": "Ouvrir le tableau de bord", "colab": "Exécuter le notebook dans Colab",
        "synthetic": "**Données synthétiques de test.** Tous les chiffres, cartes et animations de ce dépôt proviennent "
                     "du pays fictif *{country}*, créé pour tester la chaîne de traitement de bout en bout. Aucun n'est "
                     "une statistique réelle.",
        "tl_title": "{years} ans de lumières nocturnes en {sec}",
        "glance": "En un coup d'œil", "glance_sub": "Chiffres clés de l'exécution, {a}–{b}. Chacun est accompagné de "
                                                   "son niveau de confiance et de sa méthode sur le tableau de bord.",
        "shock": "Un choc vu de l'espace",
        "ucs": "Huit cas d'usage", "ucs_sub": "Chaque carte ouvre la page correspondante du tableau de bord.",
        "question": "Question", "finding": "Résultat", "open": "Ouvrir la page →",
        "ai_card": "Agent IA", "ai_card_q": "Interrogez les résultats en langage naturel — chaque chiffre est cité.",
        "tour": "Le tableau de bord", "tour_sub": "Bilingue (FR/EN), fichiers statiques, thèmes clair et sombre, "
                                                 "adapté au mobile.",
        "screens": "Captures d'écran",
        "agent": "L'agent IA",
        "agent_txt": [
            "**Ancré dans les résultats.** L'agent répond uniquement à partir des faits numérotés exportés avec le "
            "tableau de bord (`agent_context.json`, F01, F02…) : les mêmes dans le notebook et sur le site.",
            "**Sourcé.** Chaque phrase chiffrée cite son fait, par ex. `[F12]` ; les citations renvoient à la page du "
            "tableau de bord concernée, et les citations inconnues sont supprimées.",
            "**Un véritable agent à six outils.** Il planifie, appelle ses outils (*function calling*) et enchaîne "
            "plusieurs étapes : 🔎 `search_facts`, 🏆 `rank_units`, 📍 `unit_profile`, ⚖️ `compare_units`, "
            "📈 `make_chart` (graphiques dans la conversation) et 🗺️ `map_action` (il pilote la carte : année, rideau "
            "avant/après, zoom, couches). Chaque étape est affichée ; les résultats d'outils sont cités `[D2]`.",
            "**Des notes en un clic.** Note pour un décideur, fiche pays ou réponse parlementaire — structurées, "
            "sourcées, exportables en Markdown ou PDF.",
            "**Le modèle de votre choix.** Groq (`openai/gpt-oss-120b` par défaut), Google Gemini ou un modèle local "
            "Ollama, avec réponses en continu ; sans modèle, un planificateur hors ligne exécute les mêmes outils.",
            "**Garde-fous.** Outils en lecture seule, cinq appels d'outils au plus par question, données jamais "
            "traitées comme des instructions (résistance à l'injection de consignes), limitation du débit.",
            "**Vos clés restent chez vous.** Sur le site, la clé d'un visiteur reste dans son navigateur et n'est "
            "envoyée qu'au fournisseur choisi ; dans le notebook, les clés viennent des Secrets Colab. Aucune clé "
            "n'est jamais publiée.",
        ],
        "arch": "Fonctionnement",
        "quick": "Démarrage rapide",
        "quick_steps": [
            "**Ouvrir le notebook dans Colab** — [{nb}]({colab}).",
            "**Choisir le pays** — section 2 : `ISO3 = \"TUN\"` (tout code ISO 3166-1 alpha-3) et la période ; "
            "`SYNTHETIC_TEST = True` exécute tout sans Earth Engine.",
            "**Tout exécuter** — *Exécution → Tout exécuter*. Le tableau de bord est exporté dans `dashboard/` et, avec "
            "`PUBLISH = True`, publié sur GitHub Pages en un seul appel.",
        ],
        "secrets": "Les clés et jetons se placent dans les **Secrets Colab** (icône 🔑) : `GITHUB_TOKEN` (fine-grained, "
                   "limité à ce dépôt : *Contents*, *Pages* — plus *Administration* pour créer le dépôt et sa "
                   "description), et facultativement `GROQ_API_KEY` ou `GEMINI_API_KEY`. Un projet Cloud Earth Engine "
                   "est nécessaire pour un pays réel.",
        "sources": "Sources de données",
        "src_cols": ["Jeu de données", "Fournisseur · ID Earth Engine", "Utilisation", "Référence"],
        "method": "Méthodologie et normes de qualité",
        "method_txt": "Méthodologie complète : [docs/methodology.fr.md](docs/methodology.fr.md) · rapport qualité : "
                      "[docs/QUALITY.fr.md](docs/QUALITY.fr.md).",
        "std": [
            "**Principes fondamentaux de la statistique officielle (ONU)** — pertinence, impartialité, normes "
            "professionnelles, transparence des sources et méthodes, accès ouvert aux résultats.",
            "**Cadre d'évaluation de la qualité des données (DQAF)** — intégrité, rigueur méthodologique, "
            "exactitude et fiabilité, utilité, accessibilité.",
            "**GSBPM** — chaque section du notebook correspond à une phase du modèle générique du processus statistique.",
            "**FAIR** — trouvable (URL stables, fichier de citation), accessible (formats ouverts), interopérable "
            "(CSV, JSON, GeoJSON), réutilisable (licence, provenance dans `manifest.json`).",
            "**Statistiques expérimentales** — les estimations par les lumières complètent, sans jamais les remplacer, "
            "les statistiques officielles ; elles sont étiquetées *expérimentales*, avec leur incertitude.",
        ],
        "q_cols": ["Cas d'usage", "Statut", "Confiance", "Validation"],
        "experimental": "Expérimental", "official": "Intrant officiel",
        "struct": "Structure du dépôt",
        "security": "Sécurité",
        "security_txt": [
            "Les jetons et clés d'API ne sont **jamais** écrits sur disque, affichés, journalisés, versionnés ni "
            "publiés ; la publication passe par l'API REST GitHub avec un jeton en mémoire, et chaque message "
            "d'erreur est expurgé.",
            "Utiliser un **jeton fine-grained** limité à ce dépôt, avec une date d'expiration ; le révoquer dès qu'il n'est plus utile.",
            "Chaque fichier est analysé avant chaque envoi ; la publication est annulée si un motif de jeton est trouvé.",
            "Le site est statique (ni serveur, ni base de données) ; l'assistant IA s'exécute dans le navigateur du visiteur.",
        ],
        "cite": "Citer ce travail", "cite_txt": "Voir [`CITATION.cff`](CITATION.cff) (bouton *Cite this repository* "
                                               "de GitHub), ou :",
        "license": "Licence",
        "license_txt": "© AfDB-DI4A (Banque africaine de développement — Data Innovation for Africa). **Toute "
                       "réutilisation des résultats, cartes, graphiques ou images doit mentionner la source : « Source : "
                       "AfDB-DI4A ».** Code : [MIT](LICENSE). Les données et images dérivées suivent la licence de chaque source "
                       "(par exemple, les produits VIIRS de l'EOG, GHSL, WorldPop, geoBoundaries et les WDI de la Banque "
                       "mondiale sont diffusés sous CC BY 4.0, OpenStreetMap sous ODbL) — consulter la licence de chaque "
                       "source avant réutilisation.",
        "ack": "Remerciements",
        "ack_txt": "Développé par la **Banque africaine de développement (BAD)** et **Data Innovation for Africa (DI4A)**. "
                   "Lumières nocturnes : Earth Observation Group (Payne Institute, Colorado "
                   "School of Mines) et NASA Black Marble, traitées avec Google Earth Engine.",
        "footer": "Généré par le notebook le {date} · version {v}",
        "q": {1: "À quel rythme l'activité progresse-t-elle, et que s'est-il passé ces 12 derniers mois ?",
              2: "Quelles régions décollent, lesquelles décrochent ?",
              3: "Les lumières permettent-elles d'estimer la croissance du PIB avant sa publication — et le PIB régional ?",
              4: "Quelle a été la profondeur du choc, et combien de temps a duré la reprise ?",
              5: "Qui vit dans le noir, et l'activité se répartit-elle plus également ?",
              6: "Où sont les zones industrielles, et progressent-elles ?",
              7: "Quelles zones vivent du tourisme estival, et quelle a été la force de chaque saison ?",
              8: "Où les villes s'étendent-elles et les villages s'allument-ils — et où la population croît-elle sans lumière ?"},
        "t": {1: "Dynamiques temporelles", 2: "Croissance régionale", 3: "Lumières et PIB", 4: "Chocs économiques",
              5: "Inégalités et accès", 6: "Zones industrielles", 7: "Tourisme estival", 8: "Urbanisation"},
        "uc": "Cas d'usage",
    },
}

SOURCES = [  # name, provider · id, use {en, fr}, reference
    ("VIIRS VNL V2 (annual)", "NOAA/EOG · `NOAA/VIIRS/DNB/ANNUAL_V21`, `ANNUAL_V22`",
     {"en": "annual levels, maps, inequality", "fr": "niveaux annuels, cartes, inégalités"},
     "Elvidge, C. D. et al. (2021). Annual time series of global VIIRS nighttime lights. *Remote Sensing* 13(5)."),
    ("VIIRS DNB monthly (VCMSLCFG)", "NOAA/EOG · `NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG`",
     {"en": "monthly series, seasonality, shocks, tourism", "fr": "séries mensuelles, saisonnalité, chocs, tourisme"},
     "Elvidge, C. D. et al. (2017). VIIRS night-time lights. *Int. J. Remote Sensing* 38(21)."),
    ("Black Marble VNP46A2 (daily)", "NASA · `NASA/VIIRS/002/VNP46A2`",
     {"en": "daily shock index", "fr": "indice quotidien des chocs"},
     "Román, M. O. et al. (2018). NASA's Black Marble nighttime lights product suite. *RSE* 210."),
    ("DMSP-OLS / harmonised DMSP–VIIRS", "NOAA NGDC · Li et al. (sat-io)",
     {"en": "long series since 1992 (GDP elasticity)", "fr": "série longue depuis 1992 (élasticité au PIB)"},
     "Li, X. et al. (2020). A harmonized global nighttime light dataset 1992–2018. *Scientific Data* 7, 168."),
    ("GHSL R2023A (POP, SMOD, BUILT-S)", "European Commission JRC · `JRC/GHSL/P2023A/*`",
     {"en": "population, urban/rural, non-residential built-up", "fr": "population, urbain/rural, bâti non résidentiel"},
     "Schiavina, M. et al. (2023); Pesaresi, M. et al. (2023). GHSL R2023A. JRC."),
    ("WorldPop", "WorldPop · `WorldPop/GP/100m/pop`",
     {"en": "population (alternative)", "fr": "population (variante)"},
     "WorldPop (2018). Global High Resolution Population Denominators."),
    ("Sentinel-5P TROPOMI NO₂ / SO₂", "ESA Copernicus · `COPERNICUS/S5P/OFFL/L3_NO2`, `L3_SO2`",
     {"en": "activity cross-check, industrial signals", "fr": "contrôle de l'activité, signaux industriels"},
     "Veefkind, J. P. et al. (2012). TROPOMI on the ESA Sentinel-5 Precursor. *RSE* 120."),
    ("MODIS LST (MOD11A2)", "NASA · `MODIS/061/MOD11A2`",
     {"en": "surface heat of industrial sites", "fr": "chaleur de surface des sites industriels"},
     "Wan, Z. (2014). New refinements and validation of the MODIS LST products. *RSE* 140."),
    ("OpenStreetMap", "OpenStreetMap contributors · Overpass API",
     {"en": "industrial-area reference list", "fr": "liste de référence des zones industrielles"},
     "© OpenStreetMap contributors, ODbL."),
    ("World Bank WDI", "World Bank · `NY.GDP.MKTP.KD`, `NV.IND.TOTL.KD`, `EG.ELC.ACCS.ZS`…",
     {"en": "real GDP, industry value added, electricity access", "fr": "PIB réel, valeur ajoutée industrielle, accès à l'électricité"},
     "World Bank (2026). World Development Indicators."),
    ("geoBoundaries / FAO GAUL", "William & Mary geoLab · FAO",
     {"en": "administrative boundaries", "fr": "limites administratives"},
     "Runfola, D. et al. (2020). geoBoundaries. *PLoS ONE* 15(4)."),
]

UC_DOC = {  # static methodological notes per use case (complemented by quality.json and agent facts)
    "en": {
        1: {"data": "VIIRS DNB monthly (VCMSLCFG), cloud-free coverage `cf_cvg`; annual VNL V2.",
            "validation": "Seasonal pattern and breaks checked against known events; months with < 80% observed pixels excluded.",
            "uncertainty": "Theil–Sen slope with 95% confidence interval; Mann–Kendall p-value.",
            "limits": "Lights capture night-time outdoor lighting, not value added; winter cloud cover and stray light.",
            "refs": "Cleveland et al. (1990) STL; Sen (1968); Elvidge et al. (2017)."},
        2: {"data": "Annual VIIRS sum of lights per ADM1/ADM2 unit; GHSL population.",
            "validation": "Ranking compared with Sentinel-5P NO₂ (Spearman correlation across units).",
            "uncertainty": "Per-unit Theil–Sen intervals; classes require p < 0.10 and |slope| ≥ 1%/yr.",
            "limits": "Small units are noisy; boundary changes; blooming around large cities.",
            "refs": "Barro & Sala-i-Martin (1992) convergence; Henderson, Storeygard & Weil (2012)."},
        3: {"data": "VIIRS (2014–) and harmonised DMSP–VIIRS (1992–); World Bank real GDP (constant USD).",
            "validation": "Out-of-sample tracking of GDP growth (leave-one-out), residual diagnostics (DW, BP, JB).",
            "uncertainty": "HAC standard errors; prediction intervals (80% and 95%) for the unpublished year.",
            "limits": "Few annual observations; elasticity varies with development level; regional GDP is experimental.",
            "refs": "Henderson et al. (2012) AER; Chen & Nordhaus (2011) PNAS; Gibson et al. (2021) JDE."},
        4: {"data": "Seasonally adjusted monthly VIIRS; daily Black Marble VNP46A2; event catalogue.",
            "validation": "Trough compared with pre-shock month-to-month variability (signal vs noise).",
            "uncertainty": "Distinguishability test; daily index smoothed with a 7-day rolling median.",
            "limits": "Curfews and lighting policies can move lights without output changes; cloud gaps in daily data.",
            "refs": "Román et al. (2018); Elvidge et al. (2020) COVID-19 lockdown lights."},
        5: {"data": "VIIRS annual radiance; GHSL / WorldPop population (≥ 5 inhabitants per pixel).",
            "validation": "Lit-population share compared with World Bank electricity access (EG.ELC.ACCS.ZS).",
            "uncertainty": "Sensitivity to the darkness threshold (0.25 / 0.5 / 1 nW); bootstrap CI on the Gini change.",
            "limits": "A proxy for outdoor lighting, not for grid connection; small rural lights below detection.",
            "refs": "Theil (1967); Falchetta et al. (2020) electricity access from lights."},
        6: {"data": "VIIRS, GHSL non-residential built-up, Sentinel-5P NO₂/SO₂, MODIS LST, OpenStreetMap.",
            "validation": "Precision / recall against an official list or OpenStreetMap industrial areas (1.5 km match).",
            "uncertainty": "Confidence from the number of concordant signals (3 to 6).",
            "limits": "Gas flares and ports can mimic industry; reference lists are incomplete.",
            "refs": "Elvidge et al. (2016) gas flares; Pesaresi et al. (2023) GHSL."},
        7: {"data": "Monthly VIIRS per district; hotel nights or arrivals when available.",
            "validation": "Correlation of the season index with hotel nights (levels and growth).",
            "uncertainty": "One-sided t-test over summers; net excess relative to comparable units.",
            "limits": "Short summer nights and Ramadan shift night-time activity; coastal stray light.",
            "refs": "Seasonal light analyses of tourism, e.g. Hu et al. (2021)."},
        8: {"data": "Annual VIIRS VNL V2 (lit area above threshold); GHSL GHS-POP and GHS-BUILT-S R2023A; WDI urban population.",
            "validation": "Rank correlation of lit-area growth with GHSL built-up growth (independent source).",
            "uncertainty": "Two-year persistence for newly lit pixels; ± 1 pp margin before classifying units.",
            "limits": "Outdoor lighting is not urbanisation in the administrative sense; blooming widens cities; GHSL population interpolated between epochs.",
            "refs": "Zhou et al. (2015) urban extent from lights; Pesaresi et al. (2023) GHSL; Min et al. (2013) village electrification."},
    },
    "fr": {
        1: {"data": "VIIRS DNB mensuel (VCMSLCFG), couverture sans nuage `cf_cvg` ; VNL V2 annuel.",
            "validation": "Saisonnalité et ruptures confrontées aux événements connus ; mois avec < 80 % de pixels observés exclus.",
            "uncertainty": "Pente de Theil–Sen avec intervalle de confiance à 95 % ; p-valeur de Mann–Kendall.",
            "limits": "Les lumières mesurent l'éclairage nocturne extérieur, pas la valeur ajoutée ; nuages d'hiver, lumière parasite.",
            "refs": "Cleveland et al. (1990) STL ; Sen (1968) ; Elvidge et al. (2017)."},
        2: {"data": "Somme annuelle des lumières VIIRS par unité ADM1/ADM2 ; population GHSL.",
            "validation": "Classement comparé au NO₂ Sentinel-5P (corrélation de Spearman entre unités).",
            "uncertainty": "Intervalles de Theil–Sen par unité ; classes si p < 0,10 et |pente| ≥ 1 %/an.",
            "limits": "Petites unités bruitées ; changements de limites ; débordement autour des grandes villes.",
            "refs": "Barro et Sala-i-Martin (1992) convergence ; Henderson, Storeygard et Weil (2012)."},
        3: {"data": "VIIRS (2014–) et DMSP–VIIRS harmonisé (1992–) ; PIB réel Banque mondiale (USD constants).",
            "validation": "Suivi hors échantillon de la croissance du PIB (leave-one-out), diagnostics des résidus (DW, BP, JB).",
            "uncertainty": "Écarts-types HAC ; intervalles de prévision (80 % et 95 %) pour l'année non publiée.",
            "limits": "Peu d'observations annuelles ; élasticité variable selon le niveau de développement ; PIB régional expérimental.",
            "refs": "Henderson et al. (2012) AER ; Chen et Nordhaus (2011) PNAS ; Gibson et al. (2021) JDE."},
        4: {"data": "VIIRS mensuel désaisonnalisé ; Black Marble quotidien VNP46A2 ; catalogue d'événements.",
            "validation": "Creux comparé à la variabilité mensuelle d'avant-choc (signal contre bruit).",
            "uncertainty": "Test de distinguabilité ; indice quotidien lissé par médiane mobile de 7 jours.",
            "limits": "Couvre-feux et politiques d'éclairage modifient la lumière sans changer la production ; trous nuageux.",
            "refs": "Román et al. (2018) ; Elvidge et al. (2020) lumières et confinements."},
        5: {"data": "Radiance annuelle VIIRS ; population GHSL / WorldPop (≥ 5 habitants par pixel).",
            "validation": "Part de la population éclairée comparée à l'accès à l'électricité (Banque mondiale, EG.ELC.ACCS.ZS).",
            "uncertainty": "Sensibilité au seuil d'obscurité (0,25 / 0,5 / 1 nW) ; IC bootstrap sur la variation du Gini.",
            "limits": "Indicateur de l'éclairage extérieur, pas du raccordement ; petites lumières rurales sous le seuil.",
            "refs": "Theil (1967) ; Falchetta et al. (2020) accès à l'électricité par les lumières."},
        6: {"data": "VIIRS, bâti non résidentiel GHSL, NO₂/SO₂ Sentinel-5P, LST MODIS, OpenStreetMap.",
            "validation": "Précision / rappel contre une liste officielle ou les zones industrielles OpenStreetMap (appariement à 1,5 km).",
            "uncertainty": "Confiance selon le nombre de signaux concordants (3 à 6).",
            "limits": "Torchères et ports peuvent imiter l'industrie ; listes de référence incomplètes.",
            "refs": "Elvidge et al. (2016) torchères ; Pesaresi et al. (2023) GHSL."},
        7: {"data": "VIIRS mensuel par district ; nuitées ou arrivées si disponibles.",
            "validation": "Corrélation de l'indice de saison avec les nuitées (niveaux et croissance).",
            "uncertainty": "Test t unilatéral sur les étés ; surcroît net des unités comparables.",
            "limits": "Nuits d'été courtes et Ramadan déplacent l'activité nocturne ; lumière parasite côtière.",
            "refs": "Analyses saisonnières des lumières et du tourisme, par ex. Hu et al. (2021)."},
        8: {"data": "VIIRS VNL V2 annuel (surface éclairée au-dessus du seuil) ; GHSL GHS-POP et GHS-BUILT-S R2023A ; population urbaine WDI.",
            "validation": "Corrélation de rang entre croissance de la surface éclairée et croissance du bâti GHSL (source indépendante).",
            "uncertainty": "Persistance de deux ans pour les pixels nouvellement éclairés ; marge de ± 1 point avant de classer les unités.",
            "limits": "L'éclairage extérieur n'est pas l'urbanisation au sens administratif ; le débordement élargit les villes ; population GHSL interpolée entre époques.",
            "refs": "Zhou et al. (2015) étendue urbaine par les lumières ; Pesaresi et al. (2023) GHSL ; Min et al. (2013) électrification des villages."},
    },
}
DOC_LABEL = {
    "en": {"question": "Question", "data": "Data", "method": "Method", "validation": "Validation",
           "uncertainty": "Uncertainty", "limits": "Limits", "refs": "References", "results": "Results of this run",
           "status": "Status", "confidence": "Confidence", "page": "Dashboard page", "sources": "Sources",
           "general": "General limits of night-time lights", "data_proc": "Data and cleaning",
           "method_title": "Methodology", "quality_title": "Quality report"},
    "fr": {"question": "Question", "data": "Données", "method": "Méthode", "validation": "Validation",
           "uncertainty": "Incertitude", "limits": "Limites", "refs": "Références", "results": "Résultats de cette exécution",
           "status": "Statut", "confidence": "Confiance", "page": "Page du tableau de bord", "sources": "Sources",
           "general": "Limites générales des lumières nocturnes", "data_proc": "Données et nettoyage",
           "method_title": "Méthodologie", "quality_title": "Rapport qualité"},
}


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------
def _read_json(p: Path):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _num(x: float, lang: str, d: int = 1) -> str:
    s = f"{x:,.{d}f}"
    if lang == "fr":
        s = s.replace(",", "\u202f").replace(".", ",")
    return s.replace("-", "−")


def _fmt_kpi(k: dict, lang: str) -> str:
    v, f = k.get("value"), k.get("fmt")
    if v is None:
        return "—"
    pc = "\u00a0%" if lang == "fr" else "%"
    if f == "pct":
        return ("+" if v > 0 else "") + _num(100 * v, lang, 1) + pc
    if f == "pct0":
        return _num(100 * v, lang, 0) + pc
    if f == "num2":
        return _num(v, lang, 2)
    if f == "people":
        if abs(v) >= 1e6:
            return _num(v / 1e6, lang, 2) + "\u00a0M"
        if abs(v) >= 1e3:
            return _num(v / 1e3, lang, 0) + ("\u00a0k" if lang == "fr" else "k")
        return _num(v, lang, 0)
    if f == "num":
        return _num(v, lang, 0)
    return str(v)


def _badge(label: str, message: str, color: str, logo: str | None = None, style: str | None = None) -> str:
    def esc(s):
        return quote(s.replace("-", "--").replace("_", "__"), safe="")
    url = f"https://img.shields.io/badge/{esc(label)}-{esc(message)}-{color.lstrip('#')}"
    q = []
    if style:
        q.append(f"style={style}")
    if logo:
        q += [f"logo={quote(logo)}", "logoColor=white"]
    return url + ("?" + "&".join(q) if q else "")


def _first_sentences(text: str, n: int = 260) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= n:
        return text
    out = ""
    for s in re.split(r"(?<=[.!?])\s+", text):
        if len(out) + len(s) > n and out:
            break
        out = (out + " " + s).strip()
    return out if len(out) <= n + 60 else out[:n].rsplit(" ", 1)[0] + "…"


def _owner_repo(repo_url: str) -> tuple[str, str]:
    m = re.search(r"github\.com[/:]([^/]+)/([^/#?]+?)(?:\.git)?/?$", repo_url or "")
    return (m.group(1), m.group(2)) if m else ("OWNER", "REPO")


def _sanitize_text(s: str, where: str) -> str:
    if SECRET_RX.search(s):
        log.warning("repo: token-like string redacted in %s", where)
        s = SECRET_RX.sub("***", s)
    return s


def _strip_notebook(raw: bytes | str) -> str:
    """Notebook JSON without outputs, execution counts or metadata that could hold secrets/identity."""
    nb = json.loads(raw)
    md = nb.get("metadata", {}) or {}
    keep = {k: md[k] for k in ("kernelspec", "language_info", "title", "authors") if k in md}
    if isinstance(md.get("colab"), dict) and "toc_visible" in md["colab"]:
        keep["colab"] = {"toc_visible": md["colab"]["toc_visible"]}
    nb["metadata"] = keep
    for c in nb.get("cells", []):
        cm = c.get("metadata", {}) or {}
        c["metadata"] = {k: cm[k] for k in ("id", "tags", "collapsed", "cellView") if k in cm}
        if c.get("cell_type") == "code":
            c["outputs"], c["execution_count"] = [], None
        c.pop("attachments", None) if c.get("cell_type") == "code" else None
        src = c.get("source", "")
        joined = "".join(src) if isinstance(src, list) else src
        if SECRET_RX.search(joined):
            log.warning("repo: token-like string redacted in a notebook cell")
            c["source"] = SECRET_RX.sub("***", joined)
    return json.dumps(nb, ensure_ascii=False, indent=1) + "\n"


def notebook_from_colab(dst) -> Path | None:
    """In Colab, save the currently open notebook (outputs stripped) to `dst`; None elsewhere or on failure."""
    try:
        from google.colab import _message  # type: ignore
    except Exception:  # noqa: BLE001
        return None
    try:
        nb = _message.blocking_request("get_ipynb", timeout_sec=30)["ipynb"]
        dst = Path(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(_strip_notebook(json.dumps(nb)), encoding="utf-8")
        return dst
    except Exception as e:  # noqa: BLE001
        log.warning("repo: could not fetch the Colab notebook (%s)", type(e).__name__)
        return None


# --------------------------------------------------------------------------------------
# Per-language context
# --------------------------------------------------------------------------------------
class _Lang:
    def __init__(self, lang: str, data_dir: Path | None, site_url: str, iso3: str, assets: str):
        self.lang, self.dir, self.assets = lang, data_dir, assets
        self.flag = None
        d = data_dir
        self.summary = (_read_json(d / "summary.json") if d else None) or {}
        self.meta = (_read_json(d / "meta.json") if d else None) or {}
        self.ctx = (_read_json(d / "agent_context.json") if d else None) or {}
        self.quality = _read_json(d / "quality.json") if d else None
        self.media = ((_read_json(d / "media" / "media.json") if d else None) or self.meta.get("media") or {})
        sub = ""
        if d is not None and d.parent.name == "data" and d.parent.parent.name == lang:
            sub = f"{lang}/"
        base = site_url.rstrip("/") + "/"
        self.site = f"{base}{sub}?country={iso3}" if site_url else ""
        self.site_root = f"{base}{sub}" if site_url else ""

    def page(self, p: str) -> str:
        return f"{self.site}#{p}" if self.site else "#"

    def finding(self, uc: int) -> str:
        for m in self.summary.get("messages", []):
            if THEME_UC.get(m.get("theme")) == uc:
                return _first_sentences(m.get("text"))
        for f in self.ctx.get("facts", []):
            if f.get("uc") == uc and not str(f.get("title", "")).startswith(("Method", "Méthode")):
                return _first_sentences(re.sub(r"\s*\(confi[a-z]+ [^)]*\)\s*$", "", f.get("text", "")))
        return ""

    def facts(self, uc: int, n: int = 6) -> list[dict]:
        return [f for f in self.ctx.get("facts", []) if f.get("uc") == uc
                and not str(f.get("title", "")).startswith(("Method", "Méthode"))][:n]

    def method(self, uc: int) -> str:
        for f in self.ctx.get("facts", []):
            if f.get("uc") == (9 if uc == 0 else uc) and str(f.get("title", "")).startswith(("Method", "Méthode")):
                return re.sub(r"^[^:]+:\s*", "", f.get("text", ""), count=1) if uc == 0 else \
                    re.sub(r"^(Dynamics|Regions|GDP|Shocks|Inequality|Industry|Tourism|Dynamiques|Régions|PIB|Chocs|"
                           r"Inégalités|Industrie|Tourisme)\s*:\s*", "", f.get("text", ""))
        return ""

    def quc(self, uc: int) -> dict:
        for u in (self.quality or {}).get("use_cases", []) or []:
            if int(u.get("uc", -1)) == uc:
                return u
        return {}

    def asset(self, key: str) -> str | None:
        e = self.media.get(key)
        return f"{self.assets}/{Path(e['file']).name}" if e else None


# --------------------------------------------------------------------------------------
# README
# --------------------------------------------------------------------------------------
def _readme(L: _Lang, cfg, country: str, site_url: str, repo_url: str, colab: str, nb_name: str,
            synthetic: bool, tree: str, today: str) -> str:
    t, lang = TX[L.lang], L.lang
    y0, y1 = (L.meta.get("period") or [cfg.start_year, cfg.end_year])[:2]
    a = L.asset
    out = []
    w = out.append
    w(f'<p align="right">{t["lang_switch"]}</p>\n')
    if a("banner"):
        w(f'<p align="center"><a href="{L.site_root or site_url}"><img src="{a("banner")}" '
          f'alt="{t["title"]} — {country}" width="100%"></a></p>\n')
    if getattr(L, "flag", None):
        w(f'<p align="center"><img src="{L.flag}" alt="{"Drapeau" if lang == "fr" else "Flag"} — {country}" height="54">'
          f'<br><b>{country}</b> · {y0}–{y1}</p>\n')
    w(f'<p align="center">{t["pitch"].format(country=country)}</p>\n')
    bl = {"en": ("dashboard", "live", "license", "languages", "data", "AI agent", "updated"),
          "fr": ("tableau de bord", "en ligne", "licence", "langues", "données", "agent IA", "mis à jour")}[lang]
    badges = [
        (L.site_root or site_url, _badge(bl[0], bl[1], "00704A", "githubpages"), t["cta"]),
        (colab, "https://colab.research.google.com/assets/colab-badge.svg", "Open in Colab"),
        ("LICENSE", _badge(bl[2], "MIT", "3F7FC7"), "MIT"),
        ("README.fr.md" if lang == "en" else "README.md", _badge(bl[3], "FR | EN", "F5C242"), "FR | EN"),
        ("docs/methodology.md" if lang == "en" else "docs/methodology.fr.md",
         _badge(bl[4], "VIIRS · Black Marble", "0B121B", "nasa"), "VIIRS"),
        (L.page("assistant"), _badge(bl[5], "Groq | Gemini | Ollama", "6E40C9"), t["ai_card"]),
        ("CHANGELOG.md", _badge(bl[6], today, "555"), bl[6]),
    ]
    w('<p align="center">\n' + "\n".join(f'  <a href="{h}"><img src="{s}" alt="{al}"></a>' for h, s, al in badges)
      + "\n</p>\n")
    w(f'<p align="center"><a href="{L.site_root or site_url}"><img src="'
      f'{_badge(t["cta"].upper(), "▶", "00704A", "googlechrome", "for-the-badge")}" alt="{t["cta"]}" height="42"></a>'
      f'&nbsp;&nbsp;<a href="{colab}"><img src="{_badge(t["colab"].upper(), "▶", "3F7FC7", "googlecolab", "for-the-badge")}"'
      f' alt="{t["colab"]}" height="42"></a></p>\n')
    w(f'<p align="center"><a href="{L.site_root or site_url}"><b>{L.site_root or site_url}</b></a></p>\n')
    if synthetic:
        w("> [!WARNING]\n> " + t["synthetic"].format(country=country) + "\n")
    # timelapse + before/after
    tl, ba = a("timelapse"), a("before_after")
    if tl or ba:
        w(f"\n## 🌍 " + t["tl_title"].format(years=int(y1) - int(y0) + 1, sec=country) + "\n")
        cells = []
        for k, im in (("timelapse", tl), ("before_after", ba)):
            if im:
                cap = (L.media.get(k) or {}).get("caption", "")
                cells.append(f'<td width="50%" align="center"><img src="{im}" alt="{cap}" width="100%"><br>'
                             f'<sub>{cap}</sub></td>')
        w("<table>\n<tr>\n" + "\n".join(cells) + "\n</tr>\n</table>\n")
    # KPIs
    kpis = L.summary.get("kpis") or []
    if kpis:
        w(f"\n## ✨ {t['glance']}\n\n<sub>{t['glance_sub'].format(a=y0, b=y1)}</sub>\n")
        rows = [kpis[i:i + 4] for i in range(0, len(kpis), 4)]
        html = ["<table>"]
        for r in rows:
            html.append("<tr>")
            for k in r:
                html.append(f'<td align="center" width="25%"><h3>{_fmt_kpi(k, lang)}</h3>'
                            f'<b>{k.get("label", "")}</b><br><sub>{k.get("sub", "")}</sub></td>')
            html.append("</tr>")
        html.append("</table>")
        w("\n".join(html) + "\n")
    sh = a("shock")
    if sh:
        cap = (L.media.get("shock") or {}).get("caption", "")
        w(f"\n## ⚡ {t['shock']}\n\n<p align=\"center\"><img src=\"{sh}\" alt=\"{cap}\" width=\"100%\"><br>"
          f"<sub>{cap}</sub></p>\n")
    # use cases
    w(f"\n## 🧭 {t['ucs']}\n\n<sub>{t['ucs_sub']}</sub>\n")
    cards = []
    for uc in range(1, 9):
        q = L.quc(uc)
        title = q.get("title") or t["t"][uc]
        question = q.get("question") or t["q"][uc]
        img = a(f"uc{uc}")
        link = L.page(q.get("page") or UC_PAGE[uc])
        fnd = L.finding(uc)
        c = [f'<td width="50%" valign="top">']
        if img:
            c.append(f'<a href="{link}"><img src="{img}" alt="{t["uc"]} {uc} — {title}" width="100%"></a>')
        c.append(f'<h3>{UC_ICON[uc]} {uc} · {title}</h3>')
        c.append(f'<p><b>{t["question"]}</b> — <i>{question}</i></p>')
        if fnd:
            c.append(f'<p><b>{t["finding"]}</b> — {fnd}</p>')
        c.append(f'<p><a href="{link}">{t["open"]}</a></p></td>')
        cards.append("\n".join(c))
    ai = (f'<td width="50%" valign="top">'
          + (f'<a href="{L.page("assistant")}"><img src="{a("screen_assistant")}" alt="{t["ai_card"]}" width="100%"></a>'
             if a("screen_assistant") else "")
          + f'<h3>🤖 {t["ai_card"]}</h3><p><i>{t["ai_card_q"]}</i></p>'
          f'<p><a href="{L.page("assistant")}">{t["open"]}</a></p></td>')
    cards.append(ai)
    rows = ["<tr>\n" + "\n".join(cards[i:i + 2]) + "\n</tr>" for i in range(0, len(cards), 2)]
    w("<table>\n" + "\n".join(rows) + "\n</table>\n")
    # dashboard tour
    tour = a("dashboard_tour")
    shots = [(k, v) for k, v in L.media.items() if k.startswith("screen_") and k != "screen_mobile"]
    if tour or shots:
        w(f"\n## 📊 {t['tour']}\n\n<sub>{t['tour_sub']}</sub>\n")
        mob = a("screen_mobile")
        if tour:
            if mob:
                w(f'<table><tr><td width="76%"><a href="{L.site_root or site_url}"><img src="{tour}" '
                  f'alt="{t["tour"]}" width="100%"></a></td><td width="24%"><img src="{mob}" '
                  f'alt="mobile" width="100%"></td></tr></table>\n')
            else:
                w(f'<p align="center"><a href="{L.site_root or site_url}"><img src="{tour}" alt="{t["tour"]}" '
                  f'width="100%"></a></p>\n')
        if shots:
            cells = [f'<td width="33%" align="center"><a href="{L.page(v.get("page", k[7:]))}"><img src="{a(k)}" '
                     f'alt="{k[7:]}" width="100%"></a><br><sub><code>#{v.get("page", k[7:])}</code></sub></td>'
                     for k, v in shots]
            rows = ["<tr>" + "".join(cells[i:i + 3]) + "</tr>" for i in range(0, len(cells), 3)]
            w(f"\n<details>\n<summary><b>{t['screens']}</b> ({len(shots)})</summary>\n<br>\n\n<table>\n"
              + "\n".join(rows) + "\n</table>\n</details>\n")
    # agent
    w(f"\n## 🤖 {t['agent']}\n\n" + "\n".join(f"- {x}" for x in t["agent_txt"]) + "\n")
    # architecture
    w(f"\n## 🛠️ {t['arch']}\n\n" + _mermaid(lang) + "\n")
    # quick start
    w(f"\n## 🚀 {t['quick']}\n\n" + "\n".join(f"{i}. " + s.format(nb=nb_name, colab=colab)
                                            for i, s in enumerate(t["quick_steps"], 1))
      + f"\n\n> [!TIP]\n> {t['secrets']}\n")
    # sources
    cols = t["src_cols"]
    w(f"\n## 🛰️ {t['sources']}\n\n| {' | '.join(cols)} |\n|" + "---|" * len(cols) + "\n"
      + "\n".join(f"| **{n}** | {p} | {u[lang]} | {r} |" for n, p, u, r in SOURCES) + "\n")
    # methodology & quality
    w(f"\n## 📐 {t['method']}\n\n{t['method_txt']}\n\n" + "\n".join(f"- {x}" for x in t["std"]) + "\n")
    if L.quality and L.quality.get("use_cases"):
        qc = t["q_cols"]
        lines = [f"| {' | '.join(qc)} |", "|" + "---|" * len(qc)]
        for u in L.quality["use_cases"]:
            st = str(u.get("status", ""))
            stl = t["official"] if st.startswith("official") else t["experimental"] if st == "experimental" else st
            v = u.get("validation") or {}
            val = f"{v.get('metric', '')} = {v.get('value', '')}" if v.get("metric") else (v.get("text") or "")
            lines.append(f"| {UC_ICON.get(int(u.get('uc', 0)), '')} {u.get('uc')} · "
                         f"{u.get('title') or t['t'].get(int(u.get('uc', 0)), '')} | "
                         f"`{stl}` | {u.get('confidence', '')} | {val} |")
        w("\n" + "\n".join(lines) + "\n")
    # structure
    w(f"\n## 🗂️ {t['struct']}\n\n```text\n{tree}\n```\n")
    w(f"\n## 🔐 {t['security']}\n\n" + "\n".join(f"- {x}" for x in t["security_txt"]) + "\n")
    owner, rn = _owner_repo(repo_url)
    w(f"\n## 📝 {t['cite']}\n\n{t['cite_txt']}\n\n```bibtex\n@software{{ntl_{cfg.iso3.lower()}_{today[:4]},\n"
      f"  author  = {{{{African Development Bank}} and {{Data Innovation for Africa (DI4A)}}}},\n"
      f"  title   = {{{TX['en']['title']} — {country} — statistics & public policy, public dashboard and AI agent}},\n"
      f"  year    = {{{today[:4]}}},\n  version = {{{VERSION}}},\n  url     = {{{repo_url}}}\n}}\n```\n")
    w(f"\n## ⚖️ {t['license']}\n\n{t['license_txt']}\n")
    w(f"\n## 🙏 {t['ack']}\n\n{t['ack_txt']}\n")
    w(f'\n---\n<p align="center"><sub>{t["footer"].format(date=today, v=VERSION)} · '
      f'<a href="{repo_url}">{owner}/{rn}</a></sub></p>\n')
    return "\n".join(out)


def _mermaid(lang: str) -> str:
    fr = lang == "fr"
    n = {
        "A": "🛰️ Satellites<br/>VIIRS · Black Marble<br/>Sentinel-5P · MODIS" if fr else
        "🛰️ Satellites<br/>VIIRS · Black Marble<br/>Sentinel-5P · MODIS",
        "A2": "📚 Données ouvertes<br/>GHSL · WorldPop<br/>OSM · Banque mondiale" if fr else
        "📚 Open data<br/>GHSL · WorldPop<br/>OSM · World Bank",
        "B": "🌍 Earth Engine<br/>zonal stats" if fr else "🌍 Earth Engine<br/>zonal stats",
        "C": "📓 Notebook<br/>nettoyage · STL<br/>économétrie" if fr else "📓 Notebook<br/>cleaning · STL<br/>econometrics",
        "D": "🧭 8 cas<br/>d'usage" if fr else "🧭 8 use<br/>cases",
        "E": "📦 Exports<br/>JSON · CSV<br/>GeoJSON · PNG",
        "F": "📊 Tableau<br/>de bord FR/EN" if fr else "📊 Dashboard<br/>FR/EN",
        "G": "🤖 Agent IA<br/>faits cités" if fr else "🤖 AI agent<br/>cited facts",
        "H": "🚀 GitHub<br/>Pages",
    }
    return ("```mermaid\nflowchart LR\n"
            + "\n".join(f'  {k}["{v}"]' for k, v in n.items())
            + "\n  A --> B\n  A2 --> B\n  B --> C --> D --> E\n  E --> F --> H\n  E --> G --> H\n"
            "  classDef green fill:#00704A,stroke:#00553A,color:#fff\n"
            "  classDef gold fill:#F5C242,stroke:#b8901f,color:#05080d\n"
            "  classDef blue fill:#3F7FC7,stroke:#2b5f99,color:#fff\n"
            "  class A,A2,B blue\n  class C,D,E green\n  class F,G,H gold\n```")


# --------------------------------------------------------------------------------------
# Docs
# --------------------------------------------------------------------------------------
def _table(rows: list[dict], cols: list[str] | None = None) -> str:
    if not rows:
        return ""
    cols = cols or list(dict.fromkeys(k for r in rows for k in r))

    def cell(v):
        if isinstance(v, (list, tuple)):
            v = ", ".join(map(str, v))
        elif isinstance(v, dict):
            v = "; ".join(f"{k}: {x}" for k, x in v.items())
        return str("" if v is None else v).replace("|", "\\|").replace("\n", " ")
    head = "| " + " | ".join(c.replace("_", " ").capitalize() for c in cols) + " |"
    return "\n".join([head, "|" + "---|" * len(cols)] + ["| " + " | ".join(cell(r.get(c)) for c in cols) + " |"
                                                         for r in rows])


def _methodology(L: _Lang, country: str, synthetic: bool, today: str) -> str:
    lang, t, lb = L.lang, TX[L.lang], DOC_LABEL[L.lang]
    y0, y1 = (L.meta.get("period") or ["?", "?"])[:2]
    other = "methodology.md" if lang == "fr" else "methodology.fr.md"
    out = [f'<p align="right"><a href="{other}">{"English" if lang == "fr" else "Français"}</a></p>\n',
           f"# {lb['method_title']} — {country} ({y0}–{y1})\n"]
    if synthetic:
        out.append("> [!WARNING]\n> " + t["synthetic"].format(country=country) + "\n")
    m0 = L.method(0)
    if m0:
        out.append(f"## {lb['data_proc']}\n\n{m0}\n")
    for uc in range(1, 9):
        q, s = L.quc(uc), UC_DOC[lang][uc]
        out.append(f"## {UC_ICON[uc]} {t['uc']} {uc} — {q.get('title') or t['t'][uc]}\n")
        v = q.get("validation") or {}
        val = v.get("text") or s["validation"]
        if v.get("metric"):
            val += f" (**{v['metric']} = {v.get('value')}**)"
        rows = [(lb["question"], q.get("question") or t["q"][uc]),
                (lb["data"], ", ".join(q["sources"]) if q.get("sources") else s["data"]),
                (lb["method"], q.get("method") or L.method(uc)),
                (lb["validation"], val),
                (lb["uncertainty"], q.get("uncertainty") or s["uncertainty"]),
                (lb["limits"], q.get("limits") or s["limits"])]
        if q.get("status"):
            rows.append((lb["status"], f"`{q['status']}`" + (f" · {lb['confidence']}: {q['confidence']}"
                                                              if q.get("confidence") else "")))
        rows.append((lb["refs"], s["refs"]))
        if L.site:
            rows.append((lb["page"], f"[`#{q.get('page') or UC_PAGE[uc]}`]({L.page(q.get('page') or UC_PAGE[uc])})"))
        out.append("\n".join(f"- **{k}** — {v}" for k, v in rows if v) + "\n")
        fs = L.facts(uc, 4)
        if fs:
            out.append(f"**{lb['results']}**\n\n" + "\n".join(f"- `{f['id']}` {f['text']}" for f in fs) + "\n")
    lim = L.summary.get("limits") or []
    if lim:
        out.append(f"## {lb['general']}\n\n" + "\n".join(f"- **{x.get('title')}** — {x.get('text')}" for x in lim) + "\n")
    out.append(f"\n---\n<sub>{t['footer'].format(date=today, v=VERSION)}</sub>\n")
    return "\n".join(out)


def _quality(L: _Lang, country: str, synthetic: bool, today: str) -> str:
    lang, t, lb = L.lang, TX[L.lang], DOC_LABEL[L.lang]
    other = "QUALITY.md" if lang == "fr" else "QUALITY.fr.md"
    out = [f'<p align="right"><a href="{other}">{"English" if lang == "fr" else "Français"}</a></p>\n',
           f"# {lb['quality_title']} — {country}\n"]
    if synthetic:
        out.append("> [!WARNING]\n> " + t["synthetic"].format(country=country) + "\n")
    Q = L.quality
    if not Q:
        out.append(("*`quality.json` n'a pas été produit par cette exécution ; résumé des normes appliquées :*\n"
                    if lang == "fr" else "*`quality.json` was not produced by this run; summary of the standards applied:*\n"))
        out.append("\n".join(f"- {x}" for x in t["std"]) + "\n")
        return "\n".join(out)
    meta = [(k, Q.get(k)) for k in ("version", "generated", "country", "period") if Q.get(k) is not None]
    out.append("\n".join(f"- **{k}** — {', '.join(map(str, v)) if isinstance(v, list) else v}" for k, v in meta) + "\n")
    H = {"en": {"use_cases": "Use cases", "dqaf": "DQAF", "gsbpm": "GSBPM", "fair": "FAIR principles",
                "experimental": "Experimental statistics"},
         "fr": {"use_cases": "Cas d'usage", "dqaf": "DQAF", "gsbpm": "GSBPM", "fair": "Principes FAIR",
                "experimental": "Statistiques expérimentales"}}[lang]
    ucs = Q.get("use_cases") or []
    if ucs:
        rows = []
        for u in ucs:
            v = u.get("validation") or {}
            rows.append({"uc": u.get("uc"), "title": u.get("title") or t["t"].get(int(u.get("uc", 0)), ""), "status": f"`{u.get('status', '')}`",
                         "confidence": u.get("confidence"),
                         "validation": (f"{v.get('metric')} = {v.get('value')}" if v.get("metric") else "")
                         + (f" — {v.get('text')}" if v.get("text") else ""),
                         "sources": u.get("sources")})
        out.append(f"## {H['use_cases']}\n\n" + _table(rows) + "\n")
    for key in ("dqaf", "gsbpm", "fair"):
        if Q.get(key):
            out.append(f"## {H[key]}\n\n" + _table(Q[key]) + "\n")
    if Q.get("experimental"):
        out.append(f"## {H['experimental']}\n\n" + "\n".join(f"- {x}" for x in Q["experimental"]) + "\n")
    extra = [k for k in Q if k not in ("version", "generated", "country", "period", "use_cases", "dqaf", "gsbpm",
                                       "fair", "experimental")]
    for k in extra:   # forward-compatible: render unknown sections generically
        v = Q[k]
        if isinstance(v, list) and v and isinstance(v[0], dict):
            out.append(f"## {k}\n\n" + _table(v) + "\n")
        elif isinstance(v, list):
            out.append(f"## {k}\n\n" + "\n".join(f"- {x}" for x in v) + "\n")
    out.append(f"\n---\n<sub>{t['footer'].format(date=today, v=VERSION)}</sub>\n")
    return "\n".join(out)


# --------------------------------------------------------------------------------------
# Static files
# --------------------------------------------------------------------------------------
def _citation(country: str, iso3: str, site_url: str, repo_url: str, today: str) -> str:
    q = json.dumps
    kw = ["night-time lights", "VIIRS", "remote sensing", "economic statistics", "nowcasting", "Google Earth Engine",
          "big data", "official statistics", "Africa", iso3]
    lines = [
        "cff-version: 1.2.0",
        f"message: {q('If you use this software or its results, please cite it as below.')}",
        "type: software",
        f"title: {q(TX['en']['title'] + ' — ' + country + ' — statistics & public policy, public dashboard and AI agent')}",
        "authors:",
        f"  - name: {q('African Development Bank')}",
        f"  - name: {q('Data Innovation for Africa (DI4A)')}",
        f"version: {q(VERSION)}",
        f"date-released: {today}",
    ]
    if site_url:
        lines.append(f"url: {q(site_url)}")
    if repo_url:
        lines.append(f"repository-code: {q(repo_url)}")
    lines += ["license: MIT",
              f"abstract: {q('Reproducible pipeline using night-time lights (VIIRS, Black Marble, DMSP) for eight statistical and public-policy use cases, a bilingual public dashboard and a grounded AI agent.')}",
              "keywords:"] + [f"  - {q(k)}" for k in kw]
    return "\n".join(lines) + "\n"


MIT = """MIT License

Copyright (c) {year} African Development Bank and Data Innovation for Africa (DI4A)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---
Data notice: this licence covers the code only. Data, maps and images derived from
third-party datasets (VIIRS/EOG, NASA Black Marble, GHSL, WorldPop, Copernicus
Sentinel-5P, MODIS, OpenStreetMap, World Bank, geoBoundaries/FAO GAUL) remain subject
to the licence and attribution terms of each source.
Results, maps, charts and images produced by this project may be reused only with
the source stated as: "Source: AfDB-DI4A" (African Development Bank - Data Innovation for Africa).
"""

CHANGELOG = """# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [{v}] - {date}
### Added
- Showcase repository on `main`: bilingual README (EN/FR), methodology and quality documentation, citation file.
- Images and animations generated from the country's own data: night-lights timelapse, before/after wipe,
  shock animation, social preview, banner and one vignette per use case.
- Animated tour and screenshots of the dashboard (optional, Playwright).
- One-call publication now also pushes `main` and sets the repository description, homepage and topics.

### Changed
- Use cases 6 (industrial zones), 7 (summer tourism) and 8 (urbanisation signals) are part of the README, dashboard and AI agent.

### Security
- Notebooks are stripped of outputs and metadata; token-like strings are redacted before any push.

## [2.0.0]
### Added
- Seven use cases, bilingual dashboard on GitHub Pages and AI assistant (Groq, Gemini, Ollama).
"""

CONTRIBUTING = """# Contributing

Thank you for helping improve this project! Contributions in **English or French** are welcome.

## Ways to contribute
- **Report a bug** or a wrong figure: open an issue with the *Bug report* template (country, period, notebook
  section, what you expected, what you got).
- **Suggest a use case or a data source**: use the *Feature request* template.
- **Improve the code or docs**: open a pull request.

## Development workflow
1. Fork the repository and create a branch: `git checkout -b feature/my-change`.
2. Work in the notebook (`notebooks/`) or in the analysis packages (`src/`, `src_en/`). Language-neutral
   modules keep their user-facing strings in `{"fr": ..., "en": ...}` dictionaries: please update both.
3. Run the notebook end to end with `SYNTHETIC_TEST = True` (no Earth Engine needed) and check the dashboard
   locally: `python -m http.server -d dashboard 8000`.
4. Never commit outputs, caches, `.env` files, tokens or API keys. Clear notebook outputs before committing.
5. Open a pull request describing the change and how you tested it.

## Statistical standards
Changes to methods must document their assumptions, uncertainty and limits (see `docs/methodology.md`) and
keep the *experimental statistics* labelling of estimates derived from night-time lights.

## Code of conduct
Be respectful and constructive. Harassment or discrimination of any kind is not tolerated.
"""

BUG = """---
name: Bug report
about: Something does not work or a figure looks wrong
title: "[Bug] "
labels: bug
---

**Country (ISO3) and period**

**Notebook section / dashboard page**

**What happened** (error message, screenshot — never paste tokens or API keys)

**What you expected**

**Environment** (Colab / Kaggle / local, browser for the dashboard)
"""

FEATURE = """---
name: Feature request
about: Suggest a use case, a data source or an improvement
title: "[Feature] "
labels: enhancement
---

**Policy question or need**

**Proposed data / method**

**How would we validate it?**

**Additional context**
"""

PR = """## What does this change?

## How was it tested?
- [ ] Notebook run end to end with `SYNTHETIC_TEST = True`
- [ ] Dashboard checked locally (FR and EN)
- [ ] Both language strings updated (`{"fr": ..., "en": ...}`)

## Checklist
- [ ] No outputs, caches, `.env`, tokens or API keys committed
- [ ] Methodology / limits documented when a method changes
"""

GITIGNORE = """# outputs and caches (regenerated by the notebook)
outputs/
dashboard/data/
*.sqlite
*.sqlite3
*.db
.cache/

# secrets
.env
.env.*
*.pem

# Python / Jupyter
__pycache__/
*.py[cod]
.ipynb_checkpoints/
.pytest_cache/
.venv/
venv/

# OS / editors
.DS_Store
Thumbs.db
.vscode/
.idea/
"""


def _tree(root: Path, lang: str) -> str:
    desc = {
        "en": {"README.md": "this page (English)", "README.fr.md": "French version", "assets": "images & animations generated from the data",
               "docs": "methodology and quality report (EN/FR)", "notebooks": "the Colab notebook(s)",
               "src": "analysis package", "src_en": "analysis package (English messages)",
               "src_fr": "analysis package (French messages)", "dashboard": "→ the live site is on the gh-pages branch",
               ".github": "issue and pull-request templates", "CITATION.cff": "how to cite",
               "CHANGELOG.md": "release notes", "CONTRIBUTING.md": "how to contribute", "LICENSE": "MIT (code)"},
        "fr": {"README.md": "version anglaise", "README.fr.md": "cette page (français)", "assets": "images et animations générées à partir des données",
               "docs": "méthodologie et rapport qualité (EN/FR)", "notebooks": "le(s) notebook(s) Colab",
               "src": "package d'analyse", "src_en": "package d'analyse (messages en anglais)",
               "src_fr": "package d'analyse (messages en français)", "dashboard": "→ le site est sur la branche gh-pages",
               ".github": "modèles d'issues et de pull requests", "CITATION.cff": "citer ce travail",
               "CHANGELOG.md": "notes de version", "CONTRIBUTING.md": "contribuer", "LICENSE": "MIT (code)"},
    }[lang]
    names = sorted((p for p in root.iterdir() if p.name != ".gitignore"),
                   key=lambda p: (not p.is_dir(), p.name.lower().lstrip(".")))
    lines = ["."]
    width = max(len(p.name) + (1 if p.is_dir() else 0) for p in names) + 2
    for i, p in enumerate(names):
        br = "└── " if i == len(names) - 1 else "├── "
        nm = p.name + ("/" if p.is_dir() else "")
        d = desc.get(p.name, "")
        lines.append(f"{br}{nm:<{width}}{('# ' + d) if d else ''}".rstrip())
    return "\n".join(lines)


# --------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------
def _copy_pkg(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".ipynb_checkpoints", ".env"))
    for p in dst.rglob("*.py"):
        s = p.read_text(encoding="utf-8")
        s2 = _sanitize_text(s, p.name)
        if s2 != s:
            p.write_text(s2, encoding="utf-8")


def check_links(md_path: Path) -> list[str]:
    """Local image/link targets of a Markdown file that do not exist in the tree."""
    txt = Path(md_path).read_text(encoding="utf-8")
    refs = re.findall(r'(?:src|href)="([^"]+)"', txt) + re.findall(r"\]\(([^)\s]+)\)", txt)
    missing = []
    for r in refs:
        if re.match(r"^(https?:|mailto:|#)", r) or not r:
            continue
        if not (Path(md_path).parent / r.split("#")[0]).exists():
            missing.append(r)
    return missing


def build_repo(cfg, root, out_repo_dir, site_url, repo_url, data_dirs: dict, notebook_path=None, media=None,
               synthetic=False) -> Path:
    """Write the showcase repository tree (for the `main` branch) in a fresh `out_repo_dir`.

    data_dirs : {"fr": <FR country data dir>, "en": <EN country data dir>} — one may be missing.
    notebook_path : a notebook file, or a list / {"fr": .., "en": ..} of them (outputs and metadata stripped).
    media : optional manifest (dict) used when a data dir has no media/media.json.
    Returns the repository directory.
    """
    root = Path(root)
    out = Path(out_repo_dir).resolve()
    if out == root.resolve() or out in root.resolve().parents or out == Path(out.anchor):
        raise ValueError(f"refusing to overwrite {out}")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    today = _dt.date.today().isoformat()
    iso3 = cfg.iso3.upper()
    dirs = {k: Path(v) for k, v in (data_dirs or {}).items() if v and Path(v).exists()}
    if not dirs:
        raise ValueError("build_repo: no existing data directory in data_dirs")
    langs = [l for l in ("en", "fr") if l in dirs]
    primary = langs[0]
    # ---- assets: primary language in assets/, the other in assets/<lang>/ ----------------------
    Ls: dict[str, _Lang] = {}
    for lang in ("en", "fr"):
        d = dirs.get(lang)
        own = d is not None
        sub = "assets" if (lang == primary or not own) else f"assets/{lang}"
        L = _Lang(lang, d if own else dirs[primary], site_url, iso3, sub)
        if not own:     # texts of the missing language fall back on the available data (figures identical)
            L.lang = lang
        if not L.media and media:
            L.media = media
        Ls[lang] = L
    copied: set[tuple[str, str]] = set()
    for lang, L in Ls.items():
        src_dir = (dirs.get(lang) or dirs[primary]) / "media"
        if not src_dir.exists() and media:
            continue
        keep = {}
        for k, e in L.media.items():
            if k in ("timelapse_webp",) or not isinstance(e, dict) or "file" not in e:
                continue
            f = src_dir / Path(e["file"]).name
            if not f.exists():
                continue
            dst = out / L.assets / f.name
            if (L.assets, f.name) not in copied:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst)
                copied.add((L.assets, f.name))
            keep[k] = e
        L.media = keep
    # ---- country flag (assets/flag.png, from the data dir or the cache) ------------------------
    for cand in [dirs[l] / "flag.png" for l in langs] + [Path(getattr(cfg, "cache_dir", ".")) / "flag.png"]:
        if cand.exists():
            (out / "assets").mkdir(parents=True, exist_ok=True)
            shutil.copy2(cand, out / "assets" / "flag.png")
            break
    has_flag = (out / "assets" / "flag.png").exists()
    for L in Ls.values():
        L.flag = "assets/flag.png" if has_flag else None
    # ---- country name per language ----------------------------------------------------------
    c = getattr(cfg, "country", {}) or {}
    names = {"en": c.get("name") or iso3, "fr": c.get("name_fr") or c.get("name") or iso3}
    # ---- code and notebooks -----------------------------------------------------------------
    for pkg in ("src", "src_en", "src_fr"):
        if (root / pkg).is_dir():
            _copy_pkg(root / pkg, out / pkg)
    nbs: list[Path] = []
    if isinstance(notebook_path, dict):
        nbs = [Path(v) for v in notebook_path.values() if v]
    elif isinstance(notebook_path, (list, tuple)):
        nbs = [Path(v) for v in notebook_path if v]
    elif notebook_path:
        nbs = [Path(notebook_path)]
    (out / "notebooks").mkdir()
    for nb in nbs:
        if nb.exists():
            (out / "notebooks" / nb.name).write_text(_strip_notebook(nb.read_bytes()), encoding="utf-8")
    nb_names = sorted(p.name for p in (out / "notebooks").glob("*.ipynb"))
    if not nb_names:
        (out / "notebooks" / "README.md").write_text(
            "# Notebooks\n\nThe notebooks `NTL_8_use_cases_EN.ipynb` and `NTL_8_use_cases_FR.ipynb` are distributed "
            "with the project material. In Colab, `src.repo.notebook_from_colab()` saves the open notebook here "
            "(outputs stripped) before publication.\n\n*Les notebooks sont distribués avec le matériel du projet ; "
            "dans Colab, `src.repo.notebook_from_colab()` enregistre ici le notebook ouvert (sans sorties).*\n",
            encoding="utf-8")
    owner, rn = _owner_repo(repo_url)

    def nb_for(lang):
        tag = "_" + lang.upper()
        for n in nb_names:
            if tag in n.upper():
                return n
        return nb_names[0] if nb_names else f"NTL_8_use_cases_{lang.upper()}.ipynb"

    # ---- static files -----------------------------------------------------------------------
    (out / "dashboard").mkdir()
    (out / "dashboard" / "README.md").write_text(
        f"# Dashboard\n\nThe static dashboard is published from the **`gh-pages`** branch: **<{site_url}>**.\n\n"
        f"It is regenerated by the notebook (section 13) and published by `src.publish.publish_dashboard`; "
        f"it is not duplicated on `main`.\n\n*Le tableau de bord est publié depuis la branche `gh-pages` : "
        f"<{site_url}>.*\n", encoding="utf-8")
    (out / "LICENSE").write_text(MIT.format(year=today[:4]), encoding="utf-8")
    (out / "CHANGELOG.md").write_text(CHANGELOG.format(v=VERSION, date=today), encoding="utf-8")
    (out / "CONTRIBUTING.md").write_text(CONTRIBUTING, encoding="utf-8")
    (out / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    gh = out / ".github" / "ISSUE_TEMPLATE"
    gh.mkdir(parents=True)
    (gh / "bug_report.md").write_text(BUG, encoding="utf-8")
    (gh / "feature_request.md").write_text(FEATURE, encoding="utf-8")
    (out / ".github" / "PULL_REQUEST_TEMPLATE.md").write_text(PR, encoding="utf-8")
    (out / "CITATION.cff").write_text(_citation(names["en"], iso3, site_url, repo_url, today), encoding="utf-8")
    # ---- docs -------------------------------------------------------------------------------
    (out / "docs").mkdir()
    for lang, L in Ls.items():
        sfx = "" if lang == "en" else ".fr"
        (out / "docs" / f"methodology{sfx}.md").write_text(_methodology(L, names[lang], synthetic, today), encoding="utf-8")
        (out / "docs" / f"QUALITY{sfx}.md").write_text(_quality(L, names[lang], synthetic, today), encoding="utf-8")
    # ---- READMEs (last, so that the structure tree is complete) -----------------------------
    (out / "README.md").write_text("", encoding="utf-8")
    (out / "README.fr.md").write_text("", encoding="utf-8")
    for lang, L in Ls.items():
        nb = nb_for(lang)
        colab = f"https://colab.research.google.com/github/{owner}/{rn}/blob/main/notebooks/{nb}"
        txt = _readme(L, cfg, names[lang], site_url, repo_url, colab, nb, synthetic, _tree(out, lang), today)
        (out / ("README.md" if lang == "en" else "README.fr.md")).write_text(_sanitize_text(txt, "README"),
                                                                            encoding="utf-8")
    for md in ("README.md", "README.fr.md"):
        miss = check_links(out / md)
        if miss:
            log.warning("repo: %s has missing local links: %s", md, miss)
    log.info("repo: %d files written to %s", sum(1 for p in out.rglob("*") if p.is_file()), out)
    return out
