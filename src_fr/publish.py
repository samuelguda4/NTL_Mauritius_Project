"""Publish the dashboard on GitHub Pages with a personal access token — in one call.

    from src.publish import publish_dashboard
    url = publish_dashboard("TUN", "ntl-dashboard", "my-github-user")

What it does (idempotent — re-running updates the site, never duplicates the repository):
  1. reads the token from GITHUB_TOKEN, Colab secrets, a local .env file, or getpass();
  2. checks the token and its rights (GET /user);
  3. creates the public repository if it does not exist (POST /user/repos);
  4. pushes the site to the `gh-pages` branch in ONE commit through the Git Data API
     (blobs → tree → commit → ref); unchanged files are not re-uploaded;
  5. enables GitHub Pages on that branch (POST /repos/{owner}/{repo}/pages) if needed;
  6. waits for the Pages build (GET /repos/{owner}/{repo}/pages/builds/latest);
  7. returns and prints the public URL https://{user}.github.io/{repo}/.

Security: the token is never written to disk, printed, put in a URL, in git config or in
the git history (no `git push` with an embedded token). Every error message is redacted.
"""
from __future__ import annotations

import base64
import datetime as _dt
import getpass
import hashlib
import json
import os
import re
import time
import unicodedata
from pathlib import Path

import requests

API = "https://api.github.com"
TOKEN_PATTERN = re.compile(r"(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")


class PublishError(RuntimeError):
    """Publication error (message already redacted)."""


# --------------------------------------------------------------------------------------
# Token handling
# --------------------------------------------------------------------------------------
def redact(text: str, token: str | None = None) -> str:
    """Remove the token (and anything that looks like a GitHub token) from a string."""
    text = str(text)
    if token:
        text = text.replace(token, "***")
    return TOKEN_PATTERN.sub("***", text)


def _ask_hidden(prompt: str) -> str:
    """Masked input that tolerates Colab front-ends returning a dict (e.g. {"value": "..."}) instead of a str."""
    v = getpass.getpass(prompt)
    if isinstance(v, dict):
        v = v.get("value") or v.get("text") or next((x for x in v.values() if isinstance(x, str)), "")
    return str(v or "").strip()


def get_token(interactive: bool = True, env_var: str = "GITHUB_TOKEN") -> str:
    """Return the GitHub token without ever displaying it.

    Order: environment variable → Colab secret (google.colab.userdata) → `.env` file in the
    current or parent directory (python-dotenv) → hidden prompt (getpass).
    """
    tok = os.environ.get(env_var, "").strip()
    if not tok:
        try:
            from google.colab import userdata  # type: ignore
            tok = (userdata.get(env_var) or "").strip()
        except Exception:  # noqa: BLE001 - not on Colab, or secret not granted
            tok = ""
    if not tok:
        try:
            from dotenv import dotenv_values
            for p in (Path.cwd() / ".env", Path.cwd().parent / ".env"):
                if p.exists():
                    tok = (dotenv_values(p).get(env_var) or "").strip()
                    if tok:
                        break
        except ImportError:
            pass
    if not tok and interactive:
        tok = _ask_hidden("Token GitHub (saisie masquée) : ")
    if not tok:
        raise PublishError(f"Aucun token GitHub : définir la variable {env_var}, un secret Colab ou un fichier .env.")
    return tok


