#!/usr/bin/env python3
"""serve.py — zero-dependency HTTP surface for the EN 16931 / Peppol validator.

Endpoints:
  GET  /            -> serves index.html (browser validator)
  GET  /health      -> {"ok": true}
  POST /validate    -> body = invoice XML (Content-Type text/xml or anything)
                       returns JSON: {profile, valid, codes:[...], errors:[...]}

Stdlib only. No external calls. Runs on $0.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ublcheck import validate  # noqa: E402

MAX_BODY = 5 * 1024 * 1024  # 5 MB cap


class Handler(BaseHTTPRequestHandler):
    server_version = "ublcheck/1.0"

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, indent=2).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            p = os.path.join(HERE, "index.html")
            if os.path.isfile(p):
                with open(p, "rb") as fh:
                    return self._send(200, fh.read(), "text/html; charset=utf-8")
            return self._send(404, {"error": "index.html not found"})
        if self.path == "/health":
            return self._send(200, {"ok": True})
        return self._send(404, {"error": "not found", "paths": ["/", "/health", "POST /validate"]})

    def do_POST(self):
        if self.path != "/validate":
            return self._send(404, {"error": "not found", "hint": "POST /validate"})
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._send(400, {"error": "bad Content-Length"})
        if n <= 0 or n > MAX_BODY:
            return self._send(413, {"error": "body empty or exceeds 5MB"})
        raw = self.rfile.read(n)
        try:
            xml = raw.decode("utf-8", errors="replace")
        except Exception as e:  # pragma: no cover
            return self._send(400, {"error": "decode failed: %s" % e})
        try:
            r = validate(xml)
        except Exception as e:
            return self._send(500, {"error": "validator crashed: %s" % e})
        codes = sorted({e["code"] for e in r["errors"]})
        return self._send(200, {
            "profile": r["profile"],
            "valid": r["valid"],
            "codes": codes,
            "errors": r["errors"],
        })

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main():
    port = int(os.environ.get("PORT", "8080"))
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    sys.stderr.write("ublcheck serving on 0.0.0.0:%d\n" % port)
    srv.serve_forever()


if __name__ == "__main__":
    main()
