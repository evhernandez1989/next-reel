"""SupabaseStore against a tiny fake PostgREST that speaks the subset it uses:
eq/lt filters, select, order, insert (409 on duplicate key), upsert via
on_conflict + resolution=merge-duplicates, PATCH with return=representation,
DELETE with cascade from reel_rooms."""
import json
import sys
import threading
import unittest
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import rooms as roomlib  # noqa: E402

KEYS = {"reel_rooms": ("code",), "reel_players": ("room_code", "id"), "reel_votes": ("room_code", "player", "round")}


class FakePostgrest(BaseHTTPRequestHandler):
    tables = None
    seen_keys = []

    def _filters(self, q):
        out = []
        for k, v in q.items():
            if k in ("select", "order", "on_conflict"):
                continue
            op, _, val = v[0].partition(".")
            out.append((k, op, val))
        return out

    @staticmethod
    def _match(row, filters):
        for k, op, val in filters:
            cur = row.get(k)
            if op == "eq" and str(cur) != val:
                return False
            if op == "lt" and not str(cur) < val:
                return False
        return True

    def _send(self, status, obj=None):
        body = b"" if obj is None else json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _parse(self):
        u = urlsplit(self.path)
        FakePostgrest.seen_keys.append(self.headers.get("apikey"))
        table = u.path.rsplit("/", 1)[-1]
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n)) if n else None
        return table, parse_qs(u.query), body

    def do_GET(self):
        table, q, _ = self._parse()
        rows = [r for r in self.tables[table] if self._match(r, self._filters(q))]
        if "order" in q:
            rows.sort(key=lambda r: r[q["order"][0]])
        cols = q.get("select", ["*"])[0]
        if cols != "*":
            rows = [{c: r[c] for c in cols.split(",")} for r in rows]
        self._send(200, rows)

    def do_POST(self):
        table, q, body = self._parse()
        keys = KEYS[table]
        merge = "merge-duplicates" in (self.headers.get("Prefer") or "")
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        row = dict({"created_at": now, "touched_at": now, "joined_at": now}, **body)
        for existing in self.tables[table]:
            if all(existing[k] == row[k] for k in keys):
                if not merge:
                    return self._send(409, {"message": "duplicate key"})
                existing.update(body)
                return self._send(201)
        if table != "reel_rooms" and not any(r["code"] == row["room_code"] for r in self.tables["reel_rooms"]):
            return self._send(409, {"message": "foreign key"})
        self.tables[table].append(row)
        self._send(201)

    def do_PATCH(self):
        table, q, body = self._parse()
        rows = [r for r in self.tables[table] if self._match(r, self._filters(q))]
        for r in rows:
            r.update(body)
        self._send(200, rows)

    def do_DELETE(self):
        table, q, _ = self._parse()
        gone = [r for r in self.tables[table] if self._match(r, self._filters(q))]
        self.tables[table] = [r for r in self.tables[table] if r not in gone]
        if table == "reel_rooms":       # on delete cascade
            codes = {r["code"] for r in gone}
            for t in ("reel_players", "reel_votes"):
                self.tables[t] = [r for r in self.tables[t] if r["room_code"] not in codes]
        self._send(204)

    def log_message(self, *a):
        pass


class SupabaseStoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        FakePostgrest.tables = {t: [] for t in KEYS}
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), FakePostgrest)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        url = "http://127.0.0.1:%d" % cls.srv.server_address[1]
        cls.rooms = roomlib.Rooms(roomlib.SupabaseStore(url, "sb_secret_test"),
                                  lambda ids: [{"id": i, "title": i} for i in ids])

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_full_round_through_postgrest(self):
        r = self.rooms.create("Ellie")
        code, tok = r["code"], r["host_token"]
        stored = FakePostgrest.tables["reel_rooms"][-1]
        self.assertNotEqual(stored["host_hash"], tok, "only the hash is stored")
        sam = self.rooms.join(code, "Sam")["player"]
        self.rooms.join(code, "Sam again", sam)            # rejoin renames, doesn't duplicate
        self.assertEqual(len(self.rooms.state(code)["players"]), 2)
        self.rooms.spin(code, tok, ["movie:1", "movie:2"])
        self.rooms.vote(code, sam, "movie:1")
        self.rooms.vote(code, sam, "movie:2")               # changing a vote upserts
        self.rooms.vote(code, r["player"], "movie:2")
        s = self.rooms.reveal(code, tok)
        self.assertEqual((s["winner"], s["tally"]), ("movie:2", {"movie:1": 0, "movie:2": 2}))
        with self.assertRaises(roomlib.BadRequest):
            self.rooms.reveal(code, tok)                    # can't reveal twice
        self.rooms.leave(code, sam)
        self.assertEqual([p["name"] for p in self.rooms.state(code)["players"]], ["Ellie"])
        self.rooms.end(code, tok)
        with self.assertRaises(LookupError):
            self.rooms.state(code)
        self.assertFalse(FakePostgrest.tables["reel_votes"], "cascade cleared the votes")
        self.assertTrue(all(k == "sb_secret_test" for k in FakePostgrest.seen_keys))

    def test_unreachable_database_is_a_store_error(self):
        dead = roomlib.Rooms(roomlib.SupabaseStore("http://127.0.0.1:9", "k", timeout=1), lambda i: i)
        with self.assertRaises(roomlib.StoreError):
            dead.create("x")


if __name__ == "__main__":
    unittest.main()
