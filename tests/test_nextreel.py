import json
import os
import random
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.pop("TMDB_API_KEY", None)
os.environ.pop("TMDB_READ_TOKEN", None)
import catalog  # noqa: E402
from lib import core, tmdb  # noqa: E402
from lib.rooms import BadRequest, MemoryStore, Rooms, ROOM_TTL  # noqa: E402


class FakeClock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


def fake_resolve(ids):
    known = {"a", "b", "c", "d"}
    if not set(ids) <= known:
        raise BadRequest("Unknown title.")
    return [{"id": i, "title": i.upper()} for i in ids]


class CatalogTest(unittest.TestCase):
    def test_built_file_matches_source(self):
        built = json.loads((ROOT / "public" / "catalog.json").read_text())
        self.assertEqual(built, json.loads(json.dumps(catalog.build())),
                         "public/catalog.json is stale: run python3 catalog.py")

    def test_every_title_is_watchable_somewhere(self):
        d = catalog.build()
        for t in d["titles"]:
            self.assertTrue(t["subs"] or t["free"] or t["rent"] or t["buy"], t["id"])
            self.assertTrue(set(t["genres"]) <= set(d["genres"]), t["id"])
            self.assertTrue(set(t["tags"]) <= set(d["tags"]), t["id"])

    def test_enough_horror_for_october(self):
        d = catalog.build()
        horror = [t for t in d["titles"] if "horror" in t["genres"]]
        self.assertGreaterEqual(len(horror), 100)
        self.assertGreaterEqual(sum("halloween" in t["tags"] for t in d["titles"]), 15)
        self.assertGreaterEqual(len([t for t in horror if t["free"]]), 5)


class FilterTest(unittest.TestCase):
    def q(self, **kw):
        base = {"access": "sub,free", "subs": "netflix,hulu,peacock,shudder",
                "free": "tubi,pluto,roku,kanopy,plex,youtube", "stores": "apple,amazon,google,fandango"}
        base.update(kw)
        return core.parse_filters({k: [v] for k, v in base.items()})

    def test_fright_night_counts(self):
        total, titles = core.catalog_spin(self.q(genres="horror"))
        self.assertEqual(total, 77)
        self.assertTrue(all("horror" in t["genres"] for t in titles))

    def test_free_only(self):
        total, titles = core.catalog_spin(self.q(access="free", genres="horror"))
        self.assertEqual(total, 11)
        self.assertTrue(all(t["free"] for t in titles))

    def test_amc_plus_includes_shudder(self):
        f = self.q(subs="amcplus", access="sub")
        self.assertTrue(core.usable(core.BY_ID["host"], f))

    def test_junk_is_dropped(self):
        f = self.q(kind="x", genres="horror,<script>", scare="evil", max="999", seed="-5")
        self.assertEqual((f["kind"], f["genres"], f["scare"], f["maxMinutes"]), ("both", ["horror"], "any", 0))

    def test_no_access_no_titles(self):
        self.assertEqual(core.spin(self.q(access=""))["total"], 0)

    def test_spin_falls_back_to_catalog_when_tmdb_fails(self):
        with mock.patch.object(tmdb, "enabled", return_value=True), \
             mock.patch.object(tmdb, "spin", side_effect=tmdb.TMDBError("down")):
            self.assertEqual(core.spin(self.q(genres="horror"))["source"], "catalog")


class TMDBNormalizeTest(unittest.TestCase):
    def test_buckets_pick_the_right_apple(self):
        d = {"id": 603, "title": "The Matrix", "release_date": "1999-03-31", "runtime": 136,
             "genres": [{"id": 28}, {"id": 878}], "overview": "x", "poster_path": "/abc.jpg",
             "release_dates": {"results": [{"iso_3166_1": "US", "release_dates": [{"certification": "R"}]}]},
             "watch/providers": {"results": {"US": {"link": "https://www.themoviedb.org/movie/603/watch",
                 "flatrate": [{"provider_name": "HBO Max"}, {"provider_name": "Some New Thing"}],
                 "ads": [{"provider_name": "Tubi TV"}],
                 "rent": [{"provider_name": "Apple TV"}, {"provider_name": "Amazon Video"}],
                 "buy": [{"provider_name": "Fandango At Home"}]}}}}
        t = tmdb.normalize("movie", d, core.SERVICES)
        self.assertEqual(t["id"], "movie:603")
        self.assertEqual(t["subs"], ["max"])
        self.assertEqual(t["free"], ["tubi"])
        self.assertEqual(sorted(t["rent"]), ["amazon", "apple"])
        self.assertEqual(t["buy"], ["fandango"])
        self.assertEqual(t["others"], ["Some New Thing"])
        self.assertEqual((t["rating"], t["minutes"], t["genres"]), ("R", 136, ["action", "scifi"]))
        self.assertTrue(t["poster"].startswith("https://image.tmdb.org/"))

    def test_apple_subscription_is_the_sub(self):
        d = {"id": 1, "name": "Severance", "first_air_date": "2022-02-18", "genres": [],
             "watch/providers": {"results": {"US": {"flatrate": [{"provider_name": "Apple TV"}]}}}}
        t = tmdb.normalize("tv", d, core.SERVICES)
        self.assertEqual((t["subs"], t["rent"]), (["appletv"], []))

    def test_bad_poster_path_dropped(self):
        d = {"id": 2, "title": "x", "poster_path": "javascript:alert(1)", "genres": []}
        self.assertIsNone(tmdb.normalize("movie", d, core.SERVICES)["poster"])


class RoomsTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.rooms = Rooms(MemoryStore(clock=self.clock), fake_resolve)

    def test_full_round(self):
        r = self.rooms.create("Ellie")
        code, tok, host = r["code"], r["host_token"], r["player"]
        guest = self.rooms.join(code.lower(), "Sam")["player"]
        s = self.rooms.spin(code, tok, ["a", "b", "c"])
        self.assertEqual(s["status"], "voting")
        self.assertIsNone(s["tally"], "tally must stay hidden while voting")
        self.assertEqual([c["title"] for c in s["candidates"]], ["A", "B", "C"])
        self.rooms.vote(code, host, "b")
        s = self.rooms.vote(code, guest, "b")
        self.assertEqual(s["voted"], 2)
        s = self.rooms.reveal(code, tok)
        self.assertEqual((s["status"], s["winner"]), ("revealed", "b"))
        self.assertEqual(s["tally"], {"a": 0, "b": 2, "c": 0})
        self.assertNotIn(tok, json.dumps(s))
        s = self.rooms.spin(code, tok, ["d"])
        self.assertEqual((s["round"], s["voted"]), (2, 0), "votes reset each round")

    def test_tie_goes_to_the_wheel(self):
        r = self.rooms.create("H")
        self.rooms.spin(r["code"], r["host_token"], ["a", "b"])
        s = self.rooms.reveal(r["code"], r["host_token"], rng=random.Random(1))
        self.assertIn(s["winner"], ("a", "b"))

    def test_only_host_spins_reveals_and_ends(self):
        r = self.rooms.create("H")
        with self.assertRaises(PermissionError):
            self.rooms.spin(r["code"], "nope", ["a"])
        self.rooms.spin(r["code"], r["host_token"], ["a"])
        with self.assertRaises(PermissionError):
            self.rooms.reveal(r["code"], None)
        with self.assertRaises(PermissionError):
            self.rooms.end(r["code"], "guess")
        self.rooms.end(r["code"], r["host_token"])
        with self.assertRaises(LookupError):
            self.rooms.state(r["code"])

    def test_rejects_bad_votes_and_candidates(self):
        r = self.rooms.create("H")
        with self.assertRaises(BadRequest):
            self.rooms.spin(r["code"], r["host_token"], ["a", "zzz"])
        with self.assertRaises(BadRequest):
            self.rooms.spin(r["code"], r["host_token"], ["a", "a"])
        with self.assertRaises(BadRequest):
            self.rooms.vote(r["code"], r["player"], "a")      # voting not open
        self.rooms.spin(r["code"], r["host_token"], ["a", "b"])
        with self.assertRaises(BadRequest):
            self.rooms.vote(r["code"], r["player"], "c")
        with self.assertRaises(PermissionError):
            self.rooms.vote(r["code"], "stranger", "a")
        with self.assertRaises(LookupError):
            self.rooms.state("not a code")

    def test_rooms_expire(self):
        r = self.rooms.create("H")
        self.clock.t += ROOM_TTL + 1
        self.rooms.create("other")       # creating sweeps
        with self.assertRaises(LookupError):
            self.rooms.state(r["code"])

    def test_names_are_cleaned(self):
        r = self.rooms.create("  <b>x</b>\n" + "y" * 50)
        name = r["state"]["players"][0]["name"]
        self.assertLessEqual(len(name), 24)
        self.assertNotIn("\n", name)


