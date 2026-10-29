"""
ntl-economic-analysis — reusable functions for measuring economic activity with night-time lights.

Modules
-------
config        : run configuration, ISO3 validation, paths, dataset registry
gee           : Earth Engine authentication, robust calls (quota/time-out retries), availability checks
boundaries    : administrative boundaries (geoBoundaries / FAO GAUL) filtered by ISO3
acquisition   : zonal statistics from GEE (VIIRS monthly/annual, DMSP, harmonised series,
                Black Marble daily, population, land cover, NO2) -> tidy pandas tables
preprocessing : Earth Engine masks (cloud-free coverage, negatives, outliers, gas flares, DMSP saturation)
worldbank     : World Bank API (GDP, GDP per capita, electricity access, population)
timeseries    : STL decomposition, structural breaks, anomalies
indicators    : growth, classification, concentration, convergence, inequality (Gini/Theil/Lorenz)
econometrics  : NTL-GDP elasticity with diagnostics, GDP nowcast, regional GDP estimation
shocks        : event catalogue, impact and recovery metrics
viz           : Plotly / folium figures with a consistent house style
messages      : automatic key messages with confidence levels
export        : static files for the dashboard (GeoJSON, CSV, JSON, PNG)
cache         : local cache of acquired tables (avoid re-querying GEE)
publish       : publication of the dashboard on GitHub Pages with a token
industry      : use case 6 — industrial zones from six satellite signals (VIIRS, GHSL, Sentinel-5P, MODIS)
tourism       : use case 7 — summer tourism from the seasonal excess of light
agent         : AI assistant on the results (Groq, Gemini, Ollama), grounded in the exported facts
extensions    : dashboard exports of use cases 6–7 and of the assistant's facts
fixture       : synthetic test country XTS (runs everything without Earth Engine)
lang          : language of the package (fr / en)
"""

__version__ = "2.0.0"
