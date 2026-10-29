"""AI assistant on the results — Groq, Google Gemini or Ollama, grounded in the exported facts.

How it works
------------
1. ``build_context(data_dir)`` turns the dashboard data files of a country (summary, regions,
   GDP, shocks, inequality, growth, industry, tourism, methodology) into a list of short,
   numbered **facts** (``F01``, ``F02``…), each tagged with its use case and dashboard page.
   The same file, ``agent_context.json``, is published with the dashboard so that the web
   assistant and the notebook assistant share exactly the same knowledge.
2. For each question, the most relevant facts are retrieved (lexical scoring with accents and
   case removed, plus unit names and use-case keywords).
3. The LLM receives a strict system prompt: answer **only** from the facts, cite them as [F12],
   give confidence levels, say when the facts do not contain the answer, never invent figures.
4. Citations in the answer are checked against the facts actually sent; unknown ones are removed.

Providers
---------
``groq``   OpenAI-compatible API, key ``GROQ_API_KEY`` (fast, free tier) — default openai/gpt-oss-120b
``gemini`` Google Generative Language API, key ``GEMINI_API_KEY`` (or ``GOOGLE_API_KEY``)
``ollama`` local server (``OLLAMA_HOST``, default http://localhost:11434): free, data stay on site
``local``  no LLM: returns the most relevant facts verbatim (always available, used as last resort)

Keys are read from: environment variable → Colab Secrets (🔑) → ``.env`` file → masked input.
They are never printed, logged, cached or published.
"""
from __future__ import annotations

import hashlib
import html
import json
import logging
import math
import os
import re
import sqlite3
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from .lang import LANG

log = logging.getLogger("ntl")

PROVIDERS = {
    "groq": {"key": ("GROQ_API_KEY",), "url": "https://api.groq.com/openai/v1",
             "models": ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant",
                        "meta-llama/llama-4-scout-17b-16e-instruct"]},
    "gemini": {"key": ("GEMINI_API_KEY", "GOOGLE_API_KEY"), "url": "https://generativelanguage.googleapis.com/v1beta",
               "models": ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-1.5-flash"]},
    "ollama": {"key": (), "url": None, "models": ["qwen2.5:7b", "llama3.1:8b", "mistral:7b", "gemma2:9b"]},
    "local": {"key": (), "url": None, "models": ["facts"]},
}
DEFAULT_ORDER = ("groq", "gemini", "ollama")

UC = {  # use case -> (dashboard page, keywords used by retrieval)
    0: ("overview", "synthese resume message cle confiance recommandation limite summary key message overview"),
    1: ("time", "tendance evolution croissance mensuel desaisonnalise stl saison annee trend growth monthly seasonal"),
    2: ("regions", "region district convergence concentration classement herfindahl beta sigma no2 ranking"),
    3: ("time", "pib gdp elasticite elasticity nowcast prevision estimation croissance economique regional"),
    4: ("shocks", "choc covid crise rupture anomalie recuperation black marble quotidien shock break recovery daily"),
    5: ("inequality", "inegalite gini theil lorenz noir electricite acces urbain rural inequality dark access electricity"),
    6: ("industry", "industrie industriel usine grappe zone torchere hydrocarbure so2 no2 logistique industry cluster factory flare"),
    7: ("tourism", "tourisme touristique ete estival saison station balneaire nuitees ramadan tourism summer resort season"),
    8: ("urban", "urbanisation urbain ville villes extension surface eclairee nouveaux quartiers electrification village "
                 "villages population croissance demographique bati construction etalement urbanisation urban city "
                 "sprawl lit area settlement settlements electrified built-up population growth"),
    10: ("quality", "qualite norme normes dqaf gsbpm fair onu principes experimental experimentale validation incertitude "
                    "quality standard standards un principles experimental uncertainty dqaf"),
    9: ("method", "methode seuil donnees source viirs dmsp nuage torchere masque limite method threshold data source"),
}

T = {
    "fr": {
        "uc": {0: "Synthèse", 1: "Dynamiques", 2: "Régions", 3: "PIB", 4: "Chocs", 5: "Inégalités", 6: "Industrie",
               7: "Tourisme", 8: "Urbanisation", 9: "Méthode", 10: "Qualité"},
        "system": (
            "Tu es l'assistant analytique du tableau de bord « Lumières nocturnes : huit cas d'usage » pour "
            "{country} ({period}), produit par la Banque africaine de développement et Data Innovation for Africa (DI4A).\n"
            "RÈGLES IMPÉRATIVES :\n"
            "1. Réponds UNIQUEMENT à partir des FAITS fournis ci-dessous. N'invente aucun chiffre, aucune région, aucune date.\n"
            "2. Cite chaque affirmation chiffrée avec l'identifiant du fait entre crochets, par exemple [F12].\n"
            "3. Indique le niveau de confiance lorsqu'il est donné (élevée, moyenne, faible) et rappelle une limite utile.\n"
            "4. Si les faits ne permettent pas de répondre, dis-le clairement et indique quelle page du tableau de bord "
            "ou quelle analyse consulter.\n"
            "5. Les lumières sont un indicateur indirect : ne présente jamais une estimation comme une statistique officielle.\n"
            "6. Réponds dans la langue de la question (français ou anglais), de façon concise et structurée : "
            "3 à 8 phrases ou une courte liste, chiffres clés en **gras**.\n"
            "{synthetic}"),
        "synthetic": "ATTENTION : les données sont SYNTHÉTIQUES (pays test) ; rappelle-le dans la réponse.\n",
        "facts": "FAITS",
        "local_head": "Voici les résultats les plus pertinents pour votre question (mode sans modèle de langage) :",
        "local_none": "Je ne trouve aucun résultat correspondant à cette question dans les données publiées.",
        "no_provider": "Aucun fournisseur de modèle de langage n'est configuré : réponse construite à partir des faits.",
        "suggest": [
            "Compare les trois premières régions depuis 2014 et trace un graphique",
            "Quels districts ont la plus forte part de population dans le noir ? Montre-les sur la carte",
            "Quels sont les messages clés et leur niveau de confiance ?",
            "Quelles régions croissent le plus vite et lesquelles déclinent ?",
            "Que dit l'élasticité lumières–PIB et quelle est l'estimation de croissance récente ?",
            "Quel a été l'impact de la COVID-19 et en combien de temps l'activité s'est-elle redressée ?",
            "Combien de personnes vivent dans des zones habitées sans lumière ?",
            "Où se trouvent les principales zones industrielles et de quel type sont-elles ?",
            "Quelles zones sont touristiques et comment a évolué la saison estivale ?",
            "Où la surface éclairée s'étend-elle le plus vite, et où la population croît-elle sans lumière ?",
            "Quelles sont les principales limites de cette analyse ?",
        ],
        "ui_title": "Assistant IA · Lumières nocturnes",
        "ui_sub": "Posez une question sur les résultats : l'assistant répond à partir des faits publiés et cite ses sources.",
        "ask": "Votre question…", "send": "Envoyer", "clear": "Effacer", "you": "Vous", "bot": "Assistant",
        "provider": "Fournisseur", "thinking": "Analyse des résultats…",
        "sources": "Faits cités", "err": "Erreur du fournisseur {p} : {e}. Bascule sur le suivant.",
    },
    "en": {
        "uc": {0: "Summary", 1: "Dynamics", 2: "Regions", 3: "GDP", 4: "Shocks", 5: "Inequality", 6: "Industry",
               7: "Tourism", 8: "Urbanisation", 9: "Method", 10: "Quality"},
        "system": (
            "You are the analytical assistant of the \"Night-time lights: eight use cases\" dashboard for "
            "{country} ({period}), produced by the African Development Bank and Data Innovation for Africa (DI4A).\n"
            "MANDATORY RULES:\n"
            "1. Answer ONLY from the FACTS provided below. Never invent a figure, a region or a date.\n"
            "2. Cite every quantitative statement with the fact identifier in square brackets, e.g. [F12].\n"
            "3. State the confidence level when it is given (high, medium, low) and mention a relevant limitation.\n"
            "4. If the facts do not answer the question, say so clearly and point to the dashboard page or analysis to consult.\n"
            "5. Night-time lights are an indirect indicator: never present an estimate as an official statistic.\n"
            "6. Answer in the language of the question (English or French), concisely and in a structured way: "
            "3 to 8 sentences or a short list, key figures in **bold**.\n"
            "{synthetic}"),
        "synthetic": "WARNING: the data are SYNTHETIC (test country); say so in the answer.\n",
        "facts": "FACTS",
        "local_head": "Here are the most relevant results for your question (mode without a language model):",
        "local_none": "I could not find any result matching this question in the published data.",
        "no_provider": "No language-model provider is configured: answer built from the facts.",
        "suggest": [
            "Compare the top three regions since 2014 and draw a chart",
            "Which districts have the largest share of population in the dark? Show them on the map",
            "What are the key messages and their confidence levels?",
            "Which regions grow fastest and which ones decline?",
            "What does the light–GDP elasticity say, and what is the latest growth estimate?",
            "What was the impact of COVID-19 and how long did the recovery take?",
            "How many people live in inhabited areas without light?",
            "Where are the main industrial zones and what type are they?",
            "Which areas are touristic and how has the summer season evolved?",
            "Where is the lit area expanding fastest, and where does population grow without light?",
            "What are the main limitations of this analysis?",
        ],
        "ui_title": "AI assistant · Night-time lights",
        "ui_sub": "Ask a question about the results: the assistant answers from the published facts and cites its sources.",
        "ask": "Your question…", "send": "Send", "clear": "Clear", "you": "You", "bot": "Assistant",
        "provider": "Provider", "thinking": "Analysing the results…",
        "sources": "Facts cited", "err": "Provider {p} error: {e}. Switching to the next one.",
    },
}[LANG]


