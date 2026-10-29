<p align="right"><a href="QUALITY.fr.md">Français</a></p>

# Quality report — Mauritius

- **version** — 2.1.0
- **generated** — 2026-10-29T12:21:45
- **country** — Mauritius
- **period** — 2014, 2025

## Use cases

| Uc | Title | Status | Confidence | Validation | Sources |
|---|---|---|---|---|---|
| 1 | Time dynamics | `experimental` | high | p-value = < 0.0001 — Trend significance (Mann–Kendall) and monthly/annual consistency | VIIRS VCMSLCFG (monthly), VIIRS VNL V2 (annual), Harmonised DMSP–VIIRS (Li et al., 2020) |
| 2 | Regional growth and convergence | `experimental` | medium | Spearman ρ = 0.66 — Rank correlation with tropospheric NO₂ (independent source) | VIIRS VNL V2, GHSL / WorldPop, Sentinel-5P NO₂ |
| 3 | Light–GDP relationship | `experimental` | medium | correlation / MAE (pp) = -0.16 / 4.0 — Out-of-sample tracking of official growth | VIIRS, Real GDP (World Bank, WDI) |
| 4 | Shocks and resilience | `experimental` | low | trough (main shock) = -1.7% — no — Does the trough exceed ordinary variability? | VIIRS (monthly), Black Marble VNP46A2 (daily), event catalogue |
| 5 | Inequality and electrification | `experimental` | medium | mean gap (pp) = -6.4 — Gap with the World Bank electricity-access rate | VIIRS VNL V2, GHSL / WorldPop, GHSL SMOD, electricity access (WDI) |
| 6 | Industrial zones | `experimental` | low | precision / recall / F1 = not available — Comparison with the reference list (n/a) | VIIRS VNL V2, GHSL BUILT-S, Sentinel-5P NO₂/SO₂, MODIS MOD11A2, OpenStreetMap |
| 7 | Seasonal tourism | `experimental` | low | r = not available — Correlation with hotel nights | VIIRS (monthly), hotel nights or WDI arrivals |
| 8 | Urbanisation signals | `experimental` | low | Spearman ρ = 0.39 — Rank correlation with GHSL built-up area growth (independent source) | VIIRS VNL V2, GHSL GHS-POP / WorldPop, GHSL GHS-BUILT-S R2023A, urban population (WDI) |

## DQAF

| Dimension | Practice | Evidence |
|---|---|---|
| 0. Prerequisites of quality | Institutional environment, resources, relevance | African Development Bank × Data Innovation for Africa (DI4A) project; free satellite data; explicit policy question for each use case. |
| 1. Assurances of integrity | Professionalism, transparency, ethical standards | Open code, documented methods, parameters and versions recorded in the manifest; no individual data; publication without manual intervention on figures. |
| 2. Methodological soundness | Concepts, scope, classification, basis for recording | Methods published in the literature (Henderson et al. 2012; Elvidge et al. 2021; Román et al. 2018); ISO 3166 codes; geoBoundaries; WGS 84. |
| 3. Accuracy and reliability | Source data, assessment, statistical techniques, validation, revisions | Quality control (cloud cover, gas flares, outliers); validation of every use case against an independent source; confidence intervals; published confidence level. |
| 4. Serviceability | Periodicity, timeliness, consistency, revision policy | Monthly series available a few weeks after the month; full recomputation at each run (time-stamped cache); monthly/annual consistency checked. |
| 5. Accessibility | Data, metadata, assistance to users | Public bilingual dashboard, open files (CSV, JSON, GeoJSON), metadata manifest, AI agent citing its sources, GitHub repository with citation. |

## GSBPM

| Phase | Notebook sections | What |
|---|---|---|
| 1. Specify needs | 1 | Policy questions of the eight use cases |
| 2. Design | 1–2 | Choice of sources, indicators and thresholds |
| 3. Build | 2 | ISO3-driven pipeline, embedded code, tests on a synthetic dataset |
| 4. Collect | 3 | Earth Engine, World Bank, OpenStreetMap — with caching |
| 5. Process | 3 | Clouds, gas flares, outliers, harmonisation, quality control |
| 6. Analyse | 4–12 | Eight use cases, validation, uncertainty, interpretation |
| 7. Disseminate | 15–18 | Dashboard, images, AI agent, GitHub repository |
| 8. Evaluate | 13–14 | Quality sheets, confidence levels, limitations, recommendations |

## FAIR principles

| Principle | How |
|---|---|
| Findable | Public GitHub repository with description, topics and CITATION.cff; metadata manifest; persistent identifier possible (Zenodo DOI). |
| Accessible | Public HTTPS without authentication; open formats; code and data under an explicit licence. |
| Interoperable | CSV, JSON, GeoJSON (WGS 84); ISO 3166 codes; stable unit identifiers; documented indicator vocabulary. |
| Reusable | Provenance (sources, versions, parameters), licences, methods and limitations published with the results. |

## Experimental statistics

- All series and maps derived from night-time lights
- Estimated regional GDP and growth estimate for the unpublished year
- Population “in the dark” (proxy of electricity access)
- Industrial clusters and tourist season index

## un_principles

| Principle | How |
|---|---|
| Relevance and impartiality | Indicators useful to decision-makers, released to everyone at the same time. |
| Professional standards | Published scientific methods, choices based on technical criteria. |
| Accountability and transparency | Sources, methods and procedures documented. |
| Prevention of misuse | Confidence levels, limitations and an “experimental” label on every output. |
| Cost-effectiveness | Free satellite data, reproducible pipeline. |
| Confidentiality | No individual data: territorial aggregates only. |
| International standards | DQAF, GSBPM, FAIR, ISO 3166. |
| Cooperation | Open code, reusable by every statistical office. |

## references

- United Nations (2014). Fundamental Principles of Official Statistics. A/RES/68/261.
- Data Quality Assessment Framework (DQAF, 2012) — generic framework.
- UNECE (2019). Generic Statistical Business Process Model, GSBPM v5.1.
- Wilkinson, M. D. et al. (2016). The FAIR Guiding Principles for scientific data management and stewardship. Scientific Data 3.
- Eurostat (2021). Experimental statistics — European Statistical System guidelines.


---
<sub>Generated by the notebook on 2026-10-29 · version 2.1.0</sub>
