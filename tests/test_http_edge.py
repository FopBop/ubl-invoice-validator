#!/usr/bin/env python3
"""Edge-case HTTP tests for serve.py: routing, static serving, security headers,
path-traversal protection, HEAD, method handling, and body-limit boundaries.

Stdlib only. Starts a real server on an ephemeral port.

Run:  python3 tests/test_http_edge.py
"""
import io
import json
import os
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import serve  # noqa: E402

VALID_XML = open(os.path.join(HERE, "valid.xml"), encoding="utf-8").read()


def make_zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files:
            zf.writestr(name, data)
    return buf.getvalue()


class HttpBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
        cls.port = cls.srv.server_address[1]
        cls.t = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.t.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def request(self, path, method="GET", body=None, headers=None):
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path),
                                     data=body, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()


class RoutingTest(HttpBase):
    def test_health(self):
        s, h, b = self.request("/health")
        self.assertEqual(s, 200)
        self.assertTrue(json.loads(b)["ok"])

    def test_health_trailing_slash(self):
        s, h, b = self.request("/health/")
        self.assertEqual(s, 200)

    def test_unknown_json_404(self):
        s, h, b = self.request("/nope.json")
        self.assertEqual(s, 404)
        self.assertEqual(json.loads(b)["error"], "not found")

    def test_unknown_html_404_serves_page(self):
        s, h, b = self.request("/no-such-page", headers={"Accept": "text/html"})
        self.assertEqual(s, 404)
        self.assertIn("text/html", h.get("Content-Type", ""))

    def test_post_wrong_path_404(self):
        s, h, b = self.request("/validate-typo", method="POST", body=b"x",
                               headers={"Content-Length": "1"})
        self.assertEqual(s, 404)

    def test_index_served_at_root(self):
        s, h, b = self.request("/")
        self.assertEqual(s, 200)
        self.assertIn("text/html", h.get("Content-Type", ""))

    def test_robots_txt(self):
        s, h, b = self.request("/robots.txt")
        self.assertEqual(s, 200)
        self.assertIn("text/plain", h.get("Content-Type", ""))

    def test_sitemap_xml(self):
        s, h, b = self.request("/sitemap.xml")
        self.assertEqual(s, 200)
        self.assertIn("xml", h.get("Content-Type", ""))

    def test_webmanifest(self):
        s, h, b = self.request("/site.webmanifest")
        self.assertEqual(s, 200)
        self.assertIn("manifest", h.get("Content-Type", ""))


class SecurityTest(HttpBase):
    def test_security_headers_present(self):
        s, h, b = self.request("/")
        for key in ("X-Frame-Options", "X-Content-Type-Options",
                    "Referrer-Policy", "Content-Security-Policy"):
            self.assertIn(key, h, "missing %s" % key)
        self.assertEqual(h["X-Frame-Options"], "DENY")
        self.assertEqual(h["X-Content-Type-Options"], "nosniff")

    def test_cors_header(self):
        s, h, b = self.request("/health")
        self.assertEqual(h.get("Access-Control-Allow-Origin"), "*")

    def test_path_traversal_blocked(self):
        for evil in ("/../pyproject.toml", "/..%2fpyproject.toml",
                     "/../../etc/passwd", "/..%2F..%2Fetc%2Fpasswd"):
            with self.subTest(evil=evil):
                s, h, b = self.request(evil)
                # Must never return the target file contents.
                self.assertNotIn(b"build-backend", b)
                self.assertNotIn(b"root:x:", b)

    def test_disallowed_extension_not_served(self):
        # .py is not in the MIME allow-list.
        s, h, b = self.request("/serve.py")
        self.assertEqual(s, 404)

    def test_head_has_no_body_but_headers(self):
        s, h, b = self.request("/", method="HEAD")
        self.assertEqual(s, 200)
        self.assertIn("Content-Type", h)
        self.assertEqual(b, b"")


