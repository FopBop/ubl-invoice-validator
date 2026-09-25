# EN 16931 / Peppol E-Invoice Validator

A tiny, dependency-free validator for **European e-invoicing** XML (EN 16931 / Peppol BIS subset).
No install. No network. Pure Python standard library.

## Why

If you send or receive EU e-invoices (Peppol, XRechnung, UBL), a malformed field means a
**rejected invoice** — a delayed payment. Commercial validators exist and are priced.
This one is free, offline, and small enough to read in five minutes.

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

## Scope

Implements a documented **subset** of the EN 16931 business rules and the Peppol BIS
billing rules that catch the most common rejection causes. It is a **linter, not a
certification body** — passing it does not guarantee acceptance by every access point.

## License

MIT — see `LICENSE`.
