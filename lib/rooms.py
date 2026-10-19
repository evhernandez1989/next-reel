"""Watch-party rooms: host spins, everyone votes from their own phone, host reveals.

The logic is written once against a small store interface. MemoryStore runs
locally and in tests; SupabaseStore runs on Vercel, talking to PostgREST with
the project's secret key. The reel_ tables have RLS on and no policies, so
the browser's public key can't read or write them at all: only this server can.
"""
import hashlib
import json
import random
import re
import secrets
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ROOM_TTL = 6 * 3600
MAX_ROOMS = 300
MAX_PLAYERS = 30
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ"   # no I/O: read aloud across a room
CODE_RE = re.compile(r"^[A-Z]{4}$")


class BadRequest(Exception):
    pass


class StoreError(Exception):
    pass


def clean_name(v, fallback="Guest") -> str:
    v = re.sub(r"\s+", " ", str(v or "")).strip()
    v = "".join(ch for ch in v if ch.isprintable())[:24]
    return v or fallback


def token_hash(token: str) -> str:
    return hashlib.sha256(str(token).encode()).hexdigest()


def norm_code(code) -> str:
    code = str(code or "").strip().upper()
    if not CODE_RE.match(code):
        raise LookupError("That room has ended or never existed.")
    return code


# --- stores --------------------------------------------------------------------

class MemoryStore:
    def __init__(self, clock=time.time):
        self.clock = clock
        self.lock = threading.RLock()
        self.rooms, self.players, self.votes = {}, {}, {}

    def sweep(self):
        with self.lock:
            cutoff = self.clock() - ROOM_TTL
            for code in [c for c, r in self.rooms.items() if r["touched"] < cutoff]:
                self.delete_room(code)

    def count_rooms(self):
        return len(self.rooms)

    def insert_room(self, room) -> bool:
        with self.lock:
            if room["code"] in self.rooms:
                return False
            self.rooms[room["code"]] = dict(room, touched=self.clock())
            self.players[room["code"]] = {}
            self.votes[room["code"]] = {}
            return True

    def get_room(self, code):
        with self.lock:
            r = self.rooms.get(code)
            return dict(r) if r else None

    def update_room(self, code, fields, expect_status=None) -> bool:
        with self.lock:
            r = self.rooms.get(code)
            if not r or (expect_status and r["status"] != expect_status):
                return False
            r.update(fields, touched=self.clock())
            return True

    def delete_room(self, code):
        with self.lock:
            for d in (self.rooms, self.players, self.votes):
                d.pop(code, None)

    def players_of(self, code):
        with self.lock:
            return [{"id": k, "name": v} for k, v in self.players.get(code, {}).items()]

    def upsert_player(self, code, pid, name):
        with self.lock:
            self.players[code][pid] = name

    def remove_player(self, code, pid):
        with self.lock:
            self.players.get(code, {}).pop(pid, None)
            for k in [k for k in self.votes.get(code, {}) if k[0] == pid]:
                del self.votes[code][k]

    def upsert_vote(self, code, pid, rnd, pick):
        with self.lock:
            self.votes[code][(pid, rnd)] = pick

    def votes_of(self, code, rnd):
        with self.lock:
            return {pid: pick for (pid, r), pick in self.votes.get(code, {}).items() if r == rnd}


class SupabaseStore:
    """PostgREST over urllib. The secret key never leaves the server."""

    def __init__(self, url, key, timeout=6):
        self.base = url.rstrip("/") + "/rest/v1/"
        self.key = key
        self.timeout = timeout
        self.ctx = ssl.create_default_context()

    def _req(self, method, table, params=None, body=None, prefer=None):
        url = self.base + table
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = {"apikey": self.key, "Content-Type": "application/json", "Accept": "application/json"}
        if not self.key.startswith("sb_"):
            headers["Authorization"] = "Bearer " + self.key      # legacy service_role JWT
        if prefer:
            headers["Prefer"] = prefer
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self.ctx) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            if e.code == 409:
                return "conflict"
            raise StoreError("database said %d" % e.code)
        except (urllib.error.URLError, TimeoutError, OSError):
            raise StoreError("database unreachable")

    @staticmethod
    def _iso(ts):
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))

    def sweep(self):
        self._req("DELETE", "reel_rooms", {"touched_at": "lt." + self._iso(time.time() - ROOM_TTL)})

    def count_rooms(self):
        rows = self._req("GET", "reel_rooms", {"select": "code"})
        return len(rows or [])

    def insert_room(self, room) -> bool:
        row = {"code": room["code"], "host_hash": room["host_hash"], "host_player": room["host"],
               "status": room["status"], "round": room["round"], "candidates": room["candidates"],
               "winner": room["winner"]}
        return self._req("POST", "reel_rooms", body=row, prefer="return=minimal") != "conflict"

    def get_room(self, code):
        rows = self._req("GET", "reel_rooms", {"code": "eq." + code, "select": "*"})
        if not rows:
            return None
        r = rows[0]
        return {"code": r["code"], "host_hash": r["host_hash"], "host": r["host_player"], "status": r["status"],
                "round": r["round"], "candidates": r["candidates"] or [], "winner": r["winner"]}

    def update_room(self, code, fields, expect_status=None) -> bool:
        params = {"code": "eq." + code}
        if expect_status:
            params["status"] = "eq." + expect_status
        body = dict(fields, touched_at=self._iso(time.time()))
        rows = self._req("PATCH", "reel_rooms", params, body, prefer="return=representation")
        return bool(rows)

    def delete_room(self, code):
        self._req("DELETE", "reel_rooms", {"code": "eq." + code})

    def players_of(self, code):
        rows = self._req("GET", "reel_players", {"room_code": "eq." + code, "select": "id,name", "order": "joined_at"})
        return rows or []

    def upsert_player(self, code, pid, name):
        self._req("POST", "reel_players", {"on_conflict": "room_code,id"},
                  {"room_code": code, "id": pid, "name": name}, prefer="resolution=merge-duplicates,return=minimal")

    def remove_player(self, code, pid):
        self._req("DELETE", "reel_votes", {"room_code": "eq." + code, "player": "eq." + pid})
        self._req("DELETE", "reel_players", {"room_code": "eq." + code, "id": "eq." + pid})

    def upsert_vote(self, code, pid, rnd, pick):
        self._req("POST", "reel_votes", {"on_conflict": "room_code,player,round"},
                  {"room_code": code, "player": pid, "round": rnd, "pick": pick},
                  prefer="resolution=merge-duplicates,return=minimal")

    def votes_of(self, code, rnd):
        rows = self._req("GET", "reel_votes", {"room_code": "eq." + code, "round": "eq.%d" % rnd,
                                                "select": "player,pick"})
        return {r["player"]: r["pick"] for r in rows or []}


