"""Live titles and where-to-watch from TMDB (watch-provider data by JustWatch).

Everything is turned into the same title shape the bundled catalog uses, so
the browser doesn't care which source answered. Provider ids are looked up by
name at runtime rather than hard-coded, because TMDB renumbers and renames
them (HBO Max -> Max -> HBO Max). A service is matched within a bucket: "Apple TV"
under flatrate is the subscription, the same name under rent is the store.
"""
import json
import os
import random
import re
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p/w342"
REGION = "US"


class TMDBError(Exception):
    pass


def key():
    return (os.environ.get("TMDB_API_KEY") or os.environ.get("TMDB_READ_TOKEN") or "").strip()


def enabled():
    return bool(key())


# Our service id -> provider names TMDB has used for it.
ALIASES = {
    "netflix": ["Netflix", "Netflix Standard with Ads", "Netflix basic with Ads"],
    "hulu": ["Hulu"], "max": ["HBO Max", "Max", "Max Amazon Channel", "HBO Max Amazon Channel"],
    "disney": ["Disney Plus", "Disney+"], "prime": ["Amazon Prime Video", "Amazon Prime Video with Ads"],
    "appletv": ["Apple TV Plus", "Apple TV+", "Apple TV"],
    "peacock": ["Peacock Premium", "Peacock Premium Plus", "Peacock"],
    "paramount": ["Paramount Plus", "Paramount+", "Paramount Plus Essential", "Paramount Plus Premium",
                  "Paramount+ with Showtime", "Paramount Plus Apple TV Channel"],
    "shudder": ["Shudder", "Shudder Amazon Channel", "Shudder Apple TV Channel"],
    "amcplus": ["AMC+", "AMC Plus", "AMC+ Amazon Channel", "AMC Plus Apple TV Channel"],
    "mgmplus": ["MGM Plus", "MGM+", "MGM Plus Amazon Channel"], "starz": ["Starz", "Starz Amazon Channel"],
    "mubi": ["MUBI", "Mubi"],
    "tubi": ["Tubi TV", "Tubi"], "pluto": ["Pluto TV"], "roku": ["The Roku Channel", "Roku Channel"],
    "kanopy": ["Kanopy"], "plex": ["Plex", "Plex Channel"], "youtube": ["YouTube Free", "YouTube"],
    "apple": ["Apple TV", "Apple TV Store", "Apple iTunes"], "amazon": ["Amazon Video"],
    "google": ["Google Play Movies", "YouTube"], "fandango": ["Fandango At Home", "Vudu"],
}
BUCKETS = {"sub": ("flatrate",), "free": ("free", "ads"), "store": ("rent", "buy")}
MONETIZE = {"sub": "flatrate", "free": "free|ads", "rent": "rent", "buy": "buy"}

GENRE_MOVIE = {"horror": 27, "thriller": 53, "comedy": 35, "scifi": 878, "fantasy": 14, "mystery": 9648,
               "drama": 18, "action": 28, "crime": 80, "animation": 16, "family": 10751, "romance": 10749,
               "documentary": 99}
GENRE_TV = {"thriller": 9648, "comedy": 35, "scifi": 10765, "fantasy": 10765, "mystery": 9648, "drama": 18,
            "action": 10759, "crime": 80, "animation": 16, "family": 10751, "romance": 18, "documentary": 99}
REV_MOVIE = {v: k for k, v in GENRE_MOVIE.items()}
REV_TV = {16: "animation", 35: "comedy", 80: "crime", 99: "documentary", 18: "drama", 10751: "family",
          9648: "mystery", 10759: "action", 10765: "scifi"}

# Styles TMDB can do, as keyword searches (OR'd together). "classic" is a date
# filter instead. Keyword names drift, so each style lists a few spellings.
TAG_KEYWORDS = {
    # horror
    "halloween": ["halloween"], "slasher": ["slasher"], "supernatural": ["supernatural"],
    "haunted": ["haunted house"], "folk": ["folk horror"], "creature": ["creature feature", "monster"],
    "zombie": ["zombie"], "vampire": ["vampire"], "witch": ["witch"], "psychological": ["psychological horror"],
    "found-footage": ["found footage"], "horror-comedy": ["horror comedy", "comedy horror"],
    # thriller / crime / mystery
    "psych-thriller": ["psychological thriller"], "conspiracy": ["conspiracy"], "survival": ["survival"],
    "serial-killer": ["serial killer"], "heist": ["heist"], "whodunit": ["whodunit", "murder mystery"],
    "detective": ["detective", "private detective"],
    # comedy / romance
    "dark-comedy": ["dark comedy", "black comedy"], "parody": ["parody", "spoof"],
    "buddy": ["buddy comedy"],
    # sci-fi / fantasy
    "time-travel": ["time travel"], "space": ["outer space", "space travel", "space"], "dystopia": ["dystopia"],
    "ai": ["artificial intelligence (a.i.)", "artificial intelligence"], "alien": ["alien", "alien invasion"],
    "magic": ["magic"], "fairy-tale": ["fairy tale"], "dragon": ["dragon"],
    # action
    "superhero": ["superhero"], "martial-arts": ["martial arts"], "spy": ["spy", "espionage"],
    # drama / family / animation / documentary
    "true-story": ["based on true story"], "coming-of-age": ["coming of age"], "sports": ["sports"],
    "based-on-book": ["based on novel or book"], "anime": ["anime"], "stop-motion": ["stop motion"],
    "christmas": ["christmas"], "true-crime": ["true crime"], "nature": ["nature", "wildlife"],
    "music": ["music", "concert"],
}
TV_HORROR_KEYWORDS = ["horror", "supernatural", "ghost", "zombie", "vampire", "slasher"]
# Not keywords: "classic" is a date filter, and "romcom" is Comedy AND Romance,
# because TMDB has no usable romantic-comedy keyword (it returned nothing live).
SUPPORTED_TAGS = list(TAG_KEYWORDS) + ["romcom", "classic"]

