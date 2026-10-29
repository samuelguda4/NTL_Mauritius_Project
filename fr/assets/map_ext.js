/* Night-time lights dashboard — immersive hero, advanced Leaflet map, chart/table exports, keyboard & a11y.
 * Shared by the French and English sites (texts chosen from <html lang>). Loaded AFTER ext.js and BEFORE app.js;
 * it patches app.js's RENDER registry on DOMContentLoaded (app.js defines RENDER.overview / RENDER.map itself).
 *
 * ── Public API for the AI agent ────────────────────────────────────────────────────────────────────────────
 *   window.NTL_MAP = {
 *     ready            Promise<void> — resolves once the map page has rendered (a fresh promise is made when
 *                      the country changes and the map is rebuilt; always read NTL_MAP.ready, don't cache it)
 *     async show()     navigates to #map (keeps current view state) and awaits ready
 *     setMode(mode)    "lights" | "swipe" | "dark" | "indicator" | "industry" | "tourism"
 *                      ("industry"/"tourism" = night lights + that overlay switched on)
 *     setYear(year)    year of the night-lights layer; switches to "lights" if the current mode has no timeline
 *     setLevel(lv)     "ADM1" | "ADM2" (units used for hover, click, boundaries and the indicator choropleth)
 *     setIndicator(k)  one of INDICATORS[].k (growth, class, sol_pc, share_last, dark_share, pop_dark, gdp_pc_est);
 *                      switches to "indicator" mode (and to ADM1 when the indicator only exists at ADM1)
 *     compare(a, b)    swipe comparison, year a on the left, year b on the right
 *     focus(unit)      unit_id or (accent-insensitive) name → fly, highlight, popup; returns {unit_id,name,level} or null
 *     toggleLayer(name, on?)  "industry" | "tourism" | "boundaries"; on omitted = toggle; returns the new boolean
 *     play(on = true)  start / stop the timeline animation (switches to "lights" if needed)
 *     state()          { page, mode, year, level, indicator, a, b, unit, layers:{industry,tourism,boundaries},
 *                        opacity, playing, speed, swipe, years }
 *     units()          [{ unit_id, name, level }]
 *   }
 *   All setters are idempotent, can be called before the map exists (state is stored and applied at render) and
 *   return state(). The URL hash mirrors the view: #map?mode=lights&year=2020&lv=ADM2&ind=growth&a=2014&b=2025&unit=…&ov=industry,tourism
 */
