# EN 16931 / Peppol E-Invoice Validator

A tiny, dependency-free validator for **European e-invoicing** XML (EN 16931 / Peppol BIS subset).
No install. No network. Pure Python standard library.

## Why

If you send or receive EU e-invoices (Peppol, XRechnung, UBL), a malformed field means a
**rejected invoice** — a delayed payment. Commercial validators exist and are priced.
This one is free, offline, and small enough to read in five minutes.

## Who this is for

You are a developer, accountant, or ERP integrator who sends or receives EU e-invoices
(Peppol BIS, XRechnung, UBL) and has had one **rejected by an access point** for a
validation error — a delayed payment caused by a missing or malformed field.

## The failure it prevents

A rejected invoice stalls payment. Commercial validators catch the problem but cost money
and often require uploading your invoice to someone else's server. This tool is free,
offline, and readable in five minutes — run it before you send, and fix the field first.

## Reporting problems

Open a GitHub issue and attach the **rejected invoice XML** (redact customer data) plus the
validator's exit code or error codes. That is the fastest path to a fix, and it tells us
which business rules matter most in the wild. Real rejected invoices are the single most
useful thing you can send.

**Note:** this is a linter, not a certification body. Passing it does not guarantee
acceptance by every access point.

## Use it three ways

**Browser** — open `index.html`, paste an invoice, see the error codes. Nothing leaves your machine.

**CLI**
```
python3 ublcheck.py invoice.xml
# exit 0 = valid ; exit 2 = invalid, with codes like BR-03a, BR-04a, PEPPOL-001
```

**HTTP**
```
python3 serve.py            # listens on :8000
curl -s localhost:8000/health          # {"ok":true}
curl -s --data-binary @invoice.xml localhost:8000/validate
```

## Verified

```
$ python3 ublcheck.py tests/broken.xml   # -> BR-03a BR-04a BR-05 BR-08a PEPPOL-001 ; exit 2
$ python3 ublcheck.py tests/valid.xml    # -> valid ; exit 0
```

## Site & discoverability

The browser tool (`index.html`) ships with search- and answer-engine readiness:
a descriptive `<title>`/meta description, Open Graph and Twitter card tags with a
1200×630 share image, JSON-LD (`SoftwareApplication` + `FAQPage`), `robots.txt`
(including explicit GEO/answer-engine allowances), a `sitemap.xml`, and a web app
manifest. The hosted pricing page lives at `golive/index.html` (`/golive/`).

`serve.py` serves these assets for `GET`/`HEAD` alongside the validator UI, so a
single process is enough to run the whole site.

## Scope

Implements a documented **subset** of the EN 16931 business rules and the Peppol BIS
billing rules that catch the most common rejection causes. It is a **linter, not a
certification body** — passing it does not guarantee acceptance by every access point.

## License

MIT — see `LICENSE`.