# --------------------------------------------------------------------------------------
# Minimal GitHub REST client
# --------------------------------------------------------------------------------------
class GitHub:
    """Thin wrapper around the REST API that redacts the token in every error."""

    def __init__(self, token: str, session: requests.Session | None = None):
        self._token = token
        self.s = session or requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                               "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "ntl-dashboard-publisher"})

    def __repr__(self) -> str:  # never show the token, even in a debugger
        return "GitHub(token=***)"

    def req(self, method: str, path: str, ok=(200, 201, 204), **kw):
        try:
            r = self.s.request(method, API + path, timeout=60, **kw)
        except requests.RequestException as e:
            raise PublishError(redact(f"Réseau : {method} {path} a échoué — {e}", self._token)) from None
        if r.status_code not in ok:
            raise PublishError(self._explain(r, method, path))
        return r

    def _explain(self, r, method: str, path: str) -> str:
        try:
            msg = r.json().get("message", "")
        except ValueError:
            msg = r.text[:200]
        hint = ""
        if r.status_code == 401:
            hint = "Token invalide, expiré ou révoqué : en créer un nouveau."
        elif r.status_code == 403 and "rate limit" in msg.lower():
            hint = "Limite de requêtes atteinte : réessayer plus tard."
        elif r.status_code == 403 or "not accessible" in msg.lower():
            need = ("Administration (création du dépôt)" if path.startswith(("/user/repos", "/orgs/")) else
                    "Pages" if "/pages" in path else
                    "Workflows" if "workflow" in msg.lower() else "Contents")
            hint = f"Permission insuffisante : le token doit avoir « {need} : Read and write » sur ce dépôt."
        elif r.status_code == 404:
            hint = ("Ressource introuvable, ou invisible pour ce token (un token fine-grained ne voit que les "
                    "dépôts qui lui ont été attribués).")
        elif r.status_code == 422 and "name already exists" in msg.lower():
            hint = "Le dépôt existe déjà sous ce nom."
        return redact(f"GitHub {r.status_code} sur {method} {path} : {msg}. {hint}".strip(), self._token)


# --------------------------------------------------------------------------------------
# Steps
# --------------------------------------------------------------------------------------
def verify_token(gh: GitHub) -> dict:
    """GET /user — returns the user; checks classic-token scopes when they are reported."""
    r = gh.req("GET", "/user")
    user = r.json()
    scopes = r.headers.get("X-OAuth-Scopes")
    if scopes is not None:  # classic token: scopes are listed; fine-grained tokens report none
        sc = {s.strip() for s in scopes.split(",") if s.strip()}
        if not ({"repo", "public_repo"} & sc):
            raise PublishError(f"Le token classique n'a pas le scope « public_repo » ou « repo » (scopes : {sorted(sc)}).")
        user["_token_kind"] = "classic"
    else:
        user["_token_kind"] = "fine-grained"
    exp = r.headers.get("github-authentication-token-expiration")
    user["_token_expires"] = exp
    return user


def ensure_repo(gh: GitHub, owner: str, repo: str, description: str = "") -> tuple[dict, bool]:
    """Return (repository, created?). Creates a PUBLIC repo initialised with a README if absent."""
    r = gh.req("GET", f"/repos/{owner}/{repo}", ok=(200, 404))
    if r.status_code == 200:
        info = r.json()
        if info.get("private"):
            raise PublishError(f"Le dépôt {owner}/{repo} est privé : GitHub Pages gratuit exige un dépôt public.")
        return info, False
    me = gh.req("GET", "/user").json()["login"]
    path = "/user/repos" if me.lower() == owner.lower() else f"/orgs/{owner}/repos"
    body = {"name": repo, "description": description[:350], "private": False, "auto_init": True,
            "has_issues": True, "has_wiki": False}
    info = gh.req("POST", path, json=body).json()
    for _ in range(10):  # the initial commit can take a moment to be visible
        if gh.req("GET", f"/repos/{owner}/{repo}/git/refs/heads/{info['default_branch']}", ok=(200, 404, 409)).status_code == 200:
            break
        time.sleep(1.5)
    return info, True


def git_blob_sha(content: bytes) -> str:
    """SHA-1 of a git blob (lets us skip files that are already identical on GitHub)."""
    return hashlib.sha1(b"blob %d\0" % len(content) + content).hexdigest()


def collect_site(site_dir: str | Path) -> dict[str, bytes]:
    """{path in repo: bytes} of the static site; adds .nojekyll; refuses files with a token."""
    site_dir = Path(site_dir)
    if not (site_dir / "index.html").exists():
        raise PublishError(f"{site_dir}/index.html introuvable : exécuter d'abord la section 11 (export).")
    files: dict[str, bytes] = {}
    for p in sorted(site_dir.rglob("*")):
        if p.is_file() and not any(part.startswith(".") and part != ".nojekyll" for part in p.relative_to(site_dir).parts):
            files[p.relative_to(site_dir).as_posix()] = p.read_bytes()
    files[".nojekyll"] = b""
    _scan_for_secrets(files)
    return files


def _scan_for_secrets(files: dict[str, bytes]) -> None:
    for path, b in files.items():
        if path.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2", ".pdf")):
            continue
        if TOKEN_PATTERN.search(b.decode("utf-8", "ignore")):
            raise PublishError(f"Un motif de token GitHub a été trouvé dans {path} : publication annulée.")


