#!/usr/bin/env python3
"""serve.py — zero-dependency HTTP surface for the EN 16931 / Peppol validator.

Endpoints:
  GET  /            -> serves index.html (browser validator)
  GET  /health      -> {"ok": true}
  POST /validate    -> body = invoice XML (Content-Type text/xml or anything)
                       returns JSON: {profile, valid, codes:[...], errors:[...]}
  POST /validate-batch -> body = ZIP of invoice XML files OR JSON array of
                       {name, xml}; returns per-invoice reports + aggregate.

Static assets (browser UI + SEO/GEO files) are also served from the project
root for GET/HEAD, with path-traversal protection and a MIME allow-list:
  /robots.txt, /sitemap.xml, /site.webmanifest, /golive/, ...

Stdlib only. No external calls. Runs on $0.
"""
import io
import json
import os
import sys
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ublcheck import validate  # noqa: E402

MAX_BODY = 5 * 1024 * 1024  # 5 MB cap


class _BatchError(Exception):
    """Internal signal for a client error while building a batch (carries HTTP status)."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class Handler(BaseHTTPRequestHandler):
    server_version = "ublcheck/1.0"

    # ---- static asset serving (browser UI + SEO/GEO files) ----
    # Extension -> MIME type. Only these are ever served from disk.
    STATIC_TYPES = {
        ".html": "text/html; charset=utf-8",
        ".xml": "application/xml; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".webmanifest": "application/manifest+json; charset=utf-8",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".ico": "image/x-icon",
        ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
    }
    CACHEABLE = (".svg", ".png", ".ico", ".css", ".js", ".webmanifest")

    def _send(self, code, body, ctype="application/json; charset=utf-8", head=False):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, indent=2).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def _send_file(self, relpath, head=False, status=200):
        """Serve a file from the project root, guarding against path traversal.

        ``relpath`` is a URL path (may start with '/'). Only allow-listed
        extensions are served, and the resolved path must stay inside HERE.
        Returns True if a response was sent, False if the file/route is unknown.
        """
        clean = relpath.split("?", 1)[0].split("#", 1)[0].lstrip("/")
        if not clean:
            clean = "index.html"
        # Directory request -> its index.html
        if clean.endswith("/"):
            clean += "index.html"
        target = os.path.realpath(os.path.join(HERE, clean))
        root = os.path.realpath(HERE)
        if not (target == root or target.startswith(root + os.sep)):
            return False  # traversal attempt
        if not os.path.isfile(target):
            return False
        ext = os.path.splitext(target)[1].lower()
        if ext not in self.STATIC_TYPES:
            return False
        ctype = self.STATIC_TYPES[ext]
        with open(target, "rb") as fh:
            data = fh.read()
        cache = "public, max-age=3600" if ext in self.CACHEABLE else "public, max-age=300"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if not head:
            self.wfile.write(data)
        return True

    def do_GET(self):
        return self._do_static()

    def do_HEAD(self):
        return self._do_static(head=True)

    def _do_static(self, head=False):
        # API-ish endpoints are JSON, never files.
        if self.path in ("/health", "/health/"):
            return self._send(200, {"ok": True}, head=head)
        # A trailing-slash root, or "/" -> index.html, served as a real file.
        if self._send_file(self.path, head=head):
            return
        # Browser navigation -> branded HTML 404; API/tooling clients -> JSON.
        accept = (self.headers.get("Accept") or "")
        if not head and "text/html" in accept:
            if self._send_file("/404.html", status=404):
                return
        return self._send(404, {
            "error": "not found",
            "paths": ["/", "/robots.txt", "/sitemap.xml", "/site.webmanifest",
                      "/golive/", "/health", "POST /validate", "POST /validate-batch"],
        }, head=head)

    def do_POST(self):
        if self.path == "/validate-batch":
            try:
                n = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self._send(400, {"error": "bad Content-Length"})
            if n <= 0 or n > MAX_BODY:
                return self._send(413, {"error": "body empty or exceeds 5MB"})
            return self._validate_batch(self.rfile.read(n))
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


    # ---- batch validation (Pro tier: "bulk validation of an archive") ----
    MAX_ENTRIES = 200                          # max number of invoice entries per request
    MAX_TOTAL_UNCOMPRESSED = 50 * 1024 * 1024  # 50 MB cap on total uncompressed size

    def _validate_one(self, name, xml):
        """Validate a single invoice entry via the SAME validator used by /validate.

        Returns a per-invoice report {name, valid, code, codes, profile, errors}.
        Never raises: a crashed validator is reported as an invalid entry.
        """
        try:
            r = validate(xml)
        except Exception as e:  # pragma: no cover - defensive
            r = {"valid": False, "profile": "unknown",
                 "errors": [{"code": "BATCH-500", "path": "/",
                             "fix_hint": "validator crashed: %s" % e}]}
        codes = sorted({e["code"] for e in r["errors"]})
        # "code" = the primary (first) rule code for convenience; null when valid.
        return {
            "name": name,
            "valid": r["valid"],
            "code": codes[0] if codes else None,
            "profile": r["profile"],
            "codes": codes,
            "errors": r["errors"],
        }

    def _aggregate(self, results):
        """Build the aggregate summary object from per-invoice reports."""
        by_code = {}
        valid_count = 0
        for r in results:
            if r["valid"]:
                valid_count += 1
            for c in r["codes"]:
                by_code[c] = by_code.get(c, 0) + 1
        return {
            "total": len(results),
            "valid": valid_count,
            "invalid": len(results) - valid_count,
            "by_code": dict(sorted(by_code.items())),
        }

    def _entries_from_zip(self, raw):
        """Parse a ZIP body into a list of (name, xml). Raises _BatchError on limits."""
        try:
            zf = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile:
            raise _BatchError(400, "body is neither a ZIP archive nor a JSON array "
                                   "of {name, xml} objects")
        names = [n for n in zf.namelist()
                 if not n.endswith("/") and not n.startswith("__MACOSX")]
        if not names:
            raise _BatchError(400, "archive contains no files")
        if len(names) > self.MAX_ENTRIES:
            raise _BatchError(413, "too many entries: %d (max %d)"
                                     % (len(names), self.MAX_ENTRIES))
        entries = []
        total = 0
        for n in names:
            data = zf.read(n)
            total += len(data)
            if total > self.MAX_TOTAL_UNCOMPRESSED:
                raise _BatchError(413, "total uncompressed size exceeds %d bytes (max %d)"
                                         % (total, self.MAX_TOTAL_UNCOMPRESSED))
            entries.append((n, data.decode("utf-8", errors="replace")))
        return entries

    def _entries_from_json(self, raw):
        """Parse a JSON-array body ([{name, xml}, ...]) into a list of (name, xml)."""
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            raise _BatchError(400, "body is neither a ZIP archive nor valid JSON: %s" % e)
        if not isinstance(payload, list):
            raise _BatchError(400, "JSON body must be an array of {name, xml} objects")
        if not payload:
            raise _BatchError(400, "JSON array contains no invoices")
        if len(payload) > self.MAX_ENTRIES:
            raise _BatchError(413, "too many entries: %d (max %d)"
                                     % (len(payload), self.MAX_ENTRIES))
        entries = []
        total = 0
        for i, item in enumerate(payload):
            if not isinstance(item, dict):
                raise _BatchError(400, "entry %d is not an object" % i)
            name = item.get("name")
            xml = item.get("xml")
            if not isinstance(name, str) or not name:
                raise _BatchError(400, "entry %d: 'name' must be a non-empty string" % i)
            if not isinstance(xml, str):
                raise _BatchError(400, "entry %d ('%s'): 'xml' must be a string" % (i, name))
            total += len(xml.encode("utf-8"))
            if total > self.MAX_TOTAL_UNCOMPRESSED:
                raise _BatchError(413, "total uncompressed size exceeds %d bytes (max %d)"
                                         % (total, self.MAX_TOTAL_UNCOMPRESSED))
            entries.append((name, xml))
        return entries

    def _validate_batch(self, raw):
        """Body is EITHER a ZIP archive of invoice XML files OR a JSON array of
        {name, xml} objects. Returns per-invoice reports plus an aggregate summary.

        Reuses the shared ``validate()`` used by POST /validate; no validation
        logic is duplicated here. Over-limit requests are rejected up-front.
        """
        # A ZIP starts with "PK\x03\x04" (or PK\x05\x06 / PK\x07\x08 for empty/split).
        is_zip = raw[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
        try:
            if is_zip:
                entries = self._entries_from_zip(raw)
            else:
                entries = self._entries_from_json(raw)
        except _BatchError as e:
            return self._send(e.status, {"error": e.message})

        results = [self._validate_one(name, xml) for name, xml in entries]
        summary = self._aggregate(results)
        return self._send(200, dict(summary, results=results))

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main():
    port = int(os.environ.get("PORT", "8080"))
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    sys.stderr.write("ublcheck serving on 0.0.0.0:%d\n" % port)
    srv.serve_forever()


if __name__ == "__main__":
    main()
