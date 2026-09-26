# RUNBOOK — EN 16931 / Peppol BIS 3.0 invoice validator

This tool checks a UBL or CII e-invoice against a subset of the **EN 16931** rule set
and the **Peppol BIS 3.0** profile. It reports machine-readable rule-violation codes.

Everything here runs at **$0** with **no external network calls** and **no third-party
dependencies** (Python 3 stdlib only).

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

**Verified this cycle:** the new `tests/test_validate_batch.py` starts `serve.py`
on an ephemeral port and exercises both input forms end to end (all 11 assertions
pass). A ZIP of `valid.xml` + `broken.xml` returns `total=2, valid=1, invalid=1`
with `by_code` counting the broken invoice's rule codes; the JSON-array form
returns the same aggregate; 201-entry and >50 MB-uncompressed requests are
rejected with `413`; and single-file `POST /validate` still returns the exact
same bytes as before the change (backward-compatible).

**Status:** VERIFIED this cycle. `serve.py` imports the verified `validate()`; both
`POST /validate` and `POST /validate-batch` were started locally and returned the
expected codes/aggregates (see the batch note above).

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