_cache, _lock = {}, threading.Lock()
_ctx = ssl.create_default_context()


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower().replace("+", "plus"))


ALIAS_NORM = {sid: {norm(n) for n in names} for sid, names in ALIASES.items()}


def get(path, params=None, ttl=3600):
    params = dict(params or {})
    k = key()
    headers = {"Accept": "application/json"}
    if k.startswith("eyJ"):
        headers["Authorization"] = "Bearer " + k          # v4 read access token
    else:
        params["api_key"] = k
    url = BASE + path + "?" + urllib.parse.urlencode(sorted(params.items()))
    now = time.time()
    with _lock:
        hit = _cache.get(url)
        if hit and hit[0] > now:
            return hit[1]
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=6, context=_ctx) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise TMDBError("TMDB said %d" % e.code)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise TMDBError("TMDB unreachable")
    with _lock:
        if len(_cache) > 2000:
            _cache.clear()
        _cache[url] = (now + ttl, data)
    return data


def provider_ids(kind, service_ids):
    """TMDB provider ids for our services, matched by name."""
    data = get("/watch/providers/" + kind, {"watch_region": REGION}, ttl=86400)
    wanted = set().union(*[ALIAS_NORM.get(s, set()) for s in service_ids]) if service_ids else set()
    return sorted({p["provider_id"] for p in data.get("results", []) if norm(p["provider_name"]) in wanted})


def keyword_ids(queries):
    """Exact name matches; when a spelling has none, its closest result."""
    out = set()
    for q in queries:
        results = get("/search/keyword", {"query": q}, ttl=7 * 86400).get("results", [])
        exact = [k["id"] for k in results if k["name"].lower() == q.lower()]
        out.update(exact or [k["id"] for k in results[:1]])
    return sorted(out)


def services_in(bucket_list, kind_of_service, services):
    """Map TMDB provider entries to our service ids of one kind."""
    found, others = [], []
    for p in bucket_list:
        n = norm(p.get("provider_name", ""))
        hit = [sid for sid in ALIAS_NORM if services.get(sid) == kind_of_service and n in ALIAS_NORM[sid]]
        if hit:
            found.extend(h for h in hit if h not in found)
        else:
            others.append(p.get("provider_name", ""))
    return found, others


def normalize(kind, d, services):
    us = (d.get("watch/providers") or {}).get("results", {}).get(REGION, {})
    subs, other_subs = services_in(us.get("flatrate", []), "sub", services)
    free, _ = services_in(us.get("free", []) + us.get("ads", []), "free", services)
    rent, _ = services_in(us.get("rent", []), "store", services)
    buy, _ = services_in(us.get("buy", []), "store", services)
    if kind == "movie":
        title, date = d.get("title") or d.get("original_title"), d.get("release_date") or ""
        rating = ""
        for rel in (d.get("release_dates") or {}).get("results", []):
            if rel.get("iso_3166_1") == "US":
                certs = [x.get("certification") for x in rel.get("release_dates", []) if x.get("certification")]
                rating = certs[0] if certs else ""
        genres = [REV_MOVIE[g["id"]] for g in d.get("genres", []) if g["id"] in REV_MOVIE]
    else:
        title, date = d.get("name") or d.get("original_name"), d.get("first_air_date") or ""
        rating = next((c.get("rating") for c in (d.get("content_ratings") or {}).get("results", [])
                       if c.get("iso_3166_1") == "US"), "")
        genres = [REV_TV[g["id"]] for g in d.get("genres", []) if g["id"] in REV_TV]
    blurb = (d.get("overview") or "").strip()
    if len(blurb) > 240:
        blurb = blurb[:237].rsplit(" ", 1)[0] + "…"
    poster = d.get("poster_path")
    t = {"id": "%s:%d" % (kind, d["id"]), "title": title or "Untitled", "year": int(date[:4]) if date[:4].isdigit() else None,
         "kind": kind, "genres": list(dict.fromkeys(genres)), "tags": [], "rating": rating or "NR", "scare": None,
         "blurb": blurb, "subs": subs, "free": free, "rent": rent, "rentFrom": None, "buy": buy,
         "others": [o for o in other_subs if o][:3],
         "poster": IMG + poster if poster and re.match(r"^/[\w-]+\.(jpg|png)$", poster) else None,
         "link": us.get("link")}
    if kind == "movie":
        t["minutes"] = d.get("runtime") or None
    else:
        t["seasons"] = d.get("number_of_seasons") or None
    return t


