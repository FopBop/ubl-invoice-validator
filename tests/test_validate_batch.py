#!/usr/bin/env python3
"""Integration tests for POST /validate-batch (and backward-compat /validate).

Starts serve.py on an ephemeral port and issues real HTTP requests. Stdlib only.

Run:  python3 tests/test_validate_batch.py
"""
import io
import json
import re
import subprocess
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
BROKEN_XML = open(os.path.join(HERE, "broken.xml"), encoding="utf-8").read()


def make_zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files:
            zf.writestr(name, data)
    return buf.getvalue()


class BatchServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def post(self, path, body, ctype="application/octet-stream"):
        req = urllib.request.Request(
            "http://127.0.0.1:%d%s" % (self.port, path), data=body, method="POST",
            headers={"Content-Type": ctype})
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    # ---- ZIP: one valid + one invalid ----
    def test_zip_mixed(self):
        z = make_zip([("good.xml", VALID_XML), ("bad.xml", BROKEN_XML)])
        status, body = self.post("/validate-batch", z)
        self.assertEqual(status, 200)
        # Aggregate counts: exactly {total: 2, valid: 1, invalid: 1}.
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["valid"], 1)
        self.assertEqual(body["invalid"], 1)
        by_name = {r["name"]: r for r in body["results"]}
        self.assertTrue(by_name["good.xml"]["valid"])
        self.assertIsNone(by_name["good.xml"]["code"])
        self.assertFalse(by_name["bad.xml"]["valid"])
        self.assertEqual(by_name["bad.xml"]["code"], "BR-03a")
        # by_code must reflect the broken invoice's rule codes exactly: the valid
        # invoice contributes none, and each broken-invoice code is counted once.
        broken_codes = by_name["bad.xml"]["codes"]
        self.assertTrue(broken_codes, "broken fixture must produce at least one code")
        self.assertEqual(body["by_code"], {c: 1 for c in broken_codes})
        self.assertEqual(sorted(body["by_code"]), sorted(broken_codes))
        # Sanity: a known broken-invoice code is actually counted (not an empty {}).
        self.assertIn("BR-03a", body["by_code"])
        self.assertGreaterEqual(body["by_code"]["BR-03a"], 1)

    # ---- JSON array: one valid + one invalid ----
    def test_json_mixed(self):
        payload = json.dumps([
            {"name": "good.xml", "xml": VALID_XML},
            {"name": "bad.xml", "xml": BROKEN_XML},
        ]).encode("utf-8")
        status, body = self.post("/validate-batch", payload, "application/json")
        self.assertEqual(status, 200)
        self.assertEqual((body["total"], body["valid"], body["invalid"]), (2, 1, 1))
        by_name = {r["name"]: r for r in body["results"]}
        self.assertTrue(by_name["good.xml"]["valid"])
        self.assertEqual(by_name["bad.xml"]["code"], "BR-03a")

    # ---- aggregate shape is exactly {total, valid, invalid, by_code} ----
    def test_aggregate_keys(self):
        z = make_zip([("good.xml", VALID_XML)])
        status, body = self.post("/validate-batch", z)
        self.assertEqual(status, 200)
        for k in ("total", "valid", "invalid", "by_code"):
            self.assertIn(k, body)
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["valid"], 1)
        self.assertEqual(body["invalid"], 0)
        self.assertEqual(body["by_code"], {})

    # ---- entry-count cap ----
    def test_entry_count_cap_zip(self):
        files = [("f%d.xml" % i, VALID_XML) for i in range(serve.Handler.MAX_ENTRIES + 1)]
        status, body = self.post("/validate-batch", make_zip(files))
        self.assertEqual(status, 413)
        self.assertIn("too many entries", body["error"])

    def test_entry_count_cap_json(self):
        payload = json.dumps(
            [{"name": "f%d.xml" % i, "xml": VALID_XML}
             for i in range(serve.Handler.MAX_ENTRIES + 1)]).encode("utf-8")
        status, body = self.post("/validate-batch", payload, "application/json")
        self.assertEqual(status, 413)
        self.assertIn("too many entries", body["error"])

    # ---- total uncompressed size cap (zip-bomb protection) ----
    def test_total_size_cap_zip(self):
        # Highly compressible payload: small on the wire, huge uncompressed.
        big = "<x>" + ("a" * (serve.Handler.MAX_TOTAL_UNCOMPRESSED + 1024)) + "</x>"
        z = make_zip([("big.xml", big)])
        self.assertLess(len(z), serve.MAX_BODY)  # fits under the body cap
        status, body = self.post("/validate-batch", z)
        self.assertEqual(status, 413)
        self.assertIn("uncompressed", body["error"])

    # ---- malformed body is a clear 4xx ----
    def test_garbage_body(self):
        status, body = self.post("/validate-batch", b"not a zip and not json")
        self.assertEqual(status, 400)
        self.assertIn("error", body)

    def test_json_not_array(self):
        status, body = self.post("/validate-batch", b'{"name":"x"}', "application/json")
        self.assertEqual(status, 400)

    def test_json_entry_missing_xml(self):
        payload = json.dumps([{"name": "x.xml"}]).encode("utf-8")
        status, body = self.post("/validate-batch", payload, "application/json")
        self.assertEqual(status, 400)

    # ---- backward-compat: /validate unchanged ----
    def test_validate_single_valid(self):
        status, body = self.post("/validate", VALID_XML.encode("utf-8"), "text/xml")
        self.assertEqual(status, 200)
        self.assertEqual(set(body.keys()), {"profile", "valid", "codes", "errors"})
        self.assertTrue(body["valid"])
        self.assertEqual(body["codes"], [])

    def test_validate_single_broken(self):
        status, body = self.post("/validate", BROKEN_XML.encode("utf-8"), "text/xml")
        self.assertEqual(status, 200)
        self.assertEqual(set(body.keys()), {"profile", "valid", "codes", "errors"})
        self.assertFalse(body["valid"])
        self.assertIn("BR-03a", body["codes"])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class RuleParityTest(unittest.TestCase):
    """The browser engine (index.html) and the Python CLI must agree on codes.

    Both surfaces advertise the same rule subset; a commercial tool must not
    return different verdicts depending on which surface the customer used.
    Requires Node + @xmldom/xmldom; skipped cleanly if unavailable.
    """

    @staticmethod
    def _node_available():
        import shutil
        if not shutil.which("node"):
            return False
        try:
            r = subprocess.run(["node", "-e", "require('@xmldom/xmldom')"],
                               capture_output=True, timeout=15)
            return r.returncode == 0
        except Exception:
            return False

    def test_browser_and_python_agree(self):
        import shutil
        if not self._node_available():
            self.skipTest("node/@xmldom not available")

        html = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
        m = re.search(r'<script>\n"use strict";(.*?)</script>', html, re.S)
        self.assertIsNotNone(m, "could not find the browser validator <script>")
        engine = os.path.join(HERE, "_engine_tmp.js")
        with open(engine, "w", encoding="utf-8") as fh:
            fh.write(m.group(1))

        harness = os.path.join(HERE, "_parity_tmp.mjs")
        with open(harness, "w", encoding="utf-8") as fh:
            fh.write(PARITY_HARNESS)
        try:
            for name, xml in (("valid.xml", VALID_XML), ("broken.xml", BROKEN_XML)):
                r = subprocess.run(
                    ["node", harness, engine, os.path.join(HERE, name)],
                    capture_output=True, text=True, timeout=60)
                self.assertEqual(r.returncode, 0,
                                 "node harness failed: %s\n%s" % (r.stdout, r.stderr))
                js_codes = json.loads(r.stdout.strip().splitlines()[-1])
                py = serve.validate(xml)
                py_codes = sorted({e["code"] for e in py["errors"]})
                self.assertEqual(sorted(js_codes), py_codes,
                                 "%s: browser=%s python=%s" % (name, sorted(js_codes), py_codes))
        finally:
            for p in (engine, harness):
                if os.path.exists(p):
                    os.remove(p)