class HttpTest(unittest.TestCase):
    def call(self, method, path, query=None, headers=None, body=None):
        h = {"Host": "next-reel.vercel.app"}
        h.update(headers or {})
        raw = json.dumps(body).encode() if body is not None else b""
        st, hd, out = core.handle(method, path, query or {}, h, raw)
        return st, hd, json.loads(out)

    def test_config_and_spin(self):
        st, _, c = self.call("GET", "/api/config")
        self.assertEqual((st, c["source"]), (200, "catalog"))
        st, hd, s = self.call("GET", "/api/spin", {"access": ["rent"], "stores": ["apple"], "genres": ["horror"]})
        self.assertEqual(st, 200)
        self.assertIn("s-maxage", hd["Cache-Control"])
        self.assertGreater(s["total"], 50)

    def test_writes_need_same_origin_or_app_header(self):
        self.assertEqual(self.call("POST", "/api/rooms", body={"action": "create"})[0], 403)
        self.assertEqual(self.call("POST", "/api/rooms", headers={"Origin": "https://evil.com"},
                                   body={"action": "create"})[0], 403)
        st, _, r = self.call("POST", "/api/rooms", headers={"Origin": "https://next-reel.vercel.app"},
                             body={"action": "create", "name": "x"})
        self.assertEqual(st, 201)
        self.assertEqual(self.call("GET", "/api/rooms", {"code": [r["code"]]})[0], 200)
        self.assertEqual(self.call("GET", "/api/rooms", {"code": ["ZZZZ"]})[0], 404)
        self.assertEqual(self.call("POST", "/api/rooms", headers={"X-Next-Reel": "1"}, body={"action": "?"})[0], 400)


if __name__ == "__main__":
    unittest.main()


class TMDBSpinTest(unittest.TestCase):
    """The discover -> details flow against canned TMDB answers."""

    def fake_get(self, path, params=None, ttl=0):
        self.calls.append((path, dict(params or {})))
        if path.startswith("/watch/providers/"):
            return {"results": [{"provider_id": 8, "provider_name": "Netflix"},
                                {"provider_id": 99, "provider_name": "Shudder"},
                                {"provider_id": 73, "provider_name": "Tubi TV"}]}
        if path == "/search/keyword":
            q = params["query"]
            return {"results": [{"id": 3335 if q == "halloween" else len(q), "name": q},
                                {"id": 1, "name": q + " party"}]}
        if path.startswith("/discover/"):
            return {"total_results": 2, "total_pages": 1, "results": [{"id": 10}, {"id": 11}]}
        num = int(path.rsplit("/", 1)[1])
        prov = {"flatrate": [{"provider_name": "Netflix"}]} if num == 10 else {"flatrate": [{"provider_name": "Hulu"}]}
        return {"id": num, "title": "T%d" % num, "release_date": "2020-01-01", "genres": [{"id": 27}],
                "watch/providers": {"results": {"US": prov}}}

    def test_spin_builds_params_and_keeps_only_watchable(self):
        self.calls = []
        f = core.parse_filters({"kind": ["movie"], "access": ["sub,free"], "subs": ["netflix"], "free": ["tubi"],
                                "genres": ["horror"], "tags": ["halloween"], "scare": ["cozy"], "seed": ["3"]})
        with mock.patch.object(tmdb, "get", side_effect=self.fake_get):
            total, titles = tmdb.spin(f, core.SERVICES, lambda t: core.usable(t, f))
        self.assertEqual(total, 2)
        self.assertEqual([t["title"] for t in titles], ["T10"], "the Hulu-only title is dropped")
        disc = next(p for path, p in self.calls if path == "/discover/movie")
        self.assertEqual(disc["with_watch_providers"], "8|73")
        self.assertEqual(disc["with_watch_monetization_types"], "flatrate|free|ads")
        self.assertEqual((disc["with_genres"], disc["with_keywords"]), ("27", "3335"))
        self.assertEqual(disc["certification.lte"], "PG-13")

    def test_tv_horror_uses_keywords(self):
        self.calls = []
        f = core.parse_filters({"kind": ["tv"], "access": ["sub"], "subs": ["netflix"], "genres": ["horror"]})
        with mock.patch.object(tmdb, "get", side_effect=self.fake_get):
            p = tmdb.discover_params("tv", f, core.SERVICES)
        self.assertNotIn("with_genres", p)
        self.assertIn("/search/keyword", [c[0] for c in self.calls])
