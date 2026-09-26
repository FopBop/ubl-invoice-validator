#!/usr/bin/env python3
"""ublcheck — stdlib-only EN-16931 / UBL e-invoice validator CLI.

Single-surface parity: implements the SAME rule set as rules.js (index.html).
Usage:  ublcheck <file.xml> [...]
Exit:   0 = valid, 2 = rule violations found, 1 = usage/IO error.
No dependencies. Python 3.8+.
"""
import sys
import os
import re
import xml.etree.ElementTree as ET

CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
KNOWN_CURRENCIES = {"EUR", "USD", "GBP", "CHF", "SEK", "DKK", "NOK", "PLN"}
VAT_ID_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{2,12}$")


def _q(ns, name):
    return "{%s}%s" % (ns, name)


def cbc(el, name):
    """First text of a cbc:<name> descendant, stripped; None if absent."""
    found = el.iter(_q(CBC, name))
    for e in found:
        return (e.text or "").strip()
    return None


def cac(el, name):
    """First <name> aggregate descendant or None."""
    for e in el.iter(_q(CAC, name)):
        return e
    return None


def local_name(tag):
    if isinstance(tag, str) and tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def detect_profile(root):
    cid = (cbc(root, "CustomizationID") or "").lower()
    if "peppol" in cid:
        return "peppol-bis-3"
    if "en16931" in cid:
        return "en16931"
    if cid:
        return "ubl-other"
    return "unknown"


def err(code, path, fix_hint):
    return {"code": code, "path": path, "fix_hint": fix_hint}


