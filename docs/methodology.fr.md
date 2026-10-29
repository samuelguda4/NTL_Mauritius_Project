<p align="right"><a href="methodology.md">English</a></p>

# Méthodologie — Maurice (2014–2025)

## Données et nettoyage

VIIRS DNB mensuel (VCMSLCFG) et annuel VNL V2, DMSP–VIIRS harmonisé, Black Marble quotidien, GHSL/WorldPop, Sentinel-5P NO₂/SO₂, MODIS LST, Banque mondiale. Nettoyage : pixels valides si cf_cvg ≥ 2, unité-mois gardée si ≥ 80 % de pixels observés, pics remplacés, fond et torchères masqués.

## 📈 Cas d'usage 1 — Dynamiques temporelles

- **Question** — L'activité accélère-t-elle ou ralentit-elle, hors effet de saison ?
- **Données** — VIIRS VCMSLCFG (monthly), VIIRS VNL V2 (annual), Harmonised DMSP–VIIRS (Li et al., 2020)
- **Méthode** — STL robuste (période 12) sur log(somme des lumières) ; pente de Theil–Sen et test de Mann–Kendall sur les composites annuels ; détection d'anomalies et de ruptures.
- **Validation** — Significativité de la tendance (Mann–Kendall) et cohérence mensuel/annuel (**p-value = < 0,0001**)
- **Incertitude** — IC 95 % de la croissance annuelle : +4,7 % à +7,9 %
- **Limites** — Couverture nuageuse et nuits courtes en été ; la lumière n'est pas la valeur ajoutée.
- **Statut** — `experimental` · Confiance: élevée
- **Références** — Cleveland et al. (1990) STL ; Sen (1968) ; Elvidge et al. (2017).
- **Page du tableau de bord** — [`#time`](https://samuelguda4.github.io/NTL_Mauritius_Project/fr/?country=MUS#time)

**Résultats de cette exécution**

- `F02` Entre 2014 et 2025, la lumière nocturne de Maurice a évolué de +6,6 % par an (IC 95 % : +4,7 % à +7,9 %). Sur les 12 derniers mois, le niveau désaisonnalisé est -6,6 % par rapport aux 12 mois précédents. (confiance élevée : tendance significative (p < 0,01 ; n = 12))
- `F74` Validation : Significativité de la tendance (Mann–Kendall) et cohérence mensuel/annuel (p-value = < 0,0001). Incertitude : IC 95 % de la croissance annuelle : +4,7 % à +7,9 % Limites : Couverture nuageuse et nuits courtes en été ; la lumière n'est pas la valeur ajoutée. Statut : statistique expérimentale ; confiance élevée.

## 🗺️ Cas d'usage 2 — Croissance régionale et convergence

- **Question** — Quelles régions décollent, lesquelles décrochent ?
- **Données** — VIIRS VNL V2, GHSL / WorldPop, Sentinel-5P NO₂
- **Méthode** — Croissance robuste par unité (Theil–Sen, Mann–Kendall), classes croissance/stagnation/déclin, β- et σ-convergence, indice de Herfindahl.
- **Validation** — Corrélation de rang avec le NO₂ troposphérique (source indépendante) (**Spearman ρ = 0,66**)
- **Incertitude** — Classe attribuée seulement si |pente| ≥ seuil et p < α ; IC de β (erreurs robustes).
- **Limites** — Petites unités : bruit et débordement de lumière (blooming) entre voisins.
- **Statut** — `experimental` · Confiance: moyenne
- **Références** — Barro et Sala-i-Martin (1992) convergence ; Henderson, Storeygard et Weil (2012).
- **Page du tableau de bord** — [`#regions`](https://samuelguda4.github.io/NTL_Mauritius_Project/fr/?country=MUS#regions)

**Résultats de cette exécution**

- `F03` Sur 12 unités ADM2, 10 sont en croissance significative, 1 stagnent et 0 déclinent. L'activité lumineuse reste concentrée : Plaines Wilhems concentre 22 % de la lumière nationale. (confiance moyenne : classement sur 12 unités, seuil ±1 %/an et p < 0,10)
- `F04` Entre unités ADM2, la lumière par habitant ne montre ni convergence ni divergence statistiquement établie. (confiance faible : β = −0,006 [−0,027 ; 0,015], n = 10)
- `F24` Plaines Wilhems (ADM1, 2025) : part de la lumière nationale 22,0 %, croissance annuelle +4,7 % (IC +3,2 % à +6,1 %, classe Croissance), lumière par habitant 0,286, population 0,02 M, dans le noir 0 %, PIB estimé (expérimental) 3,37 Md USD.
- `F25` Pamplemousses (ADM1, 2025) : part de la lumière nationale 15,0 %, croissance annuelle +9,1 % (IC +7,3 % à +10,1 %, classe Croissance), lumière par habitant 0,523, population 0,01 M, dans le noir 8 %, PIB estimé (expérimental) 2,30 Md USD.

## 💹 Cas d'usage 3 — Relation lumières–PIB

- **Question** — Peut-on estimer la croissance avant sa publication, et le PIB régional ?
- **Données** — VIIRS, PIB réel (Banque mondiale, WDI)
- **Méthode** — log(lumière) ~ log(PIB) en niveaux et en croissance, MCO avec écarts-types HAC ; prévision hors échantillon ; PIB régional = PIB national réparti au prorata de la lumière.
- **Validation** — Suivi hors échantillon de la croissance officielle (**corrélation / EAM (points) = -0,16 / 4,0**)
- **Incertitude** — IC 95 % de l'élasticité : 1,24 à 3,18 ; intervalles de prévision 80 % et 95 %.
- **Limites** — Échantillon annuel court ; le PIB régional est une statistique expérimentale à confronter aux comptes régionaux.
- **Statut** — `experimental` · Confiance: moyenne
- **Références** — Henderson et al. (2012) AER ; Chen et Nordhaus (2011) PNAS ; Gibson et al. (2021) JDE.
- **Page du tableau de bord** — [`#time`](https://samuelguda4.github.io/NTL_Mauritius_Project/fr/?country=MUS#time)

**Résultats de cette exécution**

- `F05` L'élasticité de la lumière au PIB réel est de 2,21 en niveaux (IC 95 % : 1,24 à 3,18, R² = 0,63, 12 années) et de 0,34 en taux de croissance (IC : 0,01 à 0,66). Hors échantillon, la croissance des lumières suit celle du PIB avec une corrélation de −0,16 (erreur absolue moyenne : 4,0 point de croissance). (confiance moyenne : n = 12, significatif mais IC large (1,94))
- `F49` Élasticité lumières–PIB réel en niveaux : β = 2,21 (IC 95 % 1,24 à 3,18, R² = 0,63, n = 12, confiance moyenne : n = 12, significatif mais IC large (1,94)). +1 % de PIB ↔ +β % de lumière.
- `F50` Élasticité lumières–PIB réel en taux de croissance : β = 0,34 (IC 95 % 0,01 à 0,66, R² = 0,08, n = 11, confiance moyenne : n = 11, significatif mais IC large (0,66)). +1 % de PIB ↔ +β % de lumière.
- `F51` Élasticité lumières–PIB réel en série longue DMSP–VIIRS : β = 1,14 (IC 95 % 0,66 à 1,62, R² = 0,69, n = 30, confiance élevée : n = 30, p < 0,01, IC étroit). +1 % de PIB ↔ +β % de lumière.

## ⚡ Cas d'usage 4 — Chocs et résilience

- **Question** — Quelle a été la profondeur d'un choc, et la vitesse de récupération ?
- **Données** — VIIRS (monthly), Black Marble VNP46A2 (daily), catalogue d'événements
- **Méthode** — Écart au niveau d'avant-choc sur la série désaisonnalisée ; ruptures structurelles ; indice quotidien Black Marble.
- **Validation** — Le creux dépasse-t-il la variabilité ordinaire ? (**creux (choc principal) = -1,7 % — non**)
- **Incertitude** — Variabilité mensuelle d'avant-choc (écart-type robuste) ; ruptures inexpliquées signalées.
- **Limites** — Les chocs touchant des activités peu éclairées (agriculture, services de jour) sont sous-estimés.
- **Statut** — `experimental` · Confiance: faible
- **Références** — Román et al. (2018) ; Elvidge et al. (2020) lumières et confinements.
- **Page du tableau de bord** — [`#shocks`](https://samuelguda4.github.io/NTL_Mauritius_Project/fr/?country=MUS#shocks)

**Résultats de cette exécution**

- `F06` Le choc le plus marqué dans la série désaisonnalisée est « COVID-19 » : creux de -1,7 % (04/2020), retour au niveau d'avant-choc après 3 mois. (confiance faible : creux comparé à la variabilité mensuelle d'avant-choc)
- `F53` COVID-19 (2020-03-01 → 2021-06-30) : creux de -1,7 % le 2020-04-01, retour au niveau d'avant-choc après 3 mois. Distinct du bruit : non.
- `F54` Ruptures structurelles : 2016-11-01 (14,6 %); 2021-12-01 (12,0 %); 2024-07-01 (5,7 %). Sans événement connu à ±6 mois : 2.
- `F55` Régions les plus touchées (creux) : Grand Port -20,9 % (covid19), Plaines Wilhems -15,3 % (covid19), Agaléga -12,7 % (covid19), Flacq -11,4 % (covid19), Black River -4,7 % (covid19).

## ⚖️ Cas d'usage 5 — Inégalités et électrification

- **Question** — Où vivent les populations privées d'électricité ?
- **Données** — VIIRS VNL V2, GHSL / WorldPop, GHSL SMOD, accès à l'électricité (WDI)
- **Méthode** — Gini et Theil pondérés par la population ; population des pixels habités sous le seuil de détection ; sensibilité à trois seuils ; IC bootstrap de la variation du Gini.
- **Validation** — Écart avec le taux d'accès à l'électricité de la Banque mondiale (**écart moyen (points) = -6,4**)
- **Incertitude** — Plage selon le seuil de radiance ; IC bootstrap du Gini.
- **Limites** — Proxy de l'éclairage extérieur, pas du raccordement : un foyer raccordé mais peu éclairé paraît « dans le noir ».
- **Statut** — `experimental` · Confiance: moyenne
- **Références** — Theil (1967) ; Falchetta et al. (2020) accès à l'électricité par les lumières.
- **Page du tableau de bord** — [`#inequality`](https://samuelguda4.github.io/NTL_Mauritius_Project/fr/?country=MUS#inequality)

**Résultats de cette exécution**

- `F07` Le Gini de la lumière par habitant (ADM2) vaut 0,23 en 2025 (évolution non significative depuis 2014). Environ 0,00 million(s) de personnes vivent dans des zones habitées sans lumière détectable (6 % de la population habitée). (confiance moyenne : sensible au seuil de radiance (de 0,00 à 0,00 M selon le seuil) ; proxy d'éclairage extérieur, pas de raccordement)
- `F56` Gini de la lumière par habitant (ADM2) : 0,232 en 2014 → 0,231 en 2025 (variation -0,001, IC bootstrap -0,064 à 0,040). Theil T 0,096 ; part entre régions 100 %.
- `F57` Habitants de zones habitées sans lumière détectable : 0,00 M (8 %) en 2014 → 0,00 M (6 %) en 2025. Rapport lumière/hab. urbain/rural 0,1. Proxy de l'accès à l'électricité, sensible au seuil.
- `F58` Écart moyen entre la part de la population en zone éclairée et le taux d'accès à l'électricité de la Banque mondiale : -6,4 points.

## 🏭 Cas d'usage 6 — Zones industrielles

- **Question** — Où est l'industrie, et son activité progresse-t-elle ?
- **Données** — VIIRS VNL V2, GHSL BUILT-S, Sentinel-5P NO₂/SO₂, MODIS MOD11A2, OpenStreetMap
- **Méthode** — Concordance de six signaux par pixel (≥ 3 dont la lumière), grappes 8-connexes, typologie et confiance.
- **Validation** — Comparaison avec la liste de référence (n.d.) (**précision / rappel / F1 = non disponible**)
- **Incertitude** — Confiance par grappe selon le nombre de signaux forts ; sites isolés à vérifier.
- **Limites** — Résolution de Sentinel-5P (≈ 5 km) et MODIS (1 km) : les signaux qualifient un voisinage.
- **Statut** — `experimental` · Confiance: faible
- **Références** — Elvidge et al. (2016) torchères ; Pesaresi et al. (2023) GHSL.
- **Page du tableau de bord** — [`#industry`](https://samuelguda4.github.io/NTL_Mauritius_Project/fr/?country=MUS#industry)

**Résultats de cette exécution**

- `F08` 16 grappes industrielles détectées par concordance de signaux satellitaires : 4 d'industrie lourde, 2 zones d'activités et de logistique, 5 sites d'hydrocarbures et 5 sites isolés à vérifier. Elles émettent 17,1 % de la lumière nationale (dernière année) ; leur lumière évolue de +2,6 % par an. Plaines Wilhems concentre la plus forte activité industrielle. (confiance faible : aucune liste de référence pour valider la détection)
- `F59` 16 grappes industrielles (≥ 3 signaux sur 6) : Site isolé à vérifier 5, Hydrocarbures et torchères 5, Industrie lourde 4, Zone d'activités et logistique 2. Part de la lumière nationale : 17,1 % ; croissance annuelle +2,6 %. Pas de validation disponible.
- `F60` IND-001 — Site isolé à vérifier à Plaines Wilhems (Plaines Wilhems) (47.945 km², 3 signaux, confiance faible); IND-004 — Hydrocarbures et torchères à Port Louis (Port Louis) (3.87 km², 3 signaux, confiance faible); IND-002 — Site isolé à vérifier à Black River (Black River) (9.46 km², 3 signaux, confiance faible); IND-003 — Industrie lourde à Grand Port (Grand Port) (7.74 km², 3 signaux, confiance faible); IND-010 — Zone d'activités et logistique à Black River (Black River) (1.075 km², 3 signaux, confiance faible); IND-009 — Hydrocarbures et torchères à Savanne (Savanne) (1.29 km², 4 signaux, confiance moyenne); IND-005 — Industrie lourde à Black River (Black River) (2.15 km², 4 signaux, confiance moyenne); IND-006 — Industrie lourde à Grand Port (Grand Port) (1.505 km², 4 signaux, confiance moyenne); IND-014 — Zone d'activités et logistique à Pamplemousses (Pamplemousses) (0.86 km², 3 signaux, confiance faible); IND-008 — Hydrocarbures et torchères à Savanne (Savanne) (1.29 km², 4 signaux, confiance moyenne)
- `F61` Plaines Wilhems : 1 grappe(s) industrielle(s), 47,9 km², 42,9 % de la lumière de la région.

## 🏖️ Cas d'usage 7 — Tourisme saisonnier

- **Question** — Quelles zones vivent du tourisme, et comment évolue la saison ?
- **Données** — VIIRS (monthly), nuitées ou arrivées WDI
- **Méthode** — Surcroît estival net des unités comparables de même latitude ; test unilatéral ; indice de saison base 100 ; saisons recoupant le Ramadan signalées.
- **Validation** — Corrélation avec les nuitées (**r = non disponible**)
- **Incertitude** — p-valeur par unité ; années 2020–2021 exclues du classement.
- **Limites** — Toute activité estivale (diaspora, résidences secondaires, festivals) est captée, pas seulement le tourisme.
- **Statut** — `experimental` · Confiance: faible
- **Références** — Analyses saisonnières des lumières et du tourisme, par ex. Hu et al. (2021).
- **Page du tableau de bord** — [`#tourism`](https://samuelguda4.github.io/NTL_Mauritius_Project/fr/?country=MUS#tourism)

**Résultats de cette exécution**

- `F09` Aucune unité ne montre de surcroît estival net significatif : pas de saison touristique visible depuis l'espace. (confiance faible : aucune statistique de nuitées pour valider l'indicateur)
- `F68` 0 zone(s) touristique(s) sur 11 unités ADM2 (surcroît estival net ≥ 10 %, mois de pointe [12, 1]) : .
- `F80` Validation : Corrélation avec les nuitées (r = non disponible). Incertitude : p-valeur par unité ; années 2020–2021 exclues du classement. Limites : Toute activité estivale (diaspora, résidences secondaires, festivals) est captée, pas seulement le tourisme. Statut : statistique expérimentale ; confiance faible.

## 🏙️ Cas d'usage 8 — Signaux d'urbanisation

- **Question** — Où les villes s'étendent-elles, où les villages s'électrifient-ils, et où la population croît-elle sans lumière ?
- **Données** — VIIRS VNL V2, GHSL GHS-POP / WorldPop, GHSL GHS-BUILT-S R2023A, population urbaine (WDI)
- **Méthode** — Surface éclairée (pixels au-dessus du seuil) et population par unité ; croissances de Theil–Sen ; pixels nouvellement éclairés (sombres deux années de suite au début, éclairés deux années de suite à la fin), séparés entre électrification de zones habitées et nouvelles implantations ; typologie lumière/population.
- **Validation** — Corrélation de rang avec la croissance de la surface bâtie GHSL (source indépendante) (**Spearman ρ = 0,39**)
- **Incertitude** — Persistance exigée sur deux années pour limiter le bruit ; marge de ± 1 point entre croissances avant de classer.
- **Limites** — La lumière mesure l'éclairage extérieur, pas l'urbanisation au sens administratif ; le débordement (blooming) élargit les villes ; la population GHSL est interpolée entre époques.
- **Statut** — `experimental` · Confiance: faible
- **Références** — Zhou et al. (2015) étendue urbaine par les lumières ; Pesaresi et al. (2023) GHSL ; Min et al. (2013) électrification des villages.
- **Page du tableau de bord** — [`#urban`](https://samuelguda4.github.io/NTL_Mauritius_Project/fr/?country=MUS#urban)

**Résultats de cette exécution**

- `F69` Surface éclairée nationale : +3,9 % par an ; population : +0,1 % par an. Classes (ADM2) : Urbanisation électrifiée 9, Stable ou en déclin 2, Indéterminé 1.
- `F70` Entre 2014 et 2025 : 495 km² nouvellement éclairés, dont 15 km² de zones déjà habitées (électrification, ≈ 1 k habitants) et 480 km² de nouvelles implantations ; 1 km² ont perdu leur lumière.
- `F71` Plus forte extension de la surface éclairée : Savanne (Savanne) (+9,7 %/an), Rodrigues (Rodrigues) (+8,9 %/an), Grand Port (Grand Port) (+5,5 %/an), Flacq (Flacq) (+5,4 %/an), Black River (Black River) (+4,5 %/an), Agaléga (Agaléga) (+4,0 %/an). Croissance non éclairée (population plus rapide que la lumière) : aucune.
- `F72` Corrélation de rang (Spearman) entre croissance de la surface éclairée et croissance du bâti GHSL : 0,39 (p = 0,235, 11 unités).

## Limites générales des lumières nocturnes

- **Ce que mesurent les lumières** — Radiance émise vers le haut vers 01 h 30 : l'agriculture, le commerce de jour, les services peu éclairés et l'économie informelle rurale sont mal captés.
- **Saturation et débordement** — DMSP sature au centre des villes (DN 63) et « déborde » (blooming) ; VIIRS est bien meilleur mais le débordement gonfle encore la surface éclairée des villes.
- **Torchères et sites isolés** — Le masque automatique peut retirer des mines, ports ou centrales isolés, et manquer de petites torchères ; les candidats sont exportés pour vérification.
- **Nuages, saisons, lune** — Les mois nuageux sont partiellement observés ; la STL retire la saisonnalité moyenne mais pas une saison anormale (neige, mousson tardive).
- **Ruptures de produit** — DMSP et VIIRS ne sont pas directement comparables : la série longue harmonisée (Li et al., 2020) est un produit modélisé, à lire en tendance seulement.
- **Élasticité NTL–PIB** — Estimée sur 10 à 30 points annuels : intervalles larges, instabilité possible, relation non causale et variable selon le niveau de développement.
- **Accès à l'électricité** — « Habité sans lumière » ≠ « non raccordé » : un foyer raccordé à faible consommation est invisible ; l'indicateur dépend fortement du seuil de radiance et de la population.
- **Limites administratives** — geoBoundaries/GAUL peuvent différer des limites officielles ; les petites unités ADM2 sont sensibles au débordement de la lumière des voisines.
- **Zones industrielles** — La détection repose sur des seuils : une centrale, un port ou un grand centre commercial peut cumuler les signaux ; une usine peu éclairée ou sans émissions visibles échappe à la détection. Sentinel-5P (≈ 5 km) et MODIS (1 km) sont plus grossiers que VIIRS : les signaux NO₂/SO₂/chaleur qualifient un voisinage, pas un bâtiment.
- **Tourisme estival** — Le surcroît estival mesure toute hausse de lumière en été (résidences secondaires, diaspora, fêtes, chantiers), pas seulement le tourisme ; aux hautes latitudes, les nuits d'été très courtes réduisent les observations VIIRS. Le Ramadan modifie l'activité nocturne : les étés concernés sont signalés.
- **Urbanisation** — La surface éclairée dépend du seuil de détection et du débordement de lumière (blooming) autour des villes ; un quartier raccordé mais peu éclairé reste invisible. La population (GHSL/WorldPop) est modélisée à partir des recensements : sa croissance n'est pas une observation indépendante, et les années entre deux millésimes sont interpolées.


---
<sub>Généré par le notebook le 2026-10-29 · version 2.1.0</sub>
