#!/usr/bin/env python3
"""Run Next Reel locally the way Vercel serves it: public/ as static files,
/api/* through lib.core. Rooms live in memory here.

    python3 dev_server.py              # http://127.0.0.1:8860
    TMDB_API_KEY=... python3 dev_server.py
"""
import argparse
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from lib.core import handle

PUBLIC = Path(__file__).resolve().parent / "public"


class Dev(BaseHTTPRequestHandler):
    def _send(self, status, headers, body):
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _api(self, method):
        u = urlsplit(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        self._send(*handle(method, u.path, parse_qs(u.query), dict(self.headers), body))

    def do_GET(self):
        u = urlsplit(self.path)
        if u.path.startswith("/api/"):
            return self._api("GET")
        name = "index.html" if u.path == "/" else u.path.lstrip("/")
        f = (PUBLIC / name).resolve()
        if PUBLIC not in f.parents or not f.is_file():
            return self._send(404, {"Content-Type": "text/plain"}, b"Not found")
        kind = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        self._send(200, {"Content-Type": kind, "Cache-Control": "no-cache"}, f.read_bytes())

    do_HEAD = do_GET

    def do_POST(self):
        return self._api("POST")

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8860)
    a = ap.parse_args()
    print("next reel dev on http://127.0.0.1:%d/" % a.port, flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), Dev).serve_forever()
