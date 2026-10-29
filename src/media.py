"""Images and animations generated from the country's own results (README, social preview, dashboard).

    from src import media
    MEDIA = media.build_media(cfg, GDFS, R, ANNUAL, MONTHLY, RASTERS, cfg.cache_dir / "rasters",
                              OUT / "media", NAMES, daily=DAILY, synthetic=SYNTHETIC_TEST)
    media.capture_dashboard(cfg.dashboard_dir, OUT / "media", cfg.iso3)   # optional (Playwright)

Everything is drawn locally (Pillow + matplotlib) from the cached rasters and the result dicts:
no network, no Earth Engine. Each item degrades gracefully: when its inputs are missing it is
skipped with a log message and the other items are still produced.

Files written in ``out_dir`` (``dashboard/data/<ISO3>/media``)::

    timelapse.gif / timelapse.webp / timelapse_poster.jpg   yearly night lights, cross-faded
    before_after.gif / before_after.png                       first vs last year (wipe)
    shock.gif                                                 national SA series drawn over time
    cover.jpg (1280×640, social preview) / banner.png (1600×480, README header)
    uc1.png … uc8.png                                         one vignette per use case (800×500)
    dashboard_tour.gif, screen_<page>.png                     optional, capture_dashboard()
    media.json                                                manifest (also under meta.json["media"])

Projection: the PNG overlays exported by ``acquisition.export_pngs`` are Web-Mercator rows
(``crs: EPSG:3857`` in getThumbURL); the synthetic fixture draws plain latitude rows. The row
projection is read from ``rasters["crs"]`` when present, otherwise inferred from the PNG aspect
ratio, so that vectors drawn over the rasters are exactly aligned in both cases.
"""
from __future__ import annotations

import io
import json
import shutil
import logging
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .lang import LANG

log = logging.getLogger("ntl")

# --------------------------------------------------------------------------------------
# Brand and texts
# --------------------------------------------------------------------------------------
GREEN, GREEN_DK, GREEN_LT = "#00704A", "#00553A", "#00A86A"
GOLD, BLUE, RED = "#F5C242", "#3F7FC7", "#E0475B"
NIGHT, NIGHT2, LAND = "#05080D", "#0B121B", "#0D1721"
INK, MUTED, FAINT = "#F2F5F7", "#9AA7B4", "#5D6B78"
NTL_PALETTE = ["000004", "3b0f70", "8c2981", "de4968", "fe9f6d", "fcfdbf"]   # = acquisition.NTL_VIS
NTL_RANGE = (-1.0, 2.0)                                                      # log10 nW·cm⁻²·sr⁻¹
# media palette (warm "city lights"): the magma colours of the PNGs are decoded back to log-radiance
GLOW_STOPS = [(0.0, "#0d0703"), (0.22, "#3d1c05"), (0.45, "#9c4a0c"), (0.66, "#e8962a"), (0.84, "#ffd36e"),
              (1.0, "#fffaf0")]

T = {
    "fr": {
        "ntl": "Lumières nocturnes", "title": "Lumières nocturnes — 8 cas d'usage",
        "title2": ("Lumières nocturnes :", "8 cas d'usage"),
        "tagline": "statistiques et politiques publiques · tableau de bord · agent IA",
        "tag": "BAD × DI4A", "tag_long": "Banque africaine de développement × Data Innovation for Africa (DI4A)",
        "src": "VIIRS VNL V2 · NOAA/EOG · Google Earth Engine",
        "src_m": "VIIRS DNB mensuel (VCMSLCFG) · NOAA/EOG · Google Earth Engine",
        "src_wb": "VIIRS VNL V2 · Banque mondiale (WDI)",
        "src_gh": "VIIRS · GHSL · Sentinel-5P · MODIS · OpenStreetMap",
        "unit": "nW·cm⁻²·sr⁻¹", "synth": "DONNÉES SYNTHÉTIQUES DE TEST",
        "uc": "CAS D'USAGE", "sa": "Désaisonnalisé", "obs": "Observé", "idx": "indice, 12 premiers mois = 100",
        "shock_t": "Série mensuelle désaisonnalisée", "trough": "creux",
        "titles": {1: "Dynamiques temporelles", 2: "Croissance régionale", 3: "Lumières et PIB",
                   4: "Chocs économiques", 5: "Inégalités et accès", 6: "Zones industrielles", 7: "Tourisme estival", 8: "Urbanisation"},
        "k1": "croissance annuelle de la lumière", "k2": "unités {lv} en croissance", "k3": "élasticité lumière–PIB",
        "k4": "creux du choc", "k5": "des habitants dans le noir", "k6": "grappes industrielles",
        "k7": "zones touristiques", "per_yr": "/an",
        "k8": "croissance de la surface éclairée", "k8b": "population", "lit_area": "Surface éclairée",
        "growth": "Croissance", "stable": "Stagnation", "decline": "Déclin", "na": "Indéterminé",
        "lit": "Zone habitée éclairée", "darkz": "Zone habitée dans le noir",
        "log_ntl": "log(lumière)", "log_gdp": "log(PIB réel)", "fit": "ajustement",
        "tourist": "Zones touristiques", "other": "Autres unités", "profile": "Profil mensuel",
        "of_light": "de la lumière", "peak": "surcroît estival max.",
        "tour": "Visite du tableau de bord", "screen": "Capture — {p}", "mobile": "Version mobile",
        "tl_cap": "Évolution annuelle des lumières nocturnes, {a}–{b}, avec les limites des régions.",
        "ba_cap": "Avant / après : lumières nocturnes en {a} et en {b}.",
        "sh_cap": "Série mensuelle nationale désaisonnalisée{ev}.",
        "cover_cap": "Image de partage (1280×640) — Paramètres → General → Social preview.",
        "banner_cap": "Bandeau du README.",
        "tour_cap": "Visite animée des pages du tableau de bord public.",
    },
    "en": {
        "ntl": "Night-time lights", "title": "Night-time lights — 8 use cases",
        "title2": ("Night-time lights:", "8 use cases"),
        "tagline": "statistics & public policy · dashboard · AI agent",
        "tag": "AfDB × DI4A", "tag_long": "African Development Bank × Data Innovation for Africa (DI4A)",
        "src": "VIIRS VNL V2 · NOAA/EOG · Google Earth Engine",
        "src_m": "VIIRS DNB monthly (VCMSLCFG) · NOAA/EOG · Google Earth Engine",
        "src_wb": "VIIRS VNL V2 · World Bank (WDI)",
        "src_gh": "VIIRS · GHSL · Sentinel-5P · MODIS · OpenStreetMap",
        "unit": "nW·cm⁻²·sr⁻¹", "synth": "SYNTHETIC TEST DATA",
        "uc": "USE CASE", "sa": "Seasonally adjusted", "obs": "Observed", "idx": "index, first 12 months = 100",
        "shock_t": "Seasonally adjusted monthly series", "trough": "trough",
        "titles": {1: "Temporal dynamics", 2: "Regional growth", 3: "Lights and GDP", 4: "Economic shocks",
                   5: "Inequality & access", 6: "Industrial zones", 7: "Summer tourism", 8: "Urbanisation"},
        "k1": "annual growth of light", "k2": "{lv} units growing", "k3": "light–GDP elasticity",
        "k4": "shock trough", "k5": "of residents in the dark", "k6": "industrial clusters",
        "k7": "tourist zones", "per_yr": "/yr",
        "k8": "growth of the lit area", "k8b": "population", "lit_area": "Lit area",
        "growth": "Growth", "stable": "Stagnation", "decline": "Decline", "na": "Undetermined",
        "lit": "Inhabited, lit", "darkz": "Inhabited, in the dark",
        "log_ntl": "log(light)", "log_gdp": "log(real GDP)", "fit": "fit",
        "tourist": "Tourist zones", "other": "Other units", "profile": "Monthly profile",
        "of_light": "of light", "peak": "max. summer excess",
        "tour": "Dashboard tour", "screen": "Screenshot — {p}", "mobile": "Mobile version",
        "tl_cap": "Yearly night-time lights, {a}–{b}, with regional boundaries.",
        "ba_cap": "Before / after: night-time lights in {a} and {b}.",
        "sh_cap": "National seasonally adjusted monthly series{ev}.",
        "cover_cap": "Social preview image (1280×640) — Settings → General → Social preview.",
        "banner_cap": "README header.",
        "tour_cap": "Animated tour of the public dashboard pages.",
    },
}[LANG]
UC_PAGE = {1: "time", 2: "regions", 3: "time", 4: "shocks", 5: "inequality", 6: "industry", 7: "tourism", 8: "urban"}
CLASS_KEY = {"Croissance": "growth", "Growth": "growth", "Déclin": "decline", "Decline": "decline",
             "Stagnation": "stable"}
CLASS_COLOR = {"growth": GREEN_LT, "stable": "#7C8A99", "decline": RED, "na": "#3A4652"}


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------
def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgba(h: str, a: float = 1.0) -> tuple[int, int, int, int]:
    return (*_rgb(h), int(round(255 * a)))


def _f(x, d=1) -> str:
    s = f"{x:.{d}f}".replace("-", "−")
    return s.replace(".", ",") if LANG == "fr" else s


def _pct(x, d=1, sign=True) -> str:
    if x is None or not np.isfinite(x):
        return "n/a"
    s = f"{100 * x:+.{d}f}" if sign else f"{100 * x:.{d}f}"
    s = s.replace("-", "−")
    return s.replace(".", ",") + " %" if LANG == "fr" else s + "%"


_FONTS: dict = {}


def _font(size: int, bold: bool = False):
    from PIL import ImageFont
    key = (int(size), bold)
    if key not in _FONTS:
        try:
            import matplotlib
            p = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
            _FONTS[key] = ImageFont.truetype(str(p), int(size))
        except Exception:  # noqa: BLE001
            try:
                _FONTS[key] = ImageFont.load_default(size=int(size))
            except TypeError:
                _FONTS[key] = ImageFont.load_default()
    return _FONTS[key]


def _tw(draw, s, font) -> int:
    b = draw.textbbox((0, 0), s, font=font)
    return b[2] - b[0]


def _fit_font(draw, s, size, max_w, bold=True, min_size=12):
    while size > min_size and _tw(draw, s, _font(size, bold)) > max_w:
        size -= 1
    return _font(size, bold)


