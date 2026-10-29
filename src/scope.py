"""Scope guard of the AI agent: answer only about the published results, never make things up.

The agent may only talk about the results computed for ONE country and ONE period. This module
decides, before any call to a language model, whether a question (French or English) is within
that scope, and builds the standard reply when it is not:

* ``off_topic``      – general knowledge, news, cooking, code, personal advice… → polite refusal
                       with examples of what the agent *can* answer; no model is called.
* ``other_country``  – the question is only about countries that are not covered → refusal.
* ``greeting``       – "bonjour", "what can you do?" → short presentation of the agent.
* ``ok``             – within scope; ``notes`` may flag a country or years that are not covered,
                       which the agent then states explicitly instead of inventing figures.

Two further safeguards run after the model: the model is told to reply with the single token
``OUT_OF_SCOPE`` when the question is outside the results (the token is replaced by the standard
refusal), and an answer that contains figures but cites no source gets a visible warning.

The checks are deterministic word rules (no model), identical in the notebook (this file) and on
the website (``dashboard/assets/agent.js``). They are deliberately conservative: when in doubt the
question goes to the agent, whose instructions forbid answering beyond the results.
"""
from __future__ import annotations

import re
import unicodedata

OUT_TOKEN = "OUT_OF_SCOPE"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s).lower().replace("’", "'"))
    return "".join(c for c in s if not unicodedata.combining(c))


# ---- vocabulary ---------------------------------------------------------------------------
# Word starts (accent-free) that tie a question to the results of the dashboard.
DOMAIN = """
lumiere lumineu eclair light ntl viirs dmsp black marble satellit nocturne nuit night radiance nightlight
pib gdp croissance growth econom activit region regional district province gouvernorat wilaya departement
commune adm1 adm2 unite unit convergence divergence concentration herfindahl inegal inequal gini theil lorenz
electri acces access noir dark choc shock covid pandem confinement lockdown crise crisis recession reprise
recover rupture break anomal industri usine factor manufactur grappe cluster torchere flare touris saison
season estival summer nuitee hotel ramadan urbanis urban ville city cities villag population demograph bati
built ghsl worldpop no2 so2 pollution modis temperature carte map graph chart courbe tendance trend evolution
compar classement rank profil profile fiche note brief synthese summary qualit quality method limite limitation
confiance confidence incertitude uncertaint valid source donnee data indicateur indicator statisti
tableau de bord dashboard resultat result cas d'usage use case recommand politique policy elasticit prevision
nowcast estimat mensuel monthly annuel annual periode period hausse baisse increase decrease declin decline
stagn moyenne average share km correlation spearman fastest slowest plus vite moins vite cagr tcam
informel informal dqaf gsbpm fair export csv geojson telecharg download agent citation fact
expansion etalement sprawl implantation settlement quartier neighbourhood neighborhood
""".split()
DOMAIN_PHRASES = ["lit area", "part de", "share of", "tableau de bord", "cas d'usage", "use case", "black marble", "plus vite", "moins vite"]
# Words that, without any core signal (light, a unit, the country), mark a question as off topic.
OFF = """
recette recipe cuisine cooking cook meteo weather football soccer basket tennis match film movie serie netflix
poeme poem chanson song lyrics blague joke horoscope bitcoin crypto forex python javascript sql programming
coder traduis traduire translate dissertation essay email cv amour love medicament medicine religion dieu god
celebrity celebrite
""".split()
CORE = ["lumi", "light", "ntl", "viirs", "dmsp", "satellit", "nocturne", "night", "eclair", "radiance"]
GREET = re.compile(r"^\s*(bonjour|bonsoir|salut|coucou|hello|hi|hey|good (morning|afternoon|evening)|merci|thanks|"
                   r"thank you)\b[\s!.,?]*$|\b(qui es[- ]tu|que (peux|sais)[- ]tu faire|tu fais quoi|aide[- ]moi|"
                   r"comment (t'utiliser|ca marche|utiliser l'agent)|who are you|what can you do|how do (i|you) use|"
                   r"help me|^help\b|^aide\b)")
