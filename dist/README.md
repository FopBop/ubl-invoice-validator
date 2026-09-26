# ublcheck — catch a rejected EU e-invoice *before* you send it

**A tiny, dependency-free validator for European e-invoicing XML (EN 16931 / Peppol BIS 3.0 / XRechnung / UBL).**
No install. No network. No upload. Pure Python standard library — small enough to read in five minutes.

```console
$ python3 ublcheck.pyz invoice.xml
invoice.xml: profile=peppol-bis-3 valid=false
  [BR-03a] IssueDate '25/09/2026' is not ISO YYYY-MM-DD.
  [BR-04a] Currency 'EURO' is not an ISO-4217 code in the known set.
  [BR-05]  Set the seller name.
  [BR-08a] TaxExclusiveAmount 90.0 does not equal sum of line amounts 100.0. Recompute totals (BR-CO-13).
  [PEPPOL-001] Peppol BIS 3.0 requires the seller contact e-mail (BT-41).
$ echo $?
2
```

That is the whole pitch: **run it before you send, and fix the field first.**

---

## The problem this solves

If you send or receive EU e-invoices — through Peppol, an access point, or a public-sector ERP — a single malformed field means a **rejected invoice**. A rejected invoice means a **delayed payment**, a manual reissue, and a phone call.

The commercial validators that catch these problems cost money, and most of them ask you to **upload your invoice to someone else's server** — which for many teams is a non-starter for financial documents.

`ublcheck` is the opposite of that:

| | `ublcheck` | Typical commercial validator |
|---|---|---|
| **Cost** | Free (MIT) | Priced / per-seat |
| **Data** | Never leaves your machine | Uploaded to their cloud |
| **Setup** | Zero install (one `.pyz` file) | Account, onboarding, SDK |
| **Dependencies** | Python stdlib only | Containers, services, keys |
| **Auditable** | One file, five-minute read | Black box |
| **Offline** | Yes, fully | No |

## Who it's for

You are a **developer, accountant, or ERP integrator** who sends or receives EU e-invoices (Peppol BIS, XRechnung, UBL, CII) and has had one rejected by an access point for a validation error — a delayed payment caused by a missing or malformed field.

You want the answer *now*, locally, without creating an account or uploading a customer's invoice to a third party.

## What it checks

`ublcheck` implements a documented **subset** of the EN 16931 business rules and the Peppol BIS 3.0 profile rules that catch the most common real-world rejection causes. Every violation is reported with a rule code, the path of the offending element, and a concrete **fix hint**.

| Code | Rule (business term) | What it catches |
|---|---|---|
| `XML-001` | Well-formed XML | Document is not parseable at all |
| `XML-002` | Root element | Not a UBL `Invoice` / CII `CrossIndustryInvoice` |
| `BR-01` | CustomizationID (BT-24) | Missing profile identifier |
| `BR-02` | Invoice number (BT-1) | Empty document ID |
| `BR-03` / `BR-03a` | Issue date (BT-2) | Missing, or not ISO `YYYY-MM-DD` |
| `BR-04` / `BR-04a` | Document currency (BT-5) | Missing, or not a known ISO-4217 code |
| `BR-05` | Seller party (BT-27) | Missing party, or empty seller name |
| `BR-06` / `BR-06a` | Seller VAT/company ID (BT-30/31) | Missing `schemeID`, or malformed VAT id |
| `BR-07` | Invoice lines (BG-25) | No invoice line present |
| `BR-08` / `BR-08a` | LegalMonetaryTotal (BG-22) | Missing totals, or `TaxExclusiveAmount` not equal to the sum of line amounts (BR-CO-13) |
| `BR-09` | PayableAmount (BT-115) | No total due |
| `PEPPOL-001` | Seller contact e-mail (BT-41) | Missing on Peppol BIS 3.0 documents |

The profile is auto-detected from `CustomizationID` (`peppol-bis-3`, `en16931`, or `ubl-other`), so Peppol-specific rules only fire when they apply.

> **Honest scope.** This is a **linter, not a certification body.** It implements a subset — the rules that catch the majority of rejections — and passing it does **not** guarantee acceptance by every access point. The full rule tables are public; read them alongside this tool.

---

## Use it three ways

### 1. In the browser — nothing leaves your machine

Open `index.html` in any modern browser, paste your invoice XML, and click **Validate**. The same rule engine runs client-side via `DOMParser` — your invoice never touches a server.

### 2. From the command line — one file, zero install