def details(tid, services):
    m = re.fullmatch(r"(movie|tv):(\d{1,9})", tid)
    if not m:
        raise ValueError(tid)
    kind, num = m.group(1), m.group(2)
    extra = "watch/providers,release_dates" if kind == "movie" else "watch/providers,content_ratings"
    return normalize(kind, get("/%s/%s" % (kind, num), {"append_to_response": extra}, ttl=6 * 3600), services)


def discover_params(kind, f, services):
    p = {"watch_region": REGION, "sort_by": "popularity.desc", "include_adult": "false",
         "vote_count.gte": 40 if kind == "movie" else 20}
    wanted = []
    if "sub" in f["access"]:
        wanted += f["subs"]
    if "free" in f["access"]:
        wanted += f["free"]
    if "rent" in f["access"] or "buy" in f["access"]:
        wanted += f["stores"]
    ids = provider_ids(kind, wanted)
    if not ids:
        return None
    p["with_watch_providers"] = "|".join(map(str, ids))
    p["with_watch_monetization_types"] = "|".join(MONETIZE[a] for a in f["access"])
    gmap = GENRE_MOVIE if kind == "movie" else GENRE_TV
    genre_ids = sorted({gmap[g] for g in f["genres"] if g in gmap})
    kw_queries = [q for t in f["tags"] for q in TAG_KEYWORDS.get(t, [])]
    if kind == "tv" and "horror" in f["genres"]:
        # TMDB has no TV horror genre; keywords stand in for it.
        genre_ids = []
        kw_queries = kw_queries or TV_HORROR_KEYWORDS
    if genre_ids:
        p["with_genres"] = "|".join(map(str, genre_ids))
    if "romcom" in f["tags"] and len(f["tags"]) == 1:
        # Comma means AND in TMDB's genre filter. TV has no Romance genre, so drama stands in.
        p["with_genres"] = "35,10749" if kind == "movie" else "35,18"
    if kw_queries:
        kws = keyword_ids(kw_queries)
        if not kws:
            return None
        p["with_keywords"] = "|".join(map(str, kws))
    if "classic" in f["tags"]:
        p["primary_release_date.lte" if kind == "movie" else "first_air_date.lte"] = "1989-12-31"
    if kind == "movie":
        if f["ratings"]:
            certs = [c for r in f["ratings"] for c in MOVIE_CERTS[r]]
            p["certification_country"], p["certification"] = "US", "|".join(certs)
        if f["maxMinutes"]:
            p["with_runtime.lte"] = f["maxMinutes"]
    return p


MOVIE_CERTS = {"G": ["G"], "PG": ["PG"], "PG-13": ["PG-13"], "R": ["R", "NC-17"]}


def spin(f, services, usable, want=12):
    """A batch of enriched titles that match f, plus TMDB's match count.

    usable(t) is the final word: it re-checks services and the rating we
    actually show, because TMDB's certification filter matches if *any* US
    release has the rating (Midsommar's unrated cut, say)."""
    kinds = ["movie", "tv"] if f["kind"] == "both" else [f["kind"]]
    if f["maxMinutes"]:
        kinds = [k for k in kinds if k == "movie"] or kinds   # runtime is a movie-only filter
    rng = random.Random(f["seed"])
    total, candidates = 0, []
    for kind in kinds:
        p = discover_params(kind, f, services)
        if p is None:
            continue
        first = get("/discover/" + kind, dict(p, page=1), ttl=1800)
        total += first.get("total_results", 0)
        pages = min(first.get("total_pages", 1), 15)
        page = 1 + (f["seed"] % pages) if pages > 1 else 1
        data = first if page == 1 else get("/discover/" + kind, dict(p, page=page), ttl=1800)
        candidates += ["%s:%d" % (kind, r["id"]) for r in data.get("results", [])]
    rng.shuffle(candidates)
    candidates = candidates[: want * 2]
    with ThreadPoolExecutor(max_workers=8) as pool:
        titles = list(pool.map(lambda i: _safe_details(i, services), candidates))
    titles = [t for t in titles if t and usable(t)]
    return total, titles[:want]


def _safe_details(tid, services):
    try:
        return details(tid, services)
    except (TMDBError, ValueError, KeyError):
        return None