FR_HINT = re.compile(r"\b(le|la|les|des|du|une|est|sont|quel|quelle|quels|quelles|pourquoi|comment|combien|ou|"
                     r"dans|avec|pour|qui|que|quoi|est-ce|moi|fais|montre|donne|region|regions)\b")
EN_HINT = re.compile(r"\b(the|what|which|where|how|why|is|are|does|do|show|give|me|of|in|with|for|regions?|"
                     r"growth|fastest|map)\b")

# Countries (ISO3 → names in French and English, accent-free). Used only to detect a question about
# a country the dashboard does not cover. Longer names are matched first ("guinee-bissau" before "guinee").
COUNTRIES = {
    "DZA": "algeria algerie", "AGO": "angola", "BEN": "benin", "BWA": "botswana", "BFA": "burkina faso|burkina",
    "BDI": "burundi", "CPV": "cape verde|cap-vert|cabo verde", "CMR": "cameroon|cameroun",
    "CAF": "central african republic|republique centrafricaine|centrafrique", "TCD": "chad|tchad",
    "COM": "comoros|comores", "COG": "republic of the congo|congo-brazzaville|congo brazzaville",
    "COD": "democratic republic of the congo|republique democratique du congo|rdc|drc|congo-kinshasa",
    "CIV": "cote d'ivoire|ivory coast", "DJI": "djibouti", "EGY": "egypt|egypte",
    "GNQ": "equatorial guinea|guinee equatoriale", "ERI": "eritrea|erythree", "SWZ": "eswatini|swaziland",
    "ETH": "ethiopia|ethiopie", "GAB": "gabon", "GMB": "gambia|gambie", "GHA": "ghana",
    "GNB": "guinea-bissau|guinee-bissau|guinea bissau|guinee bissau", "GIN": "guinea|guinee", "KEN": "kenya",
    "LSO": "lesotho", "LBR": "liberia", "LBY": "libya|libye", "MDG": "madagascar", "MWI": "malawi", "MLI": "mali",
    "MRT": "mauritania|mauritanie", "MUS": "mauritius|ile maurice", "MAR": "morocco|maroc", "MOZ": "mozambique",
    "NAM": "namibia|namibie", "NER": "niger", "NGA": "nigeria", "RWA": "rwanda", "STP": "sao tome",
    "SEN": "senegal", "SYC": "seychelles", "SLE": "sierra leone", "SOM": "somalia|somalie",
    "ZAF": "south africa|afrique du sud", "SSD": "south sudan|soudan du sud", "SDN": "sudan|soudan",
    "TZA": "tanzania|tanzanie", "TGO": "togo", "TUN": "tunisia|tunisie", "UGA": "uganda|ouganda",
    "ZMB": "zambia|zambie", "ZWE": "zimbabwe",
    "FRA": "france", "DEU": "germany|allemagne", "ITA": "italy|italie", "ESP": "spain|espagne", "PRT": "portugal",
    "BEL": "belgium|belgique", "CHE": "switzerland|suisse", "NLD": "netherlands|pays-bas", "GBR":
    "united kingdom|royaume-uni|england|angleterre", "USA": "united states|etats-unis|usa", "CAN": "canada",
    "MEX": "mexico|mexique", "BRA": "brazil|bresil", "ARG": "argentina|argentine", "COL": "colombia|colombie",
    "PER": "peru|perou", "CHL": "chile|chili", "VEN": "venezuela", "HTI": "haiti", "RUS": "russia|russie",
    "UKR": "ukraine", "TUR": "turkey|turquie", "CHN": "china|chine", "IND": "india|inde", "JPN": "japan|japon",
    "KOR": "south korea|coree du sud", "IDN": "indonesia|indonesie", "PAK": "pakistan", "BGD": "bangladesh",
    "VNM": "vietnam|viet nam", "THA": "thailand|thailande", "MYS": "malaysia|malaisie", "PHL": "philippines",
    "AUS": "australia|australie", "SAU": "saudi arabia|arabie saoudite", "ARE": "united arab emirates|emirats",
    "QAT": "qatar", "IRN": "iran", "IRQ": "iraq|irak", "SYR": "syria|syrie", "LBN": "lebanon|liban",
    "JOR": "jordanie", "YEM": "yemen", "ISR": "israel", "PSE": "palestine", "AFG": "afghanistan",
}
_CNAMES = sorted(((n.strip(), iso) for iso, s in COUNTRIES.items() for n in s.split("|")), key=lambda t: -len(t[0]))
_NAME = {"fr": {}, "en": {}}
for _iso, _s in COUNTRIES.items():
    _NAME["en"][_iso] = _s.split("|")[0]