def _spaced(draw, xy, s, font, fill, tracking=1.5):
    """Letter-spaced text (eyebrows); returns the width."""
    x, y = xy
    for ch in s:
        draw.text((x, y), ch, font=font, fill=fill)
        x += _tw(draw, ch, font) + tracking
    return x - xy[0]


def _pill(draw, xy, s, font, fg, bg, pad=(10, 5), r=None, anchor_right=False):
    w = _tw(draw, s, font)
    b = draw.textbbox((0, 0), s, font=font)
    h = b[3] - b[1]
    x, y = xy
    if anchor_right:
        x -= w + 2 * pad[0]
    draw.rounded_rectangle([x, y, x + w + 2 * pad[0], y + h + 2 * pad[1]], radius=r or (h // 2 + pad[1]), fill=bg)
    draw.text((x + pad[0], y + pad[1] - b[1]), s, font=font, fill=fg)
    return x + w + 2 * pad[0]


def _gradient(w, h, top=NIGHT, bottom=NIGHT2) -> np.ndarray:
    a, b = np.array(_rgb(top), np.float32) / 255, np.array(_rgb(bottom), np.float32) / 255
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    return np.broadcast_to(a * (1 - t) + b * t, (h, w, 3)).copy()


def _to_img(arr: np.ndarray):
    from PIL import Image
    return Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB")


def _over(arr: np.ndarray, layer) -> np.ndarray:
    """Alpha-composite a PIL RGBA layer (same size) over a float RGB array."""
    L = np.asarray(layer, dtype=np.float32) / 255
    a = L[..., 3:4]
    return arr * (1 - a) + L[..., :3] * a


def _entry(out_dir: Path, name: str, title: str, alt: str, caption: str, source: str) -> dict:
    from PIL import Image
    p = out_dir / name
    with Image.open(p) as im:
        w, h = im.size
    return {"file": f"media/{name}", "kind": p.suffix.lstrip(".").replace("jpeg", "jpg"), "title": title, "alt": alt,
            "caption": caption, "source": source, "width": w, "height": h, "bytes": p.stat().st_size}


# --------------------------------------------------------------------------------------
# Geography: raster placement and vector drawing in the raster's own projection
# --------------------------------------------------------------------------------------
def _ramp(stops, n=256) -> np.ndarray:
    ts = np.array([t for t, _ in stops])
    cs = np.array([_rgb(c) for _, c in stops], np.float32)
    x = np.linspace(0, 1, n)
    return np.stack([np.interp(x, ts, cs[:, k]) for k in range(3)], -1).astype(np.float32)


_LUT: dict = {}


def _decode_magma(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """uint8 RGB coloured with NTL_PALETTE -> position t in [0, 1] and RGB distance to the palette."""
    if "lut" not in _LUT:
        pal = np.array([_rgb(c) for c in NTL_PALETTE], np.float32)
        x = np.linspace(0, len(pal) - 1, 512)
        i = np.minimum(x.astype(int), len(pal) - 2)
        f = (x - i)[:, None]
        ramp = pal[i] * (1 - f) + pal[i + 1] * f                      # 512 × 3
        c = np.arange(4, 256, 8, dtype=np.float32)                    # 32 bins per channel
        grid = np.stack(np.meshgrid(c, c, c, indexing="ij"), -1).reshape(-1, 3)
        best = np.empty(len(grid), np.int32)
        err = np.empty(len(grid), np.float32)
        for k in range(0, len(grid), 4096):
            dd = ((grid[k:k + 4096, None, :] - ramp[None]) ** 2).sum(-1)
            best[k:k + 4096] = dd.argmin(1)
            err[k:k + 4096] = np.sqrt(dd.min(1))
        _LUT["lut"] = (best.astype(np.float32) / 511).reshape(32, 32, 32)
        _LUT["err"] = err.reshape(32, 32, 32)
    q = (rgb // 8).astype(np.intp)
    t = _LUT["lut"][q[..., 0], q[..., 1], q[..., 2]]
    e = _LUT["err"][q[..., 0], q[..., 1], q[..., 2]]
    return t, e


def _merc(lat):
    lat = np.clip(np.asarray(lat, dtype=float), -85, 85)
    return np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))


class _Geo:
    """Maps lon/lat to fractions of the raster frame, in the projection the PNG rows use."""

    def __init__(self, rasters: dict | None, raster_dir: Path | None, gdfs: dict, synthetic: bool = False):
        from PIL import Image
        self.dir = Path(raster_dir) if raster_dir else None
        self.idx = rasters or {}
        self.gdfs = gdfs or {}
        b = self.idx.get("bounds")
        if not b and "ADM0" in self.gdfs:
            b = list(self.gdfs["ADM0"].total_bounds)
        self.w, self.s, self.e, self.n = [float(v) for v in b]
        self.years = sorted(int(y) for y, f in (self.idx.get("ntl") or {}).items()
                            if self.dir and (self.dir / f).exists())
        lin = (self.e - self.w) / (self.n - self.s)
        mer = math.radians(self.e - self.w) / float(_merc(self.n) - _merc(self.s))
        aspect = None
        if self.years:
            with Image.open(self.dir / self.idx["ntl"][str(self.years[-1])]) as im:
                aspect = im.size[0] / im.size[1]
        crs = str(self.idx.get("crs") or "").upper()
        if crs in ("EPSG:4326", "EPSG:3857"):
            self.mercator = crs == "EPSG:3857"
        elif aspect is not None and abs(math.log(aspect / lin) - math.log(aspect / mer)) > 0.02:
            self.mercator = abs(math.log(aspect / mer)) < abs(math.log(aspect / lin))
        else:
            self.mercator = not synthetic
        self.aspect = aspect or (mer if self.mercator else lin)
        self._y0, self._y1 = self._y(self.n), self._y(self.s)
        self._cache: dict = {}

    def _y(self, lat):
        return _merc(lat) if self.mercator else np.asarray(lat, dtype=float)

    def fit(self, box, align="center") -> tuple[int, int, int, int]:
        """Largest raster-aspect rectangle inside box=(x, y, w, h)."""
        x, y, w, h = box
        if w / h > self.aspect:
            mw, mh = h * self.aspect, h
        else:
            mw, mh = w, w / self.aspect
        dx = {"left": 0, "right": w - mw}.get(align, (w - mw) / 2)
        return int(round(x + dx)), int(round(y + (h - mh) / 2)), int(round(mw)), int(round(mh))

    def px(self, lon, lat, mb, scale=1.0):
        x0, y0, w, h = mb
        fx = (np.asarray(lon, float) - self.w) / (self.e - self.w)
        fy = (self._y0 - self._y(lat)) / (self._y0 - self._y1)
        return (x0 + fx * w) * scale, (y0 + fy * h) * scale

    # ---- rasters -----------------------------------------------------------------------------
    def png(self, kind: str, year) -> Path | None:
        f = (self.idx.get(kind) or {}).get(str(year))
        p = self.dir / f if (f and self.dir) else None
        return p if p and p.exists() else None

    def light(self, path: Path, size: tuple[int, int], glow: float = 1.0, gain: float = 1.0) -> np.ndarray:
        """Premultiplied light (+ soft glow) as float RGB of `size`, ready to add on a dark base."""
        from PIL import Image, ImageFilter
        key = (str(path), size, glow, gain)
        if key in self._cache:
            return self._cache[key]
        with Image.open(path) as im:
            im = im.convert("RGBA").resize(size, Image.LANCZOS)
        u = np.asarray(im)
        a = u[..., 3:4].astype(np.float32) / 255
        t, err = _decode_magma(u[..., :3])
        vis = u[..., 3] > 0
        if vis.any() and float(err[vis].mean()) < 24:                  # recolour the magma PNG with the warm media palette
            ramp = _ramp(GLOW_STOPS) / 255
            L = ramp[np.clip((t * 255).astype(int), 0, 255)] * a * gain
        else:                                           # unknown palette: keep the PNG colours
            L = u[..., :3].astype(np.float32) / 255 * a * gain
        if glow > 0:
            r = max(1.5, size[0] / 160)
            g1 = np.asarray(_to_img(L).filter(ImageFilter.GaussianBlur(r)), np.float32) / 255
            g2 = np.asarray(_to_img(L).filter(ImageFilter.GaussianBlur(r * 3)), np.float32) / 255
            g = 0.75 * g1 + 0.25 * g2
            lum = g.mean(axis=-1, keepdims=True)                 # warm, desaturated halo (sodium/LED glow)
            g = 0.35 * g + 0.65 * lum * np.array([1.0, 0.80, 0.55], np.float32)
            L = L + glow * g
        L = L.astype(np.float32)
        if len(self._cache) < 64:
            self._cache[key] = L
        return L

    def mask_rgba(self, path: Path, size):
        from PIL import Image
        with Image.open(path) as im:
            return im.convert("RGBA").resize(size, Image.NEAREST)

    # ---- vectors -----------------------------------------------------------------------------
    def _rings(self, geom):
        if geom is None or geom.is_empty:
            return []
        polys = [geom] if geom.geom_type == "Polygon" else list(getattr(geom, "geoms", []))
        out = []
        for p in polys:
            if p.geom_type != "Polygon":
                continue
            a0 = abs(p.area) or 1.0     # ignore sliver holes left by unions of admin units
            holes = [np.asarray(i.coords) for i in p.interiors if abs(type(p)(i).area) > 0.005 * a0]
            out.append((np.asarray(p.exterior.coords), holes))
        return out

    def layer(self, size, mb, geoms, fill=None, outline=None, width=1.0, ss=2, simplify=True):
        """RGBA PIL layer of `size` with polygons drawn (anti-aliased by supersampling)."""
        from PIL import Image, ImageDraw
        W, H = size
        big = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
        d = ImageDraw.Draw(big)
        tol = (self.e - self.w) / max(mb[2], 1) / 2 if simplify else 0
        fills = fill if isinstance(fill, (list, tuple)) and fill and isinstance(fill[0], tuple) else None
        for i, g in enumerate(geoms):
            if g is None or g.is_empty:
                continue
            if tol:
                g = g.simplify(tol, preserve_topology=True)
            fc = fills[i] if fills else fill
            for ext, holes in self._rings(g):
                xs, ys = self.px(ext[:, 0], ext[:, 1], mb, ss)
                pts = list(zip(xs.tolist(), ys.tolist()))
                if len(pts) < 3:
                    continue
                if fc:
                    d.polygon(pts, fill=fc)
                    for h in holes:
                        hx, hy = self.px(h[:, 0], h[:, 1], mb, ss)
                        d.polygon(list(zip(hx.tolist(), hy.tolist())), fill=(0, 0, 0, 0))
                if outline and width > 0:
                    d.line(pts + [pts[0]], fill=outline, width=max(1, int(round(width * ss))), joint="curve")
        return big.resize((W, H), Image.LANCZOS) if ss > 1 else big

    def boundaries(self, size, mb, adm1=True, c0=(235, 242, 248, 140), c1=(235, 242, 248, 46), w0=1.3, w1=0.8):
        from PIL import Image
        lay = Image.new("RGBA", size, (0, 0, 0, 0))
        if adm1 and "ADM1" in self.gdfs:
            lay = Image.alpha_composite(lay, self.layer(size, mb, list(self.gdfs["ADM1"].geometry), outline=c1, width=w1))
        if "ADM0" in self.gdfs:
            lay = Image.alpha_composite(lay, self.layer(size, mb, list(self.gdfs["ADM0"].geometry), outline=c0, width=w0))
        return lay

    def land(self, size, mb, color=LAND):
        if "ADM0" not in self.gdfs:
            from PIL import Image
            return Image.new("RGBA", size, (0, 0, 0, 0))
        return self.layer(size, mb, list(self.gdfs["ADM0"].geometry), fill=_rgba(color, 1.0))


def _colorbar(img, draw, x, y, w, h=7, labels=True, color=MUTED):
    from PIL import Image
    row = _ramp(GLOW_STOPS, w).astype(np.uint8)
    bar = Image.fromarray(np.repeat(row[None], h, 0), "RGB")
    img.paste(bar.convert(img.mode), (x, y))
    if labels:
        ft = _font(10)
        lo, hi = NTL_RANGE
        for v in range(int(lo), int(hi) + 1):
            xx = x + (v - lo) / (hi - lo) * (w - 1)
            s = _f(10.0 ** v, 1 if v < 0 else 0)
            draw.text((xx, y + h + 3), s, font=ft, fill=color, anchor="ma")
        draw.text((x + w + 8, y - 3), T["unit"], font=ft, fill=color)


# --------------------------------------------------------------------------------------
# GIF / WebP encoding
# --------------------------------------------------------------------------------------
def _quantize_all(frames, colors: int):
    from PIL import Image
    pick = [frames[0], frames[len(frames) // 2], frames[-1]]
    w, h = pick[0].size
    sample = Image.new("RGB", (w * len(pick), h))
    for k, f in enumerate(pick):
        sample.paste(f, (k * w, 0))
    if w * len(pick) > 1800:
        sample = sample.resize((1800, max(1, int(h * 1800 / (w * len(pick))))))
    pal = sample.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    return [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]


def _save_gif(frames, durations, path: Path, max_bytes: int, widths=(900, 820, 760, 700, 640, 560),
              colors=(160, 128, 96, 64)) -> bool:
    """Encode with a shared palette; shrink width/colours until the file fits `max_bytes`."""
    from PIL import Image
    W0 = frames[0].size[0]
    tried = []
    for w in [w for w in widths if w <= W0] or [W0]:
        fr = frames if w == W0 else [f.resize((w, round(f.size[1] * w / W0)), Image.LANCZOS) for f in frames]
        for c in colors:
            q = _quantize_all(fr, c)
            buf = io.BytesIO()
            q[0].save(buf, format="GIF", save_all=True, append_images=q[1:], duration=list(durations), loop=0,
                      optimize=False, disposal=1)
            tried.append((w, c, buf.tell()))
            if buf.tell() <= max_bytes:
                path.write_bytes(buf.getvalue())
                return True
    path.write_bytes(buf.getvalue())
    log.warning("media: %s above the size target (%s)", path.name, tried[-1])
    return False


def _save_webp(frames, durations, path: Path, max_bytes: int = 8_000_000) -> None:
    for q in (82, 72, 60, 48):
        buf = io.BytesIO()
        frames[0].save(buf, format="WEBP", save_all=True, append_images=frames[1:], duration=list(durations),
                       loop=0, quality=q, method=4)
        if buf.tell() <= max_bytes:
            break
    path.write_bytes(buf.getvalue())


# --------------------------------------------------------------------------------------
# Map canvases (timelapse, before/after)
# --------------------------------------------------------------------------------------
def _canvas_layout(geo: _Geo, W: int, header=112, footer=96, side=28, Hmin=600, Hmax=1000):
    mw = W - 2 * side
    mh = mw / geo.aspect
    H = int(min(max(mh + header + footer, Hmin), Hmax))
    box = (side, header, W - 2 * side, H - header - footer)
    return H, geo.fit(box)


_FLAG = None   # country flag (PIL RGBA), set by build_media from the cache (flags.ensure_flag)


def _header(draw, W, country, subtitle, synthetic):
    from .flags import paste_flag
    fx = paste_flag(draw._image, _FLAG, (28, 27), 30) if _FLAG is not None else 0
    x = 28 + (fx + 12 if fx else 0)
    draw.text((x, 24), country, font=_fit_font(draw, country, 30, W * 0.55 - (x - 28)), fill=INK)
    draw.text((28, 66), subtitle, font=_font(16), fill=MUTED)
    draw.rectangle([28, 96, 64, 98], fill=GREEN_LT)


def _footer(img, draw, W, H, source, cbar=True, synthetic=False):
    if cbar:
        _colorbar(img, draw, 28, H - 54, 150)
    x = _pill(draw, (W - 28, H - 58), T["tag"], _font(12, True), "#FFFFFF", GREEN, pad=(10, 5), anchor_right=True)
    if synthetic:
        w = _tw(draw, T["tag"], _font(12, True)) + 20
        _pill(draw, (W - 28 - w - 10, H - 56), T["synth"], _font(10, True), NIGHT, GOLD, pad=(8, 4), anchor_right=True)
    draw.text((28, H - 22), source, font=_font(11), fill=FAINT)


def _ease(t):
    return 0.5 - 0.5 * math.cos(math.pi * t)


def _timelapse(geo, cfg, country, out_dir, synthetic, W=900):
    from PIL import Image, ImageDraw
    years = [y for y in geo.years if cfg.start_year - 1 <= y <= (cfg.end_year or 9999)] or geo.years
    if len(years) < 2:
        log.info("media: timelapse skipped (fewer than 2 yearly rasters)")
        return []
    H, mb = _canvas_layout(geo, W, footer=112)
    size = (W, H)
    base = _gradient(W, H)
    base = _over(base, geo.land(size, mb))
    lights = {y: geo.light(geo.png("ntl", y), (mb[2], mb[3])) for y in years}
    over = Image.new("RGBA", size, (0, 0, 0, 0))
    over = Image.alpha_composite(over, geo.boundaries(size, mb))
    d = ImageDraw.Draw(over)
    _header(d, W, country, f"{T['ntl']} · {years[0]}–{years[-1]}", synthetic)
    _footer(over, d, W, H, T["src"] + " · " + T["tag_long"], synthetic=synthetic)
    # timeline track
    tx0, tx1, ty = 28, W - 28, H - 84
    d.line([tx0, ty, tx1, ty], fill=_rgba("#FFFFFF", 0.14), width=2)
    for k, y in enumerate(years):
        xx = tx0 + k / (len(years) - 1) * (tx1 - tx0)
        d.ellipse([xx - 2, ty - 2, xx + 2, ty + 2], fill=_rgba("#FFFFFF", 0.35))
    ft = _font(10)
    d.text((tx0, ty + 7), str(years[0]), font=ft, fill=FAINT)
    d.text((tx1, ty + 7), str(years[-1]), font=ft, fill=FAINT, anchor="ra")
    O = np.asarray(over, np.float32) / 255
    Oa, Oc = O[..., 3:4], O[..., :3] * O[..., 3:4]
    x0, y0, mw, mh = mb
    fbig = _font(64, True)

    def frame(L, k_float, labels):
        arr = base.copy()
        arr[y0:y0 + mh, x0:x0 + mw] += L
        arr = np.clip(arr, 0, 1) * (1 - Oa) + Oc
        im = _to_img(arr)
        dd = ImageDraw.Draw(im, "RGBA")
        xx = tx0 + k_float / (len(years) - 1) * (tx1 - tx0)
        dd.line([tx0, ty, xx, ty], fill=GOLD, width=2)
        dd.ellipse([xx - 5, ty - 5, xx + 5, ty + 5], fill=GOLD)
        for s, a, dy in labels:
            if a > 0.02:
                dd.text((W - 28, 20 + dy), s, font=fbig, fill=(*_rgb(GOLD), int(255 * a)), anchor="ra")
        return im

    frames, durs = [], []
    n_fade = 4
    for k, y in enumerate(years):
        frames.append(frame(lights[y], k, [(str(y), 1.0, 0)]))
        durs.append(2600 if k == len(years) - 1 else 900)
        if k < len(years) - 1:
            y2 = years[k + 1]
            for j in range(1, n_fade + 1):
                t = _ease(j / (n_fade + 1))
                lab = ([(str(y), max(0.0, 1 - 2 * t), -int(14 * t))] if t < 0.5 else
                       [(str(y2), min(1.0, 2 * t - 1), int(14 * (1 - t)))])     # roll: out upwards, in from below
                frames.append(frame(lights[y] * (1 - t) + lights[y2] * t, k + t, lab))
                durs.append(70)
    gif = out_dir / "timelapse.gif"
    _save_gif(frames, durs, gif, 5_000_000)
    _save_webp(frames, durs, out_dir / "timelapse.webp")
    frames[-1].save(out_dir / "timelapse_poster.jpg", quality=88, optimize=True, progressive=True)
    cap = T["tl_cap"].format(a=years[0], b=years[-1])
    title = f"{T['ntl']} — {country}, {years[0]}–{years[-1]}"
    return [("timelapse", _entry(out_dir, "timelapse.gif", title, title, cap, T["src"])),
            ("timelapse_webp", _entry(out_dir, "timelapse.webp", title, title, cap, T["src"])),
            ("timelapse_poster", _entry(out_dir, "timelapse_poster.jpg", f"{title} ({years[-1]})",
                                        f"{T['ntl']} — {country}, {years[-1]}", cap, T["src"]))]


def _before_after(geo, cfg, country, out_dir, synthetic, W=900):
    from PIL import Image, ImageDraw
    if len(geo.years) < 2:
        log.info("media: before/after skipped (fewer than 2 yearly rasters)")
        return []
    ya, yb = geo.years[0], geo.years[-1]
    H, mb = _canvas_layout(geo, W, footer=80)
    size = (W, H)
    land = _over(_gradient(W, H), geo.land(size, mb))
    x0, y0, mw, mh = mb
    full = {}
    bnd = geo.boundaries(size, mb)
    for y in (ya, yb):
        a = land.copy()
        a[y0:y0 + mh, x0:x0 + mw] += geo.light(geo.png("ntl", y), (mw, mh))
        full[y] = _over(np.clip(a, 0, 1), bnd)
    over = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    _header(d, W, country, f"{T['ntl']} · {ya} → {yb}", synthetic)
    _footer(over, d, W, H, T["src"] + " · " + T["tag_long"], synthetic=synthetic)
    O = np.asarray(over, np.float32) / 255
    Oa, Oc = O[..., 3:4], O[..., :3] * O[..., 3:4]
    fl = _font(30, True)
    frames, durs = [], []
    n = 44
    cols = np.arange(W)[None, :, None]
    for k in range(n):
        t = k / n
        pos = 0.5 + 0.36 * math.sin(2 * math.pi * t)
        xd = int(x0 + pos * mw)
        arr = np.where(cols < xd, full[ya], full[yb])
        arr = arr * (1 - Oa) + Oc
        im = _to_img(arr)
        dd = ImageDraw.Draw(im, "RGBA")
        dd.line([xd, y0 - 6, xd, y0 + mh + 6], fill=(255, 255, 255, 230), width=2)
        cy = y0 + mh // 2
        dd.ellipse([xd - 15, cy - 15, xd + 15, cy + 15], fill=(255, 255, 255, 235))
        dd.polygon([(xd - 9, cy), (xd - 3, cy - 6), (xd - 3, cy + 6)], fill=NIGHT)
        dd.polygon([(xd + 9, cy), (xd + 3, cy - 6), (xd + 3, cy + 6)], fill=NIGHT)
        dd.text((28, y0 + 4), str(ya), font=fl, fill=INK)
        dd.text((W - 28, y0 + 4), str(yb), font=fl, fill=GOLD, anchor="ra")
        frames.append(im)
        durs.append(1200 if k in (n // 4, 3 * n // 4) else 60)
    _save_gif(frames, durs, out_dir / "before_after.gif", 4_000_000)
    # side-by-side still
    pw = 600
    H2, mb2 = _canvas_layout(geo, pw, header=0, footer=0, side=20, Hmin=300, Hmax=760)
    Wt, Ht = 2 * pw, H2 + 220
    canvas = _gradient(Wt, Ht)
    for j, y in enumerate((ya, yb)):
        m = (mb2[0] + j * pw, mb2[1] + 160, mb2[2], mb2[3])
        sz = (Wt, Ht)
        canvas = _over(canvas, geo.land(sz, m))
        canvas[m[1]:m[1] + m[3], m[0]:m[0] + m[2]] += geo.light(geo.png("ntl", y), (m[2], m[3]))
        canvas = _over(np.clip(canvas, 0, 1), geo.boundaries(sz, m))
    im = _to_img(canvas)
    d = ImageDraw.Draw(im, "RGBA")
    _header(d, Wt, country, f"{T['ntl']} · {ya} → {yb}", synthetic)
    d.text((pw // 2, 112), str(ya), font=_font(34, True), fill=INK, anchor="ma")
    d.text((pw + pw // 2, 112), str(yb), font=_font(34, True), fill=GOLD, anchor="ma")
    d.line([pw, 120, pw, Ht - 80], fill=(255, 255, 255, 40), width=1)
    _footer(im, d, Wt, Ht, T["src"] + " · " + T["tag_long"], synthetic=synthetic)
    im.save(out_dir / "before_after.png", optimize=True)
    cap = T["ba_cap"].format(a=ya, b=yb)
    title = f"{country}: {ya} → {yb}"
    return [("before_after", _entry(out_dir, "before_after.gif", title, cap, cap, T["src"])),
            ("before_after_still", _entry(out_dir, "before_after.png", title, cap, cap, T["src"]))]


# --------------------------------------------------------------------------------------
# Charts (matplotlib, dark)
# --------------------------------------------------------------------------------------
def _mpl_style():
    import matplotlib
    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10, "text.color": INK, "axes.labelcolor": MUTED,
        "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": "#24303C", "axes.facecolor": "none",
        "figure.facecolor": "none", "savefig.facecolor": "none", "axes.grid": True, "grid.color": "#FFFFFF",
        "grid.alpha": 0.07, "grid.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
        "axes.spines.left": False, "legend.frameon": False, "legend.labelcolor": MUTED})
    return plt


def _fig_rgba(fig):
    fig.canvas.draw()
    return np.asarray(fig.canvas.buffer_rgba()).copy()


def _national_sa(R) -> pd.DataFrame | None:
    stl = ((R or {}).get("dyn") or {}).get("stl")
    if stl is None or not len(stl) or "sa_level" not in stl:
        return None
    df = stl.copy()
    df.index = pd.to_datetime(df.index)
    return df.sort_index()


def _shock_info(R) -> dict | None:
    sh = (R or {}).get("shocks") or {}
    imp = sh.get("impacts")
    ev = sh.get("events")
    row = None
    if isinstance(imp, pd.DataFrame) and len(imp):
        ok = imp[imp.get("computable", True) == True] if "computable" in imp else imp  # noqa: E712
        if len(ok) and "trough_pct" in ok:
            row = ok.loc[ok["trough_pct"].astype(float).idxmin()]
    if row is None and isinstance(ev, pd.DataFrame) and len(ev):
        row = ev.iloc[0]
    if row is None:
        return None
    g = row.get
    return {"label": str(g("label") or g("id") or ""), "start": pd.to_datetime(g("start"), errors="coerce"),
            "end": pd.to_datetime(g("end"), errors="coerce"),
            "trough_date": pd.to_datetime(g("trough_date"), errors="coerce") if g("trough_date") is not None else pd.NaT,
            "trough_pct": float(g("trough_pct")) if g("trough_pct") is not None and pd.notna(g("trough_pct")) else None,
            "months": g("months_to_recovery")}


def _shock_gif(R, country, out_dir, synthetic):
    from PIL import Image
    df = _national_sa(R)
    if df is None:
        log.info("media: shock animation skipped (no national seasonally adjusted series)")
        return []
    plt = _mpl_style()
    base = df["sa_level"].iloc[:12].mean()
    sa = 100 * df["sa_level"] / base
    obs = 100 * df["obs"] / base if "obs" in df else None
    info = _shock_info(R)
    W, Hh, dpi = 900, 506, 100
    fig = plt.figure(figsize=(W / dpi, Hh / dpi), dpi=dpi)
    fig.patch.set_facecolor(NIGHT)
    ax = fig.add_axes([0.075, 0.15, 0.895, 0.58])
    x = sa.index
    ax.set_xlim(x[0] - pd.Timedelta(days=20), x[-1] + pd.Timedelta(days=20))
    vals = pd.concat([sa, obs]) if obs is not None else sa
    lo, hi = float(vals.min()), float(vals.max())
    ax.set_ylim(lo - 0.06 * (hi - lo), hi + 0.12 * (hi - lo))
    ax.tick_params(length=0, labelsize=12)
    ev_txt = ""
    if info and pd.notna(info["start"]):
        end = info["end"] if pd.notna(info["end"]) else info["start"] + pd.DateOffset(months=12)
        ax.axvspan(info["start"], end, color=GOLD, alpha=0.10, lw=0)
        ax.text(info["start"] + (end - info["start"]) / 2, hi + 0.08 * (hi - lo), info["label"], color=GOLD,
                ha="center", va="center", fontsize=10, fontweight="bold")
        ev_txt = f" — {info['label']}"
    lo_obs, = ax.plot([], [], color="#8796A5", lw=0.9, alpha=0.55)
    glow, = ax.plot([], [], color=GREEN_LT, lw=7, alpha=0.18, solid_capstyle="round")
    line, = ax.plot([], [], color=GREEN_LT, lw=2.3, solid_capstyle="round")
    head, = ax.plot([], [], "o", color="#FFFFFF", ms=5)
    tr = None
    if info and info.get("trough_pct") is not None and pd.notna(info["trough_date"]) and info["trough_date"] in sa.index:
        tr = (info["trough_date"], float(sa.loc[info["trough_date"]]), info["trough_pct"])
    tdot, = ax.plot([], [], "o", color=GOLD, ms=8, mec=NIGHT, mew=1.5)
    ttxt = ax.annotate("", xy=(0, 0), xytext=(14, 0), textcoords="offset points", ha="left", va="center",
                       color=GOLD, fontsize=11, fontweight="bold")
    fig.text(0.075, 0.90, country, fontsize=19, fontweight="bold", color=INK)
    fig.text(0.075, 0.835, f"{T['shock_t']} · {T['idx']}", fontsize=11, color=MUTED)
    fig.text(0.075, 0.045, T["src_m"], fontsize=8.5, color=FAINT)
    fig.text(0.97, 0.045, T["tag"] + (f"  ·  {T['synth']}" if synthetic else ""), fontsize=8.5, color=GREEN_LT,
             ha="right", fontweight="bold")
    from matplotlib.lines import Line2D
    ax.legend([Line2D([], [], color=GREEN_LT, lw=2.3), Line2D([], [], color="#8796A5", lw=1)],
              [T["sa"], T["obs"]], loc="upper left", fontsize=9, ncol=2, bbox_to_anchor=(0, 1.02))
    n = len(sa)
    steps = np.unique(np.linspace(2, n, min(n - 1, 80)).astype(int))
    frames, durs = [], []
    for k in steps:
        xs, ys = x[:k], sa.values[:k]
        line.set_data(xs, ys)
        glow.set_data(xs, ys)
        head.set_data([xs[-1]], [ys[-1]])
        if obs is not None:
            lo_obs.set_data(xs, obs.values[:k])
        if tr is not None and xs[-1] >= tr[0]:
            tdot.set_data([tr[0]], [tr[1]])
            ttxt.xy = (tr[0], tr[1])
            ttxt.set_text(f"{_pct(tr[2] / 100, 1)}  ·  {tr[0]:%m/%Y}")
        frames.append(Image.fromarray(_fig_rgba(fig)[..., :3]))
        durs.append(120)
    head.set_data([], [])
    final = Image.fromarray(_fig_rgba(fig)[..., :3])
    frames = [final] + frames + [final]          # first frame = complete chart (still shown when motion is reduced)
    durs = [1800] + durs + [3500]
    plt.close(fig)
    _save_gif(frames, durs, out_dir / "shock.gif", 4_000_000, widths=(900, 800, 720))
    frames[-1].save(out_dir / "shock_still.png", optimize=True)
    cap = T["sh_cap"].format(ev=ev_txt)
    if tr is not None:
        cap += f" {T['trough'].capitalize()} : {_pct(tr[2] / 100, 1)} ({tr[0]:%m/%Y})." if LANG == "fr" else \
            f" {T['trough'].capitalize()}: {_pct(tr[2] / 100, 1)} ({tr[0]:%m/%Y})."
    title = f"{T['shock_t']} — {country}"
    return [("shock", _entry(out_dir, "shock.gif", title, cap, cap, T["src_m"])),
            ("shock_still", _entry(out_dir, "shock_still.png", title, cap, cap, T["src_m"]))]


# --------------------------------------------------------------------------------------
# Cover and banner
# --------------------------------------------------------------------------------------
def _cover(geo, cfg, country, out_dir, synthetic, W, H, name, compact=False):
    from PIL import Image, ImageDraw
    y0, y1 = cfg.start_year, cfg.end_year
    size = (W, H)
    # background: night gradient + soft radial halo behind the map
    arr = _gradient(W, H, "#04070B", "#0A121C")
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = W * 0.72, H * 0.5
    halo = np.exp(-(((xx - cx) / (W * 0.35)) ** 2 + ((yy - cy) / (H * 0.6)) ** 2))[..., None]
    arr += halo * (np.array(_rgb(GREEN_DK), np.float32) / 255) * 0.22
    mbox = (int(W * 0.47), int(H * 0.06), int(W * 0.50), int(H * 0.88))
    mb = geo.fit(mbox)
    yr = geo.years[-1] if geo.years else None
    arr = _over(arr, geo.land(size, mb, "#0C1520"))
    if yr is not None:
        arr[mb[1]:mb[1] + mb[3], mb[0]:mb[0] + mb[2]] += geo.light(geo.png("ntl", yr), (mb[2], mb[3]), glow=1.4, gain=1.1)
    arr = _over(np.clip(arr, 0, 1), geo.boundaries(size, mb, adm1=True, c0=(255, 255, 255, 90), c1=(255, 255, 255, 26)))
    # left-to-right dark veil for legibility
    t = np.clip((xx[..., None] - W * 0.30) / (W * 0.30), 0, 1)
    veil = (1 - t) * 0.86
    arr = arr * (1 - veil) + (np.array(_rgb("#04070B"), np.float32) / 255) * veil
    im = _to_img(arr)
    d = ImageDraw.Draw(im, "RGBA")
    X = int(W * 0.05)
    s = H / 640 if not compact else H / 520
    # brand row
    yb = int(H * 0.085)
    d.rectangle([X, yb + 2, X + 6, yb + 22], fill=GREEN_LT)
    d.rectangle([X + 9, yb + 2, X + 15, yb + 22], fill=BLUE)
    _spaced(d, (X + 26, yb + 3), T["tag_long"].upper(), _font(int(12 * s) if not compact else 12, True), MUTED, 1.2)
    # title
    maxw = int(W * 0.50)
    ft = _fit_font(d, max(T["title2"], key=len), int(52 * s), maxw)
    ty = int(H * (0.25 if not compact else 0.24))
    lh = int(ft.size * 1.16)
    for k, line in enumerate(T["title2"]):
        d.text((X, ty + k * lh), line, font=ft, fill=INK)
    cy2 = ty + 2 * lh + int(16 * s)
    d.rectangle([X, cy2, X + 54, cy2 + 3], fill=GOLD)
    from .flags import paste_flag
    fh = int(34 * s * 0.95)
    fw = paste_flag(im, _FLAG, (X, cy2 + int(16 * s) + int(3 * s)), fh) if _FLAG is not None else 0
    xc = X + (fw + int(14 * s) if fw else 0)
    fc = _fit_font(d, country, int(34 * s), maxw - (xc - X))
    d.text((xc, cy2 + int(16 * s)), country, font=fc, fill=GOLD)
    py = cy2 + int(16 * s) + int(fc.size * 1.35)
    d.text((X, py), f"{y0}–{y1}  ·  VIIRS", font=_font(int(20 * s)), fill=INK)
    d.text((X, py + int(34 * s)), T["tagline"], font=_font(int(17 * s)), fill=MUTED)
    # bottom row
    fb = _font(int(12 * s) if not compact else 12, True)
    by = H - int(52 * s) if not compact else H - 46
    xx2 = _pill(d, (X, by), "AfDB" if LANG == "en" else "BAD", fb, "#FFFFFF", GREEN, pad=(10, 6))
    d.text((xx2 + 8, by + 4), "×", font=fb, fill=MUTED)
    xx3 = _pill(d, (xx2 + 26, by), "DI4A", fb, "#FFFFFF", BLUE, pad=(10, 6))
    if synthetic:
        _pill(d, (xx3 + 14, by), T["synth"], fb, NIGHT, GOLD, pad=(10, 6))
    d.text((W - X, H - int(22 * s) if not compact else H - 20),
           T["src"] + (f" · {yr}" if yr else ""), font=_font(10 if compact else int(11 * s)), fill=FAINT, anchor="rs")
    p = out_dir / name
    if p.suffix == ".jpg":
        im.save(p, quality=90, optimize=True, progressive=True)
    else:
        im.save(p, optimize=True)
    return p


def _covers(geo, cfg, country, out_dir, synthetic):
    _cover(geo, cfg, country, out_dir, synthetic, 1280, 640, "cover.jpg")
    _cover(geo, cfg, country, out_dir, synthetic, 1600, 480, "banner.png", compact=True)
    alt = f"{T['title']} — {country}, {cfg.start_year}–{cfg.end_year}"
    return [("cover", _entry(out_dir, "cover.jpg", alt, alt, T["cover_cap"], T["src"])),
            ("banner", _entry(out_dir, "banner.png", alt, alt, T["banner_cap"], T["src"]))]


# --------------------------------------------------------------------------------------
# Use-case vignettes (800×500)
# --------------------------------------------------------------------------------------
VW, VH = 800, 500
CBOX = (24, 112, 752, 346)      # content area


def _card(n: int, kpi: str, kpi_label: str, source: str, synthetic: bool):
    """Return (float RGB background, RGBA overlay) for vignette n."""
    from PIL import Image, ImageDraw
    arr = _gradient(VW, VH, "#070B11", "#0B131C")
    over = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    d.rectangle([0, 0, VW, 3], fill=GREEN)
    _spaced(d, (28, 20), f"{T['uc']} {n}", _font(14, True), GREEN_LT, 2.0)
    fk = _fit_font(d, kpi, 42, 280)
    kw = _tw(d, kpi, fk)
    title = T["titles"][n]
    d.text((28, 42), title, font=_fit_font(d, title, 31, VW - 90 - kw - 30), fill=INK)
    d.text((VW - 28, 12), kpi, font=fk, fill=GOLD, anchor="ra")
    d.text((VW - 28, 66), kpi_label, font=_fit_font(d, kpi_label, 15, 420, bold=False, min_size=10), fill=MUTED, anchor="ra")
    d.line([28, 98, VW - 28, 98], fill=(255, 255, 255, 22), width=1)
    d.text((28, VH - 22), source, font=_font(12), fill=FAINT)
    d.text((VW - 28, VH - 22), T["tag"] + (f" · {T['synth']}" if synthetic else ""), font=_font(12, True),
           fill=GREEN_LT if not synthetic else GOLD, anchor="ra")
    return arr, over


def _finish(arr, over, path):
    _to_img(_over(np.clip(arr, 0, 1), over)).save(path, optimize=True)


def _paste_chart(arr, rgba, box=CBOX):
    x, y, w, h = box
    a = rgba.astype(np.float32) / 255
    arr[y:y + h, x:x + w] = arr[y:y + h, x:x + w] * (1 - a[..., 3:4]) + a[..., :3] * a[..., 3:4]
    return arr


def _chart_fig(box=CBOX):
    plt = _mpl_style()
    fig = plt.figure(figsize=(box[2] / 100, box[3] / 100), dpi=100)
    return plt, fig


def _legend(d, x, y, items, fs=15):
    f = _font(fs)
    for k, (c, s) in enumerate(items):
        yy = y + k * (fs + 11)
        d.rounded_rectangle([x, yy + 2, x + 14, yy + 16], radius=3, fill=c)
        d.text((x + 22, yy), s, font=f, fill=INK)


def _map_card(geo, n, kpi, label, source, synthetic, year=None, gain=1.0, glow=0.8, legend_w=230):
    """Card with the country map on the right part of the content area; returns arr, over, mb, legend xy."""
    arr, over = _card(n, kpi, label, source, synthetic)
    x, y, w, h = CBOX
    mb = geo.fit((x + legend_w, y, w - legend_w, h), align="center")
    if mb[2] < w - legend_w - 40:          # tall country: centre in the free space
        pass
    arr = _over(arr, geo.land((VW, VH), mb))
    yr = year if year is not None else (geo.years[-1] if geo.years else None)
    if yr is not None and geo.png("ntl", yr):
        arr[mb[1]:mb[1] + mb[3], mb[0]:mb[0] + mb[2]] += geo.light(geo.png("ntl", yr), (mb[2], mb[3]), glow=glow, gain=gain)
    return arr, over, mb


def _uc1(R, geo, out_dir, synthetic):
    df = _national_sa(R)
    if df is None:
        return None
    nt = (R.get("dyn") or {}).get("national_trend") or {}
    g = nt.get("growth")
    kpi = (_pct(g, 1) + T["per_yr"]) if g is not None else "—"
    arr, over = _card(1, kpi, T["k1"], T["src_m"], synthetic)
    plt, fig = _chart_fig()
    ax = fig.add_axes([0.07, 0.12, 0.91, 0.80])
    base = df["sa_level"].iloc[:12].mean()
    ax.plot(df.index, 100 * df["obs"] / base, color="#8796A5", lw=1, alpha=0.6, label=T["obs"])
    ax.plot(df.index, 100 * df["sa_level"] / base, color=GREEN_LT, lw=6, alpha=0.15)
    ax.plot(df.index, 100 * df["sa_level"] / base, color=GREEN_LT, lw=2.2, label=T["sa"])
    ax.tick_params(length=0, labelsize=12)
    ax.legend(loc="upper left", fontsize=12)
    _paste_chart(arr, _fig_rgba(fig))
    plt.close(fig)
    _finish(arr, over, out_dir / "uc1.png")
    return T["k1"]


def _uc2(R, geo, gdfs, out_dir, synthetic):
    from PIL import ImageDraw
    tr = ((R.get("growth") or {}).get("trends") or {})
    lv = "ADM2" if "ADM2" in tr and "ADM2" in gdfs else ("ADM1" if "ADM1" in tr and "ADM1" in gdfs else None)
    if lv is None:
        return None
    t = tr[lv]
    g = gdfs[lv][["unit_id", "geometry"]].merge(t[["unit_id", "class"]], on="unit_id", how="left")
    g["key"] = g["class"].map(CLASS_KEY).fillna("na")
    cnt = g["key"].value_counts()
    kpi = f"{int(cnt.get('growth', 0))}/{len(g)}"
    arr, over, mb = _map_card(geo, 2, kpi, T["k2"].format(lv=lv), T["src"], synthetic, gain=0.9, glow=0.6)
    fills = [_rgba(CLASS_COLOR[k], 0.55) for k in g["key"]]
    lay = geo.layer((VW, VH), mb, list(g.geometry), fill=fills, outline=(5, 8, 13, 200), width=1.0)
    arr = _over(np.clip(arr, 0, 1), lay)
    arr = _over(arr, geo.boundaries((VW, VH), mb, adm1=True, c0=(255, 255, 255, 150), c1=(255, 255, 255, 70)))
    d = ImageDraw.Draw(over)
    items = [(CLASS_COLOR[k], f"{T[k]} · {int(cnt.get(k, 0))}") for k in ("growth", "stable", "decline")]
    if cnt.get("na", 0):
        items.append((CLASS_COLOR["na"], f"{T['na']} · {int(cnt['na'])}"))
    _legend(d, 32, CBOX[1] + 14, items)
    if mb[0] >= CBOX[0] + 200 and "growth" in t:          # ranked growth of every unit
        tt = t.assign(key=t["class"].map(CLASS_KEY).fillna("na")).sort_values("growth", ascending=False)
        box = (32, CBOX[1] + 130, min(210, mb[0] - 50), 205)
        plt, fig = _chart_fig(box)
        ax = fig.add_axes([0.16, 0.08, 0.82, 0.78])
        ax.bar(range(len(tt)), 100 * tt["growth"], color=[CLASS_COLOR[k] for k in tt["key"]], width=0.75)
        ax.axhline(0, color="#FFFFFF", lw=0.6, alpha=0.4)
        ax.set_xticks([])
        ax.tick_params(length=0, labelsize=9)
        ax.grid(axis="x", visible=False)
        fig.text(0.0, 0.93, ("croissance par unité, %/an" if LANG == "fr" else "growth by unit, %/yr"),
                 fontsize=10, color=MUTED)
        arr = _paste_chart(arr, _fig_rgba(fig), box)
        plt.close(fig)
    _finish(arr, over, out_dir / "uc2.png")
    return T["k2"].format(lv=lv)


def _uc3(R, geo, out_dir, synthetic):
    L = ((R.get("gdp") or {}).get("levels") or {})
    data = L.get("data")
    if data is None or not len(data) or not {"lx", "ly"} <= set(data.columns):
        return None
    b = L.get("beta")
    kpi = _f(b, 2) if b is not None else "—"
    lab = T["k3"] + (f" · R² {_f(L.get('r2'), 2)}" if L.get("r2") is not None else "")
    arr, over = _card(3, kpi, lab, T["src_wb"], synthetic)
    plt, fig = _chart_fig()
    ax = fig.add_axes([0.09, 0.15, 0.89, 0.78])
    d = data.sort_values("lx")
    if "fitted" in d:
        ax.plot(d["lx"], d["fitted"], color=GOLD, lw=2, alpha=0.9, label=T["fit"])
    ax.scatter(d["lx"], d["ly"], s=60, color=GREEN_LT, edgecolor=NIGHT, lw=1.2, zorder=3)
    if "year" in d:
        for (_, r), off, ha in zip(d.iloc[[0, -1]].iterrows(), ((10, -14), (-10, 6)), ("left", "right")):
            ax.annotate(str(int(r["year"])), (r["lx"], r["ly"]), xytext=off, textcoords="offset points",
                        color=MUTED, fontsize=12, ha=ha)
    ax.set_xlabel(T["log_gdp"], fontsize=12)
    ax.set_ylabel(T["log_ntl"], fontsize=12)
    ax.tick_params(length=0, labelsize=12)
    _paste_chart(arr, _fig_rgba(fig))
    plt.close(fig)
    _finish(arr, over, out_dir / "uc3.png")
    return T["k3"]


def _uc4(R, geo, out_dir, synthetic):
    df = _national_sa(R)
    info = _shock_info(R)
    if df is None or info is None or pd.isna(info["start"]):
        return None
    a = info["start"] - pd.DateOffset(months=24)
    b = (info["end"] if pd.notna(info["end"]) else info["start"]) + pd.DateOffset(months=24)
    w = df[(df.index >= a) & (df.index <= b)]
    if len(w) < 6:
        return None
    kpi = _pct(info["trough_pct"] / 100, 1) if info.get("trough_pct") is not None else info["label"]
    lab = T["k4"] + (f" · {info['trough_date']:%m/%Y}" if pd.notna(info["trough_date"]) else "") + f" · {info['label']}"
    arr, over = _card(4, kpi, lab, T["src_m"], synthetic)
    plt, fig = _chart_fig()
    ax = fig.add_axes([0.07, 0.12, 0.91, 0.82])
    base = w["sa_level"].iloc[:12].mean()
    end = info["end"] if pd.notna(info["end"]) else info["start"] + pd.DateOffset(months=12)
    ax.axvspan(info["start"], end, color=GOLD, alpha=0.10, lw=0)
    ax.axhline(100, color="#FFFFFF", lw=0.8, alpha=0.25, ls="--")
    ax.plot(w.index, 100 * w["obs"] / base, color="#8796A5", lw=1, alpha=0.55)
    ax.plot(w.index, 100 * w["sa_level"] / base, color=GREEN_LT, lw=2.4)
    td = info["trough_date"]
    if pd.notna(td) and td in w.index:
        v = 100 * w.loc[td, "sa_level"] / base
        ax.plot([td], [v], "o", color=GOLD, ms=9, mec=NIGHT, mew=1.5)
        ax.annotate(T["trough"], (td, v), xytext=(12, -2), textcoords="offset points", color=GOLD, fontsize=13,
                    fontweight="bold", va="center")
    ax.tick_params(length=0, labelsize=12)
    _paste_chart(arr, _fig_rgba(fig))
    plt.close(fig)
    _finish(arr, over, out_dir / "uc4.png")
    return T["k4"]


def _uc5(R, geo, out_dir, synthetic):
    from PIL import ImageDraw
    ineq = R.get("ineq") or {}
    nat = ineq.get("national")
    dk = (geo.idx.get("dark") or {})
    yr = max((int(y) for y in dk), default=None)
    p = geo.png("dark", yr) if yr is not None else None
    if p is None:
        return None
    share = None
    if isinstance(nat, pd.DataFrame) and len(nat) and "dark_share" in nat:
        share = float(nat.sort_values("year")["dark_share"].iloc[-1])
    kpi = _pct(share, 0, sign=False) if share is not None else "—"
    arr, over, mb = _map_card(geo, 5, kpi, f"{T['k5']} · {yr}", T["src_gh"], synthetic, gain=0.35, glow=0.3)
    m = geo.mask_rgba(p, (mb[2], mb[3]))
    from PIL import Image
    lay = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    lay.paste(m, (mb[0], mb[1]))
    arr = _over(np.clip(arr, 0, 1), lay)
    arr = _over(arr, geo.boundaries((VW, VH), mb, c1=(255, 255, 255, 40)))
    d = ImageDraw.Draw(over)
    _legend(d, 32, CBOX[1] + 14, [(GOLD, T["lit"]), ("#D7263D", T["darkz"])])
    if isinstance(nat, pd.DataFrame) and len(nat) and "pop_dark" in nat and mb[0] >= CBOX[0] + 200:
        pdk = float(nat.sort_values("year")["pop_dark"].iloc[-1])
        y = CBOX[1] + 120
        d.text((32, y), f"{_f(pdk / 1e6, 2)} M", font=_font(36, True), fill=INK)
        d.text((32, y + 46), "habitants dans le noir" if LANG == "fr" else "people in the dark", font=_font(15),
               fill=MUTED)
        sens = ineq.get("dark_sensitivity")
        if isinstance(sens, pd.DataFrame) and len(sens) and "pop_dark" in sens:
            sv = sens[sens["year"] == sens["year"].max()]["pop_dark"] / 1e6
            d.text((32, y + 70), (f"{_f(sv.min(), 2)}–{_f(sv.max(), 2)} M selon le seuil" if LANG == "fr"
                                  else f"{_f(sv.min(), 2)}–{_f(sv.max(), 2)} M depending on threshold"),
                   font=_font(13), fill=FAINT)
    _finish(arr, over, out_dir / "uc5.png")
    return T["k5"]


def _uc6(R, geo, out_dir, synthetic):
    from PIL import ImageDraw
    ind = R.get("industry") or {}
    cl = ind.get("clusters")
    if not ind.get("available") or cl is None or not len(cl):
        return None
    from . import industry as IND
    share = None
    s = ind.get("series")
    if isinstance(s, pd.DataFrame) and len(s) and "share_of_national" in s:
        share = float(s.sort_values("year")["share_of_national"].iloc[-1])
    kpi = str(len(cl))
    lab = T["k6"] + (f" · {_pct(share, 1, False)} {T['of_light']}" if share is not None else "")
    arr, over, mb = _map_card(geo, 6, kpi, lab, T["src_gh"], synthetic, gain=0.6, glow=0.5)
    arr = _over(np.clip(arr, 0, 1), geo.boundaries((VW, VH), mb, c1=(255, 255, 255, 40)))
    types = cl["type"].astype(str).tolist() if "type" in cl else ["isolated"] * len(cl)
    col = [IND.TYPE_COLOR.get(t, GOLD) for t in types]
    if "geometry" in cl:
        lay = geo.layer((VW, VH), mb, list(cl.geometry), fill=[_rgba(c, 0.85) for c in col], simplify=False)
        arr = _over(arr, lay)
    from PIL import Image
    pts = Image.new("RGBA", (VW * 2, VH * 2), (0, 0, 0, 0))
    dp = ImageDraw.Draw(pts)
    if {"lon", "lat"} <= set(cl.columns):
        lon, lat = cl["lon"].astype(float).values, cl["lat"].astype(float).values
    else:
        c = cl.geometry.representative_point()
        lon, lat = c.x.values, c.y.values
    X, Y = geo.px(lon, lat, mb, 2)
    for xx, yy, c in zip(X, Y, col):
        dp.ellipse([xx - 13, yy - 13, xx + 13, yy + 13], outline=_rgba(c, 1), width=4)
        dp.ellipse([xx - 4, yy - 4, xx + 4, yy + 4], fill=_rgba("#FFFFFF", 0.95))
    arr = _over(arr, pts.resize((VW, VH), Image.LANCZOS))
    d = ImageDraw.Draw(over)
    cnt = pd.Series(types).value_counts()
    items = [(IND.TYPE_COLOR[k], f"{IND.TYPE_LABEL[k]} · {int(cnt[k])}") for k in IND.TYPE_COLOR if k in cnt]
    _legend(d, 32, CBOX[1] + 14, items, fs=13)
    _finish(arr, over, out_dir / "uc6.png")
    return T["k6"]


def _uc7(R, geo, gdfs, out_dir, synthetic):
    from PIL import ImageDraw
    tou = R.get("tourism") or {}
    u = tou.get("units")
    lv = tou.get("level") or "ADM2"
    if not tou.get("available") or u is None or not len(u) or lv not in gdfs:
        return None
    tz = u[u["class"] == "tourist"]
    mx = float(np.expm1(tz["net_median"].max())) if len(tz) and "net_median" in tz else None
    kpi = str(len(tz))
    lab = T["k7"] + (f" · {T['peak']} {_pct(mx, 0)}" if mx is not None else "")
    arr, over, mb = _map_card(geo, 7, kpi, lab, T["src_m"], synthetic, gain=0.8, glow=0.6)
    arr = _over(np.clip(arr, 0, 1), geo.boundaries((VW, VH), mb, c1=(255, 255, 255, 40)))
    g = gdfs[lv][gdfs[lv]["unit_id"].isin(tz["unit_id"])]
    if len(g):
        arr = _over(arr, geo.layer((VW, VH), mb, list(g.geometry), fill=_rgba(GOLD, 0.16), outline=_rgba(GOLD, 1),
                                   width=2.0))
    d = ImageDraw.Draw(over)
    _legend(d, 32, CBOX[1] + 14, [(GOLD, f"{T['tourist']} · {len(tz)}")])
    prof = tou.get("profile")
    if isinstance(prof, pd.DataFrame) and len(prof) and {"month", "tourist"} <= set(prof.columns):
        box = (32, CBOX[1] + 150, 230, 180)
        plt, fig = _chart_fig(box)
        ax = fig.add_axes([0.03, 0.2, 0.94, 0.62])
        ax.set_facecolor((0, 0, 0, 0))
        if "other" in prof:
            ax.plot(prof["month"], prof["other"], color="#8796A5", lw=1.4)
        ax.plot(prof["month"], prof["tourist"], color=GOLD, lw=2.2)
        ax.set_xticks([1, 4, 7, 10])
        from .tourism import MONTHS
        ax.set_xticklabels([MONTHS[i - 1] for i in (1, 4, 7, 10)], fontsize=10)
        ax.set_yticks([])
        ax.grid(False)
        ax.spines["bottom"].set_color("#2A3642")
        fig.text(0.03, 0.88, T["profile"], fontsize=11, color=MUTED)
        arr = _paste_chart(arr, _fig_rgba(fig), box)
        plt.close(fig)
    _finish(arr, over, out_dir / "uc7.png")
    return T["k7"]


def _uc8(R, geo, gdfs, out_dir, synthetic):
    """Units coloured by the light/population typology + indexed lit area vs population inset."""
    from PIL import ImageDraw
    from . import urban as URB
    urb = R.get("urban") or {}
    lv = urb.get("level") or "ADM2"
    u = (urb.get("units") or {}).get(lv)
    if not urb.get("available") or u is None or not len(u) or lv not in gdfs:
        return None
    tl, tp = (urb.get("trend") or {}).get("lit") or {}, (urb.get("trend") or {}).get("pop") or {}
    kpi = _pct(tl.get("growth"), 1) + T["per_yr"]
    lab = T["k8"] + (f" · {T['k8b']} {_pct(tp.get('growth'), 1)}{T['per_yr']}" if tp.get("growth") is not None else "")
    arr, over, mb = _map_card(geo, 8, kpi, lab, "VIIRS VNL V2 · GHSL POP / BUILT-S", synthetic, gain=0.7, glow=0.6)
    arr = np.clip(arr, 0, 1)
    g = gdfs[lv].merge(u[["unit_id", "class"]], on="unit_id", how="inner")
    if len(g):
        cols = [_rgba(URB.CLASS_COLOR.get(c, "#a9a8a2"), 0.55) for c in g["class"]]
        arr = _over(arr, geo.layer((VW, VH), mb, list(g.geometry), fill=cols, outline=(255, 255, 255, 120), width=1.0))
    d = ImageDraw.Draw(over)
    cnt = u["class"].value_counts()
    items = [(URB.CLASS_COLOR[k], f"{URB.CLASS[k]} · {int(cnt[k])}") for k in ("electrified", "balanced", "unlit", "stable") if k in cnt]
    _legend(d, 32, CBOX[1] + 14, items, fs=13)
    se = urb.get("series")
    if isinstance(se, pd.DataFrame) and len(se) > 2:
        box = (32, CBOX[1] + 150, 230, 180)
        plt, fig = _chart_fig(box)
        ax = fig.add_axes([0.03, 0.2, 0.94, 0.62])
        ax.set_facecolor((0, 0, 0, 0))
        ax.plot(se["year"], 100 * se["pop"] / se["pop"].iloc[0], color="#8796A5", lw=1.4, ls=":")
        ax.plot(se["year"], 100 * se["lit_km2"] / se["lit_km2"].iloc[0], color=GOLD, lw=2.2)
        ax.set_xticks([int(se["year"].iloc[0]), int(se["year"].iloc[-1])])
        ax.tick_params(labelsize=10)
        ax.set_yticks([])
        ax.grid(False)
        ax.spines["bottom"].set_color("#2A3642")
        fig.text(0.03, 0.88, f"{T['lit_area']} / {T['k8b']} (100)", fontsize=11, color=MUTED)
        arr = _paste_chart(arr, _fig_rgba(fig), box)
        plt.close(fig)
    _finish(arr, over, out_dir / "uc8.png")
    return T["k8"]


def _vignettes(R, geo, gdfs, out_dir, synthetic, facts: dict):
    out = []
    fns = {1: lambda: _uc1(R, geo, out_dir, synthetic), 2: lambda: _uc2(R, geo, gdfs, out_dir, synthetic),
           3: lambda: _uc3(R, geo, out_dir, synthetic), 4: lambda: _uc4(R, geo, out_dir, synthetic),
           5: lambda: _uc5(R, geo, out_dir, synthetic), 6: lambda: _uc6(R, geo, out_dir, synthetic),
           7: lambda: _uc7(R, geo, gdfs, out_dir, synthetic), 8: lambda: _uc8(R, geo, gdfs, out_dir, synthetic)}
    src = {1: T["src_m"], 2: T["src"], 3: T["src_wb"], 4: T["src_m"], 5: T["src_gh"], 6: T["src_gh"], 7: T["src_m"], 8: T["src"]}
    for n, fn in fns.items():
        try:
            k = fn()
        except Exception as e:  # noqa: BLE001 - a vignette must never break the export
            log.warning("media: vignette %d failed (%s: %s)", n, type(e).__name__, e)
            k = None
        if not k:
            log.info("media: vignette uc%d skipped (inputs missing)", n)
            continue
        title = f"{T['uc'].capitalize()} {n} — {T['titles'][n]}"
        cap = facts.get(n) or title
        out.append((f"uc{n}", dict(_entry(out_dir, f"uc{n}.png", title, f"{title}: {k}", cap, src[n]),
                                   uc=n, page=UC_PAGE[n])))
    return out


# --------------------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------------------
def _country_name(cfg) -> str:
    c = getattr(cfg, "country", None) or {}
    if LANG == "fr":
        return c.get("name_fr") or c.get("name") or cfg.iso3
    return c.get("name") or cfg.iso3


def _uc_facts(out_dir: Path) -> dict:
    """First fact of each use case (from agent_context.json next to the media folder) as caption."""
    p = Path(out_dir).parent / "agent_context.json"
    try:
        facts = json.loads(p.read_text(encoding="utf-8")).get("facts", [])
    except Exception:  # noqa: BLE001
        return {}
    out = {}
    for f in facts:
        uc = f.get("uc")
        if isinstance(uc, int) and 1 <= uc <= 8 and uc not in out and not str(f.get("title", "")).startswith(("Méthode", "Method")):
            out[uc] = f.get("text")
    return out


def _update_meta(out_dir: Path, manifest: dict) -> None:
    meta_p = Path(out_dir).parent / "meta.json"
    if not meta_p.exists():
        return
    try:
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        meta["media"] = {k: v for k, v in manifest.items() if not k.startswith("_")}
        meta_p.write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        log.warning("media: meta.json not updated (%s)", e)


def _write_manifest(out_dir: Path, manifest: dict) -> None:
    (Path(out_dir) / "media.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    _update_meta(out_dir, manifest)


def build_media(cfg, gdfs, R, annual, monthly, rasters, raster_dir, out_dir, names, daily=None,
                synthetic=False) -> dict:
    """Generate every image/animation of the country; returns the manifest {key: entry}.

    Never raises for a missing input: each item is skipped (logged) when its data is absent.
    """
    t0 = time.time()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    R = R or {}
    country = _country_name(cfg)
    global _FLAG
    try:   # country flag: on the headers of the animations, the cover and the banner
        from .flags import ensure_flag, flag_image
        fl = ensure_flag(cfg, synthetic)
        _FLAG = flag_image(fl["png"]) if fl.get("png") else None
        for k in ("png", "svg"):
            if fl.get(k):
                shutil.copy2(fl[k], out_dir.parent / f"flag.{k}")
    except Exception as e:  # noqa: BLE001 - a missing flag never blocks the images
        log.warning("media: flag unavailable (%s)", e)
        _FLAG = None
    geo = _Geo(rasters, raster_dir, gdfs, synthetic)
    log.info("media: rasters %d years, rows %s", len(geo.years), "Web Mercator" if geo.mercator else "latitude")
    items: list = []
    steps = [("timelapse", lambda: _timelapse(geo, cfg, country, out_dir, synthetic)),
             ("before_after", lambda: _before_after(geo, cfg, country, out_dir, synthetic)),
             ("shock", lambda: _shock_gif(R, country, out_dir, synthetic)),
             ("cover", lambda: _covers(geo, cfg, country, out_dir, synthetic)),
             ("vignettes", lambda: _vignettes(R, geo, gdfs, out_dir, synthetic, _uc_facts(out_dir)))]
    for name, fn in steps:
        t = time.time()
        try:
            items += fn() or []
        except Exception as e:  # noqa: BLE001 - media are a bonus: never break the export
            log.warning("media: %s failed (%s: %s)", name, type(e).__name__, e)
        log.info("media: %s %.1fs", name, time.time() - t)
    manifest = {k: v for k, v in items}
    prev = out_dir / "media.json"
    if prev.exists():   # keep screenshots captured earlier
        try:
            old = json.loads(prev.read_text(encoding="utf-8"))
            manifest.update({k: v for k, v in old.items() if (k.startswith("screen_") or k == "dashboard_tour")
                             and (out_dir.parent / v.get("file", "")).exists()})
        except Exception:  # noqa: BLE001
            pass
    _write_manifest(out_dir, manifest)
    geo._cache.clear()
    log.info("media: %d files in %.0fs → %s", len(manifest), time.time() - t0, out_dir)
    return manifest


# --------------------------------------------------------------------------------------
# Optional: screenshots and animated tour of the dashboard (Playwright)
# --------------------------------------------------------------------------------------
PREFERRED_PAGES = ["overview", "map", "time", "regions", "shocks", "inequality", "industry", "tourism", "urban", "assistant"]


def _serve(site_dir: Path):
    import functools
    import http.server
    import threading

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a, **k):  # noqa: D401 - silence
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(site_dir)))
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return srv


def capture_dashboard(site_dir, out_dir, iso3, pages=None, lang=None, max_pages: int = 9) -> dict:
    """Screenshot the local dashboard (desktop + mobile) and build `dashboard_tour.gif`.

    `site_dir` is the dashboard root (``cfg.dashboard_dir``); `lang` selects the language version
    ("en"/"fr": the sub-site ``<site_dir>/<lang>/`` when it exists, otherwise the root); `pages`
    defaults to every tab found in the page (``[data-page]``), in reading order.

    Returns the new manifest entries (also merged into media.json and meta.json), or {} when
    Playwright/Chromium is unavailable — never raises. In Colab, first run:
    ``!pip -q install playwright && playwright install --with-deps chromium``.
    """
    from PIL import Image
    site_dir, out_dir = Path(site_dir), Path(out_dir)
    try:
        from playwright.sync_api import sync_playwright
    except Exception:  # noqa: BLE001
        log.warning("media: Playwright not installed — dashboard screenshots skipped "
                    "(pip install playwright && playwright install chromium)")
        print("ℹ️ " + ("Playwright absent : captures du tableau de bord ignorées." if LANG == "fr"
                       else "Playwright not installed: dashboard screenshots skipped."))
        return {}
    if not (site_dir / "index.html").exists():
        log.warning("media: %s/index.html not found — screenshots skipped", site_dir)
        return {}
    out_dir.mkdir(parents=True, exist_ok=True)
    sub = _lang_subdir(site_dir, lang)
    srv = None
    shots: dict[str, Path] = {}
    entries: dict = {}
    try:
        srv = _serve(site_dir)
        base = f"http://127.0.0.1:{srv.server_address[1]}/{sub}?country={iso3}"
        # Jupyter/Colab kernels run an asyncio loop, where the Playwright *sync* API refuses to start:
        # the browser work therefore always runs in a worker thread (no event loop there).
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(1) as ex:
            ok = ex.submit(_shoot, sync_playwright, base, out_dir, pages, max_pages, shots).result()
        if not ok:
            return {}
    except Exception as e:  # noqa: BLE001
        log.warning("media: dashboard capture failed (%s: %s)", type(e).__name__, str(e)[:300])
        if not shots:
            return {}
    finally:
        if srv is not None:
            srv.shutdown()
            srv.server_close()
    return _capture_outputs(out_dir, shots, entries)


def _lang_subdir(site_dir: Path, lang: str | None) -> str:
    """'' for the site root, or '<lang>/' — the root language is read from <html lang> of index.html."""
    if not lang:
        return ""
    import re as _re
    try:
        head = (site_dir / "index.html").read_text(encoding="utf-8", errors="ignore")[:4000]
        m = _re.search(r"<html[^>]*\blang=[\"']?([a-zA-Z-]+)", head)
        root_lang = m.group(1).lower()[:2] if m else None
    except Exception:  # noqa: BLE001
        root_lang = None
    if root_lang == lang.lower()[:2]:
        return ""
    if (site_dir / lang / "index.html").exists():
        return f"{lang}/"
    log.warning("media: no '%s' version under %s — capturing the root site", lang, site_dir)
    return ""


def _shoot(sync_playwright, base: str, out_dir: Path, pages, max_pages: int, shots: dict) -> bool:
    """Playwright (sync API) session — must run in a thread without an asyncio loop."""
    from PIL import Image
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as e:  # noqa: BLE001
            log.warning("media: Chromium unavailable (%s) — screenshots skipped", str(e).splitlines()[0][:200])
            print("ℹ️ " + ("Chromium indisponible : captures ignorées (playwright install chromium)." if LANG == "fr"
                           else "Chromium unavailable: screenshots skipped (playwright install chromium)."))
            return False
        try:
            ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1,
                                      reduced_motion="no-preference", color_scheme="dark")
            page = ctx.new_page()
            page.goto(base + "#overview", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(1500)
            found = page.eval_on_selector_all("[data-page]", "els => els.map(e => e.dataset.page)") or []
            found = list(dict.fromkeys(p for p in found if p))
            if pages:
                todo = [p for p in pages if not found or p in found]
            else:
                todo = [p for p in PREFERRED_PAGES if p in found] or found or ["overview"]
            todo = todo[:max_pages]
            for p in todo:
                page.goto(base + f"#{p}", wait_until="networkidle", timeout=60000)
                page.evaluate("window.scrollTo(0, 0)")
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:  # noqa: BLE001
                    pass
                page.wait_for_timeout(1500)
                f = out_dir / f"screen_{p}.png"
                page.screenshot(path=str(f))
                shots[p] = f
            ctx.close()
            mctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                       is_mobile=True, has_touch=True, reduced_motion="no-preference",
                                       color_scheme="dark")
            mp = mctx.new_page()
            mp.goto(base + "#overview", wait_until="networkidle", timeout=60000)
            mp.wait_for_timeout(1500)
            f = out_dir / "screen_mobile.png"
            mp.screenshot(path=str(f))
            mctx.close()
            with Image.open(f) as im:   # keep the README light: 1× width
                im.resize((390, 844), Image.LANCZOS).save(f, optimize=True)
            shots["mobile"] = f
        finally:
            browser.close()
    return True


def _capture_outputs(out_dir: Path, shots: dict, entries: dict) -> dict:
    from PIL import Image
    # still entries
    for p, f in shots.items():
        title = T["mobile"] if p == "mobile" else T["screen"].format(p=p)
        entries[f"screen_{p}"] = dict(_entry(out_dir, f.name, title, title, title, "dashboard"), page=p)
    # animated tour (desktop pages, 2.5 s each with short fades)
    desk = [shots[p] for p in shots if p != "mobile"]
    if desk:
        W = 960
        ims = []
        for f in desk:
            with Image.open(f) as im:
                im = im.convert("RGB")
                ims.append(im.resize((W, round(im.size[1] * W / im.size[0])), Image.LANCZOS))
        frames, durs = [], []
        for k, im in enumerate(ims):
            frames.append(im)
            durs.append(2500)
            nxt = ims[(k + 1) % len(ims)] if len(ims) > 1 else None
            if nxt is not None and nxt.size == im.size:
                for j in (1, 2, 3):
                    frames.append(Image.blend(im, nxt, j / 4))
                    durs.append(80)
        _save_gif(frames, durs, out_dir / "dashboard_tour.gif", 6_000_000, widths=(960, 880, 800, 720, 640),
                  colors=(128, 96, 64, 48))
        entries["dashboard_tour"] = _entry(out_dir, "dashboard_tour.gif", T["tour"], T["tour"], T["tour_cap"],
                                           "dashboard")
    # merge into media.json / meta.json
    man_p = out_dir / "media.json"
    try:
        man = json.loads(man_p.read_text(encoding="utf-8")) if man_p.exists() else {}
    except Exception:  # noqa: BLE001
        man = {}
    man.update(entries)
    _write_manifest(out_dir, man)
    log.info("media: %d dashboard screenshots + tour", len(shots))
    return entries


def build_media_other_language(cfg, gdfs, R, annual, monthly, rasters, raster_dir, out_dir, names, root,
                               daily=None, synthetic=False) -> dict:
    """Same images in the other language (texts only; figures identical) via src_<other>.media.

    `out_dir` is the other-language media folder, e.g. ``OUT_EN / "media"``. Returns {} if the
    other-language package is missing.
    """
    import importlib
    import sys
    other = "en" if LANG == "fr" else "fr"
    if root and str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        M2 = importlib.import_module(f"src_{other}.media")
        from .i18n import translate
    except Exception as e:  # noqa: BLE001
        log.warning("media: other-language package unavailable (%s)", e)
        return {}
    R2 = translate({k: v for k, v in (R or {}).items() if k != "cfg"}, other)
    R2["cfg"] = (R or {}).get("cfg")
    return M2.build_media(cfg, gdfs, R2, annual, monthly, rasters, raster_dir, out_dir, names, daily=daily,
                          synthetic=synthetic)
