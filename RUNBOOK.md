# RUNBOOK — EN 16931 / Peppol BIS 3.0 invoice validator

This tool checks a UBL or CII e-invoice against a subset of the **EN 16931** rule set
and the **Peppol BIS 3.0** profile. It reports machine-readable rule-violation codes.

Everything here runs at **$0** with **no external network calls** and **no third-party
dependencies** (Python 3 stdlib only).

---

## Surface 0 — Standalone bundle (`ublcheck.pyz`, zero install)

The release bundle `ublcheck-1.0.0-standalone.zip` is the zero-install path: it
needs only a Python 3.8+ interpreter already on the machine. No `pip`, no
`virtualenv`, no network at run time.

### Obtain

Download `ublcheck-1.0.0-standalone.zip`, then extract and verify it:

```bash
unzip ublcheck-1.0.0-standalone.zip -d ublcheck
cd ublcheck
sha256sum -c SHA256SUMS        # expect: ublcheck.pyz: OK
                               #         ublcheck-1.0.0-standalone.zip: OK
```

(The bundle ships `ublcheck.pyz`, `README.md`, `LICENSE`, `RUNBOOK.md`, and
`INSTALL.md`; `SHA256SUMS` is provided alongside the downloadable archives.)

### Run

```bash
python ublcheck.pyz invoice.xml            # human-readable summary + fixes
python ublcheck.pyz --json invoice.xml     # machine-readable JSON array
python ublcheck.pyz a.xml b.xml c.xml      # batch (worst exit code wins)
```

On a system where `python` maps to Python 3 this is exactly `python ublcheck.pyz …`;
on systems that only expose `python3`, substitute `python3`. The file is
executable and carries a `#!/usr/bin/env python3` shebang, so `./ublcheck.pyz
invoice.xml` also works.

### Interpret the exit code

| exit | meaning | what to do |
|---|---|---|
| `0` | **valid** — no rule violations | ship the invoice to the access point |
| `2` | **invalid** — one or more rule violations | read the printed `[CODE] fix_hint` lines and fix the XML |
| `1` | usage / I/O error (missing file, no arguments) | check the path and arguments |

A CI step can gate on this directly — a non-zero exit fails the build, so a
malformed invoice never reaches an access point:

```yaml
- run: python ublcheck.pyz --json invoices/*.xml
```

**Verified this cycle:** `python3 ublcheck.pyz tests/valid.xml` → exit `0`;
`python3 ublcheck.pyz tests/broken.xml` → exit `2` (codes `BR-03a`, `BR-04a`,
`BR-05`, `BR-06`, `BR-08a`, `BR-09`, `PEPPOL-001`). `sha256sum -c SHA256SUMS`
passes for both artifacts; the pyz extracted from the bundle runs identically.

---

## Surface 1 — Browser (no install)

There is a single self-contained page: `index.html`. Any modern browser with
`DOMParser` can run it.

1. Open `index.html` in a browser (double-click, or `file:///…/index.html`).
2. Paste invoice XML into the input box.
3. Click **Validate**.
4. Read the violations: each line is a rule code (`BR-03a`, `PEPPOL-001`, …), the
   XPath/JSON path of the offending element, and a one-line fix hint.

> **Honest limitation:** this sandbox has no headless browser and no jsdom, so the
> browser surface was *not* machine-verified here — it is verified by construction
> (same rule subset as the CLI) and must be confirmed by opening it once in a real
> browser. Do not claim browser-verified until a human or headless browser confirms it.

---

## Surface 2 — CLI (Python 3)

`ublcheck.py` implements the identical rule subset, stdlib-only.

```bash
python3 ublcheck.py invoice.xml          # human-readable; exit 0 = valid, 2 = violations
python3 ublcheck.py --json invoice.xml   # machine-readable JSON array
python3 ublcheck.py a.xml b.xml c.xml    # batch
```

**Verified this cycle:**

| fixture | command | valid | codes | exit |
|---|---|---|---|---|
| `tests/valid.xml`  | `python3 ublcheck.py tests/valid.xml`  | `true`  | `[]` | 0 |
| `tests/broken.xml` | `python3 ublcheck.py tests/broken.xml` | `false` | `BR-03a, BR-04a, BR-05, BR-08a, PEPPOL-001` | 2 |

`--json` emits:

```json
[
  {
    "file": "tests/broken.xml",
    "profile": "peppol-bis-3",
    "valid": false,
    "codes": ["BR-03a", "BR-04a", "BR-05", "BR-08a", "PEPPOL-001"],
    "errors": [ { "code": "…", "path": "…", "fix_hint": "…" }, … ]
  }
]
```

