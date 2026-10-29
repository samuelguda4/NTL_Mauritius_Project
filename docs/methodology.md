<p align="right"><a href="methodology.fr.md">Français</a></p>

# Methodology — Mauritius (2014–2025)

## Data and cleaning

VIIRS DNB monthly (VCMSLCFG) and annual VNL V2, harmonised DMSP–VIIRS, daily Black Marble, GHSL/WorldPop, Sentinel-5P NO₂/SO₂, MODIS LST, World Bank. Cleaning: pixels valid if cf_cvg ≥ 2, unit-month kept if ≥ 80% of pixels observed, spikes replaced, background and gas flares masked.

## 📈 Use case 1 — Time dynamics

- **Question** — Is activity accelerating or slowing down, net of seasonality?
- **Data** — VIIRS VCMSLCFG (monthly), VIIRS VNL V2 (annual), Harmonised DMSP–VIIRS (Li et al., 2020)
- **Method** — Robust STL (period 12) on log(sum of lights); Theil–Sen slope and Mann–Kendall test on annual composites; anomaly and break detection.
- **Validation** — Trend significance (Mann–Kendall) and monthly/annual consistency (**p-value = < 0.0001**)
- **Uncertainty** — 95% CI of annual growth: +4.7% to +7.9%
- **Limits** — Cloud cover and short summer nights; light is not value added.
- **Status** — `experimental` · Confidence: high
- **References** — Cleveland et al. (1990) STL; Sen (1968); Elvidge et al. (2017).
- **Dashboard page** — [`#time`](https://samuelguda4.github.io/NTL_Mauritius_Project/?country=MUS#time)

**Results of this run**

- `F02` Between 2014 and 2025, night-time light in Mauritius changed by +6.6% per year (95% CI: +4.7% to +7.9%). Over the last 12 months, the seasonally adjusted level is -6.6% relative to the previous 12 months. (confidence high: significant trend (p < 0.01; n = 12))
- `F74` Validation: Trend significance (Mann–Kendall) and monthly/annual consistency (p-value = < 0.0001). Uncertainty: 95% CI of annual growth: +4.7% to +7.9% Limitations: Cloud cover and short summer nights; light is not value added. Status: experimental statistic; confidence high.

## 🗺️ Use case 2 — Regional growth and convergence

- **Question** — Which regions take off, which fall behind?
- **Data** — VIIRS VNL V2, GHSL / WorldPop, Sentinel-5P NO₂
- **Method** — Robust growth per unit (Theil–Sen, Mann–Kendall), growth/stagnation/decline classes, β- and σ-convergence, Herfindahl index.
- **Validation** — Rank correlation with tropospheric NO₂ (independent source) (**Spearman ρ = 0.66**)
- **Uncertainty** — Class assigned only if |slope| ≥ threshold and p < α; CI of β (robust errors).
- **Limits** — Small units: noise and light blooming between neighbours.
- **Status** — `experimental` · Confidence: medium
- **References** — Barro & Sala-i-Martin (1992) convergence; Henderson, Storeygard & Weil (2012).
- **Dashboard page** — [`#regions`](https://samuelguda4.github.io/NTL_Mauritius_Project/?country=MUS#regions)

**Results of this run**

- `F03` Of 12 ADM2 units, 10 show significant growth, 1 are stagnating and 0 are declining. Light remains concentrated: Plaines Wilhems accounts for 22% of national light. (confidence medium: classification of 12 units, threshold ±1%/yr and p < 0.10)
- `F04` Across ADM2 units, light per capita shows neither statistically established convergence nor divergence. (confidence low: β = −0.006 [−0.027; 0.015], n = 10)
- `F24` Plaines Wilhems (ADM1, 2025): share of national light 22.0%, annual growth +4.7% (CI +3.2% to +6.1%, class Growth), light per capita 0.286, population 0.02 M, in the dark 0%, estimated GDP (experimental) 3.37 bn USD.
- `F25` Pamplemousses (ADM1, 2025): share of national light 15.0%, annual growth +9.1% (CI +7.3% to +10.1%, class Growth), light per capita 0.523, population 0.01 M, in the dark 8%, estimated GDP (experimental) 2.30 bn USD.

## 💹 Use case 3 — Light–GDP relationship

- **Question** — Can growth be estimated before its release, and regional GDP?
- **Data** — VIIRS, Real GDP (World Bank, WDI)
- **Method** — log(light) ~ log(GDP) in levels and growth, OLS with HAC errors; out-of-sample nowcast; regional GDP = national GDP allocated pro rata of light.
- **Validation** — Out-of-sample tracking of official growth (**correlation / MAE (pp) = -0.16 / 4.0**)
- **Uncertainty** — 95% CI of the elasticity: 1.24 to 3.18; 80% and 95% prediction intervals.
- **Limits** — Short annual sample; regional GDP is an experimental statistic to be checked against regional accounts.
- **Status** — `experimental` · Confidence: medium
- **References** — Henderson et al. (2012) AER; Chen & Nordhaus (2011) PNAS; Gibson et al. (2021) JDE.
- **Dashboard page** — [`#time`](https://samuelguda4.github.io/NTL_Mauritius_Project/?country=MUS#time)

**Results of this run**

- `F05` The elasticity of light with respect to real GDP is 2.21 in levels (95% CI: 1.24 to 3.18, R² = 0.63, 12 years) and 0.34 in growth rates (CI: 0.01 to 0.66). Out of sample, light growth tracks GDP growth with a correlation of −0.16 (mean absolute error: 4.0 percentage points of growth). (confidence medium: n = 12, significant but wide CI (1.94))
- `F49` Light–real GDP elasticity in levels: β = 2.21 (95% CI 1.24 to 3.18, R² = 0.63, n = 12, confidence medium: n = 12, significant but wide CI (1.94)). +1% GDP ↔ +β% light.
- `F50` Light–real GDP elasticity in growth rates: β = 0.34 (95% CI 0.01 to 0.66, R² = 0.08, n = 11, confidence medium: n = 11, significant but wide CI (0.66)). +1% GDP ↔ +β% light.
- `F51` Light–real GDP elasticity in long DMSP–VIIRS series: β = 1.14 (95% CI 0.66 to 1.62, R² = 0.69, n = 30, confidence high: n = 30, p < 0.01, narrow CI). +1% GDP ↔ +β% light.

## ⚡ Use case 4 — Shocks and resilience

- **Question** — How deep was a shock, and how fast the recovery?
- **Data** — VIIRS (monthly), Black Marble VNP46A2 (daily), event catalogue
- **Method** — Gap to the pre-shock level on the seasonally adjusted series; structural breaks; daily Black Marble index.
- **Validation** — Does the trough exceed ordinary variability? (**trough (main shock) = -1.7% — no**)
- **Uncertainty** — Pre-shock month-to-month variability (robust SD); unexplained breaks flagged.
- **Limits** — Shocks hitting poorly lit activities (agriculture, daytime services) are underestimated.
- **Status** — `experimental` · Confidence: low
- **References** — Román et al. (2018); Elvidge et al. (2020) COVID-19 lockdown lights.
- **Dashboard page** — [`#shocks`](https://samuelguda4.github.io/NTL_Mauritius_Project/?country=MUS#shocks)

**Results of this run**

- `F06` The most pronounced shock in the seasonally adjusted series is “COVID-19”: trough of -1.7% (04/2020), return to the pre-shock level after 3 months. (confidence low: trough compared with pre-shock month-to-month variability)
- `F53` COVID-19 (2020-03-01 → 2021-06-30): trough of -1.7% on 2020-04-01, back to the pre-shock level after 3 months. Distinguishable from noise: no.
- `F54` Structural breaks: 2016-11-01 (14.6 %); 2021-12-01 (12.0 %); 2024-07-01 (5.7 %). Without a known event within ±6 months: 2.
- `F55` Hardest-hit regions (trough): Grand Port -20.9 % (covid19), Plaines Wilhems -15.3 % (covid19), Agaléga -12.7 % (covid19), Flacq -11.4 % (covid19), Black River -4.7 % (covid19).

## ⚖️ Use case 5 — Inequality and electrification

- **Question** — Where do people without electricity live?
- **Data** — VIIRS VNL V2, GHSL / WorldPop, GHSL SMOD, electricity access (WDI)
- **Method** — Population-weighted Gini and Theil; population of inhabited pixels below the detection threshold; sensitivity to three thresholds; bootstrap CI of the Gini change.
- **Validation** — Gap with the World Bank electricity-access rate (**mean gap (pp) = -6.4**)
- **Uncertainty** — Range across radiance thresholds; bootstrap CI of the Gini.
- **Limits** — Proxy of outdoor lighting, not of connection: a connected but dimly lit household looks “in the dark”.
- **Status** — `experimental` · Confidence: medium
- **References** — Theil (1967); Falchetta et al. (2020) electricity access from lights.
- **Dashboard page** — [`#inequality`](https://samuelguda4.github.io/NTL_Mauritius_Project/?country=MUS#inequality)

**Results of this run**

- `F07` The Gini coefficient of light per capita (ADM2) is 0.23 in 2025 (no significant change since 2014). About 0.00 million people live in inhabited areas with no detectable light (6% of the inhabited population). (confidence medium: sensitive to the radiance threshold (from 0.00 to 0.00 M depending on the threshold); a proxy for outdoor lighting, not for grid connection)
- `F56` Gini of light per capita (ADM2): 0.232 in 2014 → 0.231 in 2025 (change -0.001, bootstrap CI -0.064 to 0.040). Theil T 0.096; between-region share 100%.
- `F57` People in inhabited areas without detectable light: 0.00 M (8%) in 2014 → 0.00 M (6%) in 2025. Urban/rural light-per-capita ratio 0.1. Proxy of electricity access, sensitive to the threshold.
- `F58` Average gap between the share of people in lit areas and the World Bank electricity-access rate: -6.4 points.

## 🏭 Use case 6 — Industrial zones

- **Question** — Where is industry, and is its activity growing?
- **Data** — VIIRS VNL V2, GHSL BUILT-S, Sentinel-5P NO₂/SO₂, MODIS MOD11A2, OpenStreetMap
- **Method** — Concordance of six signals per pixel (≥ 3 including light), 8-connected clusters, typology and confidence.
- **Validation** — Comparison with the reference list (n/a) (**precision / recall / F1 = not available**)
- **Uncertainty** — Per-cluster confidence from the number of strong signals; isolated sites to verify.
- **Limits** — Sentinel-5P (≈ 5 km) and MODIS (1 km) resolution: signals describe a neighbourhood.
- **Status** — `experimental` · Confidence: low
- **References** — Elvidge et al. (2016) gas flares; Pesaresi et al. (2023) GHSL.
- **Dashboard page** — [`#industry`](https://samuelguda4.github.io/NTL_Mauritius_Project/?country=MUS#industry)

**Results of this run**

- `F08` 16 industrial clusters detected from concordant satellite signals: 4 heavy industry, 2 business parks & logistics, 5 oil & gas sites and 5 isolated sites to verify. They emit 17.1% of national light (latest year); their light changes by +2.6% per year. Plaines Wilhems has the most industrial activity. (confidence low: no reference list available to validate the detection)
- `F59` 16 industrial clusters (≥ 3 of 6 signals): Isolated site to verify 5, Oil, gas & flares 5, Heavy industry 4, Business park & logistics 2. Share of national light: 17.1%; annual growth +2.6%. No validation available.
- `F60` IND-001 — Isolated site to verify in Plaines Wilhems (Plaines Wilhems) (47.945 km², 3 signals, confidence low); IND-004 — Oil, gas & flares in Port Louis (Port Louis) (3.87 km², 3 signals, confidence low); IND-002 — Isolated site to verify in Black River (Black River) (9.46 km², 3 signals, confidence low); IND-003 — Heavy industry in Grand Port (Grand Port) (7.74 km², 3 signals, confidence low); IND-010 — Business park & logistics in Black River (Black River) (1.075 km², 3 signals, confidence low); IND-009 — Oil, gas & flares in Savanne (Savanne) (1.29 km², 4 signals, confidence medium); IND-005 — Heavy industry in Black River (Black River) (2.15 km², 4 signals, confidence medium); IND-006 — Heavy industry in Grand Port (Grand Port) (1.505 km², 4 signals, confidence medium); IND-014 — Business park & logistics in Pamplemousses (Pamplemousses) (0.86 km², 3 signals, confidence low); IND-008 — Oil, gas & flares in Savanne (Savanne) (1.29 km², 4 signals, confidence medium)
- `F61` Plaines Wilhems: 1 industrial cluster(s), 47.9 km², 42.9% of the region's light.

## 🏖️ Use case 7 — Seasonal tourism

- **Question** — Which areas live from tourism, and how does the season evolve?
- **Data** — VIIRS (monthly), hotel nights or WDI arrivals
- **Method** — Summer excess net of comparable units at the same latitude; one-sided test; season index base 100; seasons overlapping Ramadan flagged.
- **Validation** — Correlation with hotel nights (**r = not available**)
- **Uncertainty** — p-value per unit; 2020–2021 excluded from the classification.
- **Limits** — Any summer activity (diaspora, second homes, festivals) is captured, not only tourism.
- **Status** — `experimental` · Confidence: low
- **References** — Seasonal light analyses of tourism, e.g. Hu et al. (2021).
- **Dashboard page** — [`#tourism`](https://samuelguda4.github.io/NTL_Mauritius_Project/?country=MUS#tourism)

**Results of this run**

- `F09` No unit shows a significant net summer excess: no tourist season visible from space. (confidence low: no hotel-night statistics to validate the indicator)
- `F68` 0 tourist zone(s) out of 11 ADM2 units (net summer excess ≥ 10%, peak months [12, 1]): .
- `F80` Validation: Correlation with hotel nights (r = not available). Uncertainty: p-value per unit; 2020–2021 excluded from the classification. Limitations: Any summer activity (diaspora, second homes, festivals) is captured, not only tourism. Status: experimental statistic; confidence low.

## 🏙️ Use case 8 — Urbanisation signals

- **Question** — Where do cities spread, where do villages get electrified, and where does population grow without light?
- **Data** — VIIRS VNL V2, GHSL GHS-POP / WorldPop, GHSL GHS-BUILT-S R2023A, urban population (WDI)
- **Method** — Lit area (pixels above the threshold) and population per unit; Theil–Sen growth rates; newly lit pixels (dark two years in a row at the start, lit two years in a row at the end), split between electrification of inhabited areas and new settlements; light/population typology.
- **Validation** — Rank correlation with GHSL built-up area growth (independent source) (**Spearman ρ = 0.39**)
- **Uncertainty** — Persistence required over two years to limit noise; ± 1 pp margin between growth rates before classifying.
- **Limits** — Light measures outdoor lighting, not urbanisation in the administrative sense; blooming widens cities; GHSL population is interpolated between epochs.
- **Status** — `experimental` · Confidence: low
- **References** — Zhou et al. (2015) urban extent from lights; Pesaresi et al. (2023) GHSL; Min et al. (2013) village electrification.
- **Dashboard page** — [`#urban`](https://samuelguda4.github.io/NTL_Mauritius_Project/?country=MUS#urban)

**Results of this run**

- `F69` National lit area: +3.9% per year; population: +0.1% per year. Classes (ADM2): Electrified urbanisation 9, Stable or declining 2, Undetermined 1.
- `F70` Between 2014 and 2025: 495 km² newly lit, of which 15 km² already inhabited (electrification, ≈ 1k people) and 480 km² of new settlements; 1 km² lost their light.
- `F71` Fastest lit-area expansion: Savanne (Savanne) (+9.7%/yr), Rodrigues (Rodrigues) (+8.9%/yr), Grand Port (Grand Port) (+5.5%/yr), Flacq (Flacq) (+5.4%/yr), Black River (Black River) (+4.5%/yr), Agaléga (Agaléga) (+4.0%/yr). Unlit growth (population faster than light): none.
- `F72` Spearman rank correlation between lit-area growth and GHSL built-up growth: 0.39 (p = 0.235, 11 units).

## General limits of night-time lights

- **What lights measure** — Upward radiance emitted around 01:30: agriculture, daytime trade, poorly lit services and the rural informal economy are poorly captured.
- **Saturation and blooming** — DMSP saturates in city centres (DN 63) and “blooms” beyond lit areas; VIIRS is much better, but blooming still inflates the lit area of cities.
- **Gas flares and isolated sites** — The automatic mask may remove isolated mines, ports or power plants, and miss small flares; candidates are exported for verification.
- **Clouds, seasons, moon** — Cloudy months are only partially observed; STL removes average seasonality but not an abnormal season (snow, late monsoon).
- **Product breaks** — DMSP and VIIRS are not directly comparable: the harmonised long series (Li et al., 2020) is a modelled product, to be read for trends only.
- **NTL–GDP elasticity** — Estimated on 10 to 30 annual observations: wide intervals, possible instability, a non-causal relationship that varies with the level of development.
- **Access to electricity** — “Inhabited without light” ≠ “not connected”: a connected household with low consumption is invisible; the indicator depends strongly on the radiance threshold and the population data.
- **Administrative boundaries** — geoBoundaries/GAUL may differ from official boundaries; small ADM2 units are sensitive to light spilling over from neighbouring units.
- **Industrial zones** — Detection relies on thresholds: a power plant, a port or a large shopping centre can meet the signals; a dimly lit factory without visible emissions is missed. Sentinel-5P (≈ 5 km) and MODIS (1 km) are coarser than VIIRS: NO₂/SO₂/heat signals describe a neighbourhood, not a building.
- **Summer tourism** — The summer excess captures any rise in summer light (second homes, diaspora visits, festivals, construction), not only tourism; at high latitudes, very short summer nights reduce VIIRS observations. Ramadan changes night-time activity: the summers concerned are flagged.
- **Urbanisation** — The lit area depends on the detection threshold and on light blooming around cities; a connected but dimly lit neighbourhood stays invisible. Population (GHSL/WorldPop) is modelled from censuses: its growth is not an independent observation, and years between two epochs are interpolated.


---
<sub>Generated by the notebook on 2026-10-29 · version 2.1.0</sub>