def detect_lang(question: str, default: str = "fr") -> str:
    q = _norm(question)
    fr, en = len(FR_HINT.findall(q)), len(EN_HINT.findall(q))
    if re.search(r"[éèêàùçôîœ]", question.lower()):
        fr += 2
    return "fr" if fr > en else "en" if en > fr else default


def _has_word(q: str, w: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(w), q) is not None


def check(question: str, ctx: dict, unit_names=(), history: bool = False, years=(), default_lang: str = "fr") -> dict:
    """Classify ``question``: status ok / greeting / off_topic / other_country, with notes."""
    q = _norm(question)
    lang = detect_lang(question, default_lang)
    own_iso = str(ctx.get("iso3") or "").upper()
    own_names = {_norm(ctx.get("country") or ""), _norm(ctx.get("country") or "").split(" (")[0]} | \
        {n for n, iso in _CNAMES if iso == own_iso}
    own_names.discard("")
    units = [_norm(u).split(" (")[0] for u in unit_names if u]
    unit_hit = [u for u in units if len(u) > 2 and re.search(r"\b" + re.escape(u) + r"\b", q)]
    own_hit = any(re.search(r"\b" + re.escape(n) + r"\b", q) for n in own_names)
    # other countries (longest names first, matched spans removed; unit names never count as countries)
    rest, others = q, []
    for n, iso in _CNAMES:
        if iso == own_iso or n in units:
            continue
        m = re.search(r"\b" + re.escape(n) + r"\b", rest)
        if m:
            others.append(iso)
            rest = rest[:m.start()] + " " + rest[m.end():]
    others = list(dict.fromkeys(others))
    domain = any(p in q for p in DOMAIN_PHRASES) or any(_has_word(q, w) for w in DOMAIN)
    core = any(_has_word(q, w) for w in CORE) or bool(unit_hit) or own_hit
    off = [w for w in OFF if re.search(r"\b" + re.escape(w) + r"\b", q)]
    yrs = sorted({int(y) for y in re.findall(r"\b((?:19|20)\d\d)\b", q)})
    out_years = [y for y in yrs if years and (y < min(years) or y > max(years))]
    res = {"lang": lang, "others": others, "out_years": out_years, "units": unit_hit, "notes": []}
    if GREET.search(q) and not (core or (domain and len(q.split()) > 6)):
        return {**res, "status": "greeting"}
    if others and not (unit_hit or own_hit):
        return {**res, "status": "other_country"}
    if off and not core:
        return {**res, "status": "off_topic", "reason": off[:3]}
    if not (domain or core):
        if history and len(q.split()) <= 8 and not others:   # short follow-up ("et pour 2020 ?", "why?")
            return {**res, "status": "ok", "followup": True}
        return {**res, "status": "off_topic"}
    res["weak"] = not domain and not unit_hit       # e.g. only the country's name: let the model judge
    if others:
        res["notes"].append("other_country")
    if out_years:
        res["notes"].append("years")
    return {**res, "status": "ok"}


