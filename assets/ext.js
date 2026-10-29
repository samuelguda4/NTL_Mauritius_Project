/* Night-time lights dashboard — extension pages: Industry (use case 6), Tourism (use case 7), AI assistant.
 * Loaded BEFORE app.js; app.js merges NTL_EXT.pages / NTL_EXT.render / NTL_EXT.files and calls NTL_EXT.init().
 * Same file in the French and English sites: texts are chosen from <html lang>. */
"use strict";
(function () {
  const LANG = document.documentElement.lang === "en" ? "en" : "fr";
  // local copy: the page templates below are built before app.js defines its helpers
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const TX = {
    fr: {
      tabs: { industry: "Industrie", tourism: "Tourisme", urban: "Urbanisation", assistant: "Assistant IA", quality: "Qualité & normes" },
      u_title: "Là où les villes s'étendent et les villages s'allument",
      u_lede: "La surface éclairée suit l'extension des villes, l'apparition de nouveaux quartiers et l'électrification des villages. Comparée à la croissance de la population, elle montre où l'équipement suit la démographie — et où il prend du retard.",
      u_k1: "Croissance de la surface éclairée", u_k2: "Surface nouvellement éclairée", u_k3: "Habitants nouvellement éclairés", u_k4: "Validation (bâti GHSL)",
      u_map: "Carte des zones nouvellement éclairées", u_map_help: "Doré : nouvelles implantations (zones non habitées au départ) · vert : électrification de zones déjà habitées · rouge : lumière perdue. Les unités sont colorées selon leur classe.",
      u_series: "Surface éclairée et population", u_series_help: "Les deux séries valent 100 la première année : si la surface éclairée croît plus vite, l'équipement devance la démographie.",
      u_scatter: "Lumière ou population : qui va plus vite ?", u_scatter_help: "Chaque point est une unité. Au-dessus de la diagonale : la surface éclairée croît plus vite que la population (urbanisation électrifiée) ; en dessous : croissance non éclairée.",
      u_bars: "Zones nouvellement éclairées par région", u_bars_help: "Surface (km²) nouvellement éclairée, séparée entre électrification de zones habitées et nouvelles implantations ; en rouge, la lumière perdue.",
      u_lit: "Surface éclairée", u_pop: "Population", u_settled: "Nouvelles implantations", u_electrified: "Électrification", u_lost: "Lumière perdue",
      col_litg: "Surface éclairée (%/an)", col_popg: "Population (%/an)", col_new: "Nouvellement éclairé (km²)", col_builtg: "Bâti GHSL (%/an)",
      q_title: "Qualité et normes internationales", q_eyebrow: "STATISTIQUES EXPÉRIMENTALES · ONU · DQAF · GSBPM · FAIR",
      q_uc: "Fiches qualité des huit cas d'usage", q_val: "Validation", q_unc: "Incertitude", q_lim: "Limites", q_src: "Sources",
      q_exp: "Statistique expérimentale", q_dqaf: "Cadre d'évaluation de la qualité des données (DQAF)", q_gsbpm: "Processus de production (GSBPM, CEE-ONU)",
      q_fair: "Principes FAIR", q_un: "Principes fondamentaux de la statistique officielle (ONU)", q_dim: "Dimension", q_pr: "Pratique", q_ev: "Mise en œuvre",
      q_sections: "sections du notebook", q_refs: "Références", q_whatexp: "Ce qui est expérimental",
      conf: "confiance", source: "Source", na: "Donnée non disponible pour ce pays.",
      // industry
      i_title: "Où l'industrie éclaire la nuit",
      i_lede: "Les lumières seules ne distinguent pas une usine d'un centre commercial. Chaque pixel VIIRS (≈ 0,2 km²) est évalué sur six signaux satellitaires indépendants ; les pixels qui en cumulent au moins trois forment des grappes, classées par type et par niveau de confiance.",
      i_k1: "Grappes industrielles", i_k2: "Part de la lumière nationale", i_k3: "Croissance de la lumière industrielle",
      i_k4: "Validation (précision / rappel)", i_k4s: "face à la liste de référence", i_novalid: "pas de liste de référence",
      i_map: "Carte des grappes industrielles", i_map_help: "Couleur = type ; taille du point = lumière émise. Cliquez une grappe pour voir ses six signaux.",
      i_series: "Lumière industrielle par type", i_series_help: "Somme des radiances des grappes, par type et par année.",
      i_va: "Lumière industrielle et valeur ajoutée industrielle", i_va_help: "Les deux séries sont ramenées à 100 la première année commune : on compare des rythmes. Une corrélation élevée des taux de croissance valide la lumière comme indicateur avancé.",
      i_sig: "Les six signaux des principales grappes", i_sig_help: "Part des pixels de la grappe qui remplissent chaque critère (0 à 100 %).",
      i_reg: "Industrie par région", i_val: "Validation", i_unmatched: "Sites de référence non détectés",
      col_region: "Région", col_n: "Grappes", col_area: "Surface (km²)", col_share: "Part de la lumière régionale", col_type: "Type", col_cluster: "Grappe", col_where: "Localisation", col_signals: "Signaux", col_valid: "Validée",
      yes: "oui", no: "non", corr: "corrélation des croissances", idx: "Indice (base 100)", sumrad: "Somme des radiances",
      lightind: "Lumière industrielle", va: "Valeur ajoutée industrielle (Banque mondiale)",
      // tourism
      t_title: "La saison vue du ciel",
      t_lede: "Pour chaque unité, le surcroît estival compare la lumière des mois de pointe à celle des mois d'intersaison de la même année, net de celui des unités comparables de même latitude (nuits courtes, végétation). Ce qui reste est l'afflux touristique.",
      t_k1: "Zones touristiques", t_k2: "Surcroît estival net maximal", t_k3: "Indice de saison, dernière année", t_k4: "Corrélation avec les nuitées",
      t_prof: "Profil saisonnier moyen", t_prof_help: "Lumière de chaque mois divisée par la moyenne annuelle (années 2020–2021 exclues). Les zones touristiques s'envolent en été.",
      t_tour: "Zones touristiques", t_other: "Autres unités",
      t_idx: "Indice de saison touristique", t_idx_help: "Base 100 = année de référence. Les nuitées sont ramenées à la même base pour comparer les rythmes. ☾ = Ramadan chevauchant la saison (≥ 10 jours).",
      t_nights: "Nuitées (même base)", t_rank: "Surcroît estival net par unité", t_rank_help: "Médiane des étés (hors 2020–2021). Le trait pointillé marque le seuil de classement.",
      t_map: "Carte du surcroît estival net", t_threshold: "seuil", t_month: "Mois", t_rel: "Lumière relative (moyenne annuelle = 1)",
      col_net: "Surcroît net", col_p: "p", col_summers: "Étés", col_class: "Classe",
      // assistant
      a_title: "Assistant IA sur les résultats",
      a_lede: "Posez vos questions en langage naturel. L'assistant répond uniquement à partir des faits publiés sur ce tableau de bord et cite ses sources [F12] — cliquez une citation pour ouvrir la page correspondante.",
      a_settings: "Modèle de langage", a_provider: "Fournisseur", a_model: "Modèle", a_key: "Clé d'API", a_host: "Serveur Ollama",
      a_remember: "Mémoriser la clé sur cet appareil", a_test: "Tester la connexion", a_ok: "Connexion réussie", a_models: "modèles disponibles",
      a_local: "Sans modèle (faits bruts)", a_privacy: "La clé reste dans votre navigateur (session, ou appareil si vous cochez la case) et n'est envoyée qu'au fournisseur choisi. Les faits envoyés sont ceux affichés publiquement sur ce site.",
      a_ollama: "Ollama doit autoriser cette origine : lancez <code>OLLAMA_ORIGINS=\"{o}\" ollama serve</code>.",
      a_groq: "Clé gratuite sur <a href=\"https://console.groq.com/keys\" target=\"_blank\" rel=\"noopener\">console.groq.com</a>.",
      a_gemini: "Clé gratuite sur <a href=\"https://aistudio.google.com/apikey\" target=\"_blank\" rel=\"noopener\">aistudio.google.com</a>.",
      a_ask: "Votre question sur les résultats…", a_send: "Envoyer", a_clear: "Nouvelle conversation", a_thinking: "Analyse des faits publiés…",
      a_you: "Vous", a_bot: "Assistant", a_cited: "Faits cités", a_facts: "faits disponibles", a_err: "Le fournisseur {p} a renvoyé une erreur : {e}. Réponse construite à partir des faits.",
      a_hello: "Bonjour ! Je connais les {n} faits publiés pour {c} ({p}). Choisissez une question ci-dessous ou posez la vôtre.",
      a_nokey: "Aucune clé n'est renseignée : je réponds avec les faits les plus pertinents, sans reformulation. Ajoutez une clé Groq ou Gemini (ou un serveur Ollama) pour des réponses rédigées.",
      a_fab: "Demander à l'IA",
      a_local_head: "Voici les résultats les plus pertinents (mode sans modèle de langage) :", a_local_none: "Je ne trouve aucun résultat publié correspondant à cette question.",
    },
    en: {
      tabs: { industry: "Industry", tourism: "Tourism", urban: "Urbanisation", assistant: "AI assistant", quality: "Quality & standards" },
      u_title: "Where cities spread and villages light up",
      u_lede: "The lit area follows the spread of cities, new neighbourhoods and village electrification. Compared with population growth, it shows where infrastructure keeps pace with demography — and where it lags behind.",
      u_k1: "Growth of the lit area", u_k2: "Newly lit area", u_k3: "Newly lit inhabitants", u_k4: "Validation (GHSL built-up)",
      u_map: "Map of newly lit areas", u_map_help: "Gold: new settlements (areas not inhabited at the start) · green: electrification of already inhabited areas · red: light lost. Units are coloured by class.",
      u_series: "Lit area and population", u_series_help: "Both series equal 100 in the first year: if the lit area grows faster, infrastructure runs ahead of demography.",
      u_scatter: "Light or population: which grows faster?", u_scatter_help: "Each dot is a unit. Above the diagonal: the lit area grows faster than population (electrified urbanisation); below: unlit growth.",
      u_bars: "Newly lit areas by region", u_bars_help: "Newly lit area (km²), split between electrification of inhabited areas and new settlements; in red, light lost.",
      u_lit: "Lit area", u_pop: "Population", u_settled: "New settlements", u_electrified: "Electrification", u_lost: "Light lost",
      col_litg: "Lit area (%/yr)", col_popg: "Population (%/yr)", col_new: "Newly lit (km²)", col_builtg: "GHSL built-up (%/yr)",
      q_title: "Quality and international standards", q_eyebrow: "EXPERIMENTAL STATISTICS · UN · DQAF · GSBPM · FAIR",
      q_uc: "Quality sheets of the eight use cases", q_val: "Validation", q_unc: "Uncertainty", q_lim: "Limitations", q_src: "Sources",
      q_exp: "Experimental statistic", q_dqaf: "Data Quality Assessment Framework (DQAF)", q_gsbpm: "Statistical production process (UNECE GSBPM)",
      q_fair: "FAIR principles", q_un: "UN Fundamental Principles of Official Statistics", q_dim: "Dimension", q_pr: "Practice", q_ev: "Implementation",
      q_sections: "notebook sections", q_refs: "References", q_whatexp: "What is experimental",
      conf: "confidence", source: "Source", na: "Not available for this country.",
      i_title: "Where industry lights up the night",
      i_lede: "Light alone cannot tell a factory from a shopping centre. Each VIIRS pixel (≈ 0.2 km²) is scored on six independent satellite signals; pixels meeting at least three form clusters, classified by type and confidence level.",
      i_k1: "Industrial clusters", i_k2: "Share of national light", i_k3: "Growth of industrial light",
      i_k4: "Validation (precision / recall)", i_k4s: "against the reference list", i_novalid: "no reference list",
      i_map: "Map of industrial clusters", i_map_help: "Colour = type; dot size = light emitted. Click a cluster to see its six signals.",
      i_series: "Industrial light by type", i_series_help: "Sum of radiance of the clusters, by type and year.",
      i_va: "Industrial light and industry value added", i_va_help: "Both series are set to 100 in the first common year: we compare paces. A high correlation of growth rates validates light as a leading indicator.",
      i_sig: "The six signals of the main clusters", i_sig_help: "Share of the cluster's pixels meeting each criterion (0 to 100%).",
      i_reg: "Industry by region", i_val: "Validation", i_unmatched: "Reference sites not detected",
      col_region: "Region", col_n: "Clusters", col_area: "Area (km²)", col_share: "Share of regional light", col_type: "Type", col_cluster: "Cluster", col_where: "Location", col_signals: "Signals", col_valid: "Validated",
      yes: "yes", no: "no", corr: "growth correlation", idx: "Index (base 100)", sumrad: "Sum of radiance",
      lightind: "Industrial light", va: "Industry value added (World Bank)",
      t_title: "The season seen from the sky",
      t_lede: "For each unit, the summer excess compares the light of the peak months with the shoulder months of the same year, net of that of comparable units at the same latitude (short nights, vegetation). What remains is the tourist inflow.",
      t_k1: "Tourist zones", t_k2: "Largest net summer excess", t_k3: "Season index, latest year", t_k4: "Correlation with hotel nights",
      t_prof: "Average seasonal profile", t_prof_help: "Light of each month divided by the annual mean (2020–2021 excluded). Tourist zones soar in summer.",
      t_tour: "Tourist zones", t_other: "Other units",
      t_idx: "Tourist season index", t_idx_help: "Base 100 = reference year. Hotel nights are rebased the same way to compare paces. ☾ = Ramadan overlapping the season (≥ 10 days).",
      t_nights: "Hotel nights (same base)", t_rank: "Net summer excess by unit", t_rank_help: "Median over summers (2020–2021 excluded). The dotted line marks the classification threshold.",
      t_map: "Map of the net summer excess", t_threshold: "threshold", t_month: "Month", t_rel: "Relative light (annual mean = 1)",
      col_net: "Net excess", col_p: "p", col_summers: "Summers", col_class: "Class",
      a_title: "AI assistant on the results",
      a_lede: "Ask your questions in plain language. The assistant answers only from the facts published on this dashboard and cites its sources [F12] — click a citation to open the corresponding page.",
      a_settings: "Language model", a_provider: "Provider", a_model: "Model", a_key: "API key", a_host: "Ollama server",
      a_remember: "Remember the key on this device", a_test: "Test the connection", a_ok: "Connected", a_models: "models available",
      a_local: "No model (raw facts)", a_privacy: "The key stays in your browser (session, or device if you tick the box) and is sent only to the chosen provider. The facts sent are those publicly shown on this site.",
      a_ollama: "Ollama must allow this origin: run <code>OLLAMA_ORIGINS=\"{o}\" ollama serve</code>.",
      a_groq: "Free key at <a href=\"https://console.groq.com/keys\" target=\"_blank\" rel=\"noopener\">console.groq.com</a>.",
      a_gemini: "Free key at <a href=\"https://aistudio.google.com/apikey\" target=\"_blank\" rel=\"noopener\">aistudio.google.com</a>.",
      a_ask: "Your question about the results…", a_send: "Send", a_clear: "New conversation", a_thinking: "Analysing the published facts…",
      a_you: "You", a_bot: "Assistant", a_cited: "Facts cited", a_facts: "facts available", a_err: "Provider {p} returned an error: {e}. Answer built from the facts.",
      a_hello: "Hello! I know the {n} facts published for {c} ({p}). Pick a question below or ask your own.",
      a_nokey: "No key provided: I answer with the most relevant facts, without rewording. Add a Groq or Gemini key (or an Ollama server) for written answers.",
      a_fab: "Ask the AI",
      a_local_head: "Here are the most relevant results (mode without a language model):", a_local_none: "I could not find any published result matching this question.",
    },
  }[LANG];
  const PROV = {
    groq: { label: "Groq", models: ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"] },
    gemini: { label: "Google Gemini", models: ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"] },
    ollama: { label: "Ollama (local)", models: ["qwen2.5:7b", "llama3.1:8b", "mistral:7b"] },
    local: { label: TX.a_local, models: ["facts"] },
  };

  const dd = (k) => (S.d || {})[k];
  const loc = LANG === "fr" ? "fr-FR" : "en-US";
  const fmtPct = (v, d = 0, sign = true) => (isNum(v) ? (sign && v > 0 ? "+" : "") + new Intl.NumberFormat(loc, { maximumFractionDigits: d, minimumFractionDigits: d }).format(100 * v) + (LANG === "fr" ? " %" : "%") : "–");
  const typeColor = (t) => css({ heavy: "--t1", logistics: "--t2", hydro: "--t3", isolated: "--t4" }[t] || "--muted");
  const maps = {};
  function freshMap(id) { if (maps[id]) { try { maps[id].remove(); } catch (e) { /* already gone */ } } maps[id] = newMap(id); return maps[id]; }
  const kpi = (label, value, sub) => `<div class="kpi"><div class="label">${esc(label)}</div><div class="value">${value}</div><div class="sub">${esc(sub || "")}</div></div>`;
  const card = (id, title, help, cls = "chart", src = "") => `<article class="card"><h2>${esc(title)}</h2>${help ? `<p class="help">${esc(help)}</p>` : ""}<div class="${cls}" id="${id}"></div>${src ? `<p class="source">${esc(TX.source)} : ${esc(src)}</p>` : ""}</article>`;

  /* ------------------------------------------------------------------ page skeletons */
  const HTML = {
    industry: `
      <div class="hero hero-ind"><div><div class="hero-eyebrow">${LANG === "fr" ? "CAS D'USAGE 6 · INDUSTRIE" : "USE CASE 6 · INDUSTRY"}</div><h2>${esc(TX.i_title)}</h2><p>${esc(TX.i_lede)}</p></div><div class="chips" id="i-chips"></div></div>
      <div class="kpis" id="i-kpis"></div>
      <article class="card map-card"><h2>${esc(TX.i_map)}</h2><p class="help">${esc(TX.i_map_help)}</p>
        <div class="map-wrap small"><div id="i-map" class="map"></div><div class="map-legend" id="i-legend"></div></div>
        <p class="source">${esc(TX.source)} : VIIRS VNL V2, GHSL BUILT-S, Sentinel-5P NO₂/SO₂, MODIS MOD11A2 ; OpenStreetMap / CARTO.</p></article>
      <div class="grid two">${card("i-series", TX.i_series, TX.i_series_help, "chart", "VIIRS VNL V2")}${card("i-va", TX.i_va, TX.i_va_help, "chart", LANG === "fr" ? "VIIRS ; Banque mondiale NV.IND.TOTL.KD" : "VIIRS; World Bank NV.IND.TOTL.KD")}</div>
      <div class="grid two"><article class="card"><h2>${esc(TX.i_sig)}</h2><p class="help">${esc(TX.i_sig_help)}</p><div class="chart tall" id="i-sig"></div></article>
        <article class="card"><h2>${esc(TX.i_val)}</h2><div id="i-val"></div><h3>${esc(TX.i_reg)}</h3><div class="table-wrap" id="i-reg"></div></article></div>`,
    tourism: `
      <div class="hero hero-tou"><div><div class="hero-eyebrow">${LANG === "fr" ? "CAS D'USAGE 7 · TOURISME" : "USE CASE 7 · TOURISM"}</div><h2>${esc(TX.t_title)}</h2><p>${esc(TX.t_lede)}</p></div></div>
      <div class="kpis" id="t-kpis"></div>
      <div class="grid two">${card("t-prof", TX.t_prof, TX.t_prof_help, "chart", LANG === "fr" ? "VIIRS DNB mensuel" : "VIIRS DNB monthly")}${card("t-idx", TX.t_idx, TX.t_idx_help, "chart", LANG === "fr" ? "VIIRS DNB ; statistiques de nuitées" : "VIIRS DNB; hotel-night statistics")}</div>
      <div class="grid two">${card("t-rank", TX.t_rank, TX.t_rank_help, "chart tall", LANG === "fr" ? "VIIRS DNB mensuel" : "VIIRS DNB monthly")}
        <article class="card map-card"><h2>${esc(TX.t_map)}</h2><div class="map-wrap small"><div id="t-map" class="map"></div><div class="map-legend" id="t-legend"></div></div></article></div>
      <article class="card flush"><div class="table-wrap" id="t-table"></div></article>`,
    urban: `
      <div class="hero hero-urb"><div><div class="hero-eyebrow">${LANG === "fr" ? "CAS D'USAGE 8 · URBANISATION" : "USE CASE 8 · URBANISATION"}</div><h2>${esc(TX.u_title)}</h2><p>${esc(TX.u_lede)}</p></div></div>
      <div class="kpis" id="u-kpis"></div>
      <article class="card map-card"><h2>${esc(TX.u_map)}</h2><p class="help">${esc(TX.u_map_help)}</p>
        <div class="map-wrap small"><div id="u-map" class="map"></div><div class="map-legend" id="u-legend"></div></div>
        <p class="source">${esc(TX.source)} : VIIRS VNL V2 (NOAA/EOG) ; GHSL GHS-POP, GHS-BUILT-S R2023A ; © OpenStreetMap / CARTO.</p></article>
      <div class="grid two">${card("u-series", TX.u_series, TX.u_series_help, "chart", "VIIRS VNL V2 ; GHSL / WorldPop")}${card("u-scatter", TX.u_scatter, TX.u_scatter_help, "chart", "VIIRS VNL V2 ; GHSL / WorldPop")}</div>
      ${card("u-bars", TX.u_bars, TX.u_bars_help, "chart tall", "VIIRS VNL V2 ; GHSL")}
      <article class="card flush"><div class="table-wrap" id="u-table"></div></article>`,
    quality: `
      <div class="hero hero-q"><div><div class="hero-eyebrow">${esc(TX.q_eyebrow)}</div><h2>${esc(TX.q_title)}</h2><p id="q-statement"></p></div><div class="q-seal" aria-hidden="true">✓</div></div>
      <h2 class="q-h">${esc(TX.q_uc)}</h2><div class="q-grid" id="q-cards"></div>
      <div class="grid two"><article class="card"><h2>${esc(TX.q_gsbpm)}</h2><ol class="q-steps" id="q-gsbpm"></ol></article>
        <article class="card"><h2>${esc(TX.q_fair)}</h2><div class="q-fair" id="q-fair"></div><h3>${esc(TX.q_whatexp)}</h3><ul id="q-exp"></ul></article></div>
      <article class="card"><h2>${esc(TX.q_dqaf)}</h2><div class="table-wrap" id="q-dqaf"></div></article>
      <article class="card"><h2>${esc(TX.q_un)}</h2><div class="q-un" id="q-un"></div><h3>${esc(TX.q_refs)}</h3><ul class="small" id="q-refs"></ul></article>`,
    assistant: `
      <div class="hero hero-ai"><div><div class="hero-eyebrow">${LANG === "fr" ? "INTELLIGENCE ARTIFICIELLE · GROQ · GEMINI · OLLAMA" : "ARTIFICIAL INTELLIGENCE · GROQ · GEMINI · OLLAMA"}</div><h2>${esc(TX.a_title)}</h2><p>${esc(TX.a_lede)}</p></div><div class="ai-orb" aria-hidden="true"></div></div>
      <div class="ai-grid">
        <aside class="card ai-settings">
          <h2>${esc(TX.a_settings)}</h2>
          <label class="fld">${esc(TX.a_provider)}<select id="ai-prov">${Object.entries(PROV).map(([k, v]) => `<option value="${k}">${esc(v.label)}</option>`).join("")}</select></label>
          <label class="fld" data-show="groq gemini ollama">${esc(TX.a_model)}<input id="ai-model" list="ai-models" autocomplete="off"><datalist id="ai-models"></datalist></label>
          <label class="fld" data-show="groq gemini">${esc(TX.a_key)}<input id="ai-key" type="password" autocomplete="off" spellcheck="false" placeholder="••••••••"></label>
          <label class="fld" data-show="ollama">${esc(TX.a_host)}<input id="ai-host" value="http://localhost:11434"></label>
          <label class="chk" data-show="groq gemini"><input id="ai-remember" type="checkbox"> ${esc(TX.a_remember)}</label>
          <p class="help small" id="ai-hint"></p>
          <button type="button" class="btn ghost" id="ai-test">${esc(TX.a_test)}</button> <span id="ai-status" class="help small"></span>
          <p class="help small">🔒 ${esc(TX.a_privacy)}</p>
          <p class="help small" id="ai-nfacts"></p>
        </aside>
        <section class="card ai-chat">
          <div class="ai-log" id="ai-log" aria-live="polite"></div>
          <div class="ai-sugg" id="ai-sugg"></div>
          <form class="ai-form" id="ai-form"><textarea id="ai-q" rows="2" placeholder="${esc(TX.a_ask)}"></textarea>
            <div class="ai-actions"><button type="button" class="btn ghost" id="ai-clear">${esc(TX.a_clear)}</button><button type="submit" class="btn" id="ai-send">${esc(TX.a_send)} ➤</button></div></form>
        </section>
      </div>`,
  };

  /* ------------------------------------------------------------------ industry */
  function renderIndustry() {
    const I = dd("industry"), el = $("#page-industry");
    if (!I || !I.available) { el.innerHTML = HTML.industry; $("#i-kpis").innerHTML = `<p class="help">${esc(TX.na)}</p>`; return; }
    const c = C(), v = I.validation || {}, yrs = I.years, y1 = yrs[yrs.length - 1];
    $("#i-chips").innerHTML = Object.values(I.signal_labels || {}).map((s) => `<span class="chip">${esc(s)}</span>`).join("");
    $("#i-kpis").innerHTML = [
      kpi(TX.i_k1, F.num(I.n), Object.entries(I.counts).map(([t, n]) => `${(I.type_labels || {})[t] || t} ${n}`).join(" · ")),
      kpi(TX.i_k2, fmtPct(I.share_last, 1, false), String(y1)),
      kpi(TX.i_k3, fmtPct((I.trend || {}).growth, 1), `${yrs[0]}–${y1}`),
      kpi(TX.i_k4, v.available ? `${fmtPct(v.precision, 0, false)} / ${fmtPct(v.recall, 0, false)}` : "–", v.available ? (v.partial ? (LANG === "fr" ? `rappel sur ${v.n_reference} centrales — référence partielle (${v.source || ""})` : `recall on ${v.n_reference} power plants — partial reference (${v.source || ""})`) : `${TX.i_k4s} (${v.source || ""})`) : TX.i_novalid),
    ].join("");
    // map
    const types = Object.keys(I.type_labels || {});
    $("#i-legend").innerHTML = types.map((t) => `<div><span class="sw" style="background:${typeColor(t)}"></span>${esc(I.type_labels[t])}</div>`).join("");
    if (window.L) {
      const mp = freshMap("i-map");
      const R = (dd("meta").rasters || {}).ntl || {}; const last = Object.keys(R).sort().pop();
      if (last) { const ov = overlay(R[last]); if (ov) { ov.setOpacity(0.55); ov.addTo(mp); } }
      if (dd("adm1")) outline(dd("adm1")).addTo(mp);
      const gj = dd("iclusters");
      const mx = Math.max(...(I.top || []).map((r) => r[`sol_${y1}`] || 0), 1);
      if (gj) L.geoJSON(gj, {
        style: (f) => ({ color: typeColor(f.properties.type), weight: 2, fillColor: typeColor(f.properties.type), fillOpacity: 0.55 }),
        onEachFeature: (f, lyr) => {
          const p = f.properties;
          const bars = Object.entries(I.signal_labels || {}).map(([k, lab]) => `<div class="sigrow"><span>${esc(lab)}</span><b style="width:${Math.round(100 * (p[k] || 0))}%;background:${typeColor(p.type)}"></b><em>${fmtPct(p[k] || 0, 0, false)}</em></div>`).join("");
          lyr.bindPopup(`<strong>${esc(p.cluster_id)} · ${esc(p.type_label)}</strong><div class="why">${esc(p.adm2_name || p.adm1_name || "")} — ${F.num(p.area_km2, 2)} km² — <span class="badge ${esc(p.confidence)}">${TX.conf} ${esc(p.confidence)}</span></div>${bars}`, { maxWidth: 320 });
          const ctr = lyr.getBounds().getCenter();
          L.circleMarker(ctr, { radius: 5 + 9 * Math.sqrt((p.sol_last || 0) / mx), color: "#fff", weight: 2, fillColor: typeColor(p.type), fillOpacity: 0.95 })
            .bindTooltip(`${p.cluster_id} · ${p.type_label}`).on("click", () => lyr.openPopup(ctr)).addTo(mp);
        },
      }).addTo(mp);
    }
    // series by type (stacked area, fixed type order)
    const bt = I.by_type || [];
    plot("i-series", types.filter((t) => bt.some((r) => r.type === t)).map((t) => {
      const r = bt.filter((x) => x.type === t);
      return { x: r.map((x) => x.year), y: r.map((x) => x.sol), name: I.type_labels[t], type: "scatter", mode: "lines", stackgroup: "one", line: { color: typeColor(t), width: 1.5 }, hovertemplate: `%{x} · %{y:,.0f}<extra>${esc(I.type_labels[t])}</extra>` };
    }), { yaxis: { title: { text: TX.sumrad } } });
    // industrial light vs value added, both indexed (one axis)
    const vt = I.industry_va_table || [];
    if (vt.length) {
      const b0 = vt[0];
      plot("i-va", [
        { x: vt.map((r) => r.year), y: vt.map((r) => (100 * r.sol) / b0.sol), name: TX.lightind, mode: "lines+markers", line: { color: c.s[0], width: 2 }, marker: { size: 8 } },
        { x: vt.map((r) => r.year), y: vt.map((r) => (100 * r.industry_va_const_usd) / b0.industry_va_const_usd), name: TX.va, mode: "lines+markers", line: { color: c.s[1], width: 2, dash: "dot" }, marker: { size: 8 } },
      ], { yaxis: { title: { text: TX.idx } }, annotations: isNum((I.industry_va || {}).corr_growth) ? [{ xref: "paper", yref: "paper", x: 0.01, y: 0.98, showarrow: false, xanchor: "left", text: `${TX.corr} : ${F.num2(I.industry_va.corr_growth)}`, font: { color: c.ink2 } }] : [] });
    } else plot("i-va", []);
    // signal heatmap of the top clusters
    const top = (I.top || []).slice(0, 12), keys = Object.keys(I.signal_labels || {});
    const gjp = Object.fromEntries(((dd("iclusters") || {}).features || []).map((f) => [f.properties.cluster_id, f.properties]));
    plot("i-sig", top.length ? [{
      type: "heatmap", x: keys.map((k) => I.signal_labels[k]), y: top.map((r) => `${r.cluster_id} · ${r.adm2_name || r.adm1_name || ""}`),
      z: top.map((r) => keys.map((k) => (gjp[r.cluster_id] || {})[k] ?? null)), zmin: 0, zmax: 1, xgap: 2, ygap: 2,
      colorscale: [[0, css("--surface-2")], [1, c.s[0]]], hovertemplate: "%{y}<br>%{x} : %{z:.0%}<extra></extra>", colorbar: { tickformat: ".0%", thickness: 10 },
    }] : [], { margin: { l: 150, r: 10, t: 10, b: 90 }, xaxis: { tickangle: -25 }, yaxis: { autorange: "reversed" } });
    // validation + regions
    $("#i-val").innerHTML = v.available ? `<div class="valgrid"><div><b>${fmtPct(v.precision, 0, false)}</b><span>precision</span></div><div><b>${fmtPct(v.recall, 0, false)}</b><span>recall</span></div><div><b>${F.num2(v.f1)}</b><span>F1</span></div><div><b>${v.n_reference}</b><span>ref.</span></div></div>` +
      `<p class="help">${esc(v.source || "")} — ${LANG === "fr" ? "rayon de correspondance" : "matching radius"} ${v.match_km} km.</p>` +
      ((v.unmatched_reference || []).length ? `<p class="help"><b>${esc(TX.i_unmatched)}</b> : ${(v.unmatched_reference || []).map((r) => esc(r.name || `${r.lon},${r.lat}`)).join(", ")}</p>` : "")
      : `<p class="help">${esc(TX.i_novalid)}</p>`;
    const u = ((I.units || {}).ADM1 || []);
    $("#i-reg").innerHTML = `<table class="data"><thead><tr><th>${TX.col_region}</th><th>${TX.col_n}</th><th>${TX.col_area}</th><th>${TX.col_share}</th></tr></thead><tbody>` +
      u.map((r) => `<tr><td>${esc(r.name)}</td><td>${r.n_clusters}</td><td>${F.num(r.area_km2, 1)}</td><td>${fmtPct(r.ind_share, 1, false)}</td></tr>`).join("") + "</tbody></table>";
  }

  /* ------------------------------------------------------------------ tourism */
  function renderTourism() {
    const T = dd("tourism");
    if (!T || !T.available) { $("#t-kpis").innerHTML = `<p class="help">${esc(TX.na)}</p>`; return; }
    const c = C(), u = T.units || [], tz = u.filter((r) => r.class === "tourist"), idx = T.index || [], v = T.validation || {};
    const last = idx[idx.length - 1] || {};
    $("#t-kpis").innerHTML = [
      kpi(TX.t_k1, `${T.n_tourist} / ${T.n_units}`, `${T.level} · ${LANG === "fr" ? "pointe" : "peak"} ${T.params.peak_months.map((m) => T.months[m - 1]).join("–")}`),
      kpi(TX.t_k2, tz.length ? fmtPct(tz[0].net_gain, 0) : "–", tz.length ? tz[0].name : ""),
      kpi(TX.t_k3, isNum(last.index) ? F.num(last.index) : "–", last.year ? `${last.year} (base ${last.base_year} = 100)` : ""),
      kpi(TX.t_k4, v.available ? F.num2(v.corr) : "–", v.available ? `${v.label || v.variable}, ${v.n} ${LANG === "fr" ? "années" : "years"}` : ""),
    ].join("");
    const pr = T.profile || [];
    plot("t-prof", pr.length ? [
      { x: pr.map((r) => T.months[r.month - 1]), y: pr.map((r) => r.other), name: TX.t_other, mode: "lines+markers", line: { color: c.flat, width: 2 }, marker: { size: 8 } },
      { x: pr.map((r) => T.months[r.month - 1]), y: pr.map((r) => r.tourist), name: TX.t_tour, mode: "lines+markers", line: { color: c.s[3], width: 2.5 }, marker: { size: 8 } },
    ] : [], { yaxis: { title: { text: TX.t_rel } } });
    const vt = v.table || [];
    const nb = vt.find((r) => r.year === (idx[0] || {}).base_year) || vt[0];
    const tr = [{ x: idx.map((r) => r.year), y: idx.map((r) => r.index), type: "bar", name: TX.t_idx, marker: { color: c.s[3], line: { width: 0 } },
      text: idx.map((r) => (r.ramadan_days >= 10 ? "☾" : "")), textposition: "outside", hovertemplate: "%{x} · %{y:.0f}<extra></extra>" }];
    if (vt.length && nb) tr.push({ x: vt.map((r) => r.year), y: vt.map((r) => (100 * r[v.variable]) / nb[v.variable]), name: v.variable === "nights_millions" ? TX.t_nights : `${v.label || v.variable} (${LANG === "fr" ? "même base" : "same base"})`, mode: "lines+markers", line: { color: c.ink2, width: 2, dash: "dot" }, marker: { size: 8 } });
    plot("t-idx", tr, { yaxis: { title: { text: TX.idx } }, bargap: 0.25 });
    const rk = u.slice(0, 25).reverse();
    plot("t-rank", [{ type: "bar", orientation: "h", y: rk.map((r) => r.name), x: rk.map((r) => 100 * r.net_gain), marker: { color: rk.map((r) => (r.class === "tourist" ? c.s[3] : c.flat)) },
      hovertemplate: "%{y} · %{x:.0f} %<extra></extra>" }], { margin: { l: 130 }, xaxis: { title: { text: TX.col_net + " (%)" } },
      shapes: [{ type: "line", xref: "x", yref: "paper", x0: 100 * T.params.min_excess, x1: 100 * T.params.min_excess, y0: 0, y1: 1, line: { color: c.ink2, dash: "dot", width: 1.5 } }] });
    if (window.L) {
      const gj = dd(T.level === "ADM2" ? "adm2" : "adm1");
      const mp = freshMap("t-map");
      const by = Object.fromEntries(u.map((r) => [r.unit_id, r]));
      const ramp = SEQ_O;
      const col = (g) => (!isNum(g) ? css("--surface-2") : ramp[Math.max(0, Math.min(6, Math.floor((g + 0.05) / 0.08)))]);
      if (gj) L.geoJSON(gj, { style: (f) => { const r = by[f.properties.unit_id] || {}; return { color: r.class === "tourist" ? css("--ink") : "rgba(255,255,255,.7)", weight: r.class === "tourist" ? 2 : 0.7, fillColor: col(r.net_gain), fillOpacity: 0.85 }; },
        onEachFeature: (f, lyr) => { const r = by[f.properties.unit_id] || {}; lyr.bindTooltip(`<b>${esc(r.name || f.properties.name)}</b><br>${TX.col_net} : ${fmtPct(r.net_gain, 0)} · ${esc(r.class_label || "")}`); } }).addTo(mp);
      $("#t-legend").innerHTML = `<div>${esc(TX.col_net)}</div><div class="ramp" style="background:linear-gradient(90deg,${ramp.join(",")})"></div><div class="ticks"><span>−5 %</span><span>+20 %</span><span>+50 %</span></div>`;
    }
    $("#t-table").innerHTML = `<table class="data"><thead><tr><th>${TX.col_region}</th><th>${TX.col_net}</th><th>${TX.col_p}</th><th>${TX.col_summers}</th><th>${TX.col_class}</th><th>${TX.conf}</th></tr></thead><tbody>` +
      u.map((r) => `<tr><td>${esc(r.name)}</td><td>${fmtPct(r.net_gain, 1)}</td><td>${!isNum(r.p_value) ? "–" : r.p_value < 0.001 ? "< " + F.num(0.001, 3) : F.num(r.p_value, 3)}</td><td>${r.n_summers}</td><td>${esc(r.class_label)}</td><td><span class="badge ${esc(r.confidence)}">${esc(r.confidence)}</span></td></tr>`).join("") + "</tbody></table>";
  }

  /* ------------------------------------------------------------------ urbanisation (use case 8) */
  function renderUrban() {
    const U = dd("urban");
    if (!U || !U.available) { $("#u-kpis").innerHTML = `<p class="help">${esc(TX.na)}</p>`; return; }
    const c = C(), lv = U.level, units = (U.units || {})[lv] || [], adm1 = (U.units || {}).ADM1 || [], tr = U.trend || {}, tot = U.totals || {}, v = U.validation || {};
    const ccol = U.class_colors || {}, clab = U.class_labels || {};
    $("#u-kpis").innerHTML = [
      kpi(TX.u_k1, fmtPct((tr.lit || {}).growth, 1), `${TX.u_pop} ${fmtPct((tr.pop || {}).growth, 1)} / ${LANG === "fr" ? "an" : "yr"}`),
      kpi(TX.u_k2, isNum(tot.new_lit_km2) ? F.num(tot.new_lit_km2) + " km²" : "–", tot.y0 ? `${tot.y0} → ${tot.y1}` : ""),
      kpi(TX.u_k3, isNum(tot.electrified_pop) ? F.people(tot.electrified_pop) : "–", `${TX.u_electrified} · ${isNum(tot.electrified_km2) ? F.num(tot.electrified_km2) + " km²" : ""}`),
      kpi(TX.u_k4, v.available ? F.num2(v.rho) : "–", v.available ? `Spearman ρ · ${v.n} ${LANG === "fr" ? "unités" : "units"}` : TX.i_novalid),
    ].join("");
    const S0 = U.series || [];
    if (S0.length) {
      const b = S0[0];
      plot("u-series", [
        { x: S0.map((r) => r.year), y: S0.map((r) => (100 * r.lit_km2) / b.lit_km2), name: TX.u_lit, mode: "lines+markers", line: { color: c.s[3] || "#eda100", width: 2.5 }, marker: { size: 7 } },
        { x: S0.map((r) => r.year), y: S0.map((r) => (100 * r.pop) / b.pop), name: TX.u_pop, mode: "lines+markers", line: { color: c.ink2, width: 2, dash: "dot" }, marker: { size: 7 } },
      ], { yaxis: { title: { text: TX.idx } }, xaxis: { dtick: 2 } });
    }
    const pts = units.filter((u) => isNum(u.lit_growth) && isNum(u.pop_growth));
    const lim = Math.max(0.02, ...pts.map((u) => Math.max(Math.abs(u.lit_growth), Math.abs(u.pop_growth)))) * 100 * 1.12;
    const classes = ["electrified", "balanced", "unlit", "stable"];
    plot("u-scatter", classes.map((k) => { const d = pts.filter((u) => u.class === k); return { x: d.map((u) => 100 * u.pop_growth), y: d.map((u) => 100 * u.lit_growth), text: d.map((u) => u.name),
      mode: "markers", type: "scatter", name: clab[k] || k, marker: { color: ccol[k], size: 11, line: { color: c.surface, width: 1.5 } }, hovertemplate: "%{text}<br>" + TX.u_pop + " %{x:.1f} %/an<br>" + TX.u_lit + " %{y:.1f} %/an<extra></extra>" }; }),
      { xaxis: { title: { text: TX.col_popg }, range: [-lim, lim], zeroline: true, zerolinecolor: c.axis }, yaxis: { title: { text: TX.col_litg }, range: [-lim, lim], zeroline: true, zerolinecolor: c.axis },
        shapes: [{ type: "line", x0: -lim, y0: -lim, x1: lim, y1: lim, line: { color: c.ink2, dash: "dot", width: 1.2 } }], legend: { y: 1.18 } });
    const bars = adm1.length ? adm1 : units;
    const ord = bars.slice().sort((a, b) => (b.new_lit_km2 || 0) - (a.new_lit_km2 || 0)).reverse();
    plot("u-bars", [
      { type: "bar", orientation: "h", y: ord.map((u) => u.name), x: ord.map((u) => u.electrified_km2 || 0), name: TX.u_electrified, marker: { color: "#19c37d" } },
      { type: "bar", orientation: "h", y: ord.map((u) => u.name), x: ord.map((u) => u.settled_km2 || 0), name: TX.u_settled, marker: { color: "#f5c242" } },
      { type: "bar", orientation: "h", y: ord.map((u) => u.name), x: ord.map((u) => -(u.lost_lit_km2 || 0)), name: TX.u_lost, marker: { color: "#e34948" } },
    ], { barmode: "relative", margin: { l: 130 }, xaxis: { title: { text: "km²" } }, legend: { y: 1.12 } });
    if (window.L) {
      const mp = freshMap("u-map"), gj = dd(lv === "ADM2" ? "adm2" : "adm1"), by = Object.fromEntries(units.map((u) => [u.unit_id, u]));
      if (gj) L.geoJSON(gj, { style: (f) => { const u = by[f.properties.unit_id] || {}; return { color: "rgba(255,255,255,.75)", weight: 0.8, fillColor: ccol[u.class] || css("--surface-2"), fillOpacity: 0.28 }; },
        onEachFeature: (f, lyr) => { const u = by[f.properties.unit_id] || {}; lyr.bindTooltip(`<b>${esc(u.name || f.properties.name)}</b><br>${esc(u.class_label || "")}<br>${TX.u_lit} ${fmtPct(u.lit_growth, 1)}/an · ${TX.u_pop} ${fmtPct(u.pop_growth, 1)}/an${isNum(u.new_lit_km2) ? `<br>${TX.col_new} : ${F.num(u.new_lit_km2)}` : ""}`); } }).addTo(mp);
      const R = (dd("meta").rasters || {}).urban || {}; const f = Object.values(R)[0];
      const ov = f ? overlay(f) : null; if (ov) ov.addTo(mp);
      $("#u-legend").innerHTML = [["#f5c242", TX.u_settled], ["#19c37d", TX.u_electrified], ["#e34948", TX.u_lost]].map(([k, t]) => `<div><span class="sw" style="background:${k}"></span>${esc(t)}</div>`).join("") +
        classes.map((k) => `<div><span class="sw" style="background:${ccol[k]};opacity:.55"></span>${esc(clab[k] || k)}</div>`).join("");
    }
    $("#u-table").innerHTML = `<table class="data"><thead><tr><th>${TX.col_region}</th><th>${TX.col_class}</th><th>${TX.col_litg}</th><th>${TX.col_popg}</th><th>${TX.col_new}</th><th>${TX.col_builtg}</th></tr></thead><tbody>` +
      units.slice().sort((a, b) => (b.lit_growth || -9) - (a.lit_growth || -9)).map((u) => `<tr><td>${esc(u.name)}</td><td><span class="sw" style="background:${ccol[u.class]}"></span> ${esc(u.class_label)}</td><td>${fmtPct(u.lit_growth, 1)}</td><td>${fmtPct(u.pop_growth, 1)}</td><td>${isNum(u.new_lit_km2) ? F.num(u.new_lit_km2) : "–"}</td><td>${fmtPct(u.built_growth, 1)}</td></tr>`).join("") + "</tbody></table>";
  }

  /* ------------------------------------------------------------------ quality */
  const UCI = { 1: "📈", 2: "🗺️", 3: "💰", 4: "⚡", 5: "⚖️", 6: "🏭", 7: "🏖️" };
  function renderQuality() {
    const Q = dd("quality"); const el = document.getElementById("page-quality");
    if (!Q) { el.querySelector("#q-cards").innerHTML = `<p class="help">${esc(TX.na)}</p>`; return; }
    el.querySelector("#q-statement").textContent = Q.statement || "";
    el.querySelector("#q-cards").innerHTML = (Q.use_cases || []).map((u) => `
      <article class="card q-card"><div class="q-top"><span class="uc-n">${u.uc}</span><span class="q-ic" aria-hidden="true">${UCI[u.uc] || ""}</span>
        <span class="q-pill">${esc(TX.q_exp)}</span>${u.confidence ? `<span class="badge ${esc(u.confidence)}">${esc(TX.conf)} ${esc(u.confidence)}</span>` : ""}</div>
        <h3><a href="#${esc(u.page)}">${esc(u.title)}</a></h3><p class="q-q">${esc(u.question)}</p>
        <div class="q-val"><div class="q-k">${esc(TX.q_val)}</div><div class="q-v">${esc((u.validation || {}).value)}</div><div class="q-m">${esc((u.validation || {}).metric)} · ${esc((u.validation || {}).text)}</div></div>
        <p class="small"><b>${esc(TX.q_unc)}</b> — ${esc(u.uncertainty)}</p>
        <details class="small"><summary>${esc(TX.q_lim)} · ${esc(TX.q_src)}</summary><p>${esc(u.limits)}</p><div class="q-chips">${(u.sources || []).map((x) => `<span class="q-chip">${esc(x)}</span>`).join("")}</div><p class="help small">${esc(u.method)}</p></details>
      </article>`).join("");
    el.querySelector("#q-gsbpm").innerHTML = (Q.gsbpm || []).map((g) => `<li><b>${esc(g.phase)}</b><span class="q-sec">${esc(TX.q_sections)} ${esc(g.notebook_sections)}</span><small>${esc(g.what)}</small></li>`).join("");
    el.querySelector("#q-fair").innerHTML = (Q.fair || []).map((f) => `<div><b>${esc(f.principle.slice(0, 1))}</b><div><strong>${esc(f.principle)}</strong><p class="small">${esc(f.how)}</p></div></div>`).join("");
    el.querySelector("#q-exp").innerHTML = (Q.experimental || []).map((x) => `<li>${esc(x)}</li>`).join("");
    el.querySelector("#q-dqaf").innerHTML = `<table><thead><tr><th>${esc(TX.q_dim)}</th><th>${esc(TX.q_pr)}</th><th>${esc(TX.q_ev)}</th></tr></thead><tbody>` +
      (Q.dqaf || []).map((d) => `<tr><td><b>${esc(d.dimension)}</b></td><td>${esc(d.practice)}</td><td>${esc(d.evidence)}</td></tr>`).join("") + "</tbody></table>";
    el.querySelector("#q-un").innerHTML = (Q.un_principles || []).map((p, i) => `<div><span class="q-num">${i + 1}</span><div><strong>${esc(p.principle)}</strong><p class="small">${esc(p.how)}</p></div></div>`).join("");
    el.querySelector("#q-refs").innerHTML = (Q.references || []).map((r) => `<li>${esc(r)}</li>`).join("");
  }

  /* ------------------------------------------------------------------ assistant */
  const AI = { history: [], ctx: null };
  const STOP = new Set("le la les un une des de du d l et ou en a au aux pour par sur dans avec est sont quel quelle quels quelles que qui quoi comment combien ce cette ces il elle on nous vous ils the an of to in on for and or is are what which who how many much does do did this that these those be by with from as at it its".split(" "));
  const UCKW = { 0: "synthese resume message cle confiance recommandation limite summary key message overview", 1: "tendance evolution croissance mensuel desaisonnalise stl saison annee trend growth monthly seasonal", 2: "region district convergence concentration classement herfindahl beta sigma no2 ranking", 3: "pib gdp elasticite elasticity nowcast prevision estimation croissance economique regional", 4: "choc covid crise rupture anomalie recuperation black marble quotidien shock break recovery daily", 5: "inegalite gini theil lorenz noir electricite acces urbain rural inequality dark access electricity", 6: "industrie industriel usine grappe zone torchere hydrocarbure so2 no2 logistique industry cluster factory flare", 7: "tourisme touristique ete estival saison station balneaire nuitees ramadan tourism summer resort season", 9: "methode seuil donnees source viirs dmsp nuage torchere masque limite method threshold data source" };
  const norm = (s) => String(s || "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "");
  const tok = (s) => (norm(s).match(/[a-z0-9]+/g) || []).filter((w) => w.length > 1 && !STOP.has(w));
  function retrieve(q, k = 14, ranked = false) {
    const facts = AI.ctx.facts;
    if (!ranked && facts.reduce((a, f) => a + f.text.length + f.title.length, 0) <= 22000) return facts;
    const qs = new Set(tok(q)), nq = norm(q);
    const docs = facts.map((f) => new Set(tok(f.title + " " + f.text + " " + (UCKW[f.uc] || ""))));
    const idf = {}; qs.forEach((w) => { idf[w] = Math.log((docs.length + 1) / (1 + docs.filter((d) => d.has(w)).length)) + 1; });
    const sc = facts.map((f, i) => {
      let s = 0; qs.forEach((w) => { if (docs[i].has(w)) s += idf[w]; });
      (f.names || []).forEach((n) => { if (n && nq.includes(norm(n).split(" (")[0])) s += 3; });
      const tt = new Set(tok(f.title)); qs.forEach((w) => { if (tt.has(w)) s += 1.5; });
      if (f.uc === 0 && s > 0) s += 0.5; return s;
    });
    const ord = facts.map((_, i) => i).sort((a, b) => sc[b] - sc[a]).slice(0, k).filter((i) => sc[i] > 0);
    return ranked ? ord.map((i) => facts[i]) : ord.sort((a, b) => a - b).map((i) => facts[i]);
  }
  function systemPrompt(facts) {
    const c = AI.ctx, fr = LANG === "fr";
    const head = fr
      ? `Tu es l'assistant analytique du tableau de bord « Lumières nocturnes : huit cas d'usage » pour ${c.country} (${c.period.join("–")}), produit par la Banque africaine de développement et Data Innovation for Africa (DI4A).\nRÈGLES IMPÉRATIVES :\n1. Réponds UNIQUEMENT à partir des FAITS fournis. N'invente aucun chiffre, aucune région, aucune date.\n2. Cite chaque affirmation chiffrée avec l'identifiant du fait entre crochets, par exemple [F12].\n3. Indique le niveau de confiance lorsqu'il est donné et rappelle une limite utile.\n4. Si les faits ne permettent pas de répondre, dis-le et indique quelle page consulter.\n5. Ne présente jamais une estimation comme une statistique officielle.\n6. Réponds dans la langue de la question, de façon concise : 3 à 8 phrases ou une courte liste, chiffres clés en **gras**.\n${c.synthetic ? "ATTENTION : données SYNTHÉTIQUES (pays test) ; rappelle-le.\n" : ""}`
      : `You are the analytical assistant of the "Night-time lights: eight use cases" dashboard for ${c.country} (${c.period.join("–")}), produced by the African Development Bank and Data Innovation for Africa (DI4A).\nMANDATORY RULES:\n1. Answer ONLY from the FACTS provided. Never invent a figure, a region or a date.\n2. Cite every quantitative statement with the fact identifier in square brackets, e.g. [F12].\n3. State the confidence level when given and mention a relevant limitation.\n4. If the facts do not answer the question, say so and point to the page to consult.\n5. Never present an estimate as an official statistic.\n6. Answer in the language of the question, concisely: 3 to 8 sentences or a short list, key figures in **bold**.\n${c.synthetic ? "WARNING: SYNTHETIC data (test country); say so.\n" : ""}`;
    return head + (fr ? "FAITS :\n" : "FACTS:\n") + facts.map((f) => `[${f.id}] (${(c.uc_labels || {})[f.uc] || ""}) ${f.title} : ${f.text}`).join("\n");
  }
  const keyName = (p) => `ntl-ai-key-${p}`;
  const getKey = (p) => { try { return sessionStorage.getItem(keyName(p)) || localStorage.getItem(keyName(p)) || ""; } catch (e) { return ""; } };
  function setKey(p, v, remember) {
    try { sessionStorage.setItem(keyName(p), v); if (remember) localStorage.setItem(keyName(p), v); else localStorage.removeItem(keyName(p)); } catch (e) { /* private mode */ }
  }
  async function listModels(p, key, host) {
    if (p === "groq") { const r = await fetch("https://api.groq.com/openai/v1/models", { headers: { Authorization: `Bearer ${key}` } }); if (!r.ok) throw new Error(r.status); return (await r.json()).data.map((m) => m.id); }
    if (p === "gemini") { const r = await fetch("https://generativelanguage.googleapis.com/v1beta/models", { headers: { "x-goog-api-key": key } }); if (!r.ok) throw new Error(r.status); return (await r.json()).models.filter((m) => (m.supportedGenerationMethods || []).includes("generateContent")).map((m) => m.name.split("/").pop()); }
    if (p === "ollama") { const r = await fetch(host.replace(/\/$/, "") + "/api/tags"); if (!r.ok) throw new Error(r.status); return (await r.json()).models.map((m) => m.name); }
    return ["facts"];
  }
  async function callLLM(p, model, key, host, system, msgs) {
    if (p === "groq") {
      const r = await fetch("https://api.groq.com/openai/v1/chat/completions", { method: "POST", headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
        body: JSON.stringify({ model, temperature: 0.2, messages: [{ role: "system", content: system }, ...msgs] }) });
      if (!r.ok) throw new Error(`${r.status} ${(await r.text()).slice(0, 160)}`); return (await r.json()).choices[0].message.content;
    }
    if (p === "gemini") {
      const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`, { method: "POST", headers: { "x-goog-api-key": key, "Content-Type": "application/json" },
        body: JSON.stringify({ systemInstruction: { parts: [{ text: system }] }, contents: msgs.map((m) => ({ role: m.role === "assistant" ? "model" : "user", parts: [{ text: m.content }] })), generationConfig: { temperature: 0.2 } }) });
      if (!r.ok) throw new Error(`${r.status} ${(await r.text()).slice(0, 160)}`); const j = await r.json(); return (j.candidates[0].content.parts || []).map((x) => x.text || "").join("");
    }
    if (p === "ollama") {
      const r = await fetch(host.replace(/\/$/, "") + "/api/chat", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model, stream: false, options: { temperature: 0.2 }, messages: [{ role: "system", content: system }, ...msgs] }) });
      if (!r.ok) throw new Error(`${r.status}`); return (await r.json()).message.content;
    }
    return null;
  }
  function md(text, known) {
    let h = esc(text), out = [], inList = false;
    h.split("\n").forEach((line) => {
      const s = line.trim(), m = s.match(/^([-*•]|\d+[.)])\s+(.*)/);
      if (m) { if (!inList) { out.push("<ul>"); inList = true; } out.push(`<li>${m[2]}</li>`); return; }
      if (inList) { out.push("</ul>"); inList = false; }
      if (s.startsWith("#")) out.push(`<p><b>${s.replace(/^#+/, "").trim()}</b></p>`); else if (s) out.push(`<p>${s}</p>`);
    });
    if (inList) out.push("</ul>");
    h = out.join("").replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/(^|[^\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)/g, "$1<i>$2</i>").replace(/`(.+?)`/g, "<code>$1</code>");
    return h.replace(/\[(F\d{2,3})\]/g, (all, id) => { const f = known[id]; return f ? `<a class="cite" href="#${f.page}" title="${esc(f.title + " — " + f.text)}">${id}</a>` : ""; });
  }
  function bubble(role, html, meta = "") {
    const log = $("#ai-log");
    const d = document.createElement("div"); d.className = `msg ${role}`;
    d.innerHTML = role === "u" ? `<div class="bub">${html}</div>` : `<div class="av" aria-hidden="true">AI</div><div class="bub">${html}${meta ? `<div class="meta">${meta}</div>` : ""}</div>`;
    log.appendChild(d); log.scrollTop = log.scrollHeight; return d;
  }
  function localAnswer(q, facts) {
    const top = retrieve(q, 4, true).filter((f) => facts.includes(f) || true);
    if (!top.length) return TX.a_local_none;
    return TX.a_local_head + "\n" + top.map((f) => `- **${f.title}** — ${f.text} [${f.id}]`).join("\n");
  }
  async function ask(q) {
    q = (q || "").trim(); if (!q) return;
    bubble("u", esc(q));
    const wait = bubble("a", `<span class="dots">${esc(TX.a_thinking)}</span>`);
    const p = $("#ai-prov").value, model = $("#ai-model").value || PROV[p].models[0], key = $("#ai-key").value.trim(), host = $("#ai-host").value.trim();
    const facts = retrieve(q), known = Object.fromEntries(AI.ctx.facts.map((f) => [f.id, f]));
    let text = null, used = p, err = "";
    const t0 = performance.now();
    if (p !== "local" && (key || p === "ollama")) {
      try { text = await callLLM(p, model, key, host, systemPrompt(facts), [...AI.history.slice(-12), { role: "user", content: q }]); }
      catch (e) { err = TX.a_err.replace("{p}", PROV[p].label).replace("{e}", String(e.message || e).replace(key, "•••")); }
    }
    if (text == null) { text = localAnswer(q, facts); used = "local"; }
    text = text.replace(/\[(F\d{2,3})\]/g, (m, id) => (known[id] ? m : "")).replace(/ +([.,])/g, "$1");
    AI.history.push({ role: "user", content: q }, { role: "assistant", content: text });
    const ids = [...new Set((text.match(/\[(F\d{2,3})\]/g) || []).map((s) => s.slice(1, -1)))];
    const cited = ids.length ? `<details><summary>${esc(TX.a_cited)} (${ids.length})</summary><ul>${ids.map((i) => `<li><a class="cite" href="#${known[i].page}">${i}</a> ${esc(known[i].title)}</li>`).join("")}</ul></details>` : "";
    wait.remove();
    bubble("a", (err ? `<div class="warnbox">${esc(err)}</div>` : "") + md(text, known) + cited,
      `${esc(used === "local" ? TX.a_local : PROV[used].label)}${used !== "local" ? " · " + esc(model) : ""} · ${((performance.now() - t0) / 1000).toFixed(1)} s`);
  }
  function syncProvider() {
    const p = $("#ai-prov").value;
    $$("[data-show]").forEach((el) => { el.hidden = !el.dataset.show.split(" ").includes(p); });
    const dl = $("#ai-models"); dl.innerHTML = PROV[p].models.map((m) => `<option value="${m}">`).join("");
    const savedModel = store.get(`ntl-ai-model-${p}`); $("#ai-model").value = savedModel || PROV[p].models[0];
    $("#ai-key").value = getKey(p);
    $("#ai-hint").innerHTML = p === "groq" ? TX.a_groq : p === "gemini" ? TX.a_gemini : p === "ollama" ? TX.a_ollama.replace("{o}", esc(location.origin)) : esc(TX.a_nokey);
    $("#ai-status").textContent = ""; store.set("ntl-ai-provider", p);
  }
  async function renderAssistant() {
    const ctx = dd("agent");
    if (!ctx) { $("#ai-log").innerHTML = `<p class="help">${esc(TX.na)}</p>`; return; }
    AI.ctx = ctx; AI.history = [];
    $("#ai-nfacts").textContent = `📚 ${ctx.facts.length} ${TX.a_facts} · ${ctx.country}`;
    const sel = $("#ai-prov"); sel.value = store.get("ntl-ai-provider") || "groq"; syncProvider();
    sel.onchange = syncProvider;
    $("#ai-key").onchange = () => setKey(sel.value, $("#ai-key").value.trim(), $("#ai-remember").checked);
    $("#ai-remember").onchange = () => setKey(sel.value, $("#ai-key").value.trim(), $("#ai-remember").checked);
    $("#ai-model").onchange = () => store.set(`ntl-ai-model-${sel.value}`, $("#ai-model").value);
    $("#ai-test").onclick = async () => {
      const st = $("#ai-status"); st.textContent = "…";
      try { const ms = await listModels(sel.value, $("#ai-key").value.trim(), $("#ai-host").value.trim());
        $("#ai-models").innerHTML = ms.map((m) => `<option value="${esc(m)}">`).join("");
        const pref = PROV[sel.value].models.find((m) => ms.includes(m)); if (pref && !ms.includes($("#ai-model").value)) $("#ai-model").value = pref;
        st.textContent = `✅ ${TX.a_ok} · ${ms.length} ${TX.a_models}`; }
      catch (e) { st.textContent = `⚠️ ${String(e.message || e).slice(0, 80)}`; }
    };
    $("#ai-log").innerHTML = "";
    bubble("a", md(TX.a_hello.replace("{n}", ctx.facts.length).replace("{c}", ctx.country).replace("{p}", ctx.period.join("–")), {}) + (ctx.synthetic ? `<div class="warnbox">⚠️ ${LANG === "fr" ? "Données synthétiques de test." : "Synthetic test data."}</div>` : ""));
    $("#ai-sugg").innerHTML = (ctx.suggestions || []).map((s) => `<button type="button" class="chip btnchip">${esc(s)}</button>`).join("");
    $$("#ai-sugg button").forEach((b) => { b.onclick = () => ask(b.textContent); });
    $("#ai-form").onsubmit = (e) => { e.preventDefault(); const q = $("#ai-q").value; $("#ai-q").value = ""; ask(q); };
    $("#ai-q").onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#ai-form").requestSubmit(); } };
    $("#ai-clear").onclick = () => { AI.history = []; renderAssistant(); };
    const pending = sessionStorage.getItem("ntl-ai-pending"); if (pending) { sessionStorage.removeItem("ntl-ai-pending"); ask(pending); }
  }

  /* ------------------------------------------------------------------ registration */
  function inject() {
    const q = (sel) => document.querySelector(sel);
    const nav = q(".tabs"), before = nav && nav.querySelector('[data-page="method"]');
    ["industry", "tourism", "urban", "assistant", "quality"].forEach((p) => {
      const a = document.createElement("a"); a.href = "#" + p; a.dataset.page = p; a.textContent = TX.tabs[p];
      if (p === "assistant") a.className = "tab-ai";
      if (before) nav.insertBefore(a, before); else if (nav) nav.appendChild(a);
      const sec = document.createElement("section"); sec.className = "page"; sec.id = "page-" + p; sec.hidden = true; sec.innerHTML = HTML[p];
      const main = q("#main"), ref = q("#page-method"); if (ref) main.insertBefore(sec, ref); else main.appendChild(sec);
    });
    const UCS = LANG === "fr"
      ? [["📈", "Dynamiques", "Tendance, saisonnalité, séries régionales", "time"], ["🗺️", "Régions", "Croissance, convergence, concentration", "regions"],
         ["💰", "PIB", "Élasticité, prévision immédiate, PIB régional", "time"], ["⚡", "Chocs", "COVID-19, ruptures, récupération", "shocks"],
         ["⚖️", "Inégalités", "Gini, Theil, populations dans le noir", "inequality"], ["🏭", "Industrie", "Grappes industrielles, six signaux", "industry"],
         ["🏖️", "Tourisme", "Surcroît estival, indice de saison", "tourism"], ["🏙️", "Urbanisation", "Extension éclairée, électrification", "urban"]]
      : [["📈", "Dynamics", "Trend, seasonality, regional series", "time"], ["🗺️", "Regions", "Growth, convergence, concentration", "regions"],
         ["💰", "GDP", "Elasticity, nowcast, regional GDP", "time"], ["⚡", "Shocks", "COVID-19, breaks, recovery", "shocks"],
         ["⚖️", "Inequality", "Gini, Theil, people in the dark", "inequality"], ["🏭", "Industry", "Industrial clusters, six signals", "industry"],
         ["🏖️", "Tourism", "Summer excess, season index", "tourism"], ["🏙️", "Urbanisation", "Lit-area spread, electrification", "urban"]];
    const strip = document.createElement("nav"); strip.className = "uc-strip"; strip.setAttribute("aria-label", LANG === "fr" ? "Les huit cas d'usage" : "The eight use cases");
    strip.innerHTML = UCS.map(([ic, t, d, pg], i) => `<a href="#${pg}" class="uc"><span class="uc-n">${i + 1}</span><span class="uc-ic" aria-hidden="true">${ic}</span><b>${t}</b><small>${d}</small></a>`).join("") +
      `<a href="#assistant" class="uc uc-ai"><span class="uc-ic" aria-hidden="true">✦</span><b>${LANG === "fr" ? "Assistant IA" : "AI assistant"}</b><small>Groq · Gemini · Ollama</small></a>`;
    const kp = q("#kpis"); if (kp) kp.parentNode.insertBefore(strip, kp.nextSibling);
    const fab = document.createElement("a"); fab.href = "#assistant"; fab.className = "ai-fab"; fab.innerHTML = `<span aria-hidden="true">✦</span> ${esc(TX.a_fab)}`;
    document.body.appendChild(fab);
    window.addEventListener("hashchange", () => { fab.hidden = location.hash === "#assistant"; });
    fab.hidden = location.hash === "#assistant";
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", inject); else inject();

  window.NTL_EXT = {
    pages: ["industry", "tourism", "urban", "assistant", "quality"],
    files: { industry: "industry.json", tourism: "tourism.json", urban: "urban.json", agent: "agent_context.json", iclusters: "industry_clusters.geojson", quality: "quality.json" },
    render: { industry: renderIndustry, tourism: renderTourism, urban: renderUrban, assistant: renderAssistant, quality: renderQuality },
    fileDesc: LANG === "fr"
      ? { "industry.json": "Zones industrielles : grappes, types, séries, validation", "industry_clusters.geojson": "Polygones des grappes industrielles et leurs six signaux", "tourism.json": "Tourisme : surcroît estival, zones touristiques, indice de saison", "agent_context.json": "Faits numérotés et outils de l'agent IA", "quality.json": "Fiches qualité, DQAF, GSBPM, FAIR (normes internationales)", "urban.json": "Urbanisation : surface éclairée, zones nouvellement éclairées, typologie, validation par le bâti" }
      : { "industry.json": "Industrial zones: clusters, types, series, validation", "industry_clusters.geojson": "Industrial-cluster polygons and their six signals", "tourism.json": "Tourism: summer excess, tourist zones, season index", "agent_context.json": "Numbered facts and tools of the AI agent", "quality.json": "Quality sheets, DQAF, GSBPM, FAIR (international standards)", "urban.json": "Urbanisation: lit area, newly lit areas, typology, built-up validation" },
  };
})();