"use strict";
(function () {
  const LANG = document.documentElement.lang === "en" ? "en" : "fr";
  const RM = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const TX = {
    fr: {
      eyebrow: "Banque africaine de développement · DI4A", t1: "Lumières nocturnes", t2: "huit cas d'usage",
      pitch: "Vue de l'espace, la lumière émise la nuit éclaire huit questions de politique publique : croissance, régions, PIB, chocs, inégalités et accès à l'électricité, industrie, tourisme, urbanisation — partout, chaque mois, même là où les statistiques manquent.",
      cta_map: "Explorer la carte", cta_ai: "Interroger l'agent IA", play: "Lire l'animation", pause: "Mettre l'animation en pause",
      hx_fig: "Animation des lumières nocturnes observées par satellite, {a} à {b}", hx_cap: "VIIRS · composite annuel", hx_idx: "Lumière émise", hx_base: "base 100 en {y}",
      hx_units: "{n1} régions · {n2} districts · {ny} années d'images satellite",
      layers: "Couches", hide_panel: "Masquer le panneau des couches", show_panel: "Afficher les couches",
      m_lights: "Lumières nocturnes", m_lights_d: "Composite annuel, année par année",
      m_swipe: "Changement entre deux années", m_swipe_d: "Rideau de comparaison",
      m_dark: "Population dans le noir", m_dark_d: "Zones habitées sans lumière",
      m_ind: "Indicateurs", m_ind_d: "Carte choroplèthe par unité",
      overlays: "Superpositions", ov_industry: "Grappes industrielles", ov_tourism: "Zones touristiques", ov_bound: "Limites administratives",
      level: "Unités", lv1: "Régions (ADM1)", lv2: "Districts (ADM2)", lv1s: "ADM1", lv2s: "ADM2", indicator: "Indicateur",
      year_a: "Année A (gauche)", year_b: "Année B (droite)", year: "Année", opacity: "Opacité des images", speed: "Vitesse de lecture",
      search: "Région ou district…", search_lbl: "Rechercher une unité", none: "Aucun résultat", region: "Région", district: "District",
      fs: "Plein écran", fs_exit: "Quitter le plein écran", reset: "Recentrer la carte", share: "Copier le lien de cette vue", help: "Raccourcis clavier",
      zin: "Zoom avant", zout: "Zoom arrière", copied: "Lien copié dans le presse-papiers", copy_fail: "Copie impossible : sélectionnez l'adresse dans la barre du navigateur",
      loading: "Chargement de la carte…", map_lbl: "Carte interactive des lumières nocturnes", divider: "Séparateur de comparaison (flèches gauche / droite)",
      k_title: "Raccourcis clavier", k_year: "Année précédente / suivante", k_play: "Lecture / pause", k_fs: "Plein écran", k_search: "Rechercher une unité", k_help: "Afficher cette aide", k_esc: "Fermer",
      close: "Fermer",
      leg_rad: "Radiance (échelle log.)", leg_dark: "Zones habitées", lit: "éclairées", unlit: "non éclairées (« dans le noir »)", na: "non disponible",
      leg_tour: "Zone touristique (surcroît estival)", leg_ind: "Grappes industrielles",
      d_lights: "Composite annuel VIIRS VNL V2, torchères masquées. Lisez l'animation pour voir apparaître l'électrification et l'urbanisation.",
      d_swipe: "Faites glisser le rideau (ou utilisez les flèches) : à gauche l'année A, à droite l'année B. Les zones apparues traduisent l'électrification, l'urbanisation ou de nouvelles infrastructures.",
      d_dark: "Pixels comptant au moins {p} habitants : en rouge ceux dont la radiance reste sous le seuil de détection. Proxy de l'absence d'accès à l'électricité.",
      src: "Sources : VIIRS VNL V2 (NOAA/EOG) ; limites {b} ; population {p} ; fond de carte © OpenStreetMap, © CARTO.",
      p_sol: "Somme des lumières", p_share: "Part nationale", p_growth: "Croissance", p_solpc: "Lumière / hab.", p_pop: "Population", p_dark: "Pop. dans le noir", p_gdp: "PIB / hab. estimé",
      p_spark: "Lumière annuelle", per_yr: "/an", light_y: "Lumière {y}", change: "Variation {a} → {b}",
      i_type: "Type", i_conf: "confiance", i_area: "Surface", i_where: "Localisation", i_light: "Lumière (dernière année)", t_net: "Surcroît estival net",
      csv: "Télécharger CSV", csv_lbl: "Télécharger ce tableau au format CSV", png: "Télécharger en PNG",
    },
    en: {
      eyebrow: "African Development Bank · DI4A", t1: "Night-time lights", t2: "eight use cases",
      pitch: "Seen from space, the light emitted at night sheds light on eight policy questions: growth, regions, GDP, shocks, inequality and electricity access, industry, tourism, urbanisation — everywhere, every month, even where statistics are missing.",
      cta_map: "Explore the map", cta_ai: "Ask the AI agent", play: "Play the animation", pause: "Pause the animation",
      hx_fig: "Animation of night-time lights observed by satellite, {a} to {b}", hx_cap: "VIIRS · annual composite", hx_idx: "Light emitted", hx_base: "index, {y} = 100",
      hx_units: "{n1} regions · {n2} districts · {ny} years of satellite imagery",
      layers: "Layers", hide_panel: "Hide the layer panel", show_panel: "Show layers",
      m_lights: "Night-time lights", m_lights_d: "Annual composite, year by year",
      m_swipe: "Change between two years", m_swipe_d: "Swipe comparison",
      m_dark: "Population in the dark", m_dark_d: "Inhabited areas without light",
      m_ind: "Indicators", m_ind_d: "Choropleth map by unit",
      overlays: "Overlays", ov_industry: "Industrial clusters", ov_tourism: "Tourist zones", ov_bound: "Administrative boundaries",
      level: "Units", lv1: "Regions (ADM1)", lv2: "Districts (ADM2)", lv1s: "ADM1", lv2s: "ADM2", indicator: "Indicator",
      year_a: "Year A (left)", year_b: "Year B (right)", year: "Year", opacity: "Image opacity", speed: "Playback speed",
      search: "Region or district…", search_lbl: "Search a unit", none: "No match", region: "Region", district: "District",
      fs: "Fullscreen", fs_exit: "Exit fullscreen", reset: "Reset view", share: "Copy a link to this view", help: "Keyboard shortcuts",
      zin: "Zoom in", zout: "Zoom out", copied: "Link copied to clipboard", copy_fail: "Copy failed: select the address in the browser bar",
      loading: "Loading the map…", map_lbl: "Interactive map of night-time lights", divider: "Comparison divider (left / right arrows)",
      k_title: "Keyboard shortcuts", k_year: "Previous / next year", k_play: "Play / pause", k_fs: "Fullscreen", k_search: "Search a unit", k_help: "Show this help", k_esc: "Close",
      close: "Close",
      leg_rad: "Radiance (log scale)", leg_dark: "Inhabited areas", lit: "lit", unlit: "unlit (“in the dark”)", na: "not available",
      leg_tour: "Tourist zone (summer excess)", leg_ind: "Industrial clusters",
      d_lights: "VIIRS VNL V2 annual composite, gas flares masked. Play the animation to watch electrification and urbanisation appear.",
      d_swipe: "Drag the divider (or use the arrow keys): year A on the left, year B on the right. Newly lit areas reflect electrification, urbanisation or new infrastructure.",
      d_dark: "Pixels with at least {p} inhabitants: in red those whose radiance stays below the detection threshold. A proxy for lack of access to electricity.",
      src: "Sources: VIIRS VNL V2 (NOAA/EOG); boundaries {b}; population {p}; basemap © OpenStreetMap, © CARTO.",
      p_sol: "Sum of lights", p_share: "National share", p_growth: "Growth", p_solpc: "Light per capita", p_pop: "Population", p_dark: "People in the dark", p_gdp: "Est. GDP per capita",
      p_spark: "Annual light", per_yr: "/yr", light_y: "Light {y}", change: "Change {a} → {b}",
      i_type: "Type", i_conf: "confidence", i_area: "Area", i_where: "Location", i_light: "Light (latest year)", t_net: "Net summer excess",
      csv: "Download CSV", csv_lbl: "Download this table as CSV", png: "Download as PNG",
    },
  }[LANG];
  const fmt = (s, o) => String(s).replace(/\{(\w+)\}/g, (_, k) => (o[k] ?? ""));
  const h = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const norm = (s) => String(s || "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
  const q1 = (s, el = document) => el.querySelector(s);
  const qa = (s, el = document) => [...el.querySelectorAll(s)];
  const num = (v) => typeof v === "number" && Number.isFinite(v);
  const cssv = (v, d) => (getComputedStyle(document.documentElement).getPropertyValue(v).trim() || d);
  const GOLD = "#F5C242";
  const ICON = {
    play: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M8 5.5v13a1 1 0 0 0 1.5.86l10.4-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z"/></svg>',
    pause: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="5" width="4.2" height="14" rx="1.2" fill="currentColor"/><rect x="13.8" y="5" width="4.2" height="14" rx="1.2" fill="currentColor"/></svg>',
    fs: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg>',
    fsx: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5"/></svg>',
    reset: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3.2" fill="currentColor"/><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" d="M12 2v4M12 18v4M2 12h4M18 12h4"/><circle cx="12" cy="12" r="7.5" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>',
    share: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" d="M10 14a4.5 4.5 0 0 0 6.4 0l3-3a4.5 4.5 0 0 0-6.4-6.4l-1.2 1.2M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1.2-1.2"/></svg>',
    help: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" d="M9.2 9a3 3 0 1 1 4.3 2.7c-.9.4-1.5 1.2-1.5 2.2v.6"/><circle cx="12" cy="18" r="1.3" fill="currentColor"/></svg>',
    plus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path stroke="currentColor" stroke-width="2.2" stroke-linecap="round" d="M12 5v14M5 12h14"/></svg>',
    minus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path stroke="currentColor" stroke-width="2.2" stroke-linecap="round" d="M5 12h14"/></svg>',
    layers: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" d="M12 3 2 8.5l10 5.5 10-5.5L12 3zM2 13.5 12 19l10-5.5"/></svg>',
    chev: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" d="m15 6-6 6 6 6"/></svg>',
    search: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" stroke-width="2"/><path stroke="currentColor" stroke-width="2.2" stroke-linecap="round" d="m15.5 15.5 5 5"/></svg>',
    dl: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M12 4v11m0 0-4.5-4.5M12 15l4.5-4.5M5 19h14"/></svg>',
  };

  /* ================================================================== common helpers */
  const pageName = () => (location.hash || "#overview").slice(1).split("?")[0] || "overview";
  const hashQuery = () => { const s = location.hash.split("?")[1]; return new URLSearchParams(s || ""); };
  function toast(msg) {
    let t = q1("#mx-toast-global");
    if (!t) { t = document.createElement("div"); t.id = "mx-toast-global"; t.className = "mx-toast"; t.setAttribute("role", "status"); t.setAttribute("aria-live", "polite"); document.body.appendChild(t); }
    t.textContent = msg; t.classList.add("on"); clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove("on"), 2600);
  }
  function syncLangLink() {
    const a = q1("#lang-switch"); if (!a) return;
    a.href = (a.getAttribute("href") || "").split("#")[0] + location.hash;
  }
  function download(name, text, type = "text/csv;charset=utf-8") {
    const blob = new Blob(["﻿" + text], { type });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }
  // FR: ";" separator + decimal comma (opens directly in French Excel); EN: "," + decimal point.
  const SEP = LANG === "fr" ? ";" : ",";
  function csvCell(v) {
    if (v == null) return "";
    let s = typeof v === "number" ? (LANG === "fr" ? String(v).replace(".", ",") : String(v)) : String(v);
    return /[";,\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }
  const toCSV = (head, rows) => [head, ...rows].map((r) => r.map(csvCell).join(SEP)).join("\r\n");

  /* ================================================================== Plotly: PNG export on every chart */
  if (window.Plotly) {
    const cfg = (gd, config) => {
      const el = typeof gd === "string" ? document.getElementById(gd) : gd;
      const id = (el && el.id) || "chart";
      const sec = el && el.closest && el.closest(".page");
      const page = sec ? sec.id.replace(/^page-/, "") : "chart";
      return Object.assign({}, config || {}, {
        displayModeBar: true, displaylogo: false, responsive: true, modeBarButtons: [["toImage"]],
        toImageButtonOptions: { format: "png", filename: `${page}_${id}`, scale: 2 },
        locale: LANG === "fr" ? "fr" : "en",
      });
    };
    for (const fn of ["newPlot", "react"]) {
      const orig = Plotly[fn];
      if (typeof orig !== "function") continue;
      Plotly[fn] = function (gd, data, layout, config) {
        if (data && !Array.isArray(data) && typeof data === "object") { data.config = cfg(gd, data.config); return orig.call(this, gd, data); }
        return orig.call(this, gd, data, layout, cfg(gd, config));
      };
    }
  }

  /* ================================================================== CSV for tables */
  function addRegionsCSV() {
    const bar = q1("#page-regions .toolbar"); if (!bar || q1("#csv-regions")) return;
    const b = document.createElement("button");
    b.type = "button"; b.id = "csv-regions"; b.className = "csv-btn"; b.setAttribute("aria-label", TX.csv_lbl);
    b.innerHTML = `${ICON.dl}<span>${h(TX.csv)}</span>`;
    b.onclick = () => {
      const lv = S.regLevel || "ADM1", q = ((q1("#reg-search") || {}).value || "").toLowerCase();
      const parents = Object.fromEntries((S.d.adm2?.features || []).map((f) => [f.properties.unit_id, f.properties.parent_name]));
      const rows = (S.d.regions || []).filter((r) => r.level === lv && (!q || String(r.name).toLowerCase().includes(q)));
      const cols = ["unit_id", "name", "parent_name", "level", "sol", "share_last", "growth", "growth_lo", "growth_hi", "p_value", "class", "pop", "sol_pc", "pop_dark", "dark_share", "lit_area_share", "gdp_pc_est", "year"];
      const title = Object.fromEntries((typeof TABLE_COLS !== "undefined" ? TABLE_COLS : []).map((c) => [c.k, c.t]));
      const use = cols.filter((k) => k === "parent_name" ? lv !== "ADM1" : rows.some((r) => r[k] != null));
      download(`regions_${S.iso}_${lv}.csv`, toCSV(use.map((k) => (title[k] ? `${title[k]} [${k}]` : k)), rows.map((r) => use.map((k) => (k === "parent_name" ? parents[r.unit_id] : r[k])))));
    };
    bar.appendChild(b);
  }
  // any other rendered data table gets a DOM-based CSV button (text as displayed)
  function addTableButtons() {
    qa(".page:not([hidden]) table").forEach((t, i) => {
      if (t.id === "r-table" || t.dataset.csv || !t.tHead || !t.tBodies.length || !t.tBodies[0].rows.length) return;
      t.dataset.csv = "1";
      const host = t.closest(".table-wrap") || t;
      const b = document.createElement("button");
      b.type = "button"; b.className = "csv-btn small"; b.setAttribute("aria-label", TX.csv_lbl);
      b.innerHTML = `${ICON.dl}<span>${h(TX.csv)}</span>`;
      b.onclick = () => {
        const rows = [...t.rows].map((r) => [...r.cells].map((c) => c.textContent.trim().replace(/\s+/g, " ")));
        const page = pageName();
        download(`${page}_${t.id || "table" + (i + 1)}_${S.iso || ""}.csv`, toCSV(rows[0], rows.slice(1)));
      };
      const wrap = document.createElement("div"); wrap.className = "csv-row"; wrap.appendChild(b);
      host.parentNode.insertBefore(wrap, host);
    });
  }
  let tblT = 0;
  const queueTables = () => { clearTimeout(tblT); tblT = setTimeout(() => { try { addTableButtons(); } catch (e) { console.error(e); } }, 250); };

  /* ================================================================== HERO (overview) */
  const HX = { timer: 0, i: 0, years: [], playing: !RM, visible: true, front: 0 };
  const merc = (lat) => Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
  function projector(b) {
    const [w, s, e, n] = b, W = 1000;
    const H = (W * (merc(n) - merc(s))) / (((e - w) * Math.PI) / 180);
    return { W, H, p: (lon, lat) => [((lon - w) / (e - w)) * W, ((merc(n) - merc(lat)) / (merc(n) - merc(s))) * H] };
  }
  function geoPath(gj, P) {
    let d = "";
    const ring = (r) => { r.forEach((c, i) => { const [x, y] = P.p(c[0], c[1]); d += (i ? "L" : "M") + x.toFixed(1) + " " + y.toFixed(1); }); d += "Z"; };
    (gj?.features || []).forEach((f) => {
      const g = f.geometry; if (!g) return;
      if (g.type === "Polygon") g.coordinates.forEach(ring);
      else if (g.type === "MultiPolygon") g.coordinates.forEach((p) => p.forEach(ring));
    });
    return d;
  }
  // exterior rings only: unioned boundaries often carry sliver holes that would draw as stray lines
  function outer(gj) {
    if (!gj) return gj;
    return { type: "FeatureCollection", features: (gj.features || []).map((f) => {
      const g = f.geometry; if (!g) return f;
      const geometry = g.type === "Polygon" ? { type: "Polygon", coordinates: [g.coordinates[0]] } : g.type === "MultiPolygon" ? { type: "MultiPolygon", coordinates: g.coordinates.map((p) => [p[0]]) } : g;
      return { type: "Feature", properties: f.properties, geometry };
    }) };
  }
  function nationalIndex() {
    const rows = (S.d.annual || []).filter((r) => r.level === "ADM0").sort((a, b) => a.year - b.year);
    const base = rows.length ? rows[0].sol : null;
    return { base: rows[0]?.year, by: Object.fromEntries(rows.map((r) => [String(r.year), base ? (100 * r.sol) / base : null])) };
  }
  function renderHero() {
    const m = S.d.meta, R = m.rasters || {}, years = Object.keys(R.ntl || {}).sort();
    const main = q1("#main"); if (!main) return;
    let hx = q1("#hx");
    if (!hx) { hx = document.createElement("section"); hx.id = "hx"; hx.className = "hx"; main.parentNode.insertBefore(hx, main); }
    stopHero();
    HX.years = years; HX.i = RM ? years.length - 1 : 0; HX.idx = nationalIndex();
    const tl = (m.media || {}).timelapse;
    // the exported timelapse carries its own title and year: use it only when the yearly rasters are missing,
    // otherwise the hero animates the rasters itself (in sync with its year counter)
    HX.tl = tl && tl.file && !years.length ? `data/${S.iso}/${tl.file}` : null;
    const P = R.bounds ? projector(R.bounds) : null;
    const n1 = (S.d.adm1?.features || []).length, n2 = (S.d.adm2?.features || []).length;
    const [a, b] = m.period || [years[0], years[years.length - 1]];
    const grat = [];
    if (P) {
      const [w, s, e, n] = R.bounds;
      for (let x = Math.ceil(w); x <= Math.floor(e); x++) { const [x0, y0] = P.p(x, n), [x1, y1] = P.p(x, s); grat.push(`M${x0.toFixed(1)} ${y0.toFixed(1)}L${x1.toFixed(1)} ${y1.toFixed(1)}`); }
      for (let y = Math.ceil(s); y <= Math.floor(n); y++) { const [x0, y0] = P.p(w, y), [x1, y1] = P.p(e, y); grat.push(`M${x0.toFixed(1)} ${y0.toFixed(1)}L${x1.toFixed(1)} ${y1.toFixed(1)}`); }
    }
    const svg = P ? `<svg class="hx-svg" viewBox="0 0 ${P.W} ${P.H.toFixed(1)}" preserveAspectRatio="xMidYMid meet" aria-hidden="true" focusable="false">
        <defs><filter id="hx-glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="7"/></filter></defs>
        <path class="hx-grat" d="${grat.join("")}"/>
        <path class="hx-adm1" d="${geoPath(S.d.adm1, P)}"/>
        <path class="hx-glow" d="${geoPath(outer(S.d.adm0 || S.d.adm1), P)}" filter="url(#hx-glow)"/>
        <path class="hx-edge" pathLength="1" d="${geoPath(outer(S.d.adm0 || S.d.adm1), P)}"/>
      </svg>` : "";
    const first = years.length ? rasterUrl(R.ntl[years[HX.i]]) : "";
    // the country flag also becomes the browser-tab icon
    try { let ic = document.querySelector('link[rel="icon"]'); if (!ic) { ic = document.createElement("link"); ic.rel = "icon"; document.head.appendChild(ic); }
      ic.type = "image/svg+xml"; ic.href = `data/${S.iso}/flag.svg`; } catch (e) { /* no favicon */ }
    hx.innerHTML = `
      <div class="hx-sky" aria-hidden="true"></div>
      <div class="hx-inner">
        <div class="hx-copy">
          <p class="hx-eyebrow"><span class="hx-dot" aria-hidden="true"></span>${h(TX.eyebrow)}</p>
          <h2 class="hx-title">${h(TX.t1)} <span>${h(TX.t2)}</span></h2>
          <p class="hx-country"><img class="hx-flag" src="data/${h(S.iso)}/flag.svg" alt="${h((LANG === "fr" ? "Drapeau : " : "Flag: ") + m.name)}" onerror="this.remove()"><b>${h(m.name)}</b><span aria-hidden="true"> · </span><span class="sr">, </span>${h(a)}–${h(b)}</p>
          <p class="hx-pitch">${h(TX.pitch)}</p>
          <div class="hx-cta">
            <a class="hx-btn primary" href="#map">${h(TX.cta_map)}<span aria-hidden="true">→</span></a>
            <a class="hx-btn ghost" href="#assistant"><span aria-hidden="true" class="hx-spark">✦</span>${h(TX.cta_ai)}</a>
          </div>
          <p class="hx-meta">${h(fmt(TX.hx_units, { n1, n2, ny: years.length }))}</p>
        </div>
        <figure class="hx-vis" role="img" aria-label="${h(fmt(TX.hx_fig, { a: years[0] || a, b: years[years.length - 1] || b }))}">
          <div class="hx-frame">
            <img class="hx-img on" alt="" src="${h(HX.tl && !RM ? HX.tl : first)}" decoding="async">
            <img class="hx-img" alt="" decoding="async">
            ${svg}
          </div>
          <figcaption class="hx-cap">
            <div class="hx-yearrow">
              <span class="hx-year" aria-hidden="true">${h(years[HX.i] || b)}</span>
              ${years.length > 1 && !RM ? `<button type="button" class="hx-play" aria-pressed="true" aria-label="${h(TX.pause)}">${ICON.pause}</button>` : ""}
            </div>
            <div class="hx-track" aria-hidden="true">${years.map((y, i) => `<i data-i="${i}"></i>`).join("")}</div>
            <div class="hx-idx" aria-hidden="true"><span>${h(TX.hx_idx)}</span> <b class="hx-idxv">–</b> <small>${h(fmt(TX.hx_base, { y: HX.idx.base || years[0] }))}</small></div>
            <small class="hx-src">${h(TX.hx_cap)}</small>
          </figcaption>
        </figure>
      </div>`;
    HX.imgs = qa(".hx-img", hx); HX.front = 0;
    HX.imgs.forEach((im) => { im.onerror = () => { im.style.visibility = "hidden"; }; });
    heroFrame(HX.i, true);
    const pb = q1(".hx-play", hx);
    if (pb) pb.onclick = () => { HX.playing = !HX.playing; heroPlayUI(); if (HX.playing) heroLoop(); else stopHero(); };
    // preload every year, then start (only while the hero is visible)
    if (!RM && years.length > 1 && !HX.tl) {
      Promise.all(years.map((y) => preload(rasterUrl(R.ntl[y])))).then(() => { if (HX.playing) heroLoop(); });
    }
    if ("IntersectionObserver" in window && !HX.io) {
      HX.io = new IntersectionObserver((es) => { HX.visible = es[0].isIntersecting; if (!HX.visible) stopHero(); else if (HX.playing) heroLoop(); }, { threshold: 0.15 });
    }
    if (HX.io) { HX.io.disconnect(); HX.io.observe(hx); }
    syncHero();
  }
  function heroPlayUI() {
    const pb = q1(".hx-play"); if (!pb) return;
    pb.innerHTML = HX.playing ? ICON.pause : ICON.play;
    pb.setAttribute("aria-pressed", String(HX.playing)); pb.setAttribute("aria-label", HX.playing ? TX.pause : TX.play);
    if (HX.tl) { const R = S.d.meta.rasters; HX.imgs[0].src = HX.playing ? HX.tl : rasterUrl(R.ntl[HX.years[HX.years.length - 1]]); }
  }
  function heroFrame(i, instant) {
    const y = HX.years[i]; if (!y) return;
    const R = S.d.meta.rasters, url = rasterUrl(R.ntl[y]);
    if (!HX.tl) {
      const back = HX.imgs[1 - HX.front], front = HX.imgs[HX.front];
      if (instant) { front.src = url; }
      else {
        preload(url).then(() => { back.src = url; back.classList.add("on"); front.classList.remove("on"); HX.front = 1 - HX.front; });
      }
    }
    const ye = q1(".hx-year"); if (ye) { ye.textContent = y; if (!instant) { ye.classList.remove("tick"); void ye.offsetWidth; ye.classList.add("tick"); } }
    qa(".hx-track i").forEach((el, k) => { el.className = k < i ? "past" : k === i ? "now" : ""; });
    const v = HX.idx.by[y]; const iv = q1(".hx-idxv"); if (iv) iv.textContent = num(v) ? F.num(v) : "–";
  }
  function heroLoop() {
    clearTimeout(HX.timer);
    if (RM || !HX.playing || !HX.visible || pageName() !== "overview" || document.hidden) return;
    if (HX.tl) return;   // animated webp plays by itself
    const last = HX.i >= HX.years.length - 1;
    HX.timer = setTimeout(() => { HX.i = last ? 0 : HX.i + 1; heroFrame(HX.i); heroLoop(); }, last ? 2600 : 1150);
  }
  function stopHero() { clearTimeout(HX.timer); }
  function syncHero() {
    const hx = q1("#hx"); if (!hx) return;
    const on = pageName() === "overview";
    hx.hidden = !on;
    if (on && HX.playing) heroLoop(); else stopHero();
  }
  document.addEventListener("visibilitychange", () => { if (document.hidden) { stopHero(); stopPlay(true); } else syncHero(); });

  let counted = false;
  function countUp() {
    const ks = (S.d.summary || {}).kpis || [], els = qa("#kpis .kpi .value");
    if (counted || RM || !ks.length || els.length !== ks.length) { counted = true; return; }
    counted = true;
    const f = (k, v) => (k.fmt === "num" ? F.num(Number.isInteger(k.value) ? Math.round(v) : v) : k.fmt === "pct" ? F.pct(v) : k.fmt === "pct0" ? F.share(v) : k.fmt === "people" ? F.people(v) : F.num2(v));
    const box = q1("#kpis"); box.setAttribute("aria-busy", "true");
    const t0 = performance.now(), D = 1400;
    els.forEach((el) => { el.style.minWidth = el.offsetWidth + "px"; });
    const step = (t) => {
      const p = Math.min(1, (t - t0) / D), e = 1 - Math.pow(1 - p, 3);
      ks.forEach((k, i) => { if (num(k.value)) els[i].textContent = f(k, k.value * e); });
      if (p < 1) requestAnimationFrame(step);
      else { ks.forEach((k, i) => { if (num(k.value)) els[i].textContent = f(k, k.value); }); box.removeAttribute("aria-busy"); }
    };
    requestAnimationFrame(step);
    qa("#kpis .kpi").forEach((el, i) => { el.style.animationDelay = i * 60 + "ms"; el.classList.add("kin"); });
  }

  /* ================================================================== image preloading */
  const IMG = new Map();
  function preload(url) {
    if (!url) return Promise.resolve(null);
    if (!IMG.has(url)) IMG.set(url, new Promise((res) => {
      const im = new Image();
      im.onload = () => (im.decode ? im.decode().catch(() => {}) : Promise.resolve()).then(() => res(im));
      im.onerror = () => res(null);
      im.src = url;
    }));
    return IMG.get(url);
  }

  /* ================================================================== MAP */
  const MODES = ["lights", "swipe", "dark", "indicator", "industry", "tourism"];
  const M = { mode: "lights", year: null, a: null, b: null, lv: "ADM2", ind: "growth", unit: null, ov: { industry: false, tourism: false, boundaries: true },
    op: 0.95, swipe: 0.5, playing: false, speed: 1, panel: !matchMedia("(max-width: 760px)").matches };
  let X = {};               // live Leaflet objects for the current render
  let YEARS = [], DYEARS = [], UNITS = new Map(), ANN = new Map();
  let readyRes, readyDone = false, ready = new Promise((r) => { readyRes = r; });
  const baseMode = () => (M.mode === "industry" || M.mode === "tourism" ? "lights" : M.mode);
  const timeMode = () => baseMode() === "lights";
  const lastYear = () => YEARS[YEARS.length - 1];
  const typeColor = (t) => cssv({ heavy: "--t1", logistics: "--t2", hydro: "--t3", isolated: "--t4" }[t] || "--muted", { heavy: "#00704A", logistics: "#3F7FC7", hydro: "#eda100", isolated: "#e87ba4" }[t] || "#999");
  const classKey = (c) => { const n = norm(c); return /croiss|growth/.test(n) ? "grow" : /declin|decline/.test(n) ? "decline" : /stagn/.test(n) ? "flat" : null; };
  const classColor = (c) => { const k = classKey(c); return k ? cssv("--" + k, "#999") : cssv("--grid", "#555"); };
  const indList = () => (typeof INDICATORS !== "undefined" ? INDICATORS : []).filter((i) => !i.lvl || i.lvl === M.lv);
  const indOf = (k) => (typeof INDICATORS !== "undefined" ? INDICATORS : []).find((i) => i.k === k);
  const yearOf = (y) => { if (y == null) return null; const s = String(y); if (YEARS.includes(s)) return s; const n = +y; if (!Number.isFinite(n) || !YEARS.length) return null; return YEARS.reduce((b, c) => (Math.abs(+c - n) < Math.abs(+b - n) ? c : b)); };
  const onMap = () => pageName() === "map";

  function buildIndex() {
    UNITS = new Map(); ANN = new Map();
    for (const lv of ["ADM1", "ADM2"]) {
      ((S.d[lv.toLowerCase()] || {}).features || []).forEach((f) => {
        const p = f.properties || {}; if (!p.unit_id) return;
        UNITS.set(p.unit_id, { unit_id: p.unit_id, name: p.name || p.unit_id, level: lv, parent: p.parent_name || "", f, n: norm((p.name || "") + " " + (p.parent_name || "") + " " + p.unit_id) });
      });
    }
    (S.d.annual || []).forEach((r) => { if (!ANN.has(r.unit_id)) ANN.set(r.unit_id, []); ANN.get(r.unit_id).push(r); });
    ANN.forEach((v) => v.sort((a, b) => a.year - b.year));
  }
  const annAt = (uid, y) => (ANN.get(uid) || []).find((r) => String(r.year) === String(y));

  function findUnit(q) {
    if (!q) return null;
    if (typeof q === "object" && q.unit_id) q = q.unit_id;
    if (UNITS.has(q)) return UNITS.get(q);
    const n = norm(q); if (!n) return null;
    const all = [...UNITS.values()];
    return all.find((u) => norm(u.unit_id) === n) || all.find((u) => norm(u.name) === n) ||
      all.find((u) => norm(u.name).startsWith(n)) || all.find((u) => u.n.includes(n)) || null;
  }
  function searchUnits(q, k = 8) {
    const toks = norm(q).split(" ").filter(Boolean); if (!toks.length) return [];
    const res = [...UNITS.values()].filter((u) => toks.every((t) => u.n.includes(t)));
    const nq = norm(q);
    res.sort((a, b) => (norm(b.name).startsWith(nq) - norm(a.name).startsWith(nq)) || (a.level < b.level ? -1 : a.level > b.level ? 1 : 0) || a.name.localeCompare(b.name));
    return res.slice(0, k);
  }

  /* ---------------------------------------------------------------- template */
  function template() {
    const m = S.d.meta, levels = m.levels || ["ADM1"];
    const radio = (v, t, d, ic) => `<label class="mx-mode" data-m="${v}"><input type="radio" name="mx-mode" value="${v}"><span class="mx-mode-ic mx-ic-${v}" aria-hidden="true">${ic}</span><span class="mx-mode-t"><b>${h(t)}</b><small>${h(d)}</small></span></label>`;
    const yopts = (ys) => ys.map((y) => `<option value="${y}">${y}</option>`).join("");
    const sw = (k, t, sw) => `<label class="mx-sw"><input type="checkbox" role="switch" id="mx-ov-${k}" data-ov="${k}"><span class="mx-sw-ui" aria-hidden="true"></span><span class="mx-sw-t">${h(t)}</span>${sw}</label>`;
    const hasInd = !!(S.d.iclusters && (S.d.iclusters.features || []).length);
    const hasTour = !!(S.d.tourism && S.d.tourism.available && (S.d.tourism.units || []).some((u) => u.class === "tourist"));
    return `
    <div class="mx" id="mx">
      <aside class="mx-panel" id="mx-panel" aria-label="${h(TX.layers)}">
        <div class="mx-ph">
          <span class="mx-grab" aria-hidden="true"></span>
          <h2 class="mx-ph-t">${ICON.layers}<span>${h(TX.layers)}</span><small id="mx-sum"></small></h2>
          <button type="button" class="mx-ibtn mx-collapse" id="mx-collapse" aria-controls="mx-pbody" aria-expanded="true" aria-label="${h(TX.hide_panel)}" title="${h(TX.hide_panel)}">${ICON.chev}</button>
        </div>
        <div class="mx-pbody" id="mx-pbody">
          <div class="mx-search">
            <label class="sr" for="mx-q">${h(TX.search_lbl)}</label>
            <span class="mx-search-ic" aria-hidden="true">${ICON.search}</span>
            <input id="mx-q" type="search" autocomplete="off" spellcheck="false" placeholder="${h(TX.search)}" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="mx-res">
            <kbd class="mx-kbd" aria-hidden="true">/</kbd>
            <ul id="mx-res" class="mx-res" role="listbox" aria-label="${h(TX.search_lbl)}" hidden></ul>
          </div>
          <fieldset class="mx-modes"><legend class="sr">Mode</legend>
            ${radio("lights", TX.m_lights, TX.m_lights_d, "")}
            ${radio("swipe", TX.m_swipe, TX.m_swipe_d, "")}
            <div class="mx-sub" data-for="swipe">
              <label>${h(TX.year_a)}<select id="mx-a">${yopts(YEARS)}</select></label>
              <label>${h(TX.year_b)}<select id="mx-b">${yopts(YEARS)}</select></label>
            </div>
            ${DYEARS.length ? radio("dark", TX.m_dark, TX.m_dark_d, "") : ""}
            ${DYEARS.length > 1 ? `<div class="mx-sub" data-for="dark"><label>${h(TX.year)}<select id="mx-dy">${yopts(DYEARS)}</select></label></div>` : ""}
            ${radio("indicator", TX.m_ind, TX.m_ind_d, "")}
            <div class="mx-sub" data-for="indicator">
              <label class="mx-wide">${h(TX.indicator)}<select id="mx-ind"></select></label>
              <p class="mx-note" id="mx-ind-help"></p>
            </div>
          </fieldset>
          <p class="mx-desc" id="mx-desc"></p>
          <h3 class="mx-h">${h(TX.overlays)}</h3>
          ${hasInd ? sw("industry", TX.ov_industry, `<span class="mx-sw-k mx-k-ind" aria-hidden="true"></span>`) : ""}
          ${hasTour ? sw("tourism", TX.ov_tourism, `<span class="mx-sw-k mx-k-tour" aria-hidden="true"></span>`) : ""}
          ${sw("boundaries", TX.ov_bound, `<span class="mx-sw-k mx-k-bnd" aria-hidden="true"></span>`)}
          <div class="mx-row">
            <span class="mx-lbl" id="mx-lv-l">${h(TX.level)}</span>
            <div class="mx-seg" id="mx-lv" role="radiogroup" aria-labelledby="mx-lv-l">${levels.map((l) => `<button type="button" role="radio" data-lv="${l}" aria-checked="false" title="${h(l === "ADM1" ? TX.lv1 : TX.lv2)}">${h(l === "ADM1" ? TX.lv1 : TX.lv2)}</button>`).join("")}</div>
          </div>
          <label class="mx-range"><span>${h(TX.opacity)} <output id="mx-op-v"></output></span><input type="range" id="mx-op" min="20" max="100" step="5"></label>
        </div>
      </aside>
      <div class="mx-stage" id="mx-stage">
        <div id="mx-map" class="mx-map" aria-label="${h(TX.map_lbl)}"></div>
        <button type="button" class="mx-open" id="mx-open" aria-controls="mx-panel" aria-expanded="false">${ICON.layers}<span>${h(TX.layers)}</span></button>
        <div class="mx-year" id="mx-year" aria-live="polite"><span class="y"></span><small></small></div>
        <div class="mx-swipe" id="mx-swipe" hidden>
          <span class="mx-sl l"></span><span class="mx-sl r"></span>
          <div class="mx-swl" id="mx-swl"></div>
          <button type="button" class="mx-swh" id="mx-swh" role="slider" aria-label="${h(TX.divider)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="50">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M9 6 3 12l6 6zM15 6l6 6-6 6z"/></svg></button>
        </div>
        <div class="mx-tools" role="toolbar" aria-label="Map tools" aria-orientation="vertical">
          <button type="button" class="mx-ibtn" id="mx-zin" aria-label="${h(TX.zin)}" title="${h(TX.zin)}">${ICON.plus}</button>
          <button type="button" class="mx-ibtn" id="mx-zout" aria-label="${h(TX.zout)}" title="${h(TX.zout)}">${ICON.minus}</button>
          <span class="mx-tsep" aria-hidden="true"></span>
          <button type="button" class="mx-ibtn" id="mx-reset" aria-label="${h(TX.reset)}" title="${h(TX.reset)}">${ICON.reset}</button>
          <button type="button" class="mx-ibtn" id="mx-fs" aria-label="${h(TX.fs)}" title="${h(TX.fs)} (F)" aria-pressed="false">${ICON.fs}</button>
          <button type="button" class="mx-ibtn" id="mx-share" aria-label="${h(TX.share)}" title="${h(TX.share)}">${ICON.share}</button>
          <button type="button" class="mx-ibtn" id="mx-helpb" aria-label="${h(TX.help)}" title="${h(TX.help)} (?)" aria-expanded="false" aria-controls="mx-help">${ICON.help}</button>
        </div>
        <div class="mx-help" id="mx-help" role="dialog" aria-label="${h(TX.k_title)}" hidden>
          <div class="mx-help-h"><b>${h(TX.k_title)}</b><button type="button" class="mx-ibtn sm" id="mx-help-x" aria-label="${h(TX.close)}">✕</button></div>
          <dl>
            <div><dt><kbd>←</kbd> <kbd>→</kbd></dt><dd>${h(TX.k_year)}</dd></div>
            <div><dt><kbd>${LANG === "fr" ? "Espace" : "Space"}</kbd></dt><dd>${h(TX.k_play)}</dd></div>
            <div><dt><kbd>F</kbd></dt><dd>${h(TX.k_fs)}</dd></div>
            <div><dt><kbd>/</kbd></dt><dd>${h(TX.k_search)}</dd></div>
            <div><dt><kbd>?</kbd></dt><dd>${h(TX.k_help)}</dd></div>
            <div><dt><kbd>Échap</kbd></dt><dd>${h(TX.k_esc)}</dd></div>
          </dl>
        </div>
        <div class="mx-time" id="mx-time">
          <button type="button" class="mx-play" id="mx-play" aria-pressed="false" aria-label="${h(TX.play)}" title="${h(TX.play)} (${LANG === "fr" ? "Espace" : "Space"})">${ICON.play}</button>
          <div class="mx-slider">
            <label class="sr" for="mx-yr">${h(TX.year)}</label>
            <input type="range" id="mx-yr" min="0" max="${Math.max(0, YEARS.length - 1)}" step="1" value="${Math.max(0, YEARS.length - 1)}">
            <div class="mx-ticks" aria-hidden="true">${YEARS.map((y, i) => `<span data-i="${i}" style="left:${YEARS.length > 1 ? (100 * i) / (YEARS.length - 1) : 100}%">${y}</span>`).join("")}</div>
          </div>
          <button type="button" class="mx-speed" id="mx-speed" aria-label="${h(TX.speed)} : 1×" title="${h(TX.speed)}">1×</button>
        </div>
        <div class="mx-legends" id="mx-legends"></div>
        <div class="mx-loading" id="mx-loading" role="status"><span class="mx-spin" aria-hidden="true"></span><span>${h(TX.loading)}</span></div>
        <div class="map-fallback" id="map-fallback" hidden></div>
      </div>
    </div>
    <p class="source mx-source" id="mx-src"></p>`;
  }

  /* ---------------------------------------------------------------- render */
  function renderMap() {
    const page = q1("#page-map"); if (!page) return;
    stopPlay(true);
    if (X.map) { try { X.map.remove(); } catch (e) { /* already removed by the country switch */ } }
    X = {};
    if (readyDone) { readyDone = false; ready = new Promise((r) => { readyRes = r; }); }
    const m = S.d.meta, R = m.rasters || {};
    YEARS = Object.keys(R.ntl || {}).sort(); DYEARS = Object.keys(R.dark || {}).sort();
    buildIndex();
    const levels = m.levels || ["ADM1"];
    if (!levels.includes(M.lv)) M.lv = levels[levels.length - 1];
    M.year = yearOf(M.year) || lastYear(); M.a = yearOf(M.a) || YEARS[0]; M.b = yearOf(M.b) || lastYear();
    M.dy = DYEARS.includes(M.dy) ? M.dy : DYEARS[DYEARS.length - 1];
    if (!indOf(M.ind)) M.ind = ((typeof INDICATORS !== "undefined" && INDICATORS[0]) || {}).k;
    if (onMap()) readParams(hashQuery());
    page.innerHTML = template();
    wire();
    sizeMap();
    const src = q1("#mx-src");
    src.textContent = fmt(TX.src, { b: (m.boundaries || {}).ADM1 || "geoBoundaries", p: m.pop_source || "GHSL" });
    if (!window.L) {
      const fb = q1("#map-fallback"); fb.hidden = false; q1("#mx-loading").hidden = true;
      fb.textContent = LANG === "fr" ? "La bibliothèque cartographique (Leaflet) n'a pas pu être chargée. Les autres pages restent disponibles." : "The mapping library (Leaflet) could not be loaded. The other pages remain available.";
      syncControls(); finishReady(); return;
    }
    try { buildMap(); } catch (e) {
      console.error(e); const fb = q1("#map-fallback"); fb.hidden = false; fb.textContent = String(e && e.message || e); q1("#mx-loading").hidden = true; finishReady(); return;
    }
    apply();
    const firstUrl = rasterFor();
    preload(firstUrl).then(() => { const l = q1("#mx-loading"); if (l) l.classList.add("done"); setTimeout(() => { if (l) l.hidden = true; }, 400); });
    // warm the cache for smooth playback
    const idle = window.requestIdleCallback || ((f) => setTimeout(f, 600));
    idle(() => YEARS.forEach((y) => preload(rasterUrl(R.ntl[y]))));
    setTimeout(() => { if (!X.map) return; X.map.invalidateSize(); if (!M.unit) X.map.fitBounds(mapBounds(), { padding: pad(), animate: false }); else { const u = UNITS.get(M.unit); if (u) selectUnit(u, { fly: false }); } }, 60);
    finishReady();
  }
  function sizeMap() {
    const mx = q1("#mx"); if (!mx || isFS() || !onMap()) return;
    const top = mx.getBoundingClientRect().top + window.scrollY;
    const avail = window.innerHeight - Math.min(top, window.innerHeight * 0.42) - 14;
    mx.style.height = Math.round(Math.max(480, Math.min(1000, avail))) + "px";
    if (X.map) X.map.invalidateSize();
  }
  window.addEventListener("resize", () => { clearTimeout(sizeMap._t); sizeMap._t = setTimeout(sizeMap, 120); });
  function finishReady() { readyDone = true; readyRes(); }
  const pad = () => (matchMedia("(max-width: 760px)").matches ? [24, 24] : [36, 36]);

  function buildMap() {
    const el = q1("#mx-map");
    const mp = L.map(el, { zoomSnap: 0.25, zoomDelta: 0.5, zoomControl: false, worldCopyJump: false, fadeAnimation: !RM, zoomAnimation: !RM, markerZoomAnimation: !RM });
    X.map = mp; S.map = mp;   // app.js invalidates S.map on route and removes it on country change
    mp.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
    mp.attributionControl.setPosition("bottomright");
    // night-lights always read best on a dark basemap, whatever the UI theme
    X.base = L.tileLayer(TILES.dark, { attribution: TILE_ATTR, subdomains: "abcd", maxZoom: 19, className: "mx-tiles" }).addTo(mp);
    [["raster", 350], ["units", 380], ["top", 420], ["pts", 440], ["hl", 460]].forEach(([n, z]) => { mp.createPane(n); mp.getPane(n).style.zIndex = z; });
    mp.getPane("raster").style.pointerEvents = "none";
    L.control.scale({ imperial: false, position: "bottomright" }).addTo(mp);
    mp.fitBounds(mapBounds(), { padding: pad(), animate: false });
    const R = S.d.meta.rasters || {};
    if (R.bounds) {
      const [w, s, e, n] = R.bounds, bb = [[s, w], [n, e]];
      const mk = (cls) => L.imageOverlay(rasterUrl(R.ntl[M.year] || Object.values(R.ntl || {})[0]), bb, { pane: "raster", opacity: 0, interactive: false, className: "mx-img " + cls });
      X.ntl = [mk("ntl"), mk("ntl")]; X.front = 0;
      X.swA = mk("swa"); X.swB = mk("swb");
      X.dark = DYEARS.length ? L.imageOverlay(rasterUrl(R.dark[M.dy]), bb, { pane: "raster", opacity: 0, interactive: false, className: "mx-img dark" }) : null;
      X.swB.on("load", clipSwipe);
    }
    // units (interactive in every mode)
    X.units = {}; X.byId = {};
    for (const lv of ["ADM1", "ADM2"]) {
      const gj = S.d[lv.toLowerCase()]; if (!gj) continue;
      X.units[lv] = L.geoJSON(gj, {
        pane: "units", style: (f) => unitStyle(f, lv),
        onEachFeature: (f, l) => {
          X.byId[f.properties.unit_id] = l;
          l.bindTooltip(() => tipHtml(f.properties, lv), { sticky: true, direction: "top", opacity: 1, className: "mx-tip", offset: [0, -6] });
          l.on({
            mouseover: (e) => { e.target.setStyle({ weight: lv === "ADM1" ? 2.6 : 2, color: GOLD, opacity: 1 }); },
            mouseout: (e) => { e.target.setStyle(unitStyle(f, lv)); },
            click: () => { const u = UNITS.get(f.properties.unit_id); if (u) selectUnit(u); },
          });
        },
      });
    }
    X.adm1line = S.d.adm1 ? L.geoJSON(S.d.adm1, { pane: "top", interactive: false, style: { color: "rgba(255,255,255,.5)", weight: 1.2, fill: false } }) : null;
    const g0 = outer(S.d.adm0 || S.d.adm1);
    X.adm0 = g0 ? L.featureGroup([
      L.geoJSON(g0, { pane: "top", interactive: false, style: { color: GOLD, weight: 7, opacity: 0.13, fill: false } }),
      L.geoJSON(g0, { pane: "top", interactive: false, style: { color: "#ffe6a3", weight: 1.4, opacity: 0.75, fill: false } }),
    ]) : null;
    // industrial clusters
    const ic = S.d.iclusters;
    if (ic && (ic.features || []).length) {
      const mx = Math.max(...ic.features.map((f) => f.properties.sol_last || 0), 1);
      const pts = [];
      const poly = L.geoJSON(ic, {
        pane: "pts",
        style: (f) => ({ color: typeColor(f.properties.type), weight: 1.6, fillColor: typeColor(f.properties.type), fillOpacity: 0.32 }),
        onEachFeature: (f, l) => {
          const p = f.properties;
          l.bindPopup(() => clusterHtml(p), { maxWidth: 300, className: "mx-pop", autoPanPadding: [60, 60] });
          const c = num(p.lat) && num(p.lon) ? L.latLng(p.lat, p.lon) : l.getBounds().getCenter();
          const cm = L.circleMarker(c, { pane: "pts", radius: 4.5 + 8 * Math.sqrt((p.sol_last || 0) / mx), color: "#fff", weight: 1.6, fillColor: typeColor(p.type), fillOpacity: 0.95 });
          cm.bindTooltip(`<b>${h(p.cluster_id)}</b> · ${h(p.type_label || p.type)}`, { direction: "top", className: "mx-tip", opacity: 1 });
          cm.bindPopup(() => clusterHtml(p), { maxWidth: 300, className: "mx-pop", autoPanPadding: [60, 60] });
          pts.push(cm);
        },
      });
      X.ind = L.featureGroup([poly, ...pts]);
      X.indTypes = [...new Map(ic.features.map((f) => [f.properties.type, f.properties.type_label || f.properties.type])).entries()];
    }
    // tourist zones
    const T = S.d.tourism;
    if (T && T.available) {
      const tu = Object.fromEntries((T.units || []).filter((u) => u.class === "tourist").map((u) => [u.unit_id, u]));
      const gj = S.d[(T.level || "ADM2").toLowerCase()];
      if (gj && Object.keys(tu).length) {
        X.tour = L.geoJSON({ type: "FeatureCollection", features: gj.features.filter((f) => tu[f.properties.unit_id]) }, {
          pane: "top", style: { color: GOLD, weight: 2.4, dashArray: "6 5", fillColor: GOLD, fillOpacity: 0.1, className: "mx-tour" },
          onEachFeature: (f, l) => {
            const r = tu[f.properties.unit_id];
            l.bindTooltip(`<b>${h(r.name || f.properties.name)}</b><span>${h(TX.t_net)} : ${F.pct(r.net_gain, 0)}</span>`, { sticky: true, direction: "top", className: "mx-tip", opacity: 1 });
            l.on("click", () => { const u = UNITS.get(f.properties.unit_id); if (u) selectUnit(u); });
          },
        });
      }
    }
    // events
    mp.on("popupclose", (e) => { if (e.popup && e.popup._uid && e.popup._uid === M.unit) { M.unit = null; clearHL(); writeHash(); } });
    mp.on("move zoom resize viewreset", clipSwipe);
    mp.on("zoomanim", () => clipLoop(360));
    mp.on("zoomend moveend", () => clipSwipe());
  }

  function unitStyle(f, lv) {
    const bm = baseMode(), w = lv === "ADM1" ? 1.1 : 0.6;
    if (bm === "indicator") return { color: "rgba(255,255,255,.6)", weight: w, opacity: 1, fillColor: X.colorOf ? X.colorOf(f.properties) : "#888", fillOpacity: 0.82, dashArray: null };
    return { color: "rgba(255,255,255,.3)", weight: w, opacity: M.ov.boundaries ? 1 : 0, fill: true, fillColor: "#000", fillOpacity: 0, dashArray: null };
  }
  function tipHtml(p, lv) {
    const bm = baseMode(); let v = "";
    if (bm === "indicator") {
      const ind = indOf(M.ind) || {};
      v = `${h(ind.t || "")} : <b>${ind.kind === "cat" ? h(p.class || "–") : h(ind.fmt ? ind.fmt(p[ind.k]) : p[ind.k])}</b>`;
    } else if (bm === "swipe") {
      const a = annAt(p.unit_id, M.a), b = annAt(p.unit_id, M.b);
      v = `${h(fmt(TX.change, { a: M.a, b: M.b }))} : <b>${a && b && a.sol ? F.pct(b.sol / a.sol - 1, 0) : "–"}</b>`;
    } else if (bm === "dark") {
      v = `${h(TX.p_dark)} : <b>${F.people(p.pop_dark)}</b> (${F.share(p.dark_share)})`;
    } else {
      const r = annAt(p.unit_id, M.year);
      v = `${h(fmt(TX.light_y, { y: M.year }))} : <b>${r ? F.num(r.sol) : F.num(p.sol)}</b>`;
    }
    return `<b class="mx-tip-n">${h(p.name)}</b><span>${v}</span>`;
  }
  function spark(uid) {
    const s = (ANN.get(uid) || []).filter((r) => num(r.sol)); if (s.length < 2) return "";
    const W = 252, H = 58, P = 5, xs = s.map((r) => r.year), ys = s.map((r) => r.sol);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys) || 1;
    const X_ = (x) => P + ((x - x0) / Math.max(1, x1 - x0)) * (W - 2 * P), Y_ = (y) => H - P - ((y - y0) / Math.max(1e-9, y1 - y0)) * (H - 2 * P - 6);
    const pts = s.map((r) => `${X_(r.year).toFixed(1)},${Y_(r.sol).toFixed(1)}`);
    const cur = s.find((r) => String(r.year) === String(M.year)) || s[s.length - 1];
    const ch = s[s.length - 1].sol / s[0].sol - 1;
    return `<figure class="mxp-spark"><figcaption><span>${h(TX.p_spark)} ${x0}–${x1}</span><b class="${ch >= 0 ? "up" : "down"}">${F.pct(ch, 0)}</b></figcaption>
      <svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" role="img" aria-label="${h(TX.p_spark)} ${x0}–${x1} : ${F.pct(ch, 0)}">
      <defs><linearGradient id="sg-${h(uid)}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="currentColor" stop-opacity=".35"/><stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient></defs>
      <path d="M${pts[0]}L${pts.join("L")}L${X_(x1).toFixed(1)},${H - P}L${X_(x0).toFixed(1)},${H - P}Z" fill="url(#sg-${h(uid)})"/>
      <polyline points="${pts.join(" ")}" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
      <circle cx="${X_(cur.year).toFixed(1)}" cy="${Y_(cur.sol).toFixed(1)}" r="3.6" fill="currentColor" stroke="var(--surface)" stroke-width="1.6"/>
      </svg></figure>`;
  }
  function popupHtml(u) {
    const p = u.f.properties, lvT = u.level === "ADM1" ? TX.region : TX.district;
    const rows = [[TX.p_sol, F.num(p.sol)], [TX.p_share, F.share(p.share_last, 1)], [TX.p_growth, F.pct(p.growth) + TX.per_yr], [TX.p_solpc, F.num(p.sol_pc, 3)],
      [TX.p_pop, F.people(p.pop)], [TX.p_dark, `${F.people(p.pop_dark)} <small>(${F.share(p.dark_share)})</small>`]];
    if (u.level === "ADM1" && num(p.gdp_pc_est)) rows.push([TX.p_gdp, F.num(p.gdp_pc_est) + " USD"]);
    const cls = p.class ? `<span class="mxp-badge" style="--c:${classColor(p.class)}">${h(p.class)}</span>` : "";
    return `<div class="mxp"><div class="mxp-h"><div><div class="mxp-lv">${h(lvT)}${u.parent ? " · " + h(u.parent) : ""}</div><h3>${h(u.name)}</h3></div>${cls}</div>
      ${spark(u.unit_id)}<dl class="mxp-grid">${rows.map(([a, b]) => `<div><dt>${h(a)}</dt><dd>${b}</dd></div>`).join("")}</dl></div>`;
  }
  function clusterHtml(p) {
    return `<div class="mxp"><div class="mxp-h"><div><div class="mxp-lv">${h(TX.ov_industry)}</div><h3>${h(p.cluster_id)} · ${h(p.type_label || p.type)}</h3></div>
      <span class="mxp-badge" style="--c:${typeColor(p.type)}">${h(p.confidence || "")}</span></div>
      <dl class="mxp-grid"><div><dt>${h(TX.i_where)}</dt><dd>${h(p.adm2_name || p.adm1_name || "–")}</dd></div><div><dt>${h(TX.i_area)}</dt><dd>${F.num(p.area_km2, 1)} km²</dd></div>
      <div><dt>${h(TX.i_light)}</dt><dd>${F.num(p.sol_last)}</dd></div><div><dt>${h(TX.i_conf)}</dt><dd>${h(p.confidence || "–")}</dd></div></dl></div>`;
  }

  /* ---------------------------------------------------------------- selection */
  function clearHL() { if (X.hl && X.map) X.map.removeLayer(X.hl); X.hl = null; }
  function selectUnit(u, o = {}) {
    if (!X.map) { M.unit = u.unit_id; return; }
    if (u.level !== M.lv) { M.lv = u.level; apply(); }
    M.unit = u.unit_id; clearHL();
    X.hl = L.featureGroup([
      L.geoJSON(u.f, { pane: "hl", interactive: false, style: { color: GOLD, weight: 10, opacity: 0.22, fill: false } }),
      L.geoJSON(u.f, { pane: "hl", interactive: false, style: { color: "#ffe6a3", weight: 2.6, opacity: 1, fillColor: GOLD, fillOpacity: 0.08, className: "mx-hl" } }),
    ]).addTo(X.map);
    const lyr = X.byId[u.unit_id], b = lyr ? lyr.getBounds() : L.geoJSON(u.f).getBounds();
    const c = lyr && lyr.getCenter ? lyr.getCenter() : b.getCenter();
    let done = false;
    const open = () => {
      if (done || M.unit !== u.unit_id) return; done = true;
      const pp = L.popup({ maxWidth: 300, minWidth: 260, className: "mx-pop", autoPanPaddingTopLeft: [24, 90], autoPanPaddingBottomRight: [70, 110] }).setLatLng(c).setContent(popupHtml(u));
      pp._uid = u.unit_id; pp.openOn(X.map);
    };
    const fly = o.fly !== false && !RM;
    const opts = { padding: [70, 70], maxZoom: u.level === "ADM1" ? 9 : 10.5 };
    if (fly) { X.map.flyToBounds(b, { ...opts, duration: 0.9 }); X.map.once("moveend", open); setTimeout(open, 1500); }
    else { X.map.fitBounds(b, { ...opts, animate: false }); open(); }
    writeHash();
    return { unit_id: u.unit_id, name: u.name, level: u.level };
  }

  /* ---------------------------------------------------------------- rasters */
  const rasterFor = () => { const R = S.d.meta.rasters || {}; return baseMode() === "dark" ? (R.dark && rasterUrl(R.dark[M.dy])) : R.ntl && R.ntl[M.year] ? rasterUrl(R.ntl[M.year]) : null; };
  function show(l, on) { if (!X.map || !l) return; if (on && !X.map.hasLayer(l)) l.addTo(X.map); if (!on && X.map.hasLayer(l)) X.map.removeLayer(l); }
  let swapTok = 0;
  function setNtl(on) {
    if (!X.ntl) return;
    X.ntl.forEach((l) => show(l, on));
    if (!on) return;
    const R = S.d.meta.rasters, url = rasterUrl(R.ntl[M.year]), front = X.ntl[X.front], back = X.ntl[1 - X.front];
    if (front._url === url) { front.setOpacity(M.op); back.setOpacity(0); return; }
    const tok = ++swapTok;
    preload(url).then(() => {
      if (tok !== swapTok) return;
      let fired = false;
      const go = () => { if (fired || tok !== swapTok) return; fired = true; back.setOpacity(M.op); front.setOpacity(0); X.front = 1 - X.front; };
      back.once("load", go); back.setUrl(url); setTimeout(go, 250);
    });
  }
  function setSwipe(on) {
    if (!X.swA) return;
    show(X.swA, on); show(X.swB, on);
    q1("#mx-swipe").hidden = !on;
    if (!on) return;
    const R = S.d.meta.rasters, ua = rasterUrl(R.ntl[M.a]), ub = rasterUrl(R.ntl[M.b]);
    if (X.swA._url !== ua) X.swA.setUrl(ua);
    if (X.swB._url !== ub) X.swB.setUrl(ub);
    X.swA.setOpacity(M.op); X.swB.setOpacity(M.op);
    q1("#mx-swipe .l").textContent = M.a; q1("#mx-swipe .r").textContent = M.b;
    swipeUI();
  }
  function swipeUI() {
    const sw = q1("#mx-swipe"); if (!sw) return;
    sw.style.setProperty("--sx", (M.swipe * 100).toFixed(2) + "%");
    const hd = q1("#mx-swh"); hd.setAttribute("aria-valuenow", Math.round(M.swipe * 100));
    hd.setAttribute("aria-valuetext", `${M.a} | ${M.b} — ${Math.round(M.swipe * 100)} %`);
    clipSwipe();
  }
  function clipSwipe() {
    if (!X.swB || baseMode() !== "swipe") return;
    const img = X.swB.getElement(), cont = q1("#mx-map"); if (!img || !cont) return;
    const cr = cont.getBoundingClientRect(), ir = img.getBoundingClientRect();
    if (!img.offsetWidth) return;
    const sc = ir.width / img.offsetWidth || 1, x = cr.left + M.swipe * cr.width;
    img.style.clipPath = `inset(0 0 0 ${Math.max(0, (x - ir.left) / sc).toFixed(1)}px)`;
  }
  function clipLoop(ms) { const t0 = performance.now(); const f = (t) => { clipSwipe(); if (t - t0 < ms) requestAnimationFrame(f); }; requestAnimationFrame(f); }

  /* ---------------------------------------------------------------- indicator scale */
  function computeScale() {
    const ind = indOf(M.ind); X.colorOf = null; X.indLeg = "";
    if (!ind) return;
    const feats = (S.d[M.lv.toLowerCase()] || {}).features || [];
    if (ind.kind === "cat") {
      const cl = [...new Set(feats.map((f) => f.properties.class).filter(Boolean))].sort((a, b) => ["decline", "flat", "grow"].indexOf(classKey(a)) - ["decline", "flat", "grow"].indexOf(classKey(b)));
      X.colorOf = (p) => classColor(p.class);
      X.indLeg = cl.map((c) => `<div class="lg-it"><span class="sw" style="background:${classColor(c)}"></span>${h(c)}</div>`).join("");
      return;
    }
    const vals = feats.map((f) => f.properties[ind.k]).filter(num);
    if (!vals.length) { X.colorOf = () => cssv("--grid", "#555"); X.indLeg = `<div class="lg-it">${h(TX.na)}</div>`; return; }
    let breaks, ramp, lo = Math.min(...vals), hi = Math.max(...vals);
    if (ind.kind === "div") { const mx = Math.max(...vals.map(Math.abs), 0.01), st = mx / 3.5; breaks = [-2.5 * st, -1.5 * st, -0.5 * st, 0.5 * st, 1.5 * st, 2.5 * st]; ramp = DIV; lo = -mx; hi = mx; }
    else { breaks = quantiles(vals); ramp = ind.kind === "seqo" ? SEQ_O : SEQ_B; }
    const uq = breaks.filter((b, i) => i === 0 || b > breaks[i - 1]);
    X.colorOf = (p) => { const v = p[ind.k]; if (!num(v)) return "#4a4f57"; let k = 0; while (k < uq.length && v >= uq[k]) k++; return ramp[Math.min(k, ramp.length - 1)]; };
    X.indLeg = `<div class="ramp" style="background:linear-gradient(90deg,${ramp.join(",")})"></div><div class="ticks"><span>${h(ind.fmt(lo))}</span>${ind.kind === "div" ? "<span>0</span>" : ""}<span>${h(ind.fmt(hi))}</span></div>` +
      `<div class="lg-it lg-na"><span class="sw" style="background:#4a4f57"></span>${h(TX.na)}</div>`;
  }

  /* ---------------------------------------------------------------- apply (idempotent) */
  function apply() {
    const bm = baseMode();
    if (bm === "dark" && !DYEARS.length) M.mode = "lights";
    syncControls();
    if (X.map) {
      setNtl(bm === "lights"); setSwipe(bm === "swipe");
      if (X.dark) { show(X.dark, bm === "dark"); if (bm === "dark") { const u = rasterUrl(S.d.meta.rasters.dark[M.dy]); if (X.dark._url !== u) X.dark.setUrl(u); X.dark.setOpacity(M.op); } }
      if (bm === "indicator") computeScale();
      for (const lv of Object.keys(X.units)) { show(X.units[lv], lv === M.lv); if (lv === M.lv) X.units[lv].setStyle((f) => unitStyle(f, lv)); }
      show(X.adm1line, M.lv === "ADM2" && M.ov.boundaries && bm !== "indicator");
      show(X.adm0, M.ov.boundaries || bm !== "indicator");
      show(X.ind, M.ov.industry); show(X.tour, M.ov.tourism);
      if (X.hl) X.hl.eachLayer((g) => g.bringToFront && g.bringToFront());
      const op = X.map._popup; if (op && op._uid && UNITS.get(op._uid)) op.setContent(popupHtml(UNITS.get(op._uid)));
    }
    legends(); yearBadge();
    writeHash();
  }
  function yearBadge() {
    const el = q1("#mx-year"); if (!el) return;
    const bm = baseMode();
    const y = bm === "dark" ? M.dy : bm === "lights" ? M.year : "";
    el.hidden = !y;
    const ys = q1(".y", el);
    if (ys.textContent !== String(y || "")) { ys.textContent = y || ""; if (!RM) { ys.classList.remove("tick"); void ys.offsetWidth; ys.classList.add("tick"); } }
    q1("small", el).textContent = bm === "dark" ? TX.m_dark : TX.hx_cap;
  }
  function legends() {
    const box = q1("#mx-legends"); if (!box) return;
    const bm = baseMode(), out = [];
    const rad = `<div class="ramp" style="background:linear-gradient(90deg,#000004,#3b0f70,#8c2981,#de4968,#fe9f6d,#fcfdbf)"></div><div class="ticks"><span>0,1</span><span>1</span><span>10</span><span>100 nW</span></div>`.replace(/0,1/, LANG === "fr" ? "0,1" : "0.1");
    if (bm === "lights") out.push([TX.leg_rad + ` · ${M.year}`, rad]);
    if (bm === "swipe") out.push([`${TX.leg_rad} · ${M.a} | ${M.b}`, rad]);
    if (bm === "dark") out.push([`${TX.leg_dark} · ${M.dy}`, `<div class="lg-it"><span class="sw" style="background:#f5c242"></span>${h(TX.lit)}</div><div class="lg-it"><span class="sw" style="background:#d7263d"></span>${h(TX.unlit)}</div>`]);
    if (bm === "indicator") { const ind = indOf(M.ind); out.push([`${ind ? ind.t : ""} · ${M.lv}`, X.indLeg || ""]); }
    if (M.ov.industry && X.indTypes) out.push([TX.leg_ind, X.indTypes.map(([t, l]) => `<div class="lg-it"><span class="sw dot" style="background:${typeColor(t)}"></span>${h(l)}</div>`).join("")]);
    if (M.ov.tourism && X.tour) out.push([TX.ov_tourism, `<div class="lg-it"><span class="sw dash"></span>${h(TX.leg_tour)}</div>`]);
    box.innerHTML = out.map(([t, b]) => `<section class="mx-leg"><h4>${h(t)}</h4>${b}</section>`).join("");
  }
  function syncControls() {
    const root = q1("#mx"); if (!root) return;
    const bm = baseMode();
    root.dataset.bm = bm; root.classList.toggle("mx--collapsed", !M.panel);
    qa('input[name="mx-mode"]', root).forEach((r) => { r.checked = r.value === bm; });
    qa(".mx-mode", root).forEach((l) => l.classList.toggle("on", l.dataset.m === bm));
    qa(".mx-sub", root).forEach((s) => { s.hidden = s.dataset.for !== bm; });
    const sa = q1("#mx-a"), sb = q1("#mx-b"); if (sa) sa.value = M.a; if (sb) sb.value = M.b;
    const dy = q1("#mx-dy"); if (dy) dy.value = M.dy;
    const isel = q1("#mx-ind");
    if (isel) {
      const list = indList();
      if (!list.some((i) => i.k === M.ind) && list.length) M.ind = list[0].k;
      const sig = list.map((i) => i.k).join();
      if (isel.dataset.sig !== sig) { isel.innerHTML = list.map((i) => `<option value="${i.k}">${h(i.t)}</option>`).join(""); isel.dataset.sig = sig; }
      isel.value = M.ind;
      const ind = indOf(M.ind); q1("#mx-ind-help").textContent = ind ? ind.help || "" : "";
    }
    qa("#mx-lv button", root).forEach((b) => { const on = b.dataset.lv === M.lv; b.classList.toggle("on", on); b.setAttribute("aria-checked", String(on)); b.tabIndex = on ? 0 : -1; });
    qa("[data-ov]", root).forEach((c) => { c.checked = !!M.ov[c.dataset.ov]; });
    const op = q1("#mx-op"); op.value = Math.round(M.op * 100); q1("#mx-op-v").textContent = Math.round(M.op * 100) + " %";
    const yr = q1("#mx-yr"); const yi = Math.max(0, YEARS.indexOf(M.year)); yr.value = yi;
    yr.setAttribute("aria-valuetext", M.year || ""); yr.style.setProperty("--p", YEARS.length > 1 ? (100 * yi) / (YEARS.length - 1) + "%" : "100%");
    qa(".mx-ticks span", root).forEach((s) => s.classList.toggle("on", +s.dataset.i === yi));
    q1("#mx-time").hidden = !(bm === "lights" && YEARS.length > 1);
    const pb = q1("#mx-play"); pb.innerHTML = M.playing ? ICON.pause : ICON.play; pb.setAttribute("aria-pressed", String(M.playing));
    pb.setAttribute("aria-label", M.playing ? TX.pause : TX.play); pb.title = (M.playing ? TX.pause : TX.play) + (LANG === "fr" ? " (Espace)" : " (Space)");
    const sp = q1("#mx-speed"); sp.textContent = (M.speed === 0.5 ? (LANG === "fr" ? "0,5" : "0.5") : M.speed) + "×"; sp.setAttribute("aria-label", `${TX.speed} : ${sp.textContent}`);
    const m = S.d.meta;
    q1("#mx-desc").textContent = bm === "lights" ? TX.d_lights : bm === "swipe" ? TX.d_swipe : bm === "dark" ? fmt(TX.d_dark, { p: (m.config || {}).pop_min || 5 }) : "";
    q1("#mx-desc").hidden = bm === "indicator";
    const sumT = { lights: `${TX.m_lights} ${M.year}`, swipe: `${M.a} | ${M.b}`, dark: `${TX.m_dark} ${M.dy || ""}`, indicator: (indOf(M.ind) || {}).t || TX.m_ind }[bm];
    q1("#mx-sum").textContent = sumT ? "· " + sumT : "";
    const col = q1("#mx-collapse"); col.setAttribute("aria-expanded", String(M.panel)); col.setAttribute("aria-label", M.panel ? TX.hide_panel : TX.show_panel); col.title = col.getAttribute("aria-label");
    const ob = q1("#mx-open"); ob.setAttribute("aria-expanded", String(M.panel));
  }

  /* ---------------------------------------------------------------- URL state */
  let lastQ = null, hashT = 0;
  function writeHash() {
    clearTimeout(hashT);
    hashT = setTimeout(() => {
      if (!onMap() || !q1("#mx")) return;
      const q = new URLSearchParams();
      q.set("mode", M.mode); if (M.year) q.set("year", M.year); q.set("lv", M.lv); if (M.ind) q.set("ind", M.ind);
      if (M.a) q.set("a", M.a); if (M.b) q.set("b", M.b);
      if (M.unit) q.set("unit", M.unit);
      const ov = Object.keys(M.ov).filter((k) => k !== "boundaries" && M.ov[k]); if (ov.length) q.set("ov", ov.join(","));
      if (!M.ov.boundaries) q.set("bnd", "0");
      if (M.op !== 0.95) q.set("op", Math.round(M.op * 100));
      const s = q.toString().replace(/%2C/g, ",");
      lastQ = s;
      if (location.hash !== "#map?" + s) { history.replaceState(history.state, "", location.pathname + location.search + "#map?" + s); syncLangLink(); }
    }, 120);
  }
  function readParams(q) {
    const g = (k) => q.get(k);
    if (MODES.includes(g("mode"))) M.mode = g("mode");
    if (g("year")) M.year = yearOf(g("year")) || M.year;
    if (g("lv") && (S.d.meta.levels || ["ADM1"]).includes(g("lv"))) M.lv = g("lv");
    if (g("ind") && indOf(g("ind"))) M.ind = g("ind");
    if (g("a")) M.a = yearOf(g("a")) || M.a;
    if (g("b")) M.b = yearOf(g("b")) || M.b;
    if (q.has("ov") || q.has("mode")) { const ov = (g("ov") || "").split(","); M.ov.industry = ov.includes("industry"); M.ov.tourism = ov.includes("tourism"); }
    if (M.mode === "industry") M.ov.industry = true;
    if (M.mode === "tourism") M.ov.tourism = true;
    if (q.has("bnd") || q.has("mode")) M.ov.boundaries = g("bnd") !== "0";
    if (g("op") && num(+g("op"))) M.op = Math.min(1, Math.max(0.2, +g("op") / 100));
    M.unit = g("unit") && UNITS.has(g("unit")) ? g("unit") : (g("unit") ? (findUnit(g("unit")) || {}).unit_id || null : null);
  }
  function onHash() {
    syncHero();
    if (onMap()) setTimeout(sizeMap, 30);
    if (!onMap()) { stopPlay(true); closeHelp(); }
    else if (X.map) {
      const s = location.hash.split("?")[1] || "";
      if (s && s !== lastQ) {
        const prevUnit = M.unit; readParams(hashQuery()); apply();
        if (M.unit && M.unit !== prevUnit) selectUnit(UNITS.get(M.unit));
        if (!M.unit && prevUnit) { X.map.closePopup(); clearHL(); }
      } else writeHash();
    }
    queueTables();
  }

  /* ---------------------------------------------------------------- playback */
  let playT = 0;
  function play(on = true) {
    if (on && YEARS.length < 2) on = false;
    if (on && !timeMode()) { M.mode = "lights"; }
    M.playing = !!on; clearTimeout(playT);
    if (M.playing) { YEARS.forEach((y) => preload(rasterUrl(S.d.meta.rasters.ntl[y]))); tick(); }
    apply();
  }
  function tick() {
    clearTimeout(playT);
    if (!M.playing) return;
    playT = setTimeout(() => {
      if (!M.playing || !onMap()) return;
      const i = YEARS.indexOf(M.year), ni = i >= YEARS.length - 1 ? 0 : i + 1, url = rasterUrl(S.d.meta.rasters.ntl[YEARS[ni]]);
      preload(url).then(() => { if (!M.playing) return; M.year = YEARS[ni]; apply(); tick(); });
    }, (YEARS.indexOf(M.year) >= YEARS.length - 1 ? 1900 : 1100) / M.speed);
  }
  function stopPlay(silent) { clearTimeout(playT); if (M.playing) { M.playing = false; if (!silent) apply(); else syncControls(); } }
  function stepYear(d) {
    const i = YEARS.indexOf(M.year); const ni = Math.max(0, Math.min(YEARS.length - 1, i + d));
    if (ni !== i) { M.year = YEARS[ni]; apply(); }
  }

  /* ---------------------------------------------------------------- fullscreen, share, help */
  function isFS() { const r = q1("#mx"); return !!r && (document.fullscreenElement === r || r.classList.contains("mx--fs")); }
  async function toggleFS(force) {
    const r = q1("#mx"); if (!r) return;
    const want = force == null ? !isFS() : !!force;
    if (want === isFS()) return;
    if (want) {
      let ok = false;
      if (r.requestFullscreen) { try { await r.requestFullscreen({ navigationUI: "hide" }); ok = true; } catch (e) { ok = false; } }
      if (!ok) { r.classList.add("mx--fs"); document.documentElement.classList.add("mx-noscroll"); }
    } else {
      if (document.fullscreenElement) { try { await document.exitFullscreen(); } catch (e) { /* ignore */ } }
      r.classList.remove("mx--fs"); document.documentElement.classList.remove("mx-noscroll");
    }
    fsUI();
  }
  function fsUI() {
    const b = q1("#mx-fs"); if (!b) return; const on = isFS();
    b.innerHTML = on ? ICON.fsx : ICON.fs; b.setAttribute("aria-pressed", String(on)); b.setAttribute("aria-label", on ? TX.fs_exit : TX.fs); b.title = (on ? TX.fs_exit : TX.fs) + " (F)";
    q1("#mx").classList.toggle("mx--isfs", on);
    setTimeout(() => { if (X.map) { X.map.invalidateSize(); clipSwipe(); } }, 120);
  }
  document.addEventListener("fullscreenchange", fsUI);
  async function share() {
    clearTimeout(hashT);
    const u = location.href;
    try { await navigator.clipboard.writeText(u); toast(TX.copied); }
    catch (e) {
      const ta = document.createElement("textarea"); ta.value = u; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.opacity = "0"; document.body.appendChild(ta); ta.select();
      let ok = false; try { ok = document.execCommand("copy"); } catch (e2) { ok = false; } ta.remove();
      toast(ok ? TX.copied : TX.copy_fail);
    }
  }
  function openHelp(on) {
    const p = q1("#mx-help"), b = q1("#mx-helpb"); if (!p) return;
    p.hidden = !on; b.setAttribute("aria-expanded", String(on));
    if (on) q1("#mx-help-x").focus();
  }
  const closeHelp = () => { const p = q1("#mx-help"); if (p && !p.hidden) { openHelp(false); q1("#mx-helpb").focus(); } };

  /* ---------------------------------------------------------------- wiring */
  function wire() {
    const root = q1("#mx");
    qa('input[name="mx-mode"]', root).forEach((r) => { r.onchange = () => { M.mode = r.value; if (r.value !== "lights") stopPlay(true); apply(); }; });
    q1("#mx-a").onchange = (e) => { M.a = e.target.value; apply(); };
    q1("#mx-b").onchange = (e) => { M.b = e.target.value; apply(); };
    const dy = q1("#mx-dy"); if (dy) dy.onchange = (e) => { M.dy = e.target.value; apply(); };
    q1("#mx-ind").onchange = (e) => { M.ind = e.target.value; apply(); };
    qa("[data-ov]", root).forEach((c) => { c.onchange = () => setLayer(c.dataset.ov, c.checked); });
    const seg = q1("#mx-lv");
    seg.onclick = (e) => { const b = e.target.closest("button"); if (b) { M.lv = b.dataset.lv; apply(); } };
    seg.onkeydown = (e) => {
      if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
      e.preventDefault(); const bs = qa("button", seg), i = bs.findIndex((b) => b.dataset.lv === M.lv);
      const n = bs[(i + (e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 1) + bs.length) % bs.length]; M.lv = n.dataset.lv; apply(); n.focus();
    };
    q1("#mx-op").oninput = (e) => { M.op = +e.target.value / 100; q1("#mx-op-v").textContent = e.target.value + " %"; apply(); };
    q1("#mx-yr").oninput = (e) => { M.year = YEARS[+e.target.value]; apply(); };
    q1("#mx-play").onclick = () => play(!M.playing);
    q1("#mx-speed").onclick = () => { M.speed = M.speed === 1 ? 2 : M.speed === 2 ? 0.5 : 1; syncControls(); if (M.playing) tick(); writeHash(); };
    const tog = () => { M.panel = !M.panel; syncControls(); setTimeout(() => { if (X.map) { X.map.invalidateSize(); clipSwipe(); } }, 260); };
    q1("#mx-collapse").onclick = tog;
    q1("#mx-open").onclick = () => { M.panel = true; syncControls(); setTimeout(() => { if (X.map) X.map.invalidateSize(); q1("#mx-collapse").focus(); }, 260); };
    q1(".mx-ph").addEventListener("click", (e) => { if (matchMedia("(max-width: 760px)").matches && !e.target.closest("button")) tog(); });
    q1("#mx-zin").onclick = () => X.map && X.map.zoomIn();
    q1("#mx-zout").onclick = () => X.map && X.map.zoomOut();
    q1("#mx-reset").onclick = () => { if (!X.map) return; X.map.closePopup(); clearHL(); M.unit = null; X.map.flyToBounds(mapBounds(), { padding: pad(), duration: RM ? 0 : 0.7, animate: !RM }); writeHash(); };
    q1("#mx-fs").onclick = () => toggleFS();
    q1("#mx-share").onclick = share;
    q1("#mx-helpb").onclick = () => openHelp(q1("#mx-help").hidden);
    q1("#mx-help-x").onclick = closeHelp;
    // swipe divider: pointer + keyboard
    const sw = q1("#mx-swipe"), hd = q1("#mx-swh"), ln = q1("#mx-swl");
    const posFrom = (cx) => { const r = q1("#mx-map").getBoundingClientRect(); M.swipe = Math.min(0.98, Math.max(0.02, (cx - r.left) / r.width)); swipeUI(); };
    [hd, ln].forEach((el) => {
      el.addEventListener("pointerdown", (e) => { e.preventDefault(); e.stopPropagation(); el.setPointerCapture(e.pointerId); sw.classList.add("drag"); posFrom(e.clientX); if (el === hd) hd.focus(); });
      el.addEventListener("pointermove", (e) => { if (el.hasPointerCapture && el.hasPointerCapture(e.pointerId)) posFrom(e.clientX); });
      const up = (e) => { if (el.hasPointerCapture && el.hasPointerCapture(e.pointerId)) el.releasePointerCapture(e.pointerId); sw.classList.remove("drag"); };
      el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
    });
    hd.addEventListener("keydown", (e) => {
      const st = e.shiftKey ? 0.1 : 0.02;
      const k = { ArrowLeft: -st, ArrowDown: -st, ArrowRight: st, ArrowUp: st, PageDown: -0.1, PageUp: 0.1 }[e.key];
      if (k != null) M.swipe = Math.min(0.98, Math.max(0.02, M.swipe + k));
      else if (e.key === "Home") M.swipe = 0.02; else if (e.key === "End") M.swipe = 0.98; else return;
      e.preventDefault(); e.stopPropagation(); swipeUI();
    });
    // search combobox
    const inp = q1("#mx-q"), list = q1("#mx-res");
    let res = [], act = -1;
    const draw = () => {
      list.innerHTML = res.length ? res.map((u, i) => `<li role="option" id="mx-opt-${i}" aria-selected="${i === act}" data-i="${i}"><span class="n">${h(u.name)}</span><span class="t">${h(u.level === "ADM1" ? TX.region : TX.district)}${u.parent ? " · " + h(u.parent) : ""}</span></li>`).join("")
        : `<li class="none" role="option" aria-disabled="true" aria-selected="false">${h(TX.none)}</li>`;
      const open = !!inp.value.trim();
      list.hidden = !open; inp.setAttribute("aria-expanded", String(open));
      if (act >= 0) inp.setAttribute("aria-activedescendant", "mx-opt-" + act); else inp.removeAttribute("aria-activedescendant");
    };
    const pick = (u) => { if (!u) return; inp.value = u.name; list.hidden = true; inp.setAttribute("aria-expanded", "false"); if (matchMedia("(max-width: 760px)").matches) { M.panel = false; syncControls(); } selectUnit(u); };
    inp.oninput = () => { res = searchUnits(inp.value); act = res.length ? 0 : -1; draw(); };
    inp.onkeydown = (e) => {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); if (!res.length) return; act = (act + (e.key === "ArrowDown" ? 1 : -1) + res.length) % res.length; draw(); }
      else if (e.key === "Enter") { e.preventDefault(); pick(res[Math.max(0, act)]); }
      else if (e.key === "Escape") { if (inp.value) { e.stopPropagation(); inp.value = ""; res = []; draw(); } }
    };
    inp.onblur = () => setTimeout(() => { list.hidden = true; inp.setAttribute("aria-expanded", "false"); }, 160);
    inp.onfocus = () => { if (inp.value.trim()) { res = searchUnits(inp.value); draw(); } };
    list.addEventListener("mousedown", (e) => e.preventDefault());
    list.onclick = (e) => { const li = e.target.closest("li[data-i]"); if (li) pick(res[+li.dataset.i]); };
    window.L && L.DomEvent && [q1("#mx-time"), q1("#mx-legends")].forEach((el) => { L.DomEvent.disableClickPropagation(el); L.DomEvent.disableScrollPropagation(el); });
  }
  function setLayer(name, on) {
    const k = { clusters: "industry", industrial: "industry", tourist: "tourism", boundary: "boundaries", bounds: "boundaries", outline: "boundaries" }[name] || name;
    if (!(k in M.ov)) return null;
    M.ov[k] = on == null ? !M.ov[k] : !!on;
    if (!M.ov[k] && M.mode === k) M.mode = "lights";
    apply();
    return M.ov[k];
  }

  // keyboard shortcuts (capture phase so ← → beat Leaflet's own panning when the map has focus)
  document.addEventListener("keydown", (e) => {
    if (!onMap() || !q1("#mx") || e.ctrlKey || e.metaKey || e.altKey) return;
    const t = e.target, tag = (t.tagName || "").toLowerCase();
    const typing = tag === "input" || tag === "textarea" || tag === "select" || t.isContentEditable;
    if (e.key === "Escape") { if (!q1("#mx-help").hidden) { closeHelp(); return; } if (q1("#mx").classList.contains("mx--fs")) toggleFS(false); return; }
    if (typing) return;
    if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && timeMode() && t.id !== "mx-swh" && !t.closest("#mx-lv") && !t.closest(".leaflet-popup")) {
      e.preventDefault(); e.stopPropagation(); stopPlay(); stepYear(e.key === "ArrowLeft" ? -1 : 1);
    } else if (e.key === " " && !["button", "a", "summary"].includes(tag) && !t.closest("[role=slider],[role=radio]")) {
      e.preventDefault(); e.stopPropagation(); play(!M.playing);
    } else if (e.key === "f" || e.key === "F") { e.preventDefault(); toggleFS(); }
    else if (e.key === "/") { e.preventDefault(); if (!M.panel) { M.panel = true; syncControls(); } setTimeout(() => q1("#mx-q").focus(), M.panel ? 0 : 260); }
    else if (e.key === "?") { e.preventDefault(); openHelp(q1("#mx-help").hidden); }
  }, true);

  // UI theme switch: keep Leaflet bits that read CSS variables in sync
  new MutationObserver(() => { if (X.map) apply(); }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  /* ================================================================== public API */
  const api = {
    get ready() { return ready; },
    async show() { if (!onMap()) location.hash = "#map"; await ready; await new Promise((r) => setTimeout(r, 0)); return api.state(); },
    setMode(mode) {
      if (!MODES.includes(mode)) return api.state();
      if (mode === "dark" && !DYEARS.length && YEARS.length) return api.state();
      if (mode !== "lights" && mode !== "industry" && mode !== "tourism") stopPlay(true);
      M.mode = mode;
      if (mode === "industry") M.ov.industry = true;
      if (mode === "tourism") M.ov.tourism = true;
      apply(); return api.state();
    },
    setYear(year) { const y = yearOf(year); if (!y) return api.state(); M.year = y; if (!timeMode()) M.mode = "lights"; apply(); return api.state(); },
    setLevel(lv) { lv = String(lv || "").toUpperCase(); if (!(S.d.meta?.levels || ["ADM1", "ADM2"]).includes(lv)) return api.state(); M.lv = lv; apply(); return api.state(); },
    setIndicator(k) {
      const ind = indOf(k); if (!ind) return api.state();
      if (ind.lvl && ind.lvl !== M.lv) M.lv = ind.lvl;
      M.ind = k; M.mode = "indicator"; stopPlay(true); apply(); return api.state();
    },
    compare(a, b) { const ya = yearOf(a), yb = yearOf(b); if (ya) M.a = ya; if (yb) M.b = yb; M.mode = "swipe"; stopPlay(true); apply(); return api.state(); },
    focus(q) { const u = findUnit(q); if (!u) return null; if (!X.map) { M.unit = u.unit_id; M.lv = u.level; } else selectUnit(u); return { unit_id: u.unit_id, name: u.name, level: u.level }; },
    toggleLayer(name, on) { return setLayer(String(name || "").toLowerCase(), on); },
    play(on = true) { play(on); return api.state(); },
    state() {
      return { page: pageName(), mode: M.mode, year: M.year ? +M.year : null, level: M.lv, indicator: M.ind, a: M.a ? +M.a : null, b: M.b ? +M.b : null,
        unit: M.unit, layers: { ...M.ov }, opacity: M.op, playing: M.playing, speed: M.speed, swipe: +M.swipe.toFixed(3), years: YEARS.map(Number) };
    },
    units() { return [...UNITS.values()].map((u) => ({ unit_id: u.unit_id, name: u.name, level: u.level })); },
  };
  window.NTL_MAP = api;

  /* ================================================================== registration */
  const EXT = (window.NTL_EXT = window.NTL_EXT || { pages: [], files: {}, render: {}, fileDesc: {} });
  EXT.render = EXT.render || {};
  EXT.render.map = renderMap;
  function patch() {
    if (typeof RENDER === "undefined") return;
    const ov = RENDER.overview;
    RENDER.overview = () => { ov(); try { renderHero(); countUp(); } catch (e) { console.error(e); } };
    RENDER.map = renderMap;
    const rg = RENDER.regions;
    if (rg) RENDER.regions = () => { rg(); addRegionsCSV(); };
    for (const k of Object.keys(RENDER)) {
      const f = RENDER[k];
      RENDER[k] = function () { const r = f.apply(this, arguments); queueTables(); return r; };
    }
    try { window.applyMapMode = () => { if (X.map) apply(); }; } catch (e) { /* not writable */ }
    window.addEventListener("hashchange", onHash);
    // in the unlikely case app.js routed before this patch ran
    if (S.rendered && (S.rendered.overview || S.rendered.map)) { S.rendered = {}; route(); }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", patch); else setTimeout(patch, 0);
})();