# ---- replies --------------------------------------------------------------------------------
TXT = {
    "fr": {
        "off": ("🚫 **Question hors du périmètre de l'agent.** Je réponds uniquement à partir des résultats calculés "
                "pour **{c}** ({p}) : lumières nocturnes et données associées (population, bâti, PIB, industrie, "
                "tourisme, urbanisation…). Cette question ne porte pas sur ces résultats ; plutôt que de risquer une "
                "réponse inventée, je préfère ne pas y répondre."),
        "other": ("🚫 **Pays non couvert.** Ce tableau de bord ne contient des résultats que pour **{c}** ({p}). "
                  "Je n'ai aucun chiffre sur {o} et je n'en inventerai pas. Pour l'étudier, relancez le notebook avec "
                  "son code ISO3 (paramètre `ISO3`)."),
        "hello": ("👋 Je suis l'agent du tableau de bord **Lumières nocturnes** pour **{c}** ({p}). Je classe et compare "
                  "les régions, établis des fiches, trace des graphiques, pilote la carte et rédige des notes — "
                  "**uniquement à partir des résultats publiés**, chaque chiffre étant cité."),
        "can": "Questions auxquelles je peux répondre, par exemple :",
        "ex": ["Quelles régions croissent le plus vite, et lesquelles déclinent ?", "Fais-moi le profil de {u} et montre-le sur la carte",
               "Où la population croît-elle sans lumière ?", "Quels sont les messages clés et leur niveau de confiance ?"],
        "note_other": "ℹ️ {o} : pays non couvert par ce tableau de bord — aucun chiffre n'est donné à son sujet ; la réponse porte uniquement sur {c}.",
        "note_years": "ℹ️ Année(s) {y} hors de la période couverte ({p}) : aucun résultat n'existe pour ces années.",
        "unsourced": "⚠️ Cette réponse contient des chiffres sans source citée : vérifiez-les sur les pages du tableau de bord avant de les utiliser.",
        "nomatch": ("🚫 **Aucun résultat publié ne répond à cette question.** Je réponds uniquement à partir des chiffres "
                    "calculés pour **{c}** ({p}) et je ne trouve rien qui s'y rapporte ; je préfère le signaler plutôt "
                    "que d'inventer une réponse."),
        "sys": ("\n8. PÉRIMÈTRE : si la question ne porte pas sur ces résultats (culture générale, actualité, autre pays, "
                "conseils personnels, code, rédaction sans rapport…), ne réponds pas sur le fond et réponds uniquement par "
                "le mot " + OUT_TOKEN + ". Si une partie seulement est couverte, réponds à cette partie et dis clairement "
                "ce qui ne l'est pas. N'utilise jamais tes connaissances générales pour fournir un chiffre.\n"),
        "sys_other": "\nLa question mentionne {o}, qui n'est PAS couvert : dis-le explicitement et ne donne aucun chiffre à son sujet.",
        "sys_years": "\nLa question mentionne {y}, hors de la période couverte ({p}) : dis-le explicitement.",
    },
    "en": {
        "off": ("🚫 **Question outside the agent's scope.** I only answer from the results computed for **{c}** ({p}): "
                "night-time lights and associated data (population, built-up area, GDP, industry, tourism, "
                "urbanisation…). This question is not about these results; rather than risk a made-up answer, I will "
                "not answer it."),
        "other": ("🚫 **Country not covered.** This dashboard only contains results for **{c}** ({p}). I have no "
                  "figures on {o} and will not invent any. To study it, run the notebook again with its ISO3 code "
                  "(parameter `ISO3`)."),
        "hello": ("👋 I am the agent of the **Night-time lights** dashboard for **{c}** ({p}). I rank and compare "
                  "regions, write profiles, draw charts, control the map and draft briefs — **only from the published "
                  "results**, with every figure cited."),
        "can": "Questions I can answer, for example:",
        "ex": ["Which regions are growing fastest, and which are declining?", "Profile {u} and show it on the map",
               "Where is population growing without light?", "What are the key messages and their confidence levels?"],
        "note_other": "ℹ️ {o}: country not covered by this dashboard — no figure is given about it; the answer covers {c} only.",
        "note_years": "ℹ️ Year(s) {y} outside the period covered ({p}): no results exist for these years.",
        "unsourced": "⚠️ This answer contains figures without a cited source: check them on the dashboard pages before using them.",
        "nomatch": ("🚫 **No published result answers this question.** I only answer from the figures computed for "
                    "**{c}** ({p}) and find nothing related; I would rather say so than invent an answer."),
        "sys": ("\n8. SCOPE: if the question is not about these results (general knowledge, news, another country, personal "
                "advice, code, unrelated writing…), do not answer it and reply only with the word " + OUT_TOKEN + ". If "
                "only part of it is covered, answer that part and say clearly what is not covered. Never use your general "
                "knowledge to provide a figure.\n"),
        "sys_other": "\nThe question mentions {o}, which is NOT covered: say so explicitly and give no figure about it.",
        "sys_years": "\nThe question mentions {y}, outside the period covered ({p}): say so explicitly.",
    },
}