def push_files(gh: GitHub, owner: str, repo: str, branch: str, files: dict[str, bytes], message: str,
               delete_prefixes: tuple[str, ...] = ()) -> str | None:
    """Commit `files` on `branch` in a single commit. Returns the commit SHA, or None if nothing changed.

    Files already present with the same content are not re-uploaded. Existing files under
    `delete_prefixes` that are not in `files` are deleted (e.g. stale data of this country);
    every other existing file is kept (other countries published on the same site).
    """
    base = f"/repos/{owner}/{repo}"
    ref = gh.req("GET", f"{base}/git/refs/heads/{branch}", ok=(200, 404, 409))
    parent_sha, existing = None, {}
    if ref.status_code == 200:
        parent_sha = ref.json()["object"]["sha"]
        parent_tree = gh.req("GET", f"{base}/git/commits/{parent_sha}").json()["tree"]["sha"]
        tree = gh.req("GET", f"{base}/git/trees/{parent_tree}", params={"recursive": "1"}).json()
        existing = {e["path"]: e["sha"] for e in tree.get("tree", []) if e["type"] == "blob"}
    entries = []
    for path, content in files.items():
        sha = git_blob_sha(content)
        if existing.get(path) != sha:
            sha = gh.req("POST", f"{base}/git/blobs", json={
                "content": base64.b64encode(content).decode("ascii"), "encoding": "base64"}).json()["sha"]
        entries.append({"path": path, "mode": "100644", "type": "blob", "sha": sha})
    for path in existing:
        if path not in files and any(path.startswith(p) for p in delete_prefixes):
            entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
    body = {"tree": entries}
    if parent_sha:
        body["base_tree"] = parent_tree
    new_tree = gh.req("POST", f"{base}/git/trees", json=body).json()["sha"]
    if parent_sha and new_tree == parent_tree:
        return None
    commit = gh.req("POST", f"{base}/git/commits", json={
        "message": message, "tree": new_tree, "parents": [parent_sha] if parent_sha else []}).json()["sha"]
    if parent_sha:
        gh.req("PATCH", f"{base}/git/refs/heads/{branch}", json={"sha": commit, "force": False})
    else:
        gh.req("POST", f"{base}/git/refs", json={"ref": f"refs/heads/{branch}", "sha": commit})
    return commit


def enable_pages(gh: GitHub, owner: str, repo: str, branch: str = "gh-pages", path: str = "/") -> dict:
    """Enable GitHub Pages on `branch`/`path`, or switch its source if it points elsewhere."""
    base = f"/repos/{owner}/{repo}/pages"
    r = gh.req("GET", base, ok=(200, 404))
    src = {"branch": branch, "path": path}
    if r.status_code == 404:
        gh.req("POST", base, json={"source": src}, ok=(201, 409))
    else:
        cur = r.json().get("source") or {}
        if cur.get("branch") != branch or cur.get("path") != path or r.json().get("build_type") == "workflow":
            gh.req("PUT", base, json={"source": src, "build_type": "legacy"}, ok=(204,))
    return gh.req("GET", base).json()


def wait_for_build(gh: GitHub, owner: str, repo: str, commit: str | None, timeout: int = 600,
                   progress=print) -> str:
    """Poll the latest Pages build until it is 'built' (for `commit` when given) or 'errored'."""
    base = f"/repos/{owner}/{repo}/pages/builds/latest"
    t0, last = time.time(), None
    while time.time() - t0 < timeout:
        r = gh.req("GET", base, ok=(200, 404))
        if r.status_code == 200:
            b = r.json()
            status = b.get("status")
            if status != last:
                progress(f"  build Pages : {status}")
                last = status
            if status == "errored":
                raise PublishError(f"Échec du build GitHub Pages : {b.get('error', {}).get('message')}")
            if status == "built" and (commit is None or b.get("commit") == commit):
                return status
        time.sleep(5)
    progress("  ⏳ build toujours en cours : le site sera en ligne d'ici quelques minutes.")
    return "pending"


# --------------------------------------------------------------------------------------
# Optional: push the project source (with the redeploy workflow) to the default branch
# --------------------------------------------------------------------------------------
SOURCE_EXCLUDE_DIRS = (".git", "outputs", "__pycache__", ".ipynb_checkpoints", ".pytest_cache", "node_modules")
SOURCE_EXCLUDE_FILES = (".env",)


