<p align="right"><a href="QUALITY.md">English</a></p>

# Rapport qualité — Maurice

- **version** — 2.1.0
- **generated** — 2026-10-29T12:21:46
- **country** — Maurice
- **period** — 2014, 2025

## Cas d'usage

| Uc | Title | Status | Confidence | Validation | Sources |
|---|---|---|---|---|---|
| 1 | Dynamiques temporelles | `experimental` | élevée | p-value = < 0,0001 — Significativité de la tendance (Mann–Kendall) et cohérence mensuel/annuel | VIIRS VCMSLCFG (monthly), VIIRS VNL V2 (annual), Harmonised DMSP–VIIRS (Li et al., 2020) |
| 2 | Croissance régionale et convergence | `experimental` | moyenne | Spearman ρ = 0,66 — Corrélation de rang avec le NO₂ troposphérique (source indépendante) | VIIRS VNL V2, GHSL / WorldPop, Sentinel-5P NO₂ |
| 3 | Relation lumières–PIB | `experimental` | moyenne | corrélation / EAM (points) = -0,16 / 4,0 — Suivi hors échantillon de la croissance officielle | VIIRS, PIB réel (Banque mondiale, WDI) |
| 4 | Chocs et résilience | `experimental` | faible | creux (choc principal) = -1,7 % — non — Le creux dépasse-t-il la variabilité ordinaire ? | VIIRS (monthly), Black Marble VNP46A2 (daily), catalogue d'événements |
| 5 | Inégalités et électrification | `experimental` | moyenne | écart moyen (points) = -6,4 — Écart avec le taux d'accès à l'électricité de la Banque mondiale | VIIRS VNL V2, GHSL / WorldPop, GHSL SMOD, accès à l'électricité (WDI) |
| 6 | Zones industrielles | `experimental` | faible | précision / rappel / F1 = non disponible — Comparaison avec la liste de référence (n.d.) | VIIRS VNL V2, GHSL BUILT-S, Sentinel-5P NO₂/SO₂, MODIS MOD11A2, OpenStreetMap |
| 7 | Tourisme saisonnier | `experimental` | faible | r = non disponible — Corrélation avec les nuitées | VIIRS (monthly), nuitées ou arrivées WDI |
| 8 | Signaux d'urbanisation | `experimental` | faible | Spearman ρ = 0,39 — Corrélation de rang avec la croissance de la surface bâtie GHSL (source indépendante) | VIIRS VNL V2, GHSL GHS-POP / WorldPop, GHSL GHS-BUILT-S R2023A, population urbaine (WDI) |

## DQAF

| Dimension | Practice | Evidence |
|---|---|---|
| 0. Conditions préalables | Cadre institutionnel, ressources, pertinence | Projet Banque africaine de développement × Data Innovation for Africa (DI4A) ; données satellitaires gratuites ; questions de politique publique explicites pour chaque cas d'usage. |
| 1. Garanties d'intégrité | Professionnalisme, transparence, normes éthiques | Code ouvert, méthodes documentées, paramètres et versions consignés dans le manifeste ; aucune donnée individuelle ; publication sans intervention manuelle sur les chiffres. |
| 2. Rigueur méthodologique | Concepts, champ, classifications, base d'enregistrement | Méthodes publiées dans la littérature (Henderson et al. 2012 ; Elvidge et al. 2021 ; Román et al. 2018) ; codes ISO 3166 ; limites geoBoundaries ; WGS 84. |
| 3. Exactitude et fiabilité | Sources, évaluation, techniques statistiques, validation, révisions | Contrôle qualité (couverture nuageuse, torchères, aberrants) ; validation de chaque cas d'usage contre une source indépendante ; intervalles de confiance ; niveau de confiance publié. |
| 4. Utilité | Périodicité, actualité, cohérence, politique de révision | Séries mensuelles disponibles quelques semaines après le mois ; recalcul complet à chaque exécution (cache horodaté) ; cohérence vérifiée entre séries mensuelles et annuelles. |
| 5. Accessibilité | Données, métadonnées, assistance | Tableau de bord public bilingue, fichiers ouverts (CSV, JSON, GeoJSON), manifeste de métadonnées, agent IA citant ses sources, dépôt GitHub avec citation. |

## GSBPM

| Phase | Notebook sections | What |
|---|---|---|
| 1. Spécifier les besoins | 1 | Questions de politique publique des huit cas d'usage |
| 2. Concevoir | 1–2 | Choix des sources, des indicateurs et des seuils |
| 3. Construire | 2 | Pipeline paramétré par ISO3, code embarqué, tests sur jeu synthétique |
| 4. Collecter | 3 | Earth Engine, Banque mondiale, OpenStreetMap — avec cache |
| 5. Traiter | 3 | Nuages, torchères, aberrants, harmonisation, contrôle qualité |
| 6. Analyser | 4–12 | Huit cas d'usage, validation, incertitude, interprétation |
| 7. Diffuser | 15–18 | Tableau de bord, images, agent IA, dépôt GitHub |
| 8. Évaluer | 13–14 | Fiches qualité, niveaux de confiance, limites, recommandations |

## Principes FAIR

| Principle | How |
|---|---|
| Trouvable (Findable) | Dépôt GitHub public avec description, mots-clés et CITATION.cff ; manifeste de métadonnées ; identifiant pérenne possible (DOI Zenodo). |
| Accessible | HTTPS public sans authentification ; formats ouverts ; code et données sous licence explicite. |
| Interopérable (Interoperable) | CSV, JSON, GeoJSON (WGS 84) ; codes ISO 3166 ; identifiants d'unités stables ; vocabulaire des indicateurs documenté. |
| Réutilisable (Reusable) | Provenance (sources, versions, paramètres), licences, méthodes et limites publiées avec les résultats. |

## Statistiques expérimentales

- Toutes les séries et cartes dérivées des lumières nocturnes
- PIB régional estimé et estimation de croissance de l'année non publiée
- Population « dans le noir » (proxy de l'accès à l'électricité)
- Grappes industrielles et indice de saison touristique

## un_principles

| Principle | How |
|---|---|
| Pertinence et impartialité | Indicateurs utiles aux décideurs, diffusés à tous en même temps. |
| Normes professionnelles | Méthodes scientifiques publiées, choix fondés sur des critères techniques. |
| Responsabilité et transparence | Sources, méthodes et procédures documentées. |
| Prévention des mauvais usages | Niveaux de confiance, limites et étiquette « expérimental » sur chaque résultat. |
| Efficacité | Données satellitaires gratuites, pipeline reproductible. |
| Confidentialité | Aucune donnée individuelle : agrégats territoriaux uniquement. |
| Normes internationales | DQAF, GSBPM, FAIR, ISO 3166. |
| Coopération | Code ouvert, réutilisable par tous les instituts statistiques. |

## references

- United Nations (2014). Fundamental Principles of Official Statistics. A/RES/68/261.
- Data Quality Assessment Framework (DQAF, 2012) — generic framework.
- UNECE (2019). Generic Statistical Business Process Model, GSBPM v5.1.
- Wilkinson, M. D. et al. (2016). The FAIR Guiding Principles for scientific data management and stewardship. Scientific Data 3.
- Eurostat (2021). Experimental statistics — European Statistical System guidelines.


---
<sub>Généré par le notebook le 2026-10-29 · version 2.1.0</sub>
