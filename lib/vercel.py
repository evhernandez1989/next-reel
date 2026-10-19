"""Adapter: each api/*.py declares `class handler(Base)`. Vercel finds functions
by reading the source for a top-level `handler`, so it has to be a literal class there."""
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit

from .core import handle


class Base(BaseHTTPRequestHandler):
    def _run(self, method):
        u = urlsplit(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(min(n, 20_001)) if n else b""
        status, headers, out = handle(method, u.path, parse_qs(u.query), dict(self.headers), body)
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def do_GET(self):
        self._run("GET")

    def do_POST(self):
        self._run("POST")

    def log_message(self, *args):
        pass
