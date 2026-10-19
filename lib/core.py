"""Request handling shared by the Vercel functions (api/*.py) and dev_server.py.

handle(method, path, query, headers, body) -> (status, headers, body bytes).
Live titles come from TMDB when TMDB_API_KEY is set, else the bundled
catalog. Watch parties need SUPABASE_URL + SUPABASE_SECRET_KEY; without them
they run in memory, which is fine locally but not on serverless.
"""
import json
import os
import random
import re
from pathlib import Path
from urllib.parse import urlsplit

from . import rooms as roomlib
from . import tmdb

ROOT = Path(__file__).resolve().parent.parent
CATALOG = json.loads((ROOT / "public" / "catalog.json").read_text())
SERVICES = {s["id"]: s["kind"] for s in CATALOG["services"]}
BY_ID = {t["id"]: t for t in CATALOG["titles"]}
ACCESS = ("sub", "free", "rent", "buy")
SCARES = ("any", "cozy", "spooky", "terrifying")


def env(*names):
    for n in names:
        v = (os.environ.get(n) or "").strip()
        if v:
            return v
    return ""


def supabase_config():
    return env("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL"), env("SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY")


# --- filters ---------------------------------------------------------------------

def _list(q, name, allowed):
    raw = q.get(name, "")
    raw = raw[-1] if isinstance(raw, list) else raw
    return [x for x in dict.fromkeys(str(raw).split(",")) if x in allowed]


def _one(q, name):
    v = q.get(name, "")
    return v[-1] if isinstance(v, list) else str(v)


def parse_filters(q) -> dict:
    kind = _one(q, "kind")
    scare = _one(q, "scare")
    try:
        mx = int(_one(q, "max") or 0)
    except ValueError:
        mx = 0
    try:
        seed = int(_one(q, "seed") or 0) % 1_000_000
    except ValueError:
        seed = 0
    return {
        "kind": kind if kind in ("movie", "tv") else "both",
        "access": _list(q, "access", ACCESS),
        "subs": _list(q, "subs", {k for k, v in SERVICES.items() if v == "sub"}),
        "free": _list(q, "free", {k for k, v in SERVICES.items() if v == "free"}),
        "stores": _list(q, "stores", {k for k, v in SERVICES.items() if v == "store"}),
        "genres": _list(q, "genres", set(CATALOG["genres"])),
        "tags": _list(q, "tags", set(CATALOG["tags"])),
        "scare": scare if scare in SCARES else "any",
        "maxMinutes": mx if mx in (100, 120) else 0,
        "seed": seed,
    }


def my_subs(f):
    out = set(f["subs"])
    for s in f["subs"]:
        out.update(CATALOG["includes"].get(s, []))
    return out


def usable(t, f) -> bool:
    """Same rule as offers() in app.js: is there a way I can watch this?"""
    a = f["access"]
    if "sub" in a and my_subs(f) & set(t["subs"]):
        return True
    if "free" in a and set(f["free"]) & set(t["free"]):
        return True
    if "rent" in a and set(f["stores"]) & set(t["rent"]):
        return True
    return "buy" in a and bool(set(f["stores"]) & set(t["buy"]))


def scare_ok(t, scare):
    s = t.get("scare") or 0
    return {"cozy": 1 <= s <= 2, "spooky": s == 3, "terrifying": s >= 4}.get(scare, True)


def catalog_match(t, f) -> bool:
    if f["kind"] != "both" and t["kind"] != f["kind"]:
        return False
    if f["genres"] and not set(f["genres"]) & set(t["genres"]):
        return False
    if f["tags"] and not set(f["tags"]) & set(t["tags"]):
        return False
    if not scare_ok(t, f["scare"]):
        return False
    if f["maxMinutes"] and t["kind"] == "movie" and t["minutes"] > f["maxMinutes"]:
        return False
    return usable(t, f)


def catalog_spin(f, want=24):
    pool = [t for t in CATALOG["titles"] if catalog_match(t, f)]
    random.Random(f["seed"]).shuffle(pool)
    return len(pool), pool[:want]


def spin(f) -> dict:
    if not f["access"]:
        return {"source": "none", "total": 0, "titles": []}
    if tmdb.enabled():
        try:
            total, titles = tmdb.spin(f, SERVICES, lambda t: usable(t, f))
            return {"source": "tmdb", "total": total, "titles": titles}
        except tmdb.TMDBError:
            pass        # fall through to the bundled catalog rather than an empty screen
    total, titles = catalog_spin(f)
    return {"source": "catalog", "total": total, "titles": titles}