def _names(isos, lang):
    out = []
    for iso in isos:
        n = _NAME["en"].get(iso, iso)
        if lang == "fr":
            alt = COUNTRIES.get(iso, n).split("|")
            n = alt[1] if len(alt) > 1 and not alt[1].isupper() else alt[0]
        out.append(n.title().replace("'S", "'s").replace("D'", "d'").replace(" Du ", " du ").replace(" De ", " de "))
    return ", ".join(out)


def _period(ctx):
    return "–".join(map(str, ctx.get("period") or []))


def reply(chk: dict, ctx: dict, unit_example: str = "") -> str:
    """Standard reply for greeting / off_topic / other_country / nomatch (in the question's language)."""
    lang = chk.get("lang", "fr")
    t = TXT[lang]
    c, p = ctx.get("country", ""), _period(ctx)
    st = chk["status"]
    head = {"greeting": t["hello"], "off_topic": t["off"], "other_country": t["other"], "nomatch": t["nomatch"]}[st]
    head = head.format(c=c, p=p, o=_names(chk.get("others", []), lang))
    ex = [e.format(u=unit_example or c) for e in t["ex"]]
    txt = head + "\n\n" + t["can"] + "\n" + "\n".join(f"- {e}" for e in ex)
    if ctx.get("synthetic"):
        txt += "\n\n" + ("⚠️ Données synthétiques de test." if lang == "fr" else "⚠️ Synthetic test data.")
    return txt


def notes_text(chk: dict, ctx: dict) -> str:
    """Visible notes prepended to an in-scope answer (country / years not covered)."""
    lang, t = chk.get("lang", "fr"), TXT[chk.get("lang", "fr")]
    out = []
    if "other_country" in chk.get("notes", []):
        out.append(t["note_other"].format(o=_names(chk["others"], lang), c=ctx.get("country", "")))
    if "years" in chk.get("notes", []):
        out.append(t["note_years"].format(y=", ".join(map(str, chk["out_years"])), p=_period(ctx)))
    return "\n".join(out)


def system_rule(chk: dict | None, ctx: dict, lang: str = "fr") -> str:
    """Extra system-prompt lines: the scope rule, plus the specific notes of this question."""
    t = TXT[lang]
    s = t["sys"]
    if chk:
        if "other_country" in chk.get("notes", []):
            s += t["sys_other"].format(o=_names(chk["others"], lang))
        if "years" in chk.get("notes", []):
            s += t["sys_years"].format(y=", ".join(map(str, chk["out_years"])), p=_period(ctx))
    return s


def is_out_token(text: str) -> bool:
    return OUT_TOKEN in (text or "") or "HORS_PERIMETRE" in (text or "")


def unsourced_warning(text: str, lang: str) -> str | None:
    """Warning when an answer states figures but cites no [F..]/[D..] source."""
    if re.search(r"\[[FD]\d{1,3}\]", text or ""):
        return None
    body = re.sub(r"\b(19|20)\d\d\b", " ", text or "")
    if re.search(r"\d", body):
        return TXT[lang]["unsourced"]
    return None
