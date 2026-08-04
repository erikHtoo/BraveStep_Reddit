#!/usr/bin/env python3
"""Serve visual demo UI + proxy Erik (:8000) and Maturity (:8100)."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "visual.html"
ERIK = "http://127.0.0.1:8000"
MATURITY = "http://127.0.0.1:8100"
HOST = "127.0.0.1"
PORT = 8200


def proxy(base: str, path_qs: str, method: str, body: bytes | None, content_type: str | None):
    url = base + path_qs
    headers = {"Accept": "application/json"}
    if content_type:
        headers["Content-Type"] = content_type
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=20) as resp:
            return resp.status, resp.read(), resp.headers.get("Content-Type", "application/json")
    except HTTPError as e:
        return e.code, e.read(), e.headers.get("Content-Type", "application/json")
    except URLError as e:
        payload = json.dumps({"detail": f"upstream down: {e.reason}"}).encode()
        return 502, payload, "application/json"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(f"[demo] {self.address_string()} {fmt % args}")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html", "/demo"):
            body = HTML.read_bytes()
            self._send(200, body, "text/html; charset=utf-8")
            return
        if self.path.startswith("/proxy/erik"):
            path_qs = self.path[len("/proxy/erik") :] or "/"
            status, body, ctype = proxy(ERIK, path_qs, "GET", None, None)
            self._send(status, body, ctype)
            return
        if self.path.startswith("/proxy/maturity"):
            path_qs = self.path[len("/proxy/maturity") :] or "/"
            status, body, ctype = proxy(MATURITY, path_qs, "GET", None, None)
            self._send(status, body, ctype)
            return
        self._send(404, b'{"detail":"not found"}', "application/json")

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else None
        ctype = self.headers.get("Content-Type")
        if self.path.startswith("/proxy/erik"):
            path_qs = self.path[len("/proxy/erik") :] or "/"
            status, out, out_ctype = proxy(ERIK, path_qs, "POST", body, ctype)
            self._send(status, out, out_ctype)
            return
        if self.path.startswith("/proxy/maturity"):
            path_qs = self.path[len("/proxy/maturity") :] or "/"
            status, out, out_ctype = proxy(MATURITY, path_qs, "POST", body, ctype)
            self._send(status, out, out_ctype)
            return
        self._send(404, b'{"detail":"not found"}', "application/json")


def main() -> None:
    if not HTML.exists():
        raise SystemExit(f"missing {HTML}")
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Visual demo → http://{HOST}:{PORT}/")
    print(f"  proxy Erik     {ERIK}")
    print(f"  proxy Maturity {MATURITY}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
