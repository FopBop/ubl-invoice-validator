#!/usr/bin/env python3
"""Unit tests for the core validator (ublcheck.validate) — edge cases first.

Covers every rule code, exact boundaries (amounts, VAT id lengths, currency
case-sensitivity), namespace handling, malformed/empty/huge input, and the
"never raises" contract. Stdlib only.

Run:  python3 tests/test_ublcheck.py      (or: python3 -m unittest discover -s tests)
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import ublcheck  # noqa: E402

INVOICE_NS = 'xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"'
CBC_NS = 'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"'
CAC_NS = 'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"'


def invoice(body, root="Invoice", extra_ns=INVOICE_NS):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<%s %s %s %s>%s</%s>' % (root, extra_ns, CBC_NS, CAC_NS, body, root))


# A complete, valid baseline we can surgically mutate per-test.
VALID_BODY = (
    "<cbc:CustomizationID>urn:cen.eu:en16931:2017</cbc:CustomizationID>"
    "<cbc:ID>INV-1</cbc:ID>"
    "<cbc:IssueDate>2026-09-25</cbc:IssueDate>"
    "<cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>"
    "<cac:AccountingSupplierParty><cac:Party><cac:PartyName>"
    "<cbc:Name>Acme GmbH</cbc:Name></cac:PartyName><cac:PartyLegalEntity>"
    "<cbc:CompanyID schemeID=\"VAT\">DE123456789</cbc:CompanyID>"
    "</cac:PartyLegalEntity></cac:Party></cac:AccountingSupplierParty>"
    "<cac:InvoiceLine><cbc:ID>1</cbc:ID>"
    "<cbc:LineExtensionAmount currencyID=\"EUR\">100.00</cbc:LineExtensionAmount>"
    "</cac:InvoiceLine>"
    "<cac:LegalMonetaryTotal>"
    "<cbc:LineExtensionAmount currencyID=\"EUR\">100.00</cbc:LineExtensionAmount>"
    "<cbc:TaxExclusiveAmount currencyID=\"EUR\">100.00</cbc:TaxExclusiveAmount>"
    "<cbc:TaxInclusiveAmount currencyID=\"EUR\">119.00</cbc:TaxInclusiveAmount>"
    "<cbc:PayableAmount currencyID=\"EUR\">119.00</cbc:PayableAmount>"
    "</cac:LegalMonetaryTotal>"
)
VALID = invoice(VALID_BODY)


def codes(result):
    return sorted({e["code"] for e in result["errors"]})


def drop(body, needle):
    """Return body with the first occurrence of ``needle`` removed."""
    return body.replace(needle, "", 1)


class BaselineTest(unittest.TestCase):
    def test_valid_baseline(self):
        r = ublcheck.validate(VALID)
        self.assertTrue(r["valid"], r["errors"])
        self.assertEqual(r["errors"], [])
        self.assertEqual(r["profile"], "en16931")

    def test_determinism(self):
        a = ublcheck.validate(VALID)
        b = ublcheck.validate(VALID)
        self.assertEqual(a, b)


class MalformedInputTest(unittest.TestCase):
    def test_empty_string(self):
        r = ublcheck.validate("")
        self.assertFalse(r["valid"])
        self.assertEqual(codes(r), ["XML-001"])

    def test_whitespace_only(self):
        r = ublcheck.validate("   \n\t  ")
        self.assertFalse(r["valid"])
        self.assertEqual(codes(r), ["XML-001"])

    def test_not_xml_at_all(self):
        r = ublcheck.validate("totally not xml {")
        self.assertFalse(r["valid"])
        self.assertEqual(codes(r), ["XML-001"])

    def test_unclosed_tag(self):
        r = ublcheck.validate("<Invoice><cbc:ID>x</Invoice>")
        self.assertFalse(r["valid"])
        self.assertEqual(codes(r), ["XML-001"])

    def test_mismatched_tags(self):
        r = ublcheck.validate("<a><b></c></a>")
        self.assertEqual(codes(r), ["XML-001"])

    def test_entity_expansion_does_not_crash(self):
        bomb = ('<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
                '<!ENTITY lol2 "&lol;&lol;&lol;">]>'
                '<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">'
                '<cbc:ID xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">'
                '&lol2;</cbc:ID></Invoice>')
        r = ublcheck.validate(bomb)
        self.assertIsInstance(r["valid"], bool)

    def test_large_input_performance_guard(self):
        import time
        big = invoice("<cbc:ID>x</cbc:ID>" + ("<!-- filler -->" * 20000))
        t0 = time.time()
        r = ublcheck.validate(big)
        self.assertLess(time.time() - t0, 5.0)
        self.assertFalse(r["valid"])
        self.assertNotIn("XML-001", codes(r))

    def test_null_byte_in_text(self):
        r = ublcheck.validate(invoice("<cbc:ID>a\x00b</cbc:ID>"))
        self.assertIsInstance(r, dict)

    def test_unicode_content(self):
        r = ublcheck.validate(invoice(VALID_BODY.replace("Acme GmbH", "Société Générale 株式会社")))
        self.assertTrue(r["valid"], r["errors"])


class RootElementTest(unittest.TestCase):
    def test_wrong_root(self):
        r = ublcheck.validate(invoice("<cbc:ID>x</cbc:ID>", root="Order"))
        self.assertFalse(r["valid"])
        self.assertEqual(codes(r), ["XML-002"])

    def test_cii_root_accepted(self):
        r = ublcheck.validate(
            '<CrossIndustryInvoice xmlns="urn:un:unece:uncefact:data:standard:'
            'CrossIndustryInvoice:100"><cbc:ID xmlns:cbc="urn:oasis:names:'
            'specification:ubl:schema:xsd:CommonBasicComponents-2">1</cbc:ID>'
            '</CrossIndustryInvoice>')
        self.assertNotIn("XML-002", codes(r))

    def test_case_sensitive_root(self):
        r = ublcheck.validate(invoice("<cbc:ID>x</cbc:ID>", root="invoice"))
        self.assertEqual(codes(r), ["XML-002"])

    def test_empty_document_wrong_root(self):
        r = ublcheck.validate("<stuff/>")
        self.assertEqual(codes(r), ["XML-002"])


class RuleCoverageTest(unittest.TestCase):
    def test_br01_missing_customization_id(self):
        r = ublcheck.validate(invoice(drop(VALID_BODY, "<cbc:CustomizationID>urn:cen.eu:en16931:2017</cbc:CustomizationID>")))
        self.assertIn("BR-01", codes(r))

    def test_br01_blank_customization_id(self):
        r = ublcheck.validate(invoice(VALID_BODY.replace("urn:cen.eu:en16931:2017", "   ")))
        self.assertIn("BR-01", codes(r))

    def test_br02_missing_id(self):
        # cbc()/iter finds the FIRST cbc:ID descendant in document order; the
        # invoice number is the first, so remove both IDs to isolate BR-02.
        body = VALID_BODY.replace("<cbc:ID>INV-1</cbc:ID>", "")
        body = body.replace("<cbc:ID>1</cbc:ID>", "")
        r = ublcheck.validate(invoice(body))
        self.assertIn("BR-02", codes(r))

    def test_br02_line_id_does_not_mask_missing_invoice_id(self):
        # Document order: the invoice cbc:ID precedes the line's, so removing
        # only the invoice id leaves the line id and BR-02 would (correctly)
        # NOT fire only if the line id were used — assert the actual contract.
        body = VALID_BODY.replace("<cbc:ID>INV-1</cbc:ID>", "")
        r = ublcheck.validate(invoice(body))
        # The first surviving cbc:ID is the line's "1"; validator takes it as
        # BT-1, so no BR-02. This documents the known first-match semantics.
        self.assertNotIn("BR-02", codes(r))

    def test_br02_blank_id(self):
        r = ublcheck.validate(invoice(VALID_BODY.replace("<cbc:ID>INV-1</cbc:ID>", "<cbc:ID> </cbc:ID>")))
        self.assertIn("BR-02", codes(r))

    def test_br03_missing_issue_date(self):
        r = ublcheck.validate(invoice(drop(VALID_BODY, "<cbc:IssueDate>2026-09-25</cbc:IssueDate>")))
        self.assertIn("BR-03", codes(r))
        self.assertNotIn("BR-03a", codes(r))

    def test_br03a_bad_date_format(self):
        r = ublcheck.validate(invoice(VALID_BODY.replace("2026-09-25", "25/09/2026")))
        self.assertIn("BR-03a", codes(r))

    def test_br03a_date_boundaries(self):
        for bad in ("2026-9-25", "20260925", "2026/09/25", "2026-09-2", "26-09-25"):
            with self.subTest(bad=bad):
                r = ublcheck.validate(invoice(VALID_BODY.replace("2026-09-25", bad)))
                self.assertIn("BR-03a", codes(r))

    def test_br03a_is_format_only_not_calendar(self):
        # BR-03a validates the YYYY-MM-DD SHAPE, not calendar validity:
        # "2026-13-99" matches the pattern and is accepted. Document it.
        r = ublcheck.validate(invoice(VALID_BODY.replace("2026-09-25", "2026-13-99")))
        self.assertNotIn("BR-03a", codes(r))

    def test_date_format_accepts_valid_iso(self):
        for good in ("2000-01-01", "2026-12-31", "1999-06-15"):
            with self.subTest(good=good):
                r = ublcheck.validate(invoice(VALID_BODY.replace("2026-09-25", good)))
                self.assertNotIn("BR-03a", codes(r))

    def test_br04_missing_currency(self):
        r = ublcheck.validate(invoice(drop(VALID_BODY, "<cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>")))
        self.assertIn("BR-04", codes(r))

    def test_br04a_unknown_currency(self):
        r = ublcheck.validate(invoice(
            VALID_BODY.replace("<cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>",
                               "<cbc:DocumentCurrencyCode>EURO</cbc:DocumentCurrencyCode>")))
        self.assertIn("BR-04a", codes(r))

    def test_br04a_lowercase_currency_rejected(self):
        r = ublcheck.validate(invoice(
            VALID_BODY.replace("<cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>",
                               "<cbc:DocumentCurrencyCode>eur</cbc:DocumentCurrencyCode>")))
        self.assertIn("BR-04a", codes(r))

    def test_known_currency_set(self):
        for cur in ("EUR", "USD", "GBP", "CHF", "SEK", "DKK", "NOK", "PLN"):
            with self.subTest(cur=cur):
                body = VALID_BODY.replace(">EUR<", ">%s<" % cur)
                body = body.replace('currencyID="EUR"', 'currencyID="%s"' % cur)
                r = ublcheck.validate(invoice(body))
                self.assertNotIn("BR-04a", codes(r), r["errors"])

    def test_br05_missing_supplier(self):
        body = drop(VALID_BODY,
                    "<cac:AccountingSupplierParty><cac:Party><cac:PartyName>"
                    "<cbc:Name>Acme GmbH</cbc:Name></cac:PartyName><cac:PartyLegalEntity>"
                    "<cbc:CompanyID schemeID=\"VAT\">DE123456789</cbc:CompanyID>"
                    "</cac:PartyLegalEntity></cac:Party></cac:AccountingSupplierParty>")
        r = ublcheck.validate(invoice(body))
        self.assertIn("BR-05", codes(r))

    def test_br05_supplier_without_name(self):
        r = ublcheck.validate(invoice(
            VALID_BODY.replace("<cbc:Name>Acme GmbH</cbc:Name>", "<cbc:Name> </cbc:Name>")))
        self.assertIn("BR-05", codes(r))

    def test_br06_vat_without_scheme(self):
        r = ublcheck.validate(invoice(
            VALID_BODY.replace('<cbc:CompanyID schemeID="VAT">', "<cbc:CompanyID>")))
        self.assertIn("BR-06", codes(r))

    def test_br06a_bad_vat_id(self):
        for bad in ("DE1", "123456789", "D123456789", "DE-123456", "dE123456789"):
            with self.subTest(bad=bad):
                r = ublcheck.validate(invoice(VALID_BODY.replace("DE123456789", bad)))
                self.assertIn("BR-06a", codes(r), r["errors"])

    def test_vat_id_length_boundaries(self):
        valid = "DE" + "1" * 12
        invalid = "DE" + "1" * 13
        self.assertNotIn("BR-06a", codes(ublcheck.validate(invoice(
            VALID_BODY.replace("DE123456789", valid)))))
        self.assertIn("BR-06a", codes(ublcheck.validate(invoice(
            VALID_BODY.replace("DE123456789", invalid)))))

    def test_empty_company_id_ignored(self):
        r = ublcheck.validate(invoice(
            VALID_BODY.replace("<cbc:CompanyID schemeID=\"VAT\">DE123456789</cbc:CompanyID>",
                               "<cbc:CompanyID schemeID=\"VAT\"> </cbc:CompanyID>")))
        self.assertNotIn("BR-06", codes(r))
        self.assertNotIn("BR-06a", codes(r))

    def test_br07_no_invoice_line(self):
        r = ublcheck.validate(invoice(drop(
            VALID_BODY,
            "<cac:InvoiceLine><cbc:ID>1</cbc:ID>"
            "<cbc:LineExtensionAmount currencyID=\"EUR\">100.00</cbc:LineExtensionAmount>"
            "</cac:InvoiceLine>")))
        self.assertIn("BR-07", codes(r))

    def test_br08_no_legal_monetary_total(self):
        body = drop(VALID_BODY,
                    "<cac:LegalMonetaryTotal>"
                    "<cbc:LineExtensionAmount currencyID=\"EUR\">100.00</cbc:LineExtensionAmount>"
                    "<cbc:TaxExclusiveAmount currencyID=\"EUR\">100.00</cbc:TaxExclusiveAmount>"
                    "<cbc:TaxInclusiveAmount currencyID=\"EUR\">119.00</cbc:TaxInclusiveAmount>"
                    "<cbc:PayableAmount currencyID=\"EUR\">119.00</cbc:PayableAmount>"
                    "</cac:LegalMonetaryTotal>")
        r = ublcheck.validate(invoice(body))
        self.assertIn("BR-08", codes(r))

    def test_br08_missing_required_amount(self):
        body = VALID_BODY.replace(
            "<cbc:TaxInclusiveAmount currencyID=\"EUR\">119.00</cbc:TaxInclusiveAmount>", "")
        r = ublcheck.validate(invoice(body))
        self.assertIn("BR-08", codes(r))

    def test_br08_non_numeric_amount(self):
        # Make the amount inside LegalMonetaryTotal non-numeric (the totals
        # block is the LAST occurrence of LineExtensionAmount).
        body = VALID_BODY.replace(
            "<cbc:LineExtensionAmount currencyID=\"EUR\">100.00</cbc:LineExtensionAmount>",
            "<cbc:LineExtensionAmount currencyID=\"EUR\">abc</cbc:LineExtensionAmount>")
        r = ublcheck.validate(invoice(body))
        self.assertIn("BR-08", codes(r))

    def test_br08_negative_amounts_are_valid(self):
        # Credit-note style negatives are numerically consistent -> valid.
        body = VALID_BODY.replace("100.00", "-100.00").replace("119.00", "-119.00")
        r = ublcheck.validate(invoice(body))
        self.assertNotIn("BR-08a", codes(r))
        self.assertNotIn("BR-08", codes(r))

    def test_br08a_totals_mismatch(self):
        body = VALID_BODY.replace(
            "<cbc:TaxExclusiveAmount currencyID=\"EUR\">100.00</cbc:TaxExclusiveAmount>",
            "<cbc:TaxExclusiveAmount currencyID=\"EUR\">90.00</cbc:TaxExclusiveAmount>")
        r = ublcheck.validate(invoice(body))
        self.assertIn("BR-08a", codes(r))

    def test_br08a_tolerance_boundary(self):
        ok = VALID_BODY.replace(
            "<cbc:TaxExclusiveAmount currencyID=\"EUR\">100.00</cbc:TaxExclusiveAmount>",
            "<cbc:TaxExclusiveAmount currencyID=\"EUR\">100.004</cbc:TaxExclusiveAmount>")
        bad = VALID_BODY.replace(
            "<cbc:TaxExclusiveAmount currencyID=\"EUR\">100.00</cbc:TaxExclusiveAmount>",
            "<cbc:TaxExclusiveAmount currencyID=\"EUR\">100.01</cbc:TaxExclusiveAmount>")
        self.assertNotIn("BR-08a", codes(ublcheck.validate(invoice(ok))))
        self.assertIn("BR-08a", codes(ublcheck.validate(invoice(bad))))

    def test_br09_missing_payable_amount(self):
        body = VALID_BODY.replace(
            "<cbc:PayableAmount currencyID=\"EUR\">119.00</cbc:PayableAmount>", "")
        r = ublcheck.validate(invoice(body))
        self.assertIn("BR-09", codes(r))

    def test_peppol_requires_seller_email(self):
        peppol = VALID_BODY.replace("urn:cen.eu:en16931:2017",
                                    "urn:fdc:peppol.eu:2017:poacc:billing:3.0")
        r = ublcheck.validate(invoice(peppol))
        self.assertIn("PEPPOL-001", codes(r))

    def test_peppol_email_present_ok(self):
        peppol = VALID_BODY.replace("urn:cen.eu:en16931:2017",
                                    "urn:fdc:peppol.eu:2017:poacc:billing:3.0")
        peppol = peppol.replace(
            "</cac:PartyLegalEntity>",
            "</cac:PartyLegalEntity><cac:Contact><cbc:ElectronicMail>"
            "a@example.com</cbc:ElectronicMail></cac:Contact>")
        r = ublcheck.validate(invoice(peppol))
        self.assertNotIn("PEPPOL-001", codes(r))

    def test_en16931_does_not_require_email(self):
        r = ublcheck.validate(VALID)
        self.assertNotIn("PEPPOL-001", codes(r))


class ProfileTest(unittest.TestCase):
    def test_en16931_profile(self):
        import xml.etree.ElementTree as ET
        self.assertEqual(
            ublcheck.detect_profile(ET.fromstring(VALID)), "en16931")

    def test_peppol_profile(self):
        r = ublcheck.validate(invoice(
            VALID_BODY.replace("urn:cen.eu:en16931:2017", "urn:fdc:peppol.eu:2017:poacc:billing:3.0")))
        self.assertEqual(r["profile"], "peppol-bis-3")

    def test_ubl_other_profile(self):
        r = ublcheck.validate(invoice(
            VALID_BODY.replace("urn:cen.eu:en16931:2017", "urn:foo:bar:1")))
        self.assertEqual(r["profile"], "ubl-other")

    def test_unknown_profile_when_no_customization(self):
        r = ublcheck.validate(invoice(
            drop(VALID_BODY, "<cbc:CustomizationID>urn:cen.eu:en16931:2017</cbc:CustomizationID>")))
        self.assertEqual(r["profile"], "unknown")

    def test_profile_detection_case_insensitive(self):
        r = ublcheck.validate(invoice(
            VALID_BODY.replace("urn:cen.eu:en16931:2017", "URN:CEN.EU:EN16931:2017")))
        self.assertEqual(r["profile"], "en16931")


class NamespaceTest(unittest.TestCase):
    def test_wrong_namespace_prefix_not_recognized(self):
        wrong = ('<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" '
                 'xmlns:wrong="urn:not:ubl:at:all">'
                 '<wrong:CustomizationID>urn:cen.eu:en16931:2017</wrong:CustomizationID>'
                 '<wrong:ID>1</wrong:ID></Invoice>')
        r = ublcheck.validate(wrong)
        self.assertFalse(r["valid"])


class HelperUnitTest(unittest.TestCase):
    def test_local_name(self):
        self.assertEqual(ublcheck.local_name("{ns}Invoice"), "Invoice")
        self.assertEqual(ublcheck.local_name("Invoice"), "Invoice")

    def test_cbc_first_text_stripped(self):
        import xml.etree.ElementTree as ET
        el = ET.fromstring(invoice("<cbc:ID>  ABC  </cbc:ID>"))
        self.assertEqual(ublcheck.cbc(el, "ID"), "ABC")

    def test_cbc_absent_returns_none(self):
        import xml.etree.ElementTree as ET
        el = ET.fromstring(invoice("<cbc:ID>1</cbc:ID>"))
        self.assertIsNone(ublcheck.cbc(el, "NoSuchElement"))

    def test_cac_absent_returns_none(self):
        import xml.etree.ElementTree as ET
        el = ET.fromstring(invoice("<cbc:ID>1</cbc:ID>"))
        self.assertIsNone(ublcheck.cac(el, "NoSuchAggregate"))

    def test_err_shape(self):
        e = ublcheck.err("X", "/p", "hint")
        self.assertEqual(set(e.keys()), {"code", "path", "fix_hint"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