# --------------------------------------------------------------------------------------
# Secrets (never printed)
# --------------------------------------------------------------------------------------
def get_secret(names: tuple[str, ...], interactive: bool = False) -> str | None:
    for n in names:
        if os.environ.get(n):
            return os.environ[n].strip()
    try:  # Colab Secrets
        from google.colab import userdata  # type: ignore
        for n in names:
            try:
                v = userdata.get(n)
                if v:
                    return v.strip()
            except Exception:  # noqa: BLE001 - secret absent or access not granted
                pass
    except ImportError:
        pass
    for p in (Path.cwd() / ".env", Path.cwd().parent / ".env"):
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                k, _, v = line.partition("=")
                if k.strip() in names and v.strip():
                    return v.strip().strip('"').strip("'")
    if interactive and names:
        import getpass
        try:   # masked input; the value is never echoed, printed or stored on disk
            v = getpass.getpass(f"🔑 {names[0]} (saisie masquée / hidden input — Entrée pour ignorer) : ")
        except Exception:  # noqa: BLE001 - no interactive stdin (automated run): continue without key
            return None
        v = (v or "").strip()
        if v:
            os.environ[names[0]] = v   # current session only, so later cells do not ask again
        return v or None
    return None


def _redact(s: str, *secrets) -> str:
    s = str(s)
    for k in secrets:
        if k:
            s = s.replace(k, "•••")
    return re.sub(r"(key=|Bearer )[A-Za-z0-9_\-\.]{8,}", r"\1•••", s)


# --------------------------------------------------------------------------------------
# LLM client
# --------------------------------------------------------------------------------------
@dataclass
class Reply:
    text: str
    provider: str
    model: str
    usage: dict = field(default_factory=dict)
    cached: bool = False
    seconds: float = 0.0


