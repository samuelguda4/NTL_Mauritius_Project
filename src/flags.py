"""Country flag — one helper for the notebook, the images, the dashboard and the README.

Flags come from flagcdn.com (public-domain artwork from Wikimedia Commons), keyed by the ISO 3166-1
alpha-2 code, and are cached next to the country data: ``outputs/<ISO3>/cache/flag.png`` (640 px wide,
for Pillow images and the README) and ``flag.svg`` (crisp in the browser). For the synthetic test
country (user-assigned codes XAA–XZZ), a clearly fictional flag is drawn locally so the layout can be
checked without a network.
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path

log = logging.getLogger("ntl")
UA = {"User-Agent": "ntl-economic-analysis/2.1 (AfDB x DI4A notebook)"}

_SVG_FAKE = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 600"><rect width="900" height="600" fill="#00704A"/>'
             '<rect y="200" width="900" height="200" fill="#ffffff"/><rect y="400" width="900" height="200" fill="#1F4E8C"/>'
             '<polygon points="0,0 360,300 0,600" fill="#F5C242"/>'
             '<circle cx="120" cy="300" r="62" fill="#ffffff"/><circle cx="142" cy="300" r="56" fill="#F5C242"/></svg>')


def _is_fake(cfg) -> bool:
    return str(cfg.iso3).upper().startswith("X") and (cfg.country or {}).get("iso2", "").upper() in ("XT", "")


def _draw_fake_png(path: Path) -> None:
    from PIL import Image, ImageDraw
    W, H = 640, 427
    im = Image.new("RGB", (W, H), "#00704A")
    d = ImageDraw.Draw(im)
    d.rectangle([0, H // 3, W, 2 * H // 3], fill="#ffffff")
    d.rectangle([0, 2 * H // 3, W, H], fill="#1F4E8C")
    d.polygon([(0, 0), (int(W * 0.4), H // 2), (0, H)], fill="#F5C242")
    r = int(H * 0.1)
    d.ellipse([int(W * 0.133) - r, H // 2 - r, int(W * 0.133) + r, H // 2 + r], fill="#ffffff")
    d.ellipse([int(W * 0.158) - int(r * 0.9), H // 2 - int(r * 0.9), int(W * 0.158) + int(r * 0.9), H // 2 + int(r * 0.9)],
              fill="#F5C242")
    im.save(path, optimize=True)


def ensure_flag(cfg, synthetic: bool = False, timeout: int = 20) -> dict:
    """Make sure flag.png / flag.svg exist in the cache; returns {"png": Path|None, "svg": Path|None}."""
    cache = Path(cfg.cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    png, svg = cache / "flag.png", cache / "flag.svg"
    if synthetic or _is_fake(cfg):
        if not png.exists():
            _draw_fake_png(png)
        if not svg.exists():
            svg.write_text(_SVG_FAKE, encoding="utf-8")
        return {"png": png, "svg": svg}
    iso2 = (cfg.country or {}).get("iso2", "").lower()
    if iso2:
        import requests
        for url, dst in ((f"https://flagcdn.com/w640/{iso2}.png", png), (f"https://flagcdn.com/{iso2}.svg", svg)):
            if dst.exists() and dst.stat().st_size > 100:
                continue
            try:
                r = requests.get(url, timeout=timeout, headers=UA)
                r.raise_for_status()
                dst.write_bytes(r.content)
            except Exception as e:  # noqa: BLE001 - a missing flag is never fatal
                log.warning("flag download failed %s (%s)", url, e)
    return {"png": png if png.exists() else None, "svg": svg if svg.exists() else None}


def flag_image(cfg_or_path):
    """Pillow RGBA image of the flag (from the cache), or None."""
    p = Path(cfg_or_path) if isinstance(cfg_or_path, (str, Path)) else Path(cfg_or_path.cache_dir) / "flag.png"
    if not p.exists():
        return None
    try:
        from PIL import Image
        return Image.open(p).convert("RGBA")
    except Exception:  # noqa: BLE001
        return None


def flag_html(cfg, height: int = 26) -> str:
    """Inline <img> (base64) for notebook outputs; empty string if no flag."""
    p = Path(cfg.cache_dir) / "flag.png"
    if not p.exists():
        return ""
    b = base64.b64encode(p.read_bytes()).decode()
    return (f"<img src='data:image/png;base64,{b}' alt='flag' style='height:{height}px;vertical-align:-5px;"
            f"border-radius:3px;box-shadow:0 0 0 1px #0002;margin-right:8px'>")


def paste_flag(im, flag, xy, height: int, radius: int = 4, border=(255, 255, 255, 70)):
    """Paste a flag with rounded corners and a hairline border at ``xy`` (top-left). Returns its width."""
    if flag is None:
        return 0
    from PIL import Image, ImageDraw
    w = max(1, int(flag.width * height / flag.height))
    f = flag.resize((w, height), Image.LANCZOS)
    mask = Image.new("L", (w, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, height - 1], radius=radius, fill=255)
    base = im if im.mode == "RGBA" else None
    if base is None:
        im.paste(f, xy, mask)
    else:
        layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
        layer.paste(f, xy, mask)
        im.alpha_composite(layer)
    ImageDraw.Draw(im, "RGBA").rounded_rectangle([xy[0], xy[1], xy[0] + w - 1, xy[1] + height - 1], radius=radius,
                                                 outline=border, width=1)
    return w