class BodyLimitTest(HttpBase):
    def _post(self, path, body, ctype="text/xml"):
        return self.request(path, method="POST", body=body,
                            headers={"Content-Type": ctype,
                                     "Content-Length": str(len(body))})

    def test_empty_body_rejected(self):
        s, h, b = self._post("/validate", b"")
        self.assertEqual(s, 413)

    def test_oversized_body_rejected(self):
        # Declare an over-limit Content-Length with a tiny body: the server must
        # refuse up-front (413) WITHOUT reading/allocating the claimed size. This
        # is the real attack shape and avoids a broken pipe from the client.
        import http.client
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request("POST", "/validate", body=b"x",
                  headers={"Content-Length": str(serve.MAX_BODY + 1)})
        r = c.getresponse()
        self.assertEqual(r.status, 413)
        self.assertIn("exceeds", json.loads(r.read())["error"])
        c.close()

    def test_oversized_batch_body_rejected(self):
        import http.client
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request("POST", "/validate-batch", body=b"x",
                  headers={"Content-Length": str(serve.MAX_BODY + 1)})
        r = c.getresponse()
        self.assertEqual(r.status, 413)
        c.close()

    def test_batch_empty_zip(self):
        # A ZIP with no file entries -> clear 400.
        empty = make_zip([])
        s, h, b = self._post("/validate-batch", empty)
        self.assertEqual(s, 400)
        self.assertIn("no files", json.loads(b)["error"])

    def test_batch_macosx_entries_ignored(self):
        z = make_zip([("__MACOSX/._x", "junk"), ("good.xml", VALID_XML)])
        s, h, b = self._post("/validate-batch", z)
        self.assertEqual(s, 200)
        self.assertEqual(json.loads(b)["total"], 1)

    def test_batch_zip_directory_entries_ignored(self):
        z = make_zip([("folder/", ""), ("folder/a.xml", VALID_XML)])
        s, h, b = self._post("/validate-batch", z)
        self.assertEqual(s, 200)
        self.assertEqual(json.loads(b)["total"], 1)

    def test_batch_json_empty_array(self):
        s, h, b = self._post("/validate-batch", b"[]", "application/json")
        self.assertEqual(s, 400)

    def test_batch_json_entry_not_object(self):
        s, h, b = self._post("/validate-batch", b'["x"]', "application/json")
        self.assertEqual(s, 400)

    def test_batch_json_entry_bad_name(self):
        payload = json.dumps([{"name": "", "xml": VALID_XML}]).encode()
        s, h, b = self._post("/validate-batch", payload, "application/json")
        self.assertEqual(s, 400)

    def test_batch_json_entry_xml_not_string(self):
        payload = json.dumps([{"name": "x.xml", "xml": 5}]).encode()
        s, h, b = self._post("/validate-batch", payload, "application/json")
        self.assertEqual(s, 400)

    def test_batch_json_invalid_utf8(self):
        s, h, b = self._post("/validate-batch", b"\xff\xfe\x00bad", "application/json")
        self.assertEqual(s, 400)

    def test_single_validate_bad_utf8_does_not_crash(self):
        # Server decodes with errors="replace"; must respond 200, not 500.
        s, h, b = self._post("/validate", b"<Invoice>\xff\xfe</Invoice>")
        self.assertIn(s, (200,))
        json.loads(b)

    def test_batch_garbage_not_zip_not_json(self):
        s, h, b = self._post("/validate-batch", b"random bytes here")
        self.assertEqual(s, 400)

    def test_batch_corrupt_zip_magic(self):
        # Starts with PK\x03\x04 but is not a valid archive.
        s, h, b = self._post("/validate-batch", b"PK\x03\x04garbage")
        self.assertEqual(s, 400)


class AggregateCorrectnessTest(HttpBase):
    def _post(self, path, body, ctype):
        return self.request(path, method="POST", body=body,
                            headers={"Content-Type": ctype,
                                     "Content-Length": str(len(body))})

    def test_by_code_counts_multiplicity(self):
        # Two broken invoices sharing a code -> by_code counts 2.
        broken = open(os.path.join(HERE, "broken.xml"), encoding="utf-8").read()
        payload = json.dumps([
            {"name": "a.xml", "xml": broken},
            {"name": "b.xml", "xml": broken},
        ]).encode()
        s, h, b = self._post("/validate-batch", payload, "application/json")
        self.assertEqual(s, 200)
        body = json.loads(b)
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["invalid"], 2)
        self.assertGreaterEqual(body["by_code"]["BR-03a"], 2)

    def test_primary_code_is_first_sorted(self):
        broken = open(os.path.join(HERE, "broken.xml"), encoding="utf-8").read()
        payload = json.dumps([{"name": "b.xml", "xml": broken}]).encode()
        s, h, b = self._post("/validate-batch", payload, "application/json")
        r = json.loads(b)["results"][0]
        self.assertEqual(r["code"], r["codes"][0])

    def test_valid_entry_has_null_code_and_empty_codes(self):
        payload = json.dumps([{"name": "g.xml", "xml": VALID_XML}]).encode()
        s, h, b = self._post("/validate-batch", payload, "application/json")
        r = json.loads(b)["results"][0]
        self.assertTrue(r["valid"])
        self.assertIsNone(r["code"])
        self.assertEqual(r["codes"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