---

## Surface 3 — HTTP (for a stranger, no install)

`serve.py` wraps the CLI in a stdlib HTTP server.

```bash
PORT=8080 python3 serve.py
```

- `GET /` / `HEAD /`      → serves `index.html` (browser validator)
- `GET /health`            → `{"ok": true}`
- `POST /validate`         → body = invoice XML; returns `{profile, valid, codes, errors}`
- `POST /validate-batch`   → body is EITHER a ZIP archive of invoice XML files OR a
  JSON array of `{name, xml}` objects; returns an aggregate summary plus a
  per-invoice report (Pro-tier "bulk validation of an archive")
- Static assets (GET/HEAD): `robots.txt`, `sitemap.xml`, `site.webmanifest`,
  `og-image.png`, `favicon-32.png`, `apple-touch-icon.png`, and the
  `/golive/` pricing page. Served from the project root with a MIME allow-list
  and path-traversal protection; source files (`.py`) are never served.

```bash
curl -s -X POST --data-binary @invoice.xml http://localhost:8080/validate
curl -s -X POST --data-binary @invoices.zip http://localhost:8080/validate-batch
curl -s -X POST -H 'Content-Type: application/json' \
     --data-binary @invoices.json http://localhost:8080/validate-batch
```

`POST /validate-batch` request body — either form:

```jsonc
// ZIP: each file is one invoice, named by its archive path.
// JSON: an array of objects, one per invoice.
[ { "name": "a.xml", "xml": "<Invoice>…</Invoice>" }, … ]
```

`POST /validate-batch` response shape — the aggregate is exactly
`{total, valid, invalid, by_code}`, plus `results` (one per invoice):

```json
{
  "total": 2, "valid": 1, "invalid": 1,
  "by_code": { "BR-03a": 1, "BR-04a": 1, "PEPPOL-001": 1 },
  "results": [
    { "name": "good.xml", "valid": true,  "code": null,   "profile": "en16931",
      "codes": [], "errors": [] },
    { "name": "bad.xml",  "valid": false, "code": "BR-03a", "profile": "peppol-bis-3",
      "codes": ["BR-03a", "BR-04a", "PEPPOL-001"], "errors": [ … ] }
  ]
}
```

Each result carries `name` (the entry name), `valid`, and `code` (the primary/first
rule code, or `null` when valid); the full `codes`/`errors` arrays are included too.

Limits / safety caps (both input forms): ≤ 5 MB request body, ≤ **200** entries,
≤ **50 MB** total uncompressed size (zip-bomb protection). Over-limit requests are
rejected up-front with a `413` and a descriptive `{"error": …}` body; malformed
bodies get a `400`. Only the shared `validate()` used by `POST /validate` performs
the checks — no validation logic is duplicated.

The single-file `POST /validate` endpoint is unchanged (same request body and
same `{profile, valid, codes, errors}` response as before).

**Verified this cycle:** `tests/test_validate_batch.py` starts `serve.py`
on an ephemeral port and exercises both input forms end to end, and
`tests/test_http_edge.py` adds 31 routing/security/limit edge cases; the whole
115-test suite (`python3 -m unittest discover -s tests`) passes. A ZIP of `valid.xml` + `broken.xml` returns `total=2, valid=1, invalid=1`
with `by_code` counting the broken invoice's rule codes; the JSON-array form
returns the same aggregate; 201-entry and >50 MB-uncompressed requests are
rejected with `413`; and single-file `POST /validate` still returns the exact
same bytes as before the change (backward-compatible).

**Status:** VERIFIED this cycle. `serve.py` imports the verified `validate()`; both
`POST /validate` and `POST /validate-batch` were started locally and returned the
expected codes/aggregates (see the batch note above).

---

## Test suite (happy path + edge cases)

The product ships a **115-test**, stdlib-only automated suite. It deliberately
covers error handling and boundaries, not just the happy path:

```
python3 -m unittest discover -s tests -v
```

| File | Count | Focus |
| --- | --- | --- |
| `tests/test_ublcheck.py` | 57 | Every rule code, boundary values (VAT-id length, amount tolerance, currency case), profile detection, malformed/empty/oversized/entity-bomb XML, namespaces, helper units. |
| `tests/test_cli.py` | 15 | CLI exit codes 0/1/2, `--json` shape, missing files, directories, mixed inputs, and the shipped `ublcheck.pyz`. |
| `tests/test_http_edge.py` | 31 | Routing, HEAD, MIME allow-list, path-traversal protection, security headers, empty/oversized bodies, malformed ZIP/JSON, aggregate multiplicity. |
| `tests/test_validate_batch.py` | 12 | Batch endpoint integration + browser↔CLI rule parity (Node + `@xmldom/xmldom`; self-skips if absent). |