class LLMClient:
    """One interface for Groq, Gemini and Ollama, with automatic model choice and fallback.

    ``provider="auto"`` tries ``order`` and keeps the first provider with credentials (or a
    reachable Ollama server); on an error at call time, the next provider is tried, and the
    deterministic ``local`` mode is the last resort, so the assistant always answers.
    """

    def __init__(self, provider: str = "auto", model: str | None = None, order=DEFAULT_ORDER,
                 temperature: float = 0.2, cache_path: str | Path | None = None, interactive: bool = False,
                 ollama_host: str | None = None, timeout: int = 90, models: dict | None = None):
        self.order = [provider] if provider not in ("auto", None) else list(order)
        self.model_override = model
        # explicit model per provider, e.g. {"groq": "openai/gpt-oss-120b", "gemini": "gemini-2.5-flash"}
        self.models = {k: v for k, v in (models or {}).items() if v}
        self.temperature = temperature
        self.timeout = timeout
        self.interactive = interactive
        self.ollama_host = (ollama_host or os.environ.get("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
        if not self.ollama_host.startswith("http"):
            self.ollama_host = "http://" + self.ollama_host
        self._keys: dict[str, str | None] = {}
        self._models: dict[str, str] = {}
        self.usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
        self.cache = None
        if cache_path:
            Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
            self.cache = sqlite3.connect(str(cache_path), check_same_thread=False)
            self.cache.execute("CREATE TABLE IF NOT EXISTS c (k TEXT PRIMARY KEY, v TEXT, t REAL)")

    # ---- discovery ----------------------------------------------------------------------
    def key(self, p: str) -> str | None:
        if p not in self._keys:
            self._keys[p] = get_secret(PROVIDERS[p]["key"], self.interactive) if PROVIDERS[p]["key"] else None
        return self._keys[p]

    def ollama_up(self) -> bool:
        import requests
        try:
            return requests.get(self.ollama_host + "/api/tags", timeout=3).ok
        except Exception:  # noqa: BLE001
            return False

    def ready(self, p: str) -> bool:
        if p == "local":
            return True
        if p == "ollama":
            return self.ollama_up()
        return bool(self.key(p))

    def available(self) -> list[str]:
        return [p for p in self.order if self.ready(p)]

    def list_models(self, p: str) -> list[str]:
        import requests
        try:
            if p == "groq":
                r = requests.get(PROVIDERS["groq"]["url"] + "/models", timeout=15,
                                 headers={"Authorization": f"Bearer {self.key('groq')}"})
                r.raise_for_status()
                return [m["id"] for m in r.json().get("data", [])]
            if p == "gemini":
                r = requests.get(PROVIDERS["gemini"]["url"] + "/models", timeout=15,
                                 headers={"x-goog-api-key": self.key("gemini")})
                r.raise_for_status()
                return [m["name"].split("/")[-1] for m in r.json().get("models", [])
                        if "generateContent" in m.get("supportedGenerationMethods", [])]
            if p == "ollama":
                r = requests.get(self.ollama_host + "/api/tags", timeout=5)
                r.raise_for_status()
                return [m["name"] for m in r.json().get("models", [])]
        except Exception as e:  # noqa: BLE001
            log.info("model list unavailable for %s: %s", p, _redact(e, self._keys.get(p)))
        return []

    def model(self, p: str) -> str:
        """Explicit model, else the first preferred model the provider currently offers."""
        if self.model_override and len(self.order) == 1:
            return self.model_override
        if p in self.models:
            return self.models[p]
        if p not in self._models:
            pref = PROVIDERS[p]["models"]
            offered = self.list_models(p) if p != "local" else []
            pick = next((m for m in pref if m in offered), None)
            if pick is None and offered:
                pick = next((m for m in offered if not any(x in m for x in ("embed", "guard", "whisper", "tts"))),
                            offered[0])
            self._models[p] = pick or pref[0]
        return self._models[p]

    # ---- calls --------------------------------------------------------------------------
    def _call(self, p: str, system: str, messages: list[dict]) -> Reply:
        import requests
        m = self.model(p)
        t0 = time.time()
        if p == "groq":
            r = requests.post(PROVIDERS["groq"]["url"] + "/chat/completions", timeout=self.timeout,
                              headers={"Authorization": f"Bearer {self.key('groq')}"},
                              json={"model": m, "temperature": self.temperature,
                                    "messages": [{"role": "system", "content": system}] + messages})
            r.raise_for_status()
            j = r.json()
            u = j.get("usage", {})
            return Reply(j["choices"][0]["message"]["content"], p, m,
                         {"prompt_tokens": u.get("prompt_tokens", 0), "completion_tokens": u.get("completion_tokens", 0)},
                         seconds=time.time() - t0)
        if p == "gemini":
            contents = [{"role": "model" if x["role"] == "assistant" else "user", "parts": [{"text": x["content"]}]}
                        for x in messages]
            r = requests.post(f"{PROVIDERS['gemini']['url']}/models/{m}:generateContent", timeout=self.timeout,
                              headers={"x-goog-api-key": self.key("gemini")},
                              json={"systemInstruction": {"parts": [{"text": system}]}, "contents": contents,
                                    "generationConfig": {"temperature": self.temperature}})
            r.raise_for_status()
            j = r.json()
            parts = j["candidates"][0]["content"].get("parts", [])
            u = j.get("usageMetadata", {})
            return Reply("".join(x.get("text", "") for x in parts), p, m,
                         {"prompt_tokens": u.get("promptTokenCount", 0), "completion_tokens": u.get("candidatesTokenCount", 0)},
                         seconds=time.time() - t0)
        if p == "ollama":
            r = requests.post(self.ollama_host + "/api/chat", timeout=max(self.timeout, 300),
                              json={"model": m, "stream": False, "options": {"temperature": self.temperature},
                                    "messages": [{"role": "system", "content": system}] + messages})
            r.raise_for_status()
            j = r.json()
            return Reply(j["message"]["content"], p, m, {"prompt_tokens": j.get("prompt_eval_count", 0),
                                                         "completion_tokens": j.get("eval_count", 0)},
                         seconds=time.time() - t0)
        raise ValueError(p)

    def chat(self, system: str, messages: list[dict], on_error=None) -> Reply | None:
        """Send the conversation to the first working provider; None if every provider failed."""
        for p in [x for x in self.order if x != "local"]:
            if not self.ready(p):
                continue
            ck = hashlib.sha256(json.dumps([p, self.model(p), self.temperature, system, messages],
                                           ensure_ascii=False).encode()).hexdigest()
            if self.cache is not None:
                row = self.cache.execute("SELECT v FROM c WHERE k=?", (ck,)).fetchone()
                if row:
                    d = json.loads(row[0])
                    return Reply(d["text"], p, d["model"], d.get("usage", {}), cached=True)
            try:
                rep = self._call(p, system, messages)
            except Exception as e:  # noqa: BLE001
                msg = _redact(e, self._keys.get(p))
                log.warning("LLM %s: %s", p, msg)
                if on_error:
                    on_error(p, msg)
                continue
            self.usage["calls"] += 1
            for k in ("prompt_tokens", "completion_tokens"):
                self.usage[k] += int(rep.usage.get(k, 0) or 0)
            if self.cache is not None:
                self.cache.execute("INSERT OR REPLACE INTO c VALUES (?,?,?)",
                                   (ck, json.dumps({"text": rep.text, "model": rep.model, "usage": rep.usage}), time.time()))
                self.cache.commit()
            return rep
        return None


# --------------------------------------------------------------------------------------
# Facts: from the dashboard data files to numbered, citable chunks
# --------------------------------------------------------------------------------------
def _n(x, d=1):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "n.d." if LANG == "fr" else "n/a"
    s = f"{x:,.{d}f}"
    return s.replace(",", " ").replace(".", ",") if LANG == "fr" else s


def _p(x, d=1, sign=True):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "n.d." if LANG == "fr" else "n/a"
    s = f"{100 * x:+.{d}f}" if sign else f"{100 * x:.{d}f}"
    return (s.replace(".", ",") + " %") if LANG == "fr" else s + "%"


def _load(p: Path):
    if not p.exists():
        return None
    if p.suffix == ".csv":
        import pandas as pd
        return pd.read_csv(p)
    return json.loads(p.read_text(encoding="utf-8"))


def build_context(data_dir: str | Path) -> dict:
    """Numbered facts of a country from its dashboard data directory (``dashboard/data/<ISO3>/``)."""
    d = Path(data_dir)
    meta, summ = _load(d / "meta.json") or {}, _load(d / "summary.json") or {}
    regions, gdp, shk = _load(d / "regions.csv"), _load(d / "gdp.json") or {}, _load(d / "shocks.json") or {}
    ineq, gro = _load(d / "inequality.json") or {}, _load(d / "growth.json") or {}
    ind, tou = _load(d / "industry.json") or {}, _load(d / "tourism.json") or {}
    urb = _load(d / "urban.json") or {}
    fr = LANG == "fr"
    facts: list[dict] = []

    def add(uc, title, text, names=()):
        facts.append({"id": f"F{len(facts) + 1:02d}", "uc": uc, "page": UC[uc][0], "title": title,
                      "text": re.sub(r"\s+", " ", text).strip(), "names": list(names)})

    country = meta.get("name") if fr else (meta.get("name_en") or meta.get("name"))
    per = meta.get("period", ["?", "?"])
    add(0, "Pays et période" if fr else "Country and period",
        (f"Pays : {country} ({meta.get('iso3')}). Période annuelle {per[0]}–{per[1]}, série mensuelle "
         f"{(meta.get('monthly_period') or ['?', '?'])[0]} → {(meta.get('monthly_period') or ['?', '?'])[1]}. "
         f"Niveaux : {', '.join(meta.get('levels', []))}. Données synthétiques : {'oui' if meta.get('synthetic') else 'non'}.")
        if fr else
        (f"Country: {country} ({meta.get('iso3')}). Annual period {per[0]}–{per[1]}, monthly series "
         f"{(meta.get('monthly_period') or ['?', '?'])[0]} → {(meta.get('monthly_period') or ['?', '?'])[1]}. "
         f"Levels: {', '.join(meta.get('levels', []))}. Synthetic data: {'yes' if meta.get('synthetic') else 'no'}."))
    uc_of_theme = {"Tendance nationale": 1, "National trend": 1, "Régions": 2, "Regions": 2, "Convergence": 2,
                   "Lien avec le PIB": 3, "Link with GDP": 3, "Estimation récente": 3, "Recent estimate": 3,
                   "Chocs": 4, "Shocks": 4, "Inégalités et accès": 5, "Inequality and access": 5,
                   "Zones industrielles": 6, "Industrial zones": 6, "Tourisme estival": 7, "Summer tourism": 7}
    for m in summ.get("messages", []):
        add(uc_of_theme.get(m.get("theme"), 0), m.get("theme", ""),
            f"{m.get('text', '')} (confiance {m.get('confidence')} : {m.get('why')})" if fr else
            f"{m.get('text', '')} (confidence {m.get('confidence')}: {m.get('why')})")
    k = summ.get("kpis", [])
    if k:
        def kv(x):
            v = x.get("value")
            f = x.get("fmt")
            if v is None:
                return "n.d."
            if f == "num":
                return _n(v, 0)
            return _p(v, 1) if f == "pct" else _p(v, 0, False) if f == "pct0" else _n(v / 1e6, 2) + " M" if f == "people" else _n(v, 2)
        add(0, "Indicateurs clés" if fr else "Key indicators",
            "; ".join(f"{x.get('label')} = {kv(x)} ({x.get('sub', '')})" for x in k))
    if summ.get("recommendations"):
        add(0, "Recommandations" if fr else "Recommendations", " ".join(f"• {r}" for r in summ["recommendations"]))
    for lim in summ.get("limits", []):
        add(9, (("Limite : " if fr else "Limitation: ") + lim.get("title", "")), lim.get("text", ""))

    # ---- regions (use cases 1, 2) ----------------------------------------------------------
    if regions is not None and len(regions):
        import numpy as np
        for lv in ("ADM1", "ADM2"):
            r = regions[regions["level"] == lv].copy()
            if not len(r):
                continue
            yr = int(r["year"].iloc[0])
            if lv == "ADM1" or len(r) <= 12:
                for _, x in r.sort_values("sol", ascending=False).iterrows():
                    add(2, f"{x['name']} ({lv})",
                        (f"{x['name']} ({lv}, {yr}) : part de la lumière nationale {_p(x.get('share_last'), 1, False)}, "
                         f"croissance annuelle {_p(x.get('growth'))} (IC {_p(x.get('growth_lo'))} à {_p(x.get('growth_hi'))}, "
                         f"classe {x.get('class')}), lumière par habitant {_n(x.get('sol_pc'), 3)}, population "
                         f"{_n(x.get('pop', np.nan) / 1e6, 2)} M, dans le noir {_p(x.get('dark_share'), 0, False)}"
                         + (f", PIB estimé (expérimental) {_n(x['gdp_est'] / 1e9, 2)} Md USD" if 'gdp_est' in x and x['gdp_est'] == x['gdp_est'] else "") + ".")
                        if fr else
                        (f"{x['name']} ({lv}, {yr}): share of national light {_p(x.get('share_last'), 1, False)}, "
                         f"annual growth {_p(x.get('growth'))} (CI {_p(x.get('growth_lo'))} to {_p(x.get('growth_hi'))}, "
                         f"class {x.get('class')}), light per capita {_n(x.get('sol_pc'), 3)}, population "
                         f"{_n(x.get('pop', np.nan) / 1e6, 2)} M, in the dark {_p(x.get('dark_share'), 0, False)}"
                         + (f", estimated GDP (experimental) {_n(x['gdp_est'] / 1e9, 2)} bn USD" if 'gdp_est' in x and x['gdp_est'] == x['gdp_est'] else "") + "."),
                        names=[str(x["name"])])
            else:
                s = r.dropna(subset=["growth"]).sort_values("growth", ascending=False)
                top = ", ".join(f"{a} ({_p(b)})" for a, b in zip(s["name"].head(8), s["growth"].head(8)))
                bot = ", ".join(f"{a} ({_p(b)})" for a, b in zip(s["name"].tail(8)[::-1], s["growth"].tail(8)[::-1]))
                cc = ", ".join(f"{k} {v}" for k, v in r["class"].value_counts().items())
                add(2, f"{lv} : classement" if fr else f"{lv}: ranking",
                    (f"{len(r)} unités {lv}. Classes : {cc}. Croissance la plus forte : {top}. "
                     f"La plus faible : {bot}.") if fr else
                    (f"{len(r)} {lv} units. Classes: {cc}. Fastest growth: {top}. Slowest: {bot}."),
                    names=list(s["name"].head(8)) + list(s["name"].tail(8)))
                big = r.sort_values("sol", ascending=False).head(10)
                add(2, f"{lv} : plus lumineuses" if fr else f"{lv}: brightest",
                    ("Unités les plus lumineuses : " if fr else "Brightest units: ")
                    + ", ".join(f"{a} ({_p(b, 1, False)})" for a, b in zip(big["name"], big["share_last"])) + ".",
                    names=list(big["name"]))
    b = gro.get("beta") or {}
    if b.get("beta") is not None:
        ci = b.get("ci") or [None, None]
        conc = (gro.get("concentration") or {}).get("ADM1") or []
        add(2, "Convergence et concentration" if fr else "Convergence and concentration",
            (f"β-convergence ({b.get('level')}) : β = {_n(b['beta'], 3)} (IC {_n(ci[0], 3)} à {_n(ci[1], 3)}, n = {b.get('n')}). "
             "β < 0 avec un IC entièrement négatif = convergence. "
             + (f"Part de la 1ʳᵉ région : {_p(conc[0]['top1_share'], 1, False)} en {conc[0]['year']} → "
                f"{_p(conc[-1]['top1_share'], 1, False)} en {conc[-1]['year']} ; HHI {_n(conc[-1]['hhi'], 3)}." if conc else ""))
            if fr else
            (f"β-convergence ({b.get('level')}): β = {_n(b['beta'], 3)} (CI {_n(ci[0], 3)} to {_n(ci[1], 3)}, n = {b.get('n')}). "
             "β < 0 with a fully negative CI = convergence. "
             + (f"Share of the leading region: {_p(conc[0]['top1_share'], 1, False)} in {conc[0]['year']} → "
                f"{_p(conc[-1]['top1_share'], 1, False)} in {conc[-1]['year']}; HHI {_n(conc[-1]['hhi'], 3)}." if conc else "")))

    # ---- GDP (use case 3) -----------------------------------------------------------------------
    for spec in ("levels", "growth", "long"):
        e = gdp.get(spec)
        if e:
            lab = {"levels": "niveaux" if fr else "levels", "growth": "taux de croissance" if fr else "growth rates",
                   "long": "série longue DMSP–VIIRS" if fr else "long DMSP–VIIRS series"}[spec]
            add(3, f"Élasticité ({lab})" if fr else f"Elasticity ({lab})",
                (f"Élasticité lumières–PIB réel en {lab} : β = {_n(e['beta'], 2)} (IC 95 % {_n(e['ci'][0], 2)} à "
                 f"{_n(e['ci'][1], 2)}, R² = {_n(e.get('r2'), 2)}, n = {e.get('n')}, confiance {e.get('confidence')} : "
                 f"{e.get('confidence_reason')}). +1 % de PIB ↔ +β % de lumière.") if fr else
                (f"Light–real GDP elasticity in {lab}: β = {_n(e['beta'], 2)} (95% CI {_n(e['ci'][0], 2)} to "
                 f"{_n(e['ci'][1], 2)}, R² = {_n(e.get('r2'), 2)}, n = {e.get('n')}, confidence {e.get('confidence')}: "
                 f"{e.get('confidence_reason')}). +1% GDP ↔ +β% light."))
    nc = (gdp.get("nowcast") or {}).get("estimates") or []
    for x in nc:
        add(3, "Estimation du PIB (année non publiée)" if fr else "GDP estimate (unpublished year)",
            (f"Croissance du PIB réel estimée par les lumières pour {x['year']} : {_p(x.get('growth_est'))} ; PIB "
             f"{_n(x.get('gdp_est', 0) / 1e9, 2)} Md USD constants (IC 80 % {_n(x.get('lo80', 0) / 1e9, 2)}–"
             f"{_n(x.get('hi80', 0) / 1e9, 2)}). Estimation expérimentale, confiance faible.") if fr else
            (f"Real GDP growth estimated from lights for {x['year']}: {_p(x.get('growth_est'))}; GDP "
             f"{_n(x.get('gdp_est', 0) / 1e9, 2)} bn constant USD (80% interval {_n(x.get('lo80', 0) / 1e9, 2)}–"
             f"{_n(x.get('hi80', 0) / 1e9, 2)}). Experimental estimate, low confidence."))
    if gdp.get("tracking_corr") is not None:
        add(3, "Suivi hors échantillon" if fr else "Out-of-sample tracking",
            (f"Hors échantillon, la croissance estimée par les lumières a une corrélation de {_n(gdp['tracking_corr'], 2)} "
             f"avec la croissance officielle ; erreur absolue moyenne {_n(gdp.get('tracking_mae_pp'), 1)} point.") if fr else
            (f"Out of sample, light-based growth has a correlation of {_n(gdp['tracking_corr'], 2)} with official growth; "
             f"mean absolute error {_n(gdp.get('tracking_mae_pp'), 1)} percentage point."))

    # ---- shocks (use case 4) --------------------------------------------------------------------
    for x in shk.get("impacts", []):
        if not x.get("computable"):
            continue
        rec = (f"retour au niveau d'avant-choc après {x.get('months_to_recovery'):.0f} mois" if fr else
               f"back to the pre-shock level after {x.get('months_to_recovery'):.0f} months") if x.get("recovered") else \
            ("pas de retour au niveau d'avant-choc" if fr else "no return to the pre-shock level")
        add(4, f"Choc : {x.get('label')}" if fr else f"Shock: {x.get('label')}",
            (f"{x.get('label')} ({x.get('start')} → {x.get('end')}) : creux de {_n(x.get('trough_pct'), 1)} % le "
             f"{x.get('trough_date')}, {rec}. Distinct du bruit : {'oui' if x.get('distinguishable_from_noise') else 'non'}.") if fr else
            (f"{x.get('label')} ({x.get('start')} → {x.get('end')}): trough of {_n(x.get('trough_pct'), 1)}% on "
             f"{x.get('trough_date')}, {rec}. Distinguishable from noise: {'yes' if x.get('distinguishable_from_noise') else 'no'}."))
    if shk.get("breaks"):
        add(4, "Ruptures détectées" if fr else "Detected breaks",
            ("Ruptures structurelles : " if fr else "Structural breaks: ")
            + "; ".join(f"{x.get('date')} ({_n(x.get('jump_pct'), 1)} %)" for x in shk["breaks"])
            + (f". Sans événement connu à ±6 mois : {len(shk.get('unexplained_breaks', []))}." if fr else
               f". Without a known event within ±6 months: {len(shk.get('unexplained_breaks', []))}."))
    reg = shk.get("regional") or []
    if reg and regions is not None:
        nm = dict(zip(regions["unit_id"], regions["name"]))
        worst = sorted(reg, key=lambda x: x.get("trough_pct") or 0)[:5]
        add(4, "Impact régional des chocs" if fr else "Regional impact of shocks",
            ("Régions les plus touchées (creux) : " if fr else "Hardest-hit regions (trough): ")
            + ", ".join(f"{nm.get(x['unit_id'], x['unit_id'])} {_n(x['trough_pct'], 1)} % ({x['event']})" for x in worst) + ".",
            names=[nm.get(x["unit_id"], "") for x in worst])

    # ---- inequality (use case 5) ---------------------------------------------------------------
    s = ineq.get("series") or []
    if s:
        ci = ineq.get("gini_change_ci") or [None, None]
        add(5, "Gini et Theil" if fr else "Gini and Theil",
            (f"Gini de la lumière par habitant ({ineq.get('level')}) : {_n(s[0]['gini'], 3)} en {s[0]['year']} → "
             f"{_n(s[-1]['gini'], 3)} en {s[-1]['year']} (variation {_n(ineq.get('gini_change'), 3)}, IC bootstrap "
             f"{_n(ci[0], 3)} à {_n(ci[1], 3)}). Theil T {_n(s[-1].get('theil'), 3)} ; part entre régions "
             f"{_p(s[-1].get('theil_between_share'), 0, False)}.") if fr else
            (f"Gini of light per capita ({ineq.get('level')}): {_n(s[0]['gini'], 3)} in {s[0]['year']} → "
             f"{_n(s[-1]['gini'], 3)} in {s[-1]['year']} (change {_n(ineq.get('gini_change'), 3)}, bootstrap CI "
             f"{_n(ci[0], 3)} to {_n(ci[1], 3)}). Theil T {_n(s[-1].get('theil'), 3)}; between-region share "
             f"{_p(s[-1].get('theil_between_share'), 0, False)}."))
    nat = ineq.get("national") or []
    if nat:
        a, z = nat[0], nat[-1]
        add(5, "Populations dans le noir" if fr else "Population in the dark",
            (f"Habitants de zones habitées sans lumière détectable : {_n((a.get('pop_dark') or 0) / 1e6, 2)} M "
             f"({_p(a.get('dark_share'), 0, False)}) en {a['year']} → {_n((z.get('pop_dark') or 0) / 1e6, 2)} M "
             f"({_p(z.get('dark_share'), 0, False)}) en {z['year']}. Rapport lumière/hab. urbain/rural "
             f"{_n(z.get('urban_rural_ratio'), 1)}. Proxy de l'accès à l'électricité, sensible au seuil.") if fr else
            (f"People in inhabited areas without detectable light: {_n((a.get('pop_dark') or 0) / 1e6, 2)} M "
             f"({_p(a.get('dark_share'), 0, False)}) in {a['year']} → {_n((z.get('pop_dark') or 0) / 1e6, 2)} M "
             f"({_p(z.get('dark_share'), 0, False)}) in {z['year']}. Urban/rural light-per-capita ratio "
             f"{_n(z.get('urban_rural_ratio'), 1)}. Proxy of electricity access, sensitive to the threshold."))
    if ineq.get("access_gap_pp") is not None:
        add(5, "Comparaison avec la Banque mondiale" if fr else "Comparison with the World Bank",
            (f"Écart moyen entre la part de la population en zone éclairée et le taux d'accès à l'électricité de la "
             f"Banque mondiale : {_n(ineq['access_gap_pp'], 1)} points.") if fr else
            (f"Average gap between the share of people in lit areas and the World Bank electricity-access rate: "
             f"{_n(ineq['access_gap_pp'], 1)} points."))

    # ---- industry (use case 6) -----------------------------------------------------------------
    if ind.get("available"):
        c = ind.get("counts", {})
        lab = ind.get("type_labels", {})
        v = ind.get("validation") or {}
        add(6, "Zones industrielles : synthèse" if fr else "Industrial zones: summary",
            (f"{ind.get('n')} grappes industrielles (≥ {ind['params']['min_signals']} signaux sur 6) : "
             + ", ".join(f"{lab.get(t, t)} {n}" for t, n in c.items())
             + f". Part de la lumière nationale : {_p(ind.get('share_last'), 1, False)} ; croissance annuelle "
               f"{_p((ind.get('trend') or {}).get('growth'))}."
             + (f" Validation ({v.get('source')}) : précision {_p(v.get('precision'), 0, False)}, rappel "
                f"{_p(v.get('recall'), 0, False)}." if v.get("available") else " Pas de validation disponible."))
            if fr else
            (f"{ind.get('n')} industrial clusters (≥ {ind['params']['min_signals']} of 6 signals): "
             + ", ".join(f"{lab.get(t, t)} {n}" for t, n in c.items())
             + f". Share of national light: {_p(ind.get('share_last'), 1, False)}; annual growth "
               f"{_p((ind.get('trend') or {}).get('growth'))}."
             + (f" Validation ({v.get('source')}): precision {_p(v.get('precision'), 0, False)}, recall "
                f"{_p(v.get('recall'), 0, False)}." if v.get("available") else " No validation available.")))
        top = ind.get("top") or []
        if top:
            add(6, "Principales grappes industrielles" if fr else "Main industrial clusters",
                "; ".join(f"{x['cluster_id']} — {x.get('type_label')} à {x.get('adm2_name') or x.get('adm1_name')} "
                          f"({x.get('area_km2')} km², {x.get('n_strong')} signaux, confiance {x.get('confidence')})"
                          if fr else
                          f"{x['cluster_id']} — {x.get('type_label')} in {x.get('adm2_name') or x.get('adm1_name')} "
                          f"({x.get('area_km2')} km², {x.get('n_strong')} signals, confidence {x.get('confidence')})"
                          for x in top[:10]),
                names=[x.get("adm2_name") or "" for x in top[:10]] + [x.get("adm1_name") or "" for x in top[:10]])
        for u in (ind.get("units") or {}).get("ADM1", [])[:12]:
            add(6, f"Industrie — {u['name']}" if fr else f"Industry — {u['name']}",
                (f"{u['name']} : {u['n_clusters']} grappe(s) industrielle(s), {_n(u.get('area_km2'), 1)} km², "
                 f"{_p(u.get('ind_share'), 1, False)} de la lumière de la région.") if fr else
                (f"{u['name']}: {u['n_clusters']} industrial cluster(s), {_n(u.get('area_km2'), 1)} km², "
                 f"{_p(u.get('ind_share'), 1, False)} of the region's light."), names=[u["name"]])
        va = ind.get("industry_va") or {}
        if va.get("corr_growth") is not None:
            add(6, "Lumière industrielle et valeur ajoutée" if fr else "Industrial light and value added",
                (f"Corrélation entre la croissance de la lumière industrielle et celle de la valeur ajoutée industrielle "
                 f"(Banque mondiale, NV.IND.TOTL.KD) : {_n(va['corr_growth'], 2)} sur {va.get('n')} années.") if fr else
                (f"Correlation between the growth of industrial light and of industry value added (World Bank, "
                 f"NV.IND.TOTL.KD): {_n(va['corr_growth'], 2)} over {va.get('n')} years."))

    # ---- tourism (use case 7) ------------------------------------------------------------------
    if tou.get("available"):
        tz = [u for u in tou.get("units", []) if u.get("class") == "tourist"]
        add(7, "Tourisme : zones touristiques" if fr else "Tourism: tourist zones",
            ((f"{len(tz)} zone(s) touristique(s) sur {tou.get('n_units')} unités {tou.get('level')} (surcroît estival net "
              f"≥ {_p(tou['params']['min_excess'], 0, False)}, mois de pointe {tou['params']['peak_months']}) : "
              + ", ".join(f"{u['name']} ({_p(u.get('net_gain'), 0)}, confiance {u.get('confidence')})" for u in tz[:10]) + ".")
             if fr else
             (f"{len(tz)} tourist zone(s) out of {tou.get('n_units')} {tou.get('level')} units (net summer excess "
              f"≥ {_p(tou['params']['min_excess'], 0, False)}, peak months {tou['params']['peak_months']}): "
              + ", ".join(f"{u['name']} ({_p(u.get('net_gain'), 0)}, confidence {u.get('confidence')})" for u in tz[:10]) + ".")),
            names=[u["name"] for u in tz[:10]])
        idx = tou.get("index") or []
        if idx:
            add(7, "Indice de saison touristique" if fr else "Tourist season index",
                (f"Indice de saison (base 100 = {idx[0].get('base_year')}) : "
                 + ", ".join(f"{x['year']} : {x['index']:.0f}" for x in idx if x.get("index") is not None)
                 + ". Années avec Ramadan chevauchant la saison : "
                 + ", ".join(str(x["year"]) for x in idx if (x.get("ramadan_days") or 0) >= 10) + ".") if fr else
                (f"Season index (base 100 = {idx[0].get('base_year')}): "
                 + ", ".join(f"{x['year']}: {x['index']:.0f}" for x in idx if x.get("index") is not None)
                 + ". Years when Ramadan overlaps the season: "
                 + ", ".join(str(x["year"]) for x in idx if (x.get("ramadan_days") or 0) >= 10) + "."))
        v = tou.get("validation") or {}
        if v.get("available"):
            add(7, "Validation par les nuitées" if fr else "Validation with hotel nights",
                (f"Corrélation entre l'indice de saison et {v.get('label') or v.get('variable')} : {_n(v.get('corr'), 2)} "
                 f"({v.get('n')} années ; en croissance : {_n(v.get('corr_growth'), 2)}).") if fr else
                (f"Correlation between the season index and {v.get('label') or v.get('variable')}: {_n(v.get('corr'), 2)} "
                 f"({v.get('n')} years; in growth rates: {_n(v.get('corr_growth'), 2)})."))

    # ---- use case 8: urbanisation -----------------------------------------------------------------
    if urb.get("available"):
        tr, tot, cc, v = urb.get("trend") or {}, urb.get("totals") or {}, urb.get("class_counts") or {}, urb.get("validation") or {}
        lab = urb.get("class_labels") or {}
        lg, pg = (tr.get("lit") or {}).get("growth"), (tr.get("pop") or {}).get("growth")
        add(8, "Urbanisation : surface éclairée et population" if fr else "Urbanisation: lit area and population",
            (f"Surface éclairée nationale : {_p(lg)} par an ; population : {_p(pg)} par an. Classes ({urb.get('level')}) : "
             + ", ".join(f"{lab.get(k, k)} {n}" for k, n in cc.items()) + ".") if fr else
            (f"National lit area: {_p(lg)} per year; population: {_p(pg)} per year. Classes ({urb.get('level')}): "
             + ", ".join(f"{lab.get(k, k)} {n}" for k, n in cc.items()) + "."))
        if tot:
            add(8, "Urbanisation : zones nouvellement éclairées" if fr else "Urbanisation: newly lit areas",
                (f"Entre {tot.get('y0')} et {tot.get('y1')} : {_n(tot.get('new_lit_km2'), 0)} km² nouvellement éclairés, dont "
                 f"{_n(tot.get('electrified_km2'), 0)} km² de zones déjà habitées (électrification, ≈ {_n((tot.get('electrified_pop') or 0) / 1e3, 0)} k "
                 f"habitants) et {_n(tot.get('settled_km2'), 0)} km² de nouvelles implantations ; {_n(tot.get('lost_lit_km2'), 0)} km² "
                 f"ont perdu leur lumière.") if fr else
                (f"Between {tot.get('y0')} and {tot.get('y1')}: {_n(tot.get('new_lit_km2'), 0)} km² newly lit, of which "
                 f"{_n(tot.get('electrified_km2'), 0)} km² already inhabited (electrification, ≈ {_n((tot.get('electrified_pop') or 0) / 1e3, 0)}k "
                 f"people) and {_n(tot.get('settled_km2'), 0)} km² of new settlements; {_n(tot.get('lost_lit_km2'), 0)} km² lost their light."))
        units = (urb.get("units") or {}).get(urb.get("level")) or []
        if units:
            srt = sorted([u for u in units if u.get("lit_growth") is not None], key=lambda u: -u["lit_growth"])
            unl = [u for u in units if u.get("class") == "unlit"]
            add(8, "Urbanisation : unités" if fr else "Urbanisation: units",
                (("Plus forte extension de la surface éclairée : " + ", ".join(f"{u['name']} ({_p(u['lit_growth'])}/an)" for u in srt[:6])
                  + ". Croissance non éclairée (population plus rapide que la lumière) : "
                  + (", ".join(u["name"] for u in unl[:8]) or "aucune") + ".") if fr else
                 ("Fastest lit-area expansion: " + ", ".join(f"{u['name']} ({_p(u['lit_growth'])}/yr)" for u in srt[:6])
                  + ". Unlit growth (population faster than light): " + (", ".join(u["name"] for u in unl[:8]) or "none") + ".")),
                names=[u["name"] for u in srt[:6] + unl[:8]])
        if v.get("available"):
            add(8, "Validation par le bâti GHSL" if fr else "Validation with GHSL built-up",
                (f"Corrélation de rang (Spearman) entre croissance de la surface éclairée et croissance du bâti GHSL : "
                 f"{_n(v.get('rho'), 2)} (p = {_n(v.get('p_value'), 3)}, {v.get('n')} unités).") if fr else
                (f"Spearman rank correlation between lit-area growth and GHSL built-up growth: {_n(v.get('rho'), 2)} "
                 f"(p = {_n(v.get('p_value'), 3)}, {v.get('n')} units)."))

    # ---- quality and international standards ------------------------------------------------------
    q = _load(d / "quality.json") or {}
    if q:
        add(10, "Qualité et normes internationales" if fr else "Quality and international standards",
            q.get("statement", "") + (" Cadres appliqués : Principes fondamentaux de la statistique officielle (ONU), "
                                      "DQAF, GSBPM (CEE-ONU), principes FAIR." if fr else
                                      " Frameworks applied: UN Fundamental Principles of Official Statistics, DQAF, "
                                      "UNECE GSBPM, FAIR principles."))
        for u in q.get("use_cases", []):
            v = u.get("validation") or {}
            add(u["uc"], ("Fiche qualité — " if fr else "Quality sheet — ") + u["title"],
                (f"Validation : {v.get('text')} ({v.get('metric')} = {v.get('value')}). Incertitude : {u.get('uncertainty')} "
                 f"Limites : {u.get('limits')} Statut : statistique expérimentale ; confiance {u.get('confidence') or 'n.d.'}.") if fr else
                (f"Validation: {v.get('text')} ({v.get('metric')} = {v.get('value')}). Uncertainty: {u.get('uncertainty')} "
                 f"Limitations: {u.get('limits')} Status: experimental statistic; confidence {u.get('confidence') or 'n/a'}."))

    # ---- methodology -----------------------------------------------------------------------------
    for uc, txt in METHOD[LANG].items():
        add(9 if uc == 0 else uc, ("Méthode — " if fr else "Method — ") + T["uc"][uc if uc else 9], txt)
    return {"country": country, "iso3": meta.get("iso3"), "period": per, "synthetic": bool(meta.get("synthetic")),
            "lang": LANG, "generated_at": meta.get("generated_at"), "facts": facts,
            "suggestions": T["suggest"], "uc_labels": {str(k): v for k, v in T["uc"].items()},
            "tools": _tool_specs(meta.get("levels") or ("ADM1", "ADM2"))}


def _tool_specs(levels):
    from .agent_tools import tool_specs
    return tool_specs(tuple(levels))


METHOD = {
    "fr": {
        0: "Données : VIIRS DNB mensuel (VCMSLCFG) et annuel VNL V2, DMSP–VIIRS harmonisé, Black Marble quotidien, "
           "GHSL/WorldPop, Sentinel-5P NO₂/SO₂, MODIS LST, Banque mondiale. Nettoyage : pixels valides si cf_cvg ≥ 2, "
           "unité-mois gardée si ≥ 80 % de pixels observés, pics remplacés, fond et torchères masqués.",
        1: "Dynamiques : STL robuste sur log(somme des lumières), tendance de Theil–Sen + test de Mann–Kendall, "
           "glissement annuel, ruptures par segmentation linéaire avec pénalité BIC.",
        2: "Régions : croissance robuste par unité, classe Croissance/Déclin si |pente| ≥ 1 %/an et p < 0,10 ; "
           "β-convergence (MCO robustes), σ-convergence, indice de Herfindahl.",
        3: "PIB : log(NTL) = α + β log(PIB) en niveaux et en croissance, écarts-types HAC, diagnostics DW/BP/JB, "
           "prévision hors échantillon ; PIB régional expérimental au prorata de la lumière (γ = 1 et 0,5).",
        4: "Chocs : creux = écart maximal au niveau des 12 mois d'avant-choc sur la série désaisonnalisée, "
           "récupération = retour à ce niveau ; indice quotidien Black Marble (médiane mobile 7 jours).",
        5: "Inégalités : Gini, Theil (décomposition entre/intra) et Lorenz pondérés par la population ; "
           "population dans le noir = habitants de pixels ≥ 5 hab. sous 0,5 nW (sensibilité 0,25/0,5/1).",
        6: "Industrie : six signaux par pixel (lumière ≥ 5 nW, lumière/habitant, bâti non résidentiel GHSL, NO₂ et "
           "SO₂ Sentinel-5P, chaleur de surface MODIS) ; pixels ≥ 3 signaux regroupés en grappes ; typologie, "
           "confiance selon le nombre de signaux concordants, validation précision/rappel (liste officielle ou OSM).",
        7: "Tourisme : surcroît estival = log(lumière des mois de pointe / mois d'intersaison) ; net de la médiane "
           "des unités comparables de même latitude ; zone touristique si ≥ +10 % et significatif sur ≥ 3 étés ; "
           "indice de saison base 100 ; Ramadan signalé ; validation par les nuitées.",
        8: "Urbanisation : surface éclairée annuelle (pixels ≥ seuil) et sa croissance (Theil–Sen) comparée à celle de la "
           "population (GHSL/WorldPop) ; zones nouvellement éclairées (sombres les 2 premières années, éclairées les 2 "
           "dernières), séparées en électrification de zones déjà habitées et nouvelles implantations ; validation par "
           "la croissance du bâti GHSL BUILT-S.",
    },
    "en": {
        0: "Data: VIIRS DNB monthly (VCMSLCFG) and annual VNL V2, harmonised DMSP–VIIRS, daily Black Marble, "
           "GHSL/WorldPop, Sentinel-5P NO₂/SO₂, MODIS LST, World Bank. Cleaning: pixels valid if cf_cvg ≥ 2, "
           "unit-month kept if ≥ 80% of pixels observed, spikes replaced, background and gas flares masked.",
        1: "Dynamics: robust STL on log(sum of lights), Theil–Sen trend + Mann–Kendall test, year-on-year growth, "
           "breaks by piecewise-linear segmentation with a BIC penalty.",
        2: "Regions: robust growth per unit, Growth/Decline class if |slope| ≥ 1%/yr and p < 0.10; β-convergence "
           "(robust OLS), σ-convergence, Herfindahl index.",
        3: "GDP: log(NTL) = α + β log(GDP) in levels and growth rates, HAC standard errors, DW/BP/JB diagnostics, "
           "out-of-sample tracking; experimental regional GDP allocated by light (γ = 1 and 0.5).",
        4: "Shocks: trough = largest gap to the 12-month pre-shock level of the seasonally adjusted series, recovery "
           "= return to that level; daily Black Marble index (7-day rolling median).",
        5: "Inequality: population-weighted Gini, Theil (between/within decomposition) and Lorenz; population in the "
           "dark = residents of pixels ≥ 5 people below 0.5 nW (sensitivity 0.25/0.5/1).",
        6: "Industry: six signals per pixel (light ≥ 5 nW, light per resident, GHSL non-residential built-up, "
           "Sentinel-5P NO₂ and SO₂, MODIS surface heat); pixels with ≥ 3 signals grouped into clusters; typology, "
           "confidence from concordant signals, precision/recall validation (official list or OSM).",
        7: "Tourism: summer excess = log(peak-month light / shoulder-month light); net of the median of comparable "
           "units at the same latitude; tourist zone if ≥ +10% and significant over ≥ 3 summers; season index base "
           "100; Ramadan flagged; validation with hotel nights.",
        8: "Urbanisation: annual lit area (pixels ≥ threshold) and its growth (Theil–Sen) compared with population "
           "growth (GHSL/WorldPop); newly lit areas (dark in the first 2 years, lit in the last 2), split into "
           "electrification of already inhabited areas and new settlements; validation with GHSL BUILT-S built-up growth.",
    },
}


# --------------------------------------------------------------------------------------
# Retrieval
# --------------------------------------------------------------------------------------
STOP = set("""le la les un une des de du d l et ou en a au aux pour par sur dans avec est sont quel quelle quels
quelles que qui quoi comment combien ce cette ces il elle on nous vous ils the a an of to in on for and or is are
what which who how many much does do did this that these those be by with from as at it its""".split())


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s).lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _tok(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", _norm(s)) if len(w) > 1 and w not in STOP]


def retrieve(ctx: dict, question: str, k: int = 14, max_chars: int = 22000, ranked: bool = False) -> list[dict]:
    """Most relevant facts for ``question`` (all facts if they fit in ``max_chars``).

    With ``ranked=True`` the facts are returned by decreasing relevance (and only those with a
    positive score); otherwise they are returned in their original order.
    """
    facts = ctx["facts"]
    if not ranked and sum(len(f["text"]) + len(f["title"]) for f in facts) <= max_chars:
        return facts
    q = set(_tok(question))
    docs = [set(_tok(f["title"] + " " + f["text"] + " " + UC[f["uc"]][1])) for f in facts]
    nd = len(docs)
    idf = {w: math.log((nd + 1) / (1 + sum(w in d for d in docs))) + 1 for w in q}
    scores = []
    nq = _norm(question)
    for f, d in zip(facts, docs):
        sc = sum(idf[w] for w in q if w in d)
        sc += sum(3.0 for nm in f.get("names", []) if nm and _norm(nm).split(" (")[0] in nq)
        sc += 1.5 * sum(1 for w in q if w in _tok(f["title"]))
        if f["uc"] == 0 and sc > 0:
            sc += 0.5
        scores.append(sc)
    order = sorted(range(nd), key=lambda i: -scores[i])
    keep = [facts[i] for i in order[:k] if scores[i] > 0]
    if ranked:
        return keep
    return sorted(keep or [f for f in facts if f["uc"] == 0][:k], key=lambda f: f["id"])


# --------------------------------------------------------------------------------------
# Agent
# --------------------------------------------------------------------------------------
@dataclass
class Answer:
    question: str
    text: str
    citations: list[dict]
    provider: str
    model: str
    seconds: float = 0.0
    cached: bool = False

    def _repr_markdown_(self):
        src = "  \n".join(f"[{c['id']}] {c['title']}" for c in self.citations)
        return f"{self.text}\n\n<sub>{self.provider} · {self.model} — {src}</sub>"


class ResultsAgent:
    """Question answering on the results of one country, grounded in the exported facts."""

    def __init__(self, context: dict | str | Path, client: LLMClient | None = None, history: int = 6):
        if isinstance(context, (str, Path)):
            p = Path(context)
            context = json.loads((p / "agent_context.json" if p.is_dir() else p).read_text(encoding="utf-8"))
        self.ctx = context
        self.client = client or LLMClient()
        self.history: list[dict] = []
        self.max_turns = history
        self.errors: list[str] = []

    def system_prompt(self, facts: list[dict]) -> str:
        head = T["system"].format(country=self.ctx.get("country"), period="–".join(map(str, self.ctx.get("period", []))),
                                  synthetic=T["synthetic"] if self.ctx.get("synthetic") else "")
        body = "\n".join(f"[{f['id']}] ({T['uc'][f['uc']]}) {f['title']} : {f['text']}" for f in facts)
        return f"{head}\n{T['facts']} :\n{body}"

    def local_answer(self, question: str, facts: list[dict]) -> str:
        top = retrieve({"facts": facts}, question, k=4, ranked=True)
        if not top:
            return T["local_none"]
        return T["local_head"] + "\n\n" + "\n".join(f"- **{f['title']}** — {f['text']} [{f['id']}]" for f in top)

    def ask(self, question: str) -> Answer:
        from . import scope as SC
        names = sorted({n for f in self.ctx.get("facts", []) for n in f.get("names", []) if n})
        per = self.ctx.get("period") or []
        chk = SC.check(question, self.ctx, names, history=bool(self.history),
                       years=range(per[0], per[-1] + 1) if len(per) >= 2 else (), default_lang=LANG)
        if chk["status"] != "ok":          # outside the results: standard reply, no model call
            text = SC.reply(chk, self.ctx, names[0] if names else "")
            self.history += [{"role": "user", "content": question}, {"role": "assistant", "content": text}]
            return Answer(question, text, [], "guard", "scope")
        facts = retrieve(self.ctx, question)
        known = {f["id"]: f for f in facts}
        msgs = self.history[-2 * self.max_turns:] + [{"role": "user", "content": question}]
        rep = self.client.chat(self.system_prompt(facts) + SC.system_rule(chk, self.ctx, LANG), msgs,
                               on_error=lambda p, e: self.errors.append(T["err"].format(p=p, e=e)))
        if rep is None:
            top = [] if chk.get("weak") else retrieve({"facts": facts}, question, k=4, ranked=True)
            text = (self.local_answer(question, facts) if top else SC.reply({**chk, "status": "nomatch"}, self.ctx))
            prov, model, sec, cached = "local", "facts", 0.0, False
        else:
            text, prov, model, sec, cached = rep.text.strip(), rep.provider, rep.model, rep.seconds, rep.cached
            if SC.is_out_token(text):
                text = SC.reply({**chk, "status": "off_topic"}, self.ctx, names[0] if names else "")
            else:
                w = SC.unsourced_warning(text, chk["lang"])
                text += ("\n\n" + w) if w else ""
        notes = SC.notes_text(chk, self.ctx)
        if notes and prov != "guard" and not text.startswith("🚫"):
            text = notes + "\n\n" + text
        # keep only citations that exist among the facts sent
        text = re.sub(r"\[(F\d{2,3})\]", lambda m: m.group(0) if m.group(1) in known else "", text)
        text = re.sub(r" +([.,])", r"\1", text)
        ids = list(dict.fromkeys(re.findall(r"\[(F\d{2,3})\]", text)))
        self.history += [{"role": "user", "content": question}, {"role": "assistant", "content": text}]
        return Answer(question, text, [known[i] for i in ids], prov, model, sec, cached)

    def reset(self):
        self.history = []


# --------------------------------------------------------------------------------------
# Notebook chat interface (ipywidgets)
# --------------------------------------------------------------------------------------
CSS = """
<style>
.ntl-chat{font-family:'Segoe UI',Calibri,system-ui,sans-serif;border-radius:16px;overflow:hidden;border:1px solid #00704A33;
 box-shadow:0 4px 18px #00553A1f;max-width:980px}
.ntl-chat .hd{background:linear-gradient(135deg,#00553A 0%,#00704A 55%,#00A86A 100%);color:#fff;padding:16px 20px;border-bottom:4px solid #3F7FC7}
.ntl-chat .hd b{font-size:1.15em}.ntl-chat .hd .sub{color:#E6F6EE;font-size:.9em;margin-top:4px}
.ntl-chat .badge{display:inline-block;margin-left:8px;padding:2px 10px;border-radius:999px;background:#F5C242;color:#00553A;font-size:.75em;font-weight:700}
.ntl-chat .log{background:#F7FAF8;padding:14px 16px;max-height:560px;overflow-y:auto}
.ntl-chat .msg{margin:8px 0;display:flex;gap:10px}.ntl-chat .msg.u{justify-content:flex-end}
.ntl-chat .bub{max-width:78%;padding:10px 14px;border-radius:14px;line-height:1.5;font-size:.95em}
.ntl-chat .u .bub{background:#1F4E8C;color:#fff;border-bottom-right-radius:4px}
.ntl-chat .a .bub{background:#fff;border:1px solid #00704A22;color:#231F20;border-bottom-left-radius:4px}
.ntl-chat .av{width:30px;height:30px;border-radius:50%;background:#00704A;color:#F5C242;display:grid;place-items:center;font-weight:800;flex:none}
.ntl-chat .cite{display:inline-block;background:#E8F5EF;color:#00553A;border:1px solid #00A86A55;border-radius:6px;padding:0 5px;font-size:.78em;font-weight:700;cursor:help}
.ntl-chat .meta{color:#6f6d68;font-size:.78em;margin-top:6px}
.ntl-chat details{margin-top:6px;font-size:.82em;color:#52514e}.ntl-chat details li{margin:2px 0}
.ntl-chat .warn{background:#fff4d6;color:#5b4300;padding:6px 10px;border-radius:8px;font-size:.82em;margin:6px 0}
</style>"""


def md_to_html(text: str, facts: dict | None = None) -> str:
    """Tiny, safe markdown renderer (bold, italics, code, lists, paragraphs) + citation chips."""
    facts = facts or {}
    out, in_list = [], False
    for line in html.escape(text).split("\n"):
        s = line.strip()
        m = re.match(r"^([-*•]|\d+[.)])\s+(.*)", s)
        if m:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{m.group(2)}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if s.startswith("#"):
            out.append(f"<b>{s.lstrip('#').strip()}</b><br>")
        elif s:
            out.append(f"<p style='margin:.35em 0'>{s}</p>")
    if in_list:
        out.append("</ul>")
    h = "".join(out)
    h = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", h)
    h = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<i>\1</i>", h)
    h = re.sub(r"`(.+?)`", r"<code>\1</code>", h)

    def chip(m):
        f = facts.get(m.group(1))
        tip = html.escape(f"{f['title']} — {f['text']}", quote=True) if f else ""
        return f"<span class='cite' title=\"{tip}\">{m.group(1)}</span>"
    return re.sub(r"\[(F\d{2,3})\]", chip, h)


def chat_ui(agent: ResultsAgent, suggestions: list[str] | None = None):
    """Attractive chat panel for Colab / Jupyter (ipywidgets). Returns the widget."""
    import ipywidgets as W
    facts = {f["id"]: f for f in agent.ctx["facts"]}
    prov = agent.client.available()
    badge = " · ".join(prov) if prov else "local"
    head = W.HTML(CSS + f"<div class='ntl-chat'><div class='hd'><b>🛰️ {T['ui_title']}</b>"
                        f"<span class='badge'>{html.escape(badge)}</span><div class='sub'>{T['ui_sub']} "
                        f"— {html.escape(str(agent.ctx.get('country')))}, {'–'.join(map(str, agent.ctx.get('period', [])))}"
                        f"</div></div></div>")
    log_ = W.HTML()
    turns: list[str] = []
    if agent.ctx.get("synthetic"):
        turns.append(f"<div class='warn'>⚠️ {T['synthetic'].strip()}</div>")
    if not prov:
        turns.append(f"<div class='warn'>ℹ️ {T['no_provider']}</div>")

    def render(extra=""):
        log_.value = (CSS + "<div class='ntl-chat'><div class='log'>" + "".join(turns) + extra + "</div></div>")

    def send(q):
        q = (q or "").strip()
        if not q:
            return
        turns.append(f"<div class='msg u'><div class='bub'>{html.escape(q)}</div></div>")
        render(f"<div class='msg a'><div class='av'>IA</div><div class='bub'><i>{T['thinking']}</i></div></div>")
        a = agent.ask(q)
        src = "".join(f"<li><b>{c['id']}</b> {html.escape(c['title'])}</li>" for c in a.citations)
        errs = "".join(f"<div class='warn'>{html.escape(e)}</div>" for e in agent.errors[-2:])
        agent.errors.clear()
        turns.append(f"<div class='msg a'><div class='av'>IA</div><div class='bub'>{errs}{md_to_html(a.text, facts)}"
                     f"<div class='meta'>{html.escape(a.provider)} · {html.escape(a.model)}"
                     f"{' · cache' if a.cached else ''}{f' · {a.seconds:.1f} s' if a.seconds else ''}</div>"
                     + (f"<details><summary>{T['sources']} ({len(a.citations)})</summary><ul>{src}</ul></details>" if src else "")
                     + "</div></div>")
        render()

    box = W.Text(placeholder=T["ask"], layout=W.Layout(width="70%"))
    btn = W.Button(description=T["send"], button_style="success", icon="paper-plane", layout=W.Layout(width="14%"))
    clr = W.Button(description=T["clear"], icon="eraser", layout=W.Layout(width="14%"))

    def on_send(_=None):
        q = box.value
        box.value = ""
        send(q)

    def on_clear(_):
        turns.clear()
        agent.reset()
        render()
    btn.on_click(on_send)
    clr.on_click(on_clear)
    box.on_submit(on_send) if hasattr(box, "on_submit") else None
    sug = [W.Button(description=s if len(s) < 60 else s[:57] + "…", tooltip=s,
                    layout=W.Layout(width="auto", margin="2px")) for s in (suggestions or agent.ctx.get("suggestions", []))]
    for b_, s in zip(sug, suggestions or agent.ctx.get("suggestions", [])):
        b_.on_click(lambda _, s=s: send(s))
    render()
    ui = W.VBox([head, W.HBox(sug, layout=W.Layout(flex_flow="row wrap")), log_, W.HBox([box, btn, clr])])
    ui.send = send          # programmatic use: ui.send("question")
    return ui


# --------------------------------------------------------------------------------------
# Ollama inside Colab (optional)
# --------------------------------------------------------------------------------------
def start_ollama_colab(model: str = "qwen2.5:7b", wait: int = 60) -> bool:
    """Install and start an Ollama server inside the Colab VM, then pull ``model``.

    A GPU runtime is strongly recommended. Data never leave the VM. Returns True when ready.
    """
    import shutil
    import subprocess
    import requests
    if not shutil.which("ollama"):
        subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    if not shutil.which("ollama"):
        return False
    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(wait):
        try:
            if requests.get("http://localhost:11434/api/tags", timeout=2).ok:
                break
        except Exception:  # noqa: BLE001
            time.sleep(1)
    subprocess.run(["ollama", "pull", model], check=False)
    try:
        return requests.get("http://localhost:11434/api/tags", timeout=3).ok
    except Exception:  # noqa: BLE001
        return False
