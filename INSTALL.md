# Install & Run — ublcheck

Validate EU e-invoice XML (EN 16931 / Peppol BIS / XRechnung / UBL) **offline, with no dependencies.**

Choose whichever path fits you.

---

## 1. Zero install (recommended for non-Python users)

Download `ublcheck.pyz` from the release bundle and run it directly — no `pip`, no
setup, no network. Needs only Python 3.8+ already on your machine.

```bash
python ublcheck.pyz invoice.xml
```

Machine-readable output (for CI / scripts):

```bash
python ublcheck.pyz --json invoice.xml
```

Exit codes: `0` = valid, `2` = rule violations found, `1` = usage/IO error.

**Verify your download first** (tamper check):

```bash
sha256sum -c SHA256SUMS
```

You should see `ublcheck.pyz: OK`.

---

## 2. Install from source with pip

If you use the Python ecosystem, install it as a real command:

```bash
pip install .
ublcheck invoice.xml
```

Or install straight from the repository:

```bash
pip install git+https://github.com/FopBop/ubl-invoice-validator
```

This installs a `ublcheck` console command. No third-party dependencies are pulled in.

---

## 3. Run the raw script

If you prefer zero packaging at all, just use the single source file:

```bash
python ublcheck.py invoice.xml
```

It is one file, standard library only — read it in five minutes.

---

## What it checks

The same rule set as the browser validator (`index.html`), including document-level
rules such as:

- **BR-01** CustomizationID / profile (BT-24)
- **BR-02** Invoice number (BT-1), non-empty
- **BR-03** Issue date (BT-2), `YYYY-MM-DD`
- **BR-04** Document currency code (BT-5)
- **BR-05** Seller party (BT-27)
- **BR-07** At least one invoice line (BG-25)
- **BR-08** LegalMonetaryTotal (BG-22) with document totals

Each violation is reported with a code and a concrete fix hint.

---

## Using it in CI

```yaml
- name: Validate invoices
  run: python ublcheck.pyz --json invoices/*.xml
```

A non-zero exit fails the build, so a malformed invoice never reaches an access point.