def resolve(ids):
    out = []
    for i in ids:
        if i in BY_ID:
            out.append(BY_ID[i])
        elif re.fullmatch(r"(movie|tv):\d{1,9}", i) and tmdb.enabled():
            try:
                out.append(tmdb.details(i, SERVICES))
            except tmdb.TMDBError:
                raise roomlib.BadRequest("Couldn't look that title up. Try again.")
        else:
            raise roomlib.BadRequest("Unknown title.")
    return out


# --- rooms -------------------------------------------------------------------------

_rooms = None


def rooms():
    global _rooms
    if _rooms is None:
        url, key = supabase_config()
        store = roomlib.SupabaseStore(url, key) if url and key else roomlib.MemoryStore()
        _rooms = roomlib.Rooms(store, resolve)
    return _rooms


def parties_ready():
    url, key = supabase_config()
    return bool(url and key) or not os.environ.get("VERCEL")


def config() -> dict:
    return {
        "source": "tmdb" if tmdb.enabled() else "catalog",
        "parties": parties_ready(),
        "snapshot": CATALOG["snapshot"],
        "services": CATALOG["services"], "includes": CATALOG["includes"],
        "genres": CATALOG["genres"],
        "tags": tmdb.SUPPORTED_TAGS if tmdb.enabled() else CATALOG["tags"],
        "scareByRating": tmdb.enabled(),
    }


# --- http --------------------------------------------------------------------------

SECURITY = {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "strict-origin-when-cross-origin"}


def reply(status, obj, cache="no-store"):
    h = dict(SECURITY, **{"Content-Type": "application/json", "Cache-Control": cache})
    return status, h, json.dumps(obj).encode()


def same_origin(headers) -> bool:
    origin = headers.get("Origin") or headers.get("origin")
    host = headers.get("Host") or headers.get("host") or ""
    if origin:
        return urlsplit(origin).netloc.lower() == host.lower()
    # Scripts send no Origin; the app always sends this header, a bare cross-site form can't.
    return bool(headers.get("X-Next-Reel") or headers.get("x-next-reel"))


def handle(method, path, query, headers, body=b""):
    path = path.rstrip("/") or "/"
    try:
        if path == "/api/config" and method == "GET":
            return reply(200, config(), "public, max-age=60")
        if path == "/api/spin" and method == "GET":
            # Cacheable at the edge: the URL is the whole question, and seeds are 0-9.
            return reply(200, spin(parse_filters(query)), "public, s-maxage=1800, max-age=300")
        if path == "/api/rooms" and method == "GET":
            return reply(200, rooms().state(_one(query, "code")))
        if path == "/api/rooms" and method == "POST":
            if not same_origin(headers):
                return reply(403, {"error": "Cross-site write refused."})
            if len(body) > 20_000:
                raise roomlib.BadRequest("Too big.")
            try:
                b = json.loads(body or b"{}")
            except ValueError:
                raise roomlib.BadRequest("That wasn't valid JSON.")
            if not isinstance(b, dict):
                raise roomlib.BadRequest("Expected an object.")
            r, act, code = rooms(), b.get("action"), b.get("code")
            if act == "create":
                return reply(201, r.create(b.get("name")))
            if act == "join":
                return reply(200, r.join(code, b.get("name"), b.get("player")))
            if act == "spin":
                return reply(200, r.spin(code, b.get("host_token"), b.get("candidates")))
            if act == "vote":
                return reply(200, r.vote(code, b.get("player"), b.get("pick")))
            if act == "reveal":
                return reply(200, r.reveal(code, b.get("host_token")))
            if act == "leave":
                return reply(200, r.leave(code, b.get("player")))
            if act == "end":
                return reply(200, r.end(code, b.get("host_token")))
            raise roomlib.BadRequest("Unknown action.")
        return reply(404, {"error": "Not found."})
    except roomlib.BadRequest as e:
        return reply(400, {"error": str(e)})
    except PermissionError as e:
        return reply(403, {"error": str(e)})
    except LookupError as e:
        return reply(404, {"error": str(e)})
    except roomlib.StoreError:
        return reply(503, {"error": "Watch parties are having trouble right now. Try again in a minute."})
