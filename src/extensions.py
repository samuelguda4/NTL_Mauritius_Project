"""Dashboard exports of use cases 6 (industry) and 7 (tourism) and of the AI-assistant facts.

Called at the end of ``export.export_dashboard`` (same language as the calling package)::

    <ISO3>/industry.json               counts, series, regions, validation, top clusters
    <ISO3>/industry_clusters.geojson   one polygon per cluster (map)
    <ISO3>/tourism.json                tourist zones, season index, profile, validation
    <ISO3>/agent_context.json          numbered facts used by the AI assistant (web and notebook)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .lang import LANG


def _rec(df, cols=None):
    from .export import _df_records
    return _df_records(df, cols)


def export_extensions(out: Path, R: dict, names: dict) -> list[str]:
    from .export import _clean, write_json
    from . import agent, industry as ind, tourism as tou
    out = Path(out)
    written = []
    I = R.get("industry") or {}
    if I.get("available"):
        y1 = I["years"][-1]
        lay = ind.map_layer(I)
        num = lay.select_dtypes("number").columns
        lay[num] = lay[num].astype(float).round(5)
        (out / "industry_clusters.geojson").write_text(lay.to_json(drop_id=True, na="null"), encoding="utf-8")
        v = dict(I.get("validation") or {})
        v.pop("matched", None)
        write_json(out / "industry.json", {
            "available": True, "n": I["n"], "years": I["years"], "params": I["params"], "counts": I["counts"],
            "conf_counts": I["conf_counts"], "type_labels": ind.TYPE_LABEL, "type_colors": ind.TYPE_COLOR,
            "signal_labels": ind.SIGNAL_LABEL,
            "share_last": float(I["series"]["share_of_national"].iloc[-1]) if len(I["series"]) else None,
            "series": _rec(I["series"]), "by_type": _rec(I["by_type"]), "trend": I.get("trend"),
            "type_trends": I.get("type_trends"),
            "units": {lv: _rec(u) for lv, u in I["units"].items()},
            "industry_va": {k: v_ for k, v_ in (I.get("industry_va") or {}).items() if k != "table"},
            "industry_va_table": _rec((I.get("industry_va") or {}).get("table")),
            "validation": {k: (_rec(x) if isinstance(x, pd.DataFrame) else x) for k, x in v.items()},
            "top": _rec(I["top"].drop(columns="geometry", errors="ignore"),
                        ["cluster_id", "type", "type_label", "confidence", "n_strong", "area_km2", "lon", "lat",
                         f"sol_{y1}", "adm1_name", "adm2_name", "validated"]),
        })
        written += ["industry.json", "industry_clusters.geojson"]
    else:
        write_json(out / "industry.json", {"available": False})
    Tz = R.get("tourism") or {}
    if Tz.get("available"):
        u = Tz["units"]
        write_json(out / "tourism.json", {
            "available": True, "level": Tz["level"], "params": Tz["params"], "n_units": Tz["n_units"],
            "n_tourist": Tz["n_tourist"], "class_labels": tou.CLASS, "months": tou.MONTHS,
            "units": _rec(u, ["unit_id", "name", "lat", "n_summers", "excess_median", "ref_median", "net_median",
                              "net_gain", "p_value", "class", "class_label", "confidence"]),
            "panel": _rec(Tz["panel"][Tz["panel"]["unit_id"].isin(Tz["tourist_units"])],
                          ["unit_id", "year", "excess", "ref", "net"]),
            "index": _rec(Tz["index"]), "profile": _rec(Tz["profile"]),
            "ramadan": _rec(Tz["ramadan"]),
            "validation": {k: (_rec(x) if isinstance(x, pd.DataFrame) else x) for k, x in Tz["validation"].items()},
        })
        written.append("tourism.json")
    else:
        write_json(out / "tourism.json", {"available": False})
    Uz = R.get("urban") or {}
    if Uz.get("available"):
        from . import urban as urb
        num = lambda d: d.replace([np.inf, -np.inf], np.nan)  # noqa: E731
        write_json(out / "urban.json", {
            "available": True, "level": Uz["level"], "class_labels": urb.CLASS, "class_colors": urb.CLASS_COLOR,
            "units": {lv: _rec(num(u)) for lv, u in Uz["units"].items()}, "series": _rec(Uz["series"]),
            "trend": Uz["trend"], "totals": Uz["totals"], "class_counts": Uz["class_counts"],
            "validation": Uz["validation"],
            "wdi": {k: (_rec(v) if isinstance(v, pd.DataFrame) else v) for k, v in (Uz.get("wdi") or {}).items()},
        })
        written.append("urban.json")
    else:
        write_json(out / "urban.json", {"available": False})
    # KPIs of the new use cases
    sp = out / "summary.json"
    s = json.loads(sp.read_text(encoding="utf-8"))
    fr = LANG == "fr"
    if I.get("available"):
        s["kpis"].append({"id": "industry", "label": "Grappes industrielles" if fr else "Industrial clusters",
                          "value": I["n"], "fmt": "num",
                          "sub": (f"{_clean(100 * I['series']['share_of_national'].iloc[-1]):.0f} % de la lumière nationale"
                                  if fr else f"{_clean(100 * I['series']['share_of_national'].iloc[-1]):.0f}% of national light")})
    if Tz.get("available"):
        top = Tz["units"].iloc[0]
        s["kpis"].append({"id": "tourism", "label": "Zones touristiques" if fr else "Tourist zones",
                          "value": Tz["n_tourist"], "fmt": "num",
                          "sub": (f"surcroît estival max. {100 * top['net_gain']:+.0f} % ({top['name']})".replace(".", ",")
                                  if fr else f"max. summer excess {100 * top['net_gain']:+.0f}% ({top['name']})")})
    if Uz.get("available"):
        tr = Uz["trend"]["lit"].get("growth")
        s["kpis"].append({"id": "urban", "label": "Surface éclairée" if fr else "Lit area",
                          "value": tr, "fmt": "pct",
                          "sub": (f"croissance annuelle ; population {100 * Uz['trend']['pop']['growth']:+.1f} %/an".replace(".", ",")
                                  if fr else f"annual growth; population {100 * Uz['trend']['pop']['growth']:+.1f}%/yr")})
    write_json(sp, s)
    # quality sheets and international standards (quality.json), before the agent so that it knows them
    if R.get("cfg") is not None:
        from .quality import build_quality
        try:
            build_quality(R, R["cfg"], out, messages=s.get("messages"))
            written.append("quality.json")
        except Exception as e:  # noqa: BLE001 - quality sheets must never block the export
            import logging
            logging.getLogger("ntl").warning("quality.json: %s", e)
    ctx = agent.build_context(out)
    write_json(out / "agent_context.json", ctx)
    written.append("agent_context.json")
    _ = np, names
    return written