Download `ublcheck.pyz` from the release bundle and run it with any Python 3.8+:

```bash
python ublcheck.pyz invoice.xml          # human-readable summary + fix hints
python ublcheck.pyz --json invoice.xml   # machine-readable JSON array
python ublcheck.pyz a.xml b.xml c.xml    # batch — worst exit code wins
```

Exit codes are CI-friendly:

| exit | meaning | what to do |
|---|---|---|
| `0` | **valid** | ship it to the access point |
| `2` | **invalid** — rule violations found | read the `[CODE] fix_hint` lines and fix the XML |
| `1` | usage / I/O error | check the path and arguments |

### 3. Over HTTP — validate a stream or a whole batch

`serve.py` is a zero-dependency HTTP surface (stdlib `http.server`) for programmatic use:

```bash
python3 serve.py                          # listens on :8000
curl -s localhost:8000/health             # {"ok":true}
curl -s --data-binary @invoice.xml \
     localhost:8000/validate              # {"profile":...,"valid":...,"codes":[...],"errors":[...]}
```

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | Browser validator UI |
| `/health` | GET | Liveness probe. Returns `{"ok":true}` |
| `/validate` | POST | Validate one invoice (XML body) |
| `/validate-batch` | POST | Validate an archive (ZIP of XML) or a JSON array, with per-invoice reports |

`serve.py` also serves the static site (`index.html`, `robots.txt`, `sitemap.xml`, the pricing page under `/golive/`, and more) with path-traversal protection, a MIME allow-list, and production security headers (strict CSP, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, cross-origin isolation).

---

## Install

**Zero install (recommended).** Grab `ublcheck.pyz` from the release bundle and run it — no `pip`, no `virtualenv`, no network at run time. Only Python 3.8+ is needed.

```bash
sha256sum -c SHA256SUMS   # verify the download first -> "ublcheck.pyz: OK"
python ublcheck.pyz invoice.xml
```

**As a real command (pip).**

```bash
pip install .                                                     # from a checkout
pip install git+https://github.com/FopBop/ubl-invoice-validator   # or from the repo
ublcheck invoice.xml
```

This installs a `ublcheck` console entry point. **No third-party dependencies are pulled in.**

**Raw script.** If you prefer no packaging at all, run the single source file directly:

```bash
python3 ublcheck.py invoice.xml
```

Full step-by-step instructions, including download verification and CI setup, are in [`INSTALL.md`](INSTALL.md). Operator/deployment notes are in [`RUNBOOK.md`](RUNBOOK.md).

---

## Wire it into CI

A non-zero exit fails the build, so a malformed invoice never reaches an access point:

```yaml
- name: Validate all invoices
  run: python ublcheck.pyz --json invoices/*.xml
```

## Verified behavior

```
$ python3 ublcheck.py tests/valid.xml    # -> valid=true  ; exit 0
$ python3 ublcheck.py tests/broken.xml   # -> codes BR-03a BR-04a BR-05 BR-06 BR-08a BR-09 PEPPOL-001 ; exit 2
$ python3 tests/test_validate_batch.py   # -> Ran 11 tests ... OK
```

The `ublcheck.pyz` standalone bundle runs identically to the source script, and `sha256sum -c SHA256SUMS` passes for both release artifacts.

---

## Project layout

```
ublcheck.py     # the validator: rules + CLI (single file, stdlib only)
ublcheck.pyz    # zero-install standalone bundle of the above
serve.py        # zero-dependency HTTP surface + static file server
index.html      # browser validator (client-side, no upload)
golive/         # commercial model + hosted-pricing page (/golive/)
tests/          # valid.xml, broken.xml, batch CLI tests
INSTALL.md      # install & run instructions
RUNBOOK.md      # operator/deployment notes
SET_SITE_URL.sh # set the real site URL in canonical/OG/sitemap before go-live
```

## Reporting problems

Open a GitHub issue and attach the **rejected invoice XML** (redact customer data) plus the validator's exit code or error codes. That is the fastest path to a fix, and it tells us which business rules matter most in the wild. **Real rejected invoices are the single most useful thing you can send.**

## Commercial use

The core validator is **free and MIT-licensed** — CLI, library, browser tool, and HTTP surface. The free tier is the proof, not the product. If you would rather not run it yourself, hosted validation, bulk archive checks, on-prem deployment, and custom CIUS rule packs are described in [`golive/`](golive/) (Pro hosted API, Enterprise on-prem). No lock-in: the free CLI always works.

## License

MIT — see [`LICENSE`](LICENSE).
