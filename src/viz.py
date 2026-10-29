"""Figures with a single house style (Plotly for charts, folium for choropleths).

Rules applied to every figure: explicit title, axis titles with units, legend when there are
≥ 2 series, and the data source written under the plot. Colours follow fixed roles
(validated categorical order; blue↔red diverging pair with a grey midpoint for growth;
one-hue sequential ramps for magnitudes) and are shared with the dashboard.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ---- palette (shared with dashboard/assets/style.css) ----------------------------------
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
CLASS_COLORS = {"Growth": "#2a78d6", "Stagnation": "#a9a8a2", "Decline": "#e34948", "Undetermined": "#e1e0d9"}
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SEQ_ORANGE = ["#fde3d6", "#f9bfa4", "#f39a72", "#eb6834", "#c94f20", "#9f3c17", "#73290e"]
DIVERGING = ["#e34948", "#ef8f8a", "#f6c6c2", "#f0efec", "#b7d3f6", "#6da7ec", "#2a78d6"]
FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"

SRC_VIIRS = "VIIRS DNB (NOAA/EOG) via Google Earth Engine"
SRC_WB = "World Bank, WDI"


def style(fig, title: str, source: str, y_title: str | None = None, x_title: str | None = None,
          height: int = 440, legend: bool | None = None):
    """Apply the house style, a title, axis titles (with units) and a source line."""
    fig.update_layout(
        template="plotly_white", height=height, font=dict(family=FONT, size=13, color=INK2),
        title=dict(text=title, x=0.01, xanchor="left", font=dict(size=16, color=INK)),
        margin=dict(l=64, r=24, t=64, b=86), paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        hoverlabel=dict(font=dict(family=FONT)), colorway=SERIES,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0.0, title=None),
    )
    if legend is not None:
        fig.update_layout(showlegend=legend)
    fig.update_xaxes(showgrid=False, linecolor=AXIS, ticks="outside", tickcolor=AXIS,
                     title=x_title, title_font=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=AXIS, title=y_title,
                     title_font=dict(color=MUTED))
    fig.add_annotation(text=f"Source: {source}", xref="paper", yref="paper", x=0, y=-0.22,
                       showarrow=False, xanchor="left", font=dict(size=11, color=MUTED))
    return fig


def national_series(stl: pd.DataFrame, events: pd.DataFrame | None = None,
                    breaks: pd.DataFrame | None = None, anomalies: pd.DataFrame | None = None,
                    country: str = ""):
    """Observed vs seasonally adjusted monthly SoL, with events (bands), breaks and anomalies."""
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_scatter(x=stl.index, y=stl["obs"], name="Observed", mode="lines",
                    line=dict(color=AXIS, width=1.5))
    fig.add_scatter(x=stl.index, y=stl["sa_level"], name="Seasonally adjusted (STL)", mode="lines",
                    line=dict(color=SERIES[0], width=2.2))
    fig.add_scatter(x=stl.index, y=stl["trend_level"], name="Trend", mode="lines",
                    line=dict(color=INK2, width=1.5, dash="dot"))
    if anomalies is not None and len(anomalies):
        fig.add_scatter(x=anomalies.index, y=anomalies["obs"], name="Anomaly (|z| ≥ threshold)", mode="markers",
                        marker=dict(color=SERIES[1], size=9, line=dict(color=SURFACE, width=2)))
    if events is not None:
        for _, e in events.iterrows():
            fig.add_vrect(x0=e["start"], x1=e["end"], fillcolor="#a9a8a2", opacity=0.18, line_width=0,
                          annotation_text=e["label"], annotation_position="top left",
                          annotation_font=dict(size=11, color=INK2))
    if breaks is not None:
        for _, b in breaks.iterrows():
            fig.add_vline(x=b["date"], line=dict(color=SERIES[6], width=1.5, dash="dash"))
            fig.add_annotation(x=b["date"], y=1.0, yref="paper", text=f"break ({b['jump_pct']:+.0f}%)",
                               showarrow=False, yanchor="bottom", font=dict(size=10, color=SERIES[6]))
    fig.update_traces(hovertemplate="%{x|%b %Y}<br>%{y:,.0f}<extra>%{fullData.name}</extra>")
    return style(fig, f"{country} — Monthly sum of lights, observed and seasonally adjusted",
                 SRC_VIIRS + " (VCMSLCFG); cleaning and STL: author's calculations",
                 "Sum of radiance (nW·cm⁻²·sr⁻¹)")


def regional_lines(df: pd.DataFrame, value: str, names: dict, title: str, y_title: str,
                   top: int = 8, source: str = SRC_VIIRS):
    """One line per unit for the `top` largest units; the rest folded into 'Others'."""
    import plotly.graph_objects as go
    last = df[df["year"] == df["year"].max()].nlargest(top, value)["unit_id"].tolist()
    fig = go.Figure()
    for i, uid in enumerate(last):
        g = df[df["unit_id"] == uid].sort_values("year")
        fig.add_scatter(x=g["year"], y=g[value], name=names.get(uid, uid), mode="lines+markers",
                        line=dict(color=SERIES[i % 8], width=2), marker=dict(size=6))
    rest = df[~df["unit_id"].isin(last)].groupby("year")[value].sum()
    if len(rest) and rest.sum() > 0:
        fig.add_scatter(x=rest.index, y=rest.values, name="Others (sum)", mode="lines",
                        line=dict(color=MUTED, width=1.5, dash="dot"))
    return style(fig, title, source, y_title, "Year", height=460)


def growth_ranking(trends: pd.DataFrame, names: dict, title: str, n: int = 25):
    """Horizontal bars of robust annual growth (with 95% CI), coloured by class."""
    import plotly.graph_objects as go
    d = trends.dropna(subset=["growth"]).copy()
    d["name"] = d["unit_id"].map(names)
    if len(d) > n:
        d = pd.concat([d.nlargest(n // 2, "growth"), d.nsmallest(n - n // 2, "growth")]).drop_duplicates("unit_id")
    d = d.sort_values("growth")
    fig = go.Figure()
    for cls, g in d.groupby("class"):
        fig.add_bar(y=g["name"], x=100 * g["growth"], orientation="h", name=cls,
                    marker=dict(color=CLASS_COLORS.get(cls, MUTED), line=dict(color=SURFACE, width=1)),
                    error_x=dict(type="data", symmetric=False, array=100 * (g["growth_hi"] - g["growth"]),
                                 arrayminus=100 * (g["growth"] - g["growth_lo"]), color=AXIS, thickness=1),
                    hovertemplate="%{y}<br>%{x:.1f}%/yr<extra>%{fullData.name}</extra>")
    fig.update_yaxes(categoryorder="array", categoryarray=d["name"].tolist(), gridcolor="rgba(0,0,0,0)")
    fig.add_vline(x=0, line=dict(color=AXIS, width=1))
    return style(fig, title, SRC_VIIRS + " (VNL V2 annual); Theil–Sen slope on log(SoL)",
                 None, "Annual growth of the sum of lights (%/yr)", height=max(420, 22 * len(d) + 140))


def ntl_gdp_scatter(res: dict, country: str = ""):
    """log(NTL) vs log(GDP) with the OLS line, labelled years and 95% band."""
    import plotly.graph_objects as go
    import statsmodels.api as sm
    d = res["data"]
    fig = go.Figure()
    fig.add_scatter(x=d["lx"], y=d["ly"], mode="markers+text", text=d["year"].astype(str),
                    textposition="top center", textfont=dict(size=10, color=MUTED), name="Years",
                    marker=dict(color=SERIES[0], size=10, line=dict(color=SURFACE, width=2)),
                    hovertemplate="%{text}<br>log GDP %{x:.3f}<br>log NTL %{y:.3f}<extra></extra>")
    xs = np.linspace(d["lx"].min(), d["lx"].max(), 50)
    m = sm.OLS(d["ly"], sm.add_constant(d["lx"])).fit()
    pr = m.get_prediction(sm.add_constant(xs)).summary_frame(alpha=0.05)
    fig.add_scatter(x=np.r_[xs, xs[::-1]], y=np.r_[pr["mean_ci_upper"], pr["mean_ci_lower"][::-1]],
                    fill="toself", fillcolor="rgba(42,120,214,0.12)", line=dict(width=0),
                    name="95% CI of the fitted line", hoverinfo="skip")
    fig.add_scatter(x=xs, y=pr["mean"], mode="lines", line=dict(color=SERIES[0], width=2),
                    name=f"β = {res['beta']:.2f} [{res['ci'][0]:.2f}; {res['ci'][1]:.2f}]")
    lab = "Δ log" if res["spec"] == "growth" else "log"
    return style(fig, f"{country} — Night-time lights and real GDP ({res['years'][0]}–{res['years'][1]})",
                 f"{SRC_VIIRS}; {SRC_WB} (NY.GDP.MKTP.KD); OLS, HAC standard errors",
                 f"{lab} sum of lights", f"{lab} GDP (constant 2015 USD)", height=480)


def lorenz_curves(curves: dict, gini_by_year: dict, title: str):
    """Lorenz curves of light vs population for several years, with the equality line."""
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", name="Perfect equality",
                    line=dict(color=AXIS, width=1, dash="dash"))
    for i, (y, (q, l)) in enumerate(curves.items()):
        fig.add_scatter(x=q, y=l, mode="lines", name=f"{y} (Gini {gini_by_year[y]:.2f})",
                        line=dict(color=SERIES[i % 8], width=2.2),
                        hovertemplate="%{x:.0%} of population<br>%{y:.0%} of light<extra></extra>")
    fig.update_xaxes(tickformat=".0%", range=[0, 1])
    fig.update_yaxes(tickformat=".0%", range=[0, 1])
    return style(fig, title, SRC_VIIRS + "; population GHSL/WorldPop; units ranked by light per capita",
                 "Cumulative share of light", "Cumulative share of population", height=480)


def dark_population_bars(df: pd.DataFrame, names: dict, title: str, n: int = 20):
    """Population living in inhabited but unlit pixels, by unit (absolute and share)."""
    import plotly.graph_objects as go
    d = df.nlargest(n, "pop_dark").sort_values("pop_dark").copy()
    d["name"] = d["unit_id"].map(names)
    fig = go.Figure(go.Bar(y=d["name"], x=d["pop_dark"], orientation="h",
                           marker=dict(color=SERIES[1], line=dict(color=SURFACE, width=1)),
                           customdata=100 * d["dark_share"],
                           hovertemplate="%{y}<br>%{x:,.0f} people<br>%{customdata:.0f}% of inhabited pop.<extra></extra>"))
    return style(fig, title, SRC_VIIRS + "; population GHSL/WorldPop; radiance threshold given in the methodology",
                 None, "People in inhabited unlit pixels", height=max(420, 24 * len(d) + 140), legend=False)


def daily_index_fig(idx: pd.DataFrame, label: str, start=None, end=None):
    """Daily Black Marble index (raw points + 7-day rolling median)."""
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_scatter(x=idx.index, y=idx["index"], mode="markers", name="Daily index",
                    marker=dict(color=AXIS, size=5))
    fig.add_scatter(x=idx.index, y=idx["index_smooth"], mode="lines", name="7-day rolling median",
                    line=dict(color=SERIES[0], width=2.2))
    fig.add_hline(y=100, line=dict(color=MUTED, width=1, dash="dot"))
    if start is not None:
        fig.add_vrect(x0=start, x1=end or start, fillcolor="#a9a8a2", opacity=0.18, line_width=0)
    return style(fig, f"Daily Black Marble — {label}",
                 "NASA Black Marble VNP46A2 (high-quality pixels, cloud- and snow-free) via GEE",
                 "Index (100 = median of the first 60 days)", None)


def choropleth(gdf, column: str, title: str, legend: str, colors: list[str] | None = None,
               categorical: dict | None = None, tooltip_cols: list[str] | None = None):
    """folium choropleth with tooltip. `categorical` maps class -> colour (for growth classes)."""
    import branca.colormap as cm
    import folium
    g = gdf.copy()
    center = g.to_crs(4326).union_all().centroid
    # Esri tiles: served without API key or Referer (OSM and CARTO tiles are blocked in Colab)
    m = folium.Map(location=[center.y, center.x], zoom_start=6, control_scale=True,
                   tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
                   attr="Tiles © Esri — Esri, HERE, Garmin, © OpenStreetMap contributors")
    if categorical:
        def sty(f):
            return {"fillColor": categorical.get(f["properties"][column], "#e1e0d9"), "color": "#ffffff",
                    "weight": 0.6, "fillOpacity": 0.85}
    else:
        vals = g[column].replace([np.inf, -np.inf], np.nan).dropna()
        lo, hi = (float(vals.quantile(0.02)), float(vals.quantile(0.98))) if len(vals) else (0, 1)
        cmap = cm.LinearColormap(colors or SEQ_BLUE, vmin=lo, vmax=hi, caption=legend)
        cmap.add_to(m)

        def sty(f):
            v = f["properties"].get(column)
            ok = v is not None and np.isfinite(v)
            return {"fillColor": cmap(min(max(v, lo), hi)) if ok else "#e1e0d9", "color": "#ffffff",
                    "weight": 0.6, "fillOpacity": 0.85}
    cols = ["name"] + (tooltip_cols or [column])
    folium.GeoJson(g[cols + ["geometry"]].to_json(), style_function=sty,
                   tooltip=folium.GeoJsonTooltip(fields=cols)).add_to(m)
    if categorical:
        items = "".join(f"<div><span style='display:inline-block;width:12px;height:12px;background:{c};"
                        f"margin-right:6px;border-radius:2px'></span>{k}</div>" for k, c in categorical.items()
                        if k != "Undetermined")
        m.get_root().html.add_child(folium.Element(
            f"<div style='position:fixed;bottom:24px;left:24px;z-index:999;background:#fff;padding:8px 10px;"
            f"border-radius:6px;font:12px {FONT};box-shadow:0 1px 4px rgba(0,0,0,.2)'><b>{legend}</b>{items}</div>"))
    m.get_root().html.add_child(folium.Element(
        f"<div style='position:fixed;top:10px;left:60px;z-index:999;background:rgba(255,255,255,.9);padding:6px 10px;"
        f"border-radius:6px;font:600 14px {FONT}'>{title}</div>"))
    return m