def validate(xml_text):
    errors = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        return {"valid": False, "profile": "unknown",
                "errors": [err("XML-001", "/", "Document is not well-formed XML: %s" % str(exc)[:160])]}

    rn = local_name(root.tag)
    if rn not in ("Invoice", "CrossIndustryInvoice"):
        return {"valid": False, "profile": "unknown",
                "errors": [err("XML-002", "/", "Root element is '%s'; expected a UBL Invoice or CII CrossIndustryInvoice. Send UBL 2.1 Invoice XML." % rn)]}

    profile = detect_profile(root)

    if not cbc(root, "CustomizationID"):
        errors.append(err("BR-01", "/Invoice/cbc:CustomizationID",
                          "Add a CustomizationID (BT-24) naming the profile, e.g. 'urn:cen.eu:en16931:2017'."))
    if not cbc(root, "ID"):
        errors.append(err("BR-02", "/Invoice/cbc:ID", "Set the invoice number (BT-1), non-empty."))

    issue = cbc(root, "IssueDate")
    if not issue:
        errors.append(err("BR-03", "/Invoice/cbc:IssueDate", "Set the issue date (BT-2) as YYYY-MM-DD."))
    elif not re.match(r"^\d{4}-\d{2}-\d{2}$", issue):
        errors.append(err("BR-03a", "/Invoice/cbc:IssueDate", "IssueDate '%s' is not ISO YYYY-MM-DD." % issue))

    cur = cbc(root, "DocumentCurrencyCode")
    if not cur:
        errors.append(err("BR-04", "/Invoice/cbc:DocumentCurrencyCode", "Set DocumentCurrencyCode (BT-5)."))
    elif cur not in KNOWN_CURRENCIES:
        errors.append(err("BR-04a", "/Invoice/cbc:DocumentCurrencyCode",
                          "Currency '%s' is not an ISO-4217 code in the known set." % cur))

    seller = cac(root, "AccountingSupplierParty")
    if seller is None:
        errors.append(err("BR-05", "/Invoice/cac:AccountingSupplierParty", "Add the seller party (BT-27)."))
    else:
        names = [(e.text or "").strip() for e in seller.iter(_q(CBC, "Name"))]
        if not names or not names[0]:
            errors.append(err("BR-05", "/Invoice/cac:AccountingSupplierParty/.../cbc:Name", "Set the seller name."))
        # BR-06: a seller VAT/company identifier present but with no schemeID is
        # ambiguous (cannot tell BT-31 from BT-30); BR-06a: VAT id must be
        # country-prefix + alphanumeric (2 + 2..12). Mirrors the browser engine.
        for cid_el in seller.iter(_q(CBC, "CompanyID")):
            vat = (cid_el.text or "").strip()
            if not vat:
                continue
            scheme = cid_el.get("schemeID")
            if not scheme:
                errors.append(err("BR-06", "/Invoice/cac:AccountingSupplierParty/.../cbc:CompanyID",
                                  "Seller VAT id present but cbc:CompanyID has no schemeID attribute "
                                  "(needed to identify BT-31 vs BT-30)."))
            elif not VAT_ID_RE.match(vat):
                errors.append(err("BR-06a", "/Invoice/cac:AccountingSupplierParty/.../cbc:CompanyID",
                                  "VAT identifier '%s' must be country-prefix + alphanumeric "
                                  "(2 + 2..12 chars), e.g. 'DE123456789'." % vat))
            break

    if cac(root, "InvoiceLine") is None:
        errors.append(err("BR-07", "/Invoice/cac:InvoiceLine", "Add at least one InvoiceLine (BG-25)."))

    totals = cac(root, "LegalMonetaryTotal")
    if totals is None:
        errors.append(err("BR-08", "/Invoice/cac:LegalMonetaryTotal", "Add LegalMonetaryTotal (BG-22) with the document totals."))
    else:
        def amt(tag):
            for e in totals.iter(_q(CBC, tag)):
                try:
                    return float((e.text or "").strip())
                except ValueError:
                    return None
            return None
        line_ext = amt("LineExtensionAmount")
        tax_excl = amt("TaxExclusiveAmount")
        tax_incl = amt("TaxInclusiveAmount")
        if line_ext is None or tax_excl is None or tax_incl is None:
            errors.append(err("BR-08", "/Invoice/cac:LegalMonetaryTotal",
                              "LegalMonetaryTotal must include LineExtensionAmount (BT-106), "
                              "TaxExclusiveAmount (BT-109) and TaxInclusiveAmount (BT-112)."))
        elif abs(line_ext - tax_excl) > 0.005:
            errors.append(err("BR-08a", "/Invoice/cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount",
                              "TaxExclusiveAmount %s does not equal sum of line amounts %s "
                              "(difference %.4f). Recompute totals (BR-CO-13)."
                              % (tax_excl, line_ext, abs(line_ext - tax_excl))))
        # BR-09: a monetary total with no payable amount has no total due.
        payable = cbc(totals, "PayableAmount")
        if not payable:
            errors.append(err("BR-09", "/Invoice/cac:LegalMonetaryTotal/cbc:PayableAmount",
                              "Add PayableAmount (BT-115) so the invoice has a total due."))

    if seller is not None and profile == "peppol-bis-3":
        mails = [(e.text or "").strip() for e in seller.iter(_q(CBC, "ElectronicMail"))]
        if not mails or not mails[0]:
            errors.append(err("PEPPOL-001", "/Invoice/cac:AccountingSupplierParty/.../cbc:ElectronicMail",
                              "Peppol BIS 3.0 requires the seller contact e-mail (BT-41). Add Party/Contact/ElectronicMail."))

    return {"valid": len(errors) == 0, "profile": profile, "errors": errors}


def main(argv):
    args = argv[1:]
    as_json = "--json" in args
    files = [a for a in args if not a.startswith("-")]
    if not files:
        sys.stderr.write("usage: ublcheck [--json] <file.xml> [more.xml ...]\n")
        return 1
    if as_json:
        import json
        out = []
        worst = 0
        for path in files:
            if not os.path.isfile(path):
                out.append({"file": path, "error": "not a file"})
                worst = max(worst, 1)
                continue
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                r = validate(fh.read())
            out.append({"file": path, "profile": r["profile"], "valid": r["valid"],
                        "codes": sorted({e["code"] for e in r["errors"]}),
                        "errors": r["errors"]})
            if not r["valid"]:
                worst = max(worst, 2)
        print(json.dumps(out, indent=2))
        return worst
    worst = 0
    for path in files:
        if not os.path.isfile(path):
            sys.stderr.write("%s: not a file\n" % path)
            worst = max(worst, 1)
            continue
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            result = validate(fh.read())
        print("%s: profile=%s valid=%s" % (path, result["profile"], "true" if result["valid"] else "false"))
        for e in result["errors"]:
            print("  [%s] %s" % (e["code"], e["fix_hint"]))
        if not result["valid"]:
            worst = max(worst, 2)
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv))


def cli():
    """Console-script entry point for pip-installed `ublcheck`."""
    sys.exit(main(sys.argv))