# --- the game ----------------------------------------------------------------------

class Rooms:
    def __init__(self, store, resolve):
        """resolve(ids) -> list of title dicts, or raises BadRequest for unknown ids."""
        self.store = store
        self.resolve = resolve

    def _get(self, code) -> dict:
        r = self.store.get_room(norm_code(code))
        if r is None:
            raise LookupError("That room has ended or never existed.")
        return r

    def _host(self, r, token):
        if not token or not secrets.compare_digest(token_hash(token), r["host_hash"]):
            raise PermissionError("Only the host can do that.")

    def create(self, name) -> dict:
        self.store.sweep()
        if self.store.count_rooms() >= MAX_ROOMS:
            raise BadRequest("Too many rooms open right now. Try again later.")
        token, pid = secrets.token_urlsafe(18), secrets.token_hex(8)
        for _ in range(20):
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(4))
            room = {"code": code, "host_hash": token_hash(token), "host": pid, "status": "lobby",
                    "round": 0, "candidates": [], "winner": None}
            if self.store.insert_room(room):
                break
        else:
            raise BadRequest("Couldn't find a free room code. Try again.")
        self.store.upsert_player(code, pid, clean_name(name, "Host"))
        return {"code": code, "host_token": token, "player": pid, "state": self.state(code)}

    def join(self, code, name, player=None) -> dict:
        r = self._get(code)
        known = {p["id"] for p in self.store.players_of(r["code"])}
        if not (player and player in known):
            if len(known) >= MAX_PLAYERS:
                raise BadRequest("This room is full.")
            player = secrets.token_hex(8)
        self.store.upsert_player(r["code"], player, clean_name(name))
        return {"code": r["code"], "player": player, "state": self.state(r["code"])}

    def spin(self, code, token, ids) -> dict:
        r = self._get(code)
        self._host(r, token)
        if not isinstance(ids, list) or not 1 <= len(ids) <= 3 or len(set(map(str, ids))) != len(ids):
            raise BadRequest("Send one to three different titles.")
        cands = self.resolve([str(i) for i in ids])
        self.store.update_room(r["code"], {"status": "voting", "round": r["round"] + 1,
                                           "candidates": cands, "winner": None})
        return self.state(r["code"])

    def vote(self, code, player, pick) -> dict:
        r = self._get(code)
        if player not in {p["id"] for p in self.store.players_of(r["code"])}:
            raise PermissionError("Join the room first.")
        if r["status"] != "voting":
            raise BadRequest("Voting isn't open.")
        if str(pick) not in [c["id"] for c in r["candidates"]]:
            raise BadRequest("That isn't one of the choices.")
        self.store.upsert_vote(r["code"], player, r["round"], str(pick))
        return self.state(r["code"])

    def reveal(self, code, token, rng=random) -> dict:
        r = self._get(code)
        self._host(r, token)
        if r["status"] != "voting":
            raise BadRequest("Spin first.")
        tally = self._tally(r)
        top = max(tally.values())
        # Ties (including nobody voting) go to the wheel, like Next Stop.
        winner = rng.choice([c for c, n in tally.items() if n == top])
        self.store.update_room(r["code"], {"status": "revealed", "winner": winner}, expect_status="voting")
        return self.state(r["code"])

    def leave(self, code, player) -> dict:
        r = self._get(code)
        if player and player != r["host"]:
            self.store.remove_player(r["code"], player)
        return {"ok": True}

    def end(self, code, token) -> dict:
        r = self._get(code)
        self._host(r, token)
        self.store.delete_room(r["code"])
        return {"ok": True}

    def _tally(self, r):
        tally = {c["id"]: 0 for c in r["candidates"]}
        for pick in self.store.votes_of(r["code"], r["round"]).values():
            if pick in tally:
                tally[pick] += 1
        return tally

    def state(self, code) -> dict:
        r = self._get(code)
        players = self.store.players_of(r["code"])
        votes = self.store.votes_of(r["code"], r["round"]) if r["status"] != "lobby" else {}
        return {
            "code": r["code"], "status": r["status"], "round": r["round"], "host": r["host"],
            "candidates": r["candidates"], "winner": r["winner"],
            "players": [{"id": p["id"], "name": p["name"], "voted": p["id"] in votes} for p in players],
            # Counts only after the reveal, so nobody sees who picked what while voting.
            "tally": self._tally(r) if r["status"] == "revealed" else None,
            "voted": len(votes),
        }