CI (`.github/workflows/ci.yml`) runs the full suite on Python 3.8/3.10/3.12 and
installs Node + `@xmldom/xmldom` so the parity test runs rather than skips.

---

## Presentation & hardening (commercial-quality pass)

Every `GET`/`HEAD` response now carries a baseline of production security headers,
emitted centrally by `Handler._security_headers()`:

- `Content-Security-Policy` — `default-src 'self'` with `object-src 'none'`,
  `frame-ancestors 'none'`, `base-uri 'self'`, `img-src 'self' data:` (the inline
  favicon), and `'unsafe-inline'` for style/script because the pages are
  deliberately self-contained (no external requests).
- `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: strict-origin-when-cross-origin`,
  `Permissions-Policy` (geo/mic/camera/payment disabled),
  `Cross-Origin-Opener-Policy` and `Cross-Origin-Resource-Policy`.

The landing page and pricing page also ship viewability/meta polish: `color-scheme`,
light/dark `theme-color`, `og:image:type` + `og:image:secure_url`, `twitter:image:alt`,
`application-name`, `apple-mobile-web-app-*`, `format-detection`, a keyboard
**skip-link**, a `WebSite` JSON-LD node (and a `BreadcrumbList` on `/golive/`), and a
tidy `sitemap.xml` (page URLs only). All pages parse with balanced tags and valid
JSON-LD.

**Verified this cycle:** started `serve.py` locally; `HEAD /` returns every header
above; `/`, `/golive/`, `/robots.txt`, `/sitemap.xml`, `/site.webmanifest` all 200;
unknown path with `Accept: text/html` returns the branded `404`; the full
115-test suite (`python3 -m unittest discover -s tests`) still passes,
including 31 HTTP edge-case tests in `tests/test_http_edge.py`.

---

## What this is NOT

- Not a full EN 16931 validator — a documented **subset** of rules.
- Free core; a Pro tier (hosted endpoint + bulk validation + support) is defined
  in `golive/1_commercial_model.md`. No paying customer yet.
- Not a swarm deliverable — do not spawn workers to re-derive these three commands.

## Rule codes seen in the bundled fixtures

`BR-03a` (IssueDate not ISO-8601) · `BR-04a` (currency not ISO-4217) ·
`BR-05` (missing seller name) · `BR-08a` (totals mismatch, BR-CO-13) ·
`PEPPOL-001` (missing seller contact e-mail, BT-41).

---

## Presentation polish — commercial-quality pass #2 (this cycle)

Focused on the three surfaces that make the product *presentable* rather than
functional-only, keeping every change self-contained (no external assets, CSP intact):

- **Homepage value proposition** — added a compact **"From rejected to accepted, in
  three steps"** band directly under the hero (`id="start"`): drop in → get exact rule
  codes → fix and re-run. A commercial visitor now sees the *outcome* before the tool.
  Nav label `How it works` renamed `Rules checked` so the two sections read distinctly.
- **Consistent social/SEO metadata across all pages.** The pricing page
  (`golive/index.html`) was shipping `twitter:card=summary` despite a 1200×630 OG
  image, and was missing `og:image:secure_url`, `og:locale`, `twitter:image:alt`,
  `apple-touch-icon`, and the 32px PNG favicon. All added; card is now
  `summary_large_image`.
- **The 404 page is now a real page, not a stub.** It gained a canonical URL, the full
  Open Graph + Twitter card set, light/dark `theme-color`, an `apple-touch-icon`/PNG
  favicon, and a **"Looking for something specific?"** quick-link row (validator, rules,
  FAQ, pricing) so a mistyped URL still routes the visitor to value.
- **`SET_SITE_URL.sh` now rewrites `404.html` too**, and its leftover-placeholder check
  covers every page. Verified: running it with a real origin leaves **zero**
  `invoice-validator.example` occurrences across the tree.

**Verified this cycle:** all three HTML pages parse with balanced tags and valid
JSON-LD (checked programmatically); `serve.py` returns `200` for `/` and `/golive/`,
`404` (branded, with the new quick-links) for an unknown path with `Accept: text/html`,
and the full security-header set on every response; the full suite
still passes **115/115**; `ublcheck.py tests/broken.xml` → exit 2, `tests/valid.xml` →
exit 0.