def collect_source(project_dir: str | Path) -> dict[str, bytes]:
    """Project files to version on the default branch (notebook outputs are cleared).

    Never included: `.env`, outputs/caches, and the generated dashboard data (published on
    gh-pages instead).
    """
    root = Path(project_dir)
    files = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        parts = rel.split("/")
        if (not p.is_file() or p.name in SOURCE_EXCLUDE_FILES
                or any(part in SOURCE_EXCLUDE_DIRS for part in parts[:-1])
                or rel.startswith("dashboard/data/")):
            continue
        b = p.read_bytes()
        if p.suffix == ".ipynb":
            nb = json.loads(b)
            for c in nb.get("cells", []):
                if c.get("cell_type") == "code":
                    c["outputs"], c["execution_count"] = [], None
            b = (json.dumps(nb, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
        files[rel] = b
    _scan_for_secrets(files)
    return files


# --------------------------------------------------------------------------------------
# Optional: showcase repository (README, docs, assets) on the default branch + metadata
# --------------------------------------------------------------------------------------
MAX_FILE_BYTES = 95 * 1024 * 1024     # GitHub rejects blobs above 100 MB
TOPICS = ("night-time-lights", "viirs", "remote-sensing", "economic-statistics", "google-earth-engine",
          "nowcasting", "africa", "dashboard", "ai-agent", "official-statistics", "big-data")


def collect_repo(repo_dir: str | Path, progress=print) -> dict[str, bytes]:
    """{path: bytes} of the showcase tree written by repo.build_repo (binary assets included)."""
    root = Path(repo_dir)
    if not (root / "README.md").exists():
        raise PublishError("{d}/README.md introuvable : exécuter d'abord repo.build_repo().".format(d=root))
    files: dict[str, bytes] = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        parts = rel.split("/")
        if (not p.is_file() or p.name in SOURCE_EXCLUDE_FILES
                or any(part in SOURCE_EXCLUDE_DIRS for part in parts[:-1])):
            continue
        if p.stat().st_size > MAX_FILE_BYTES:
            progress("fichier ignoré (> 95 Mo, limite GitHub) : {p}".format(p=rel))
            continue
        files[rel] = p.read_bytes()
    _scan_for_secrets(files)
    return files


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:50]


def repo_topics(country: str | None, iso3: str) -> list[str]:
    out = list(TOPICS) + [t for t in (_slug(country or ""), iso3.lower()) if t]
    return [t for t in dict.fromkeys(out) if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,49}", t)][:20]


def update_repo_metadata(gh: GitHub, owner: str, repo: str, description: str, homepage: str,
                         topics: list[str], progress=print) -> bool:
    """PATCH description/homepage and PUT topics; a 403 (no Administration permission) is only a warning."""
    try:
        r1 = gh.req("PATCH", f"/repos/{owner}/{repo}", ok=(200, 403, 404, 422),
                    json={"description": description[:350], "homepage": homepage})
        r2 = gh.req("PUT", f"/repos/{owner}/{repo}/topics", ok=(200, 403, 404, 422), json={"names": topics})
    except PublishError as e:
        progress("⚠️ métadonnées du dépôt non modifiées ({e}) — le site est bien publié.".format(e=e))
        return False
    if 403 in (r1.status_code, r2.status_code) or 404 in (r1.status_code, r2.status_code):
        progress("⚠️ description/sujets non modifiés : le token n'a pas la permission « Administration : Read and write » (le site est bien publié).")
        return False
    if 422 in (r1.status_code, r2.status_code):
        progress("⚠️ métadonnées du dépôt non modifiées ({e}) — le site est bien publié.".format(e="422"))
        return False
    progress("✔ description, site web et sujets (topics) du dépôt mis à jour")
    return True


def _country_from_site(site_dir: str | Path, iso3: str) -> str | None:
    try:
        meta = json.loads((Path(site_dir) / "data" / iso3.upper() / "meta.json").read_text(encoding="utf-8"))
        return meta.get("name_en") or meta.get("name")
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------------------
# One-call entry point
# --------------------------------------------------------------------------------------
def publish_dashboard(iso3: str, repo_name: str, github_user: str | None = None, site_dir: str | Path = "dashboard",
                      branch: str = "gh-pages", period: tuple[int, int] | None = None,
                      project_dir: str | Path | None = None, wait: bool = True, timeout: int = 600,
                      token: str | None = None, interactive: bool = True, progress=print,
                      repo_dir: str | Path | None = None, country: str | None = None) -> str:
    """Create/update the repository, push the site, enable Pages, wait, return the public URL.

    Parameters
    ----------
    iso3        : country code (used in the commit message and to replace only this country's data)
    repo_name   : repository name, e.g. "ntl-dashboard"
    github_user : owner (user or organisation); defaults to the token's user
    site_dir    : local folder of the static site (index.html + assets + data)
    project_dir : if given, also pushes the project source (with .github/workflows/deploy.yml)
                  to the default branch — requires the "Workflows" permission
    repo_dir    : si fourni, pousse tout l'arbre du dépôt vitrine (repo.build_repo) sur la branche par défaut
                  (main) en un commit, puis met à jour description, site web et sujets du dépôt
    country     : nom du pays pour la description (défaut : meta.json du site)
    token       : for tests only; otherwise read by get_token()
    """
    tok = token or get_token(interactive=interactive)
    try:
        gh = GitHub(tok)
        user = verify_token(gh)
        owner = github_user or user["login"]
        progress(f"✔ token valide ({user['_token_kind']}) pour {user['login']}"
                 + (f" — expire le {user['_token_expires']}" if user.get("_token_expires") else ""))
        info, created = ensure_repo(gh, owner, repo_name,
                                    f"Night-time lights economic dashboard — {iso3}")
        progress(f"✔ dépôt {'créé' if created else 'existant'} : {info['html_url']}")
        now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        per = f"{period[0]}–{period[1]}" if period else ""
        msg = f"Update NTL dashboard — {iso3.upper()} {per} — run {now}".replace("  ", " ")
        if project_dir:
            c = push_files(gh, owner, repo_name, info["default_branch"], collect_source(project_dir),
                           f"Update project source — {iso3.upper()} — {now}")
            progress(f"✔ sources poussées sur {info['default_branch']}" if c else "✔ sources déjà à jour")
        files = collect_site(site_dir)
        commit = push_files(gh, owner, repo_name, branch, files, msg,
                            delete_prefixes=(f"data/{iso3.upper()}/",))
        progress(f"✔ {len(files)} fichiers publiés sur {branch} (commit {commit[:7]})" if commit
                 else "✔ site déjà à jour : aucun changement à publier")
        pages = enable_pages(gh, owner, repo_name, branch, "/")
        url = pages.get("html_url") or f"https://{owner.lower()}.github.io/{repo_name}/"
        if repo_dir:
            main = info.get("default_branch") or "main"
            try:
                rfiles = collect_repo(repo_dir, progress)
                c = push_files(gh, owner, repo_name, main, rfiles,
                               f"Showcase repository — README, docs and media — {iso3.upper()} {per} — {now}".replace("  ", " "),
                               delete_prefixes=("assets/", "docs/"))
                progress("✔ dépôt vitrine poussé sur {b} ({n} fichiers, commit {c})".format(b=main, n=len(rfiles), c=c[:7]) if c
                         else "✔ branche {b} déjà à jour".format(b=main))
            except PublishError as e:
                progress("⚠️ branche {b} non mise à jour : {e}".format(b=main, e=e))
            name = country or _country_from_site(site_dir, iso3) or iso3.upper()
            desc = (f"Night-time lights — {name}: 8 use cases for statistics & public policy, public dashboard and AI agent "
                    f"(AfDB × DI4A)")
            update_repo_metadata(gh, owner, repo_name, desc, url, repo_topics(name, iso3), progress)
            repo_web = info.get("html_url") or f"https://github.com/{owner}/{repo_name}"
            progress("ℹ️ Image de partage : téléverser assets/cover.jpg dans Settings → General → Social preview ({u}/settings) — l'API GitHub ne le permet pas.".format(u=repo_web))
        if wait:
            wait_for_build(gh, owner, repo_name, commit, timeout, progress)
        progress(f"🌍 Tableau de bord public : {url}")
        return url
    except PublishError:
        raise
    except Exception as e:  # noqa: BLE001 - never leak the token through an unexpected error
        raise PublishError(redact(f"{type(e).__name__}: {e}", tok)) from None
    finally:
        tok = None  # noqa: F841 - drop the reference as early as possible