PARITY_HARNESS = r'''
import { DOMParser } from '@xmldom/xmldom';
import fs from 'fs';
import vm from 'vm';
globalThis.DOMParser = DOMParser;
const fakeEl = () => new Proxy(function(){}, {
  get: (t,p) => {
    if (p === 'style') return {};
    if (p === 'classList') return { add(){}, remove(){}, toggle(){} };
    if (p === 'textContent' || p === 'value') return '';
    if (p === 'files') return [];
    if (p === 'addEventListener') return () => {};
    if (p === 'appendChild' || p === 'setAttribute' || p === 'removeAttribute') return () => {};
    return fakeEl();
  }, apply: () => fakeEl(),
});
const doc = { getElementById: () => fakeEl(), querySelector: () => fakeEl(),
  querySelectorAll: () => [], createElement: () => fakeEl(),
  addEventListener: () => {}, body: fakeEl(), documentElement: fakeEl() };
const nav = { clipboard: { writeText: async()=>{} } };
const sandbox = { DOMParser, document: doc, window: { addEventListener(){}, matchMedia:()=>({matches:false}) },
  navigator: nav, setTimeout: () => 0, console };
const ctx = vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), ctx);
const xml = fs.readFileSync(process.argv[3], 'utf8');
const r = ctx.validate(xml);
console.log(JSON.stringify([...new Set(r.errors.map(e => e.code))].sort()));
'''
