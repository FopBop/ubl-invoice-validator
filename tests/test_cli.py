#!/usr/bin/env python3
"""CLI edge-case tests for ublcheck.py (and the zipapp entry point).

Verifies exit codes (0 valid / 2 violations / 1 usage-IO), --json shape,
missing/unreadable files, multiple files, and non-file arguments. Stdlib only.

Run:  python3 tests/test_cli.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CLI = os.path.join(ROOT, "ublcheck.py")
ZIPAPP = os.path.join(ROOT, "ublcheck.pyz")

VALID_XML = open(os.path.join(HERE, "valid.xml"), encoding="utf-8").read()
BROKEN_XML = open(os.path.join(HERE, "broken.xml"), encoding="utf-8").read()


def run(args, **kw):
    return subprocess.run([sys.executable, CLI] + args,
                          capture_output=True, text=True, timeout=60, **kw)


class CliExitCodeTest(unittest.TestCase):
    def test_no_args_is_usage_error(self):
        r = run([])
        self.assertEqual(r.returncode, 1)
        self.assertIn("usage", r.stderr.lower())

    def test_valid_exit_zero(self):
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as fh:
            fh.write(VALID_XML)
            p = fh.name
        try:
            r = run([p])
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("valid=true", r.stdout)
        finally:
            os.unlink(p)

    def test_broken_exit_two(self):
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as fh:
            fh.write(BROKEN_XML)
            p = fh.name
        try:
            r = run([p])
            self.assertEqual(r.returncode, 2)
            self.assertIn("valid=false", r.stdout)
        finally:
            os.unlink(p)

    def test_missing_file_exit_one(self):
        r = run(["/no/such/file-does-not-exist.xml"])
        self.assertEqual(r.returncode, 1)
        self.assertIn("not a file", r.stderr)

    def test_directory_arg_is_io_error(self):
        r = run([HERE])  # a directory, not a file
        self.assertEqual(r.returncode, 1)
        self.assertIn("not a file", r.stderr)

    def test_mix_missing_and_broken_worst_is_two(self):
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as fh:
            fh.write(BROKEN_XML)
            p = fh.name
        try:
            r = run(["/no/such/file.xml", p])
            self.assertEqual(r.returncode, 2)  # violations outrank IO error
        finally:
            os.unlink(p)

    def test_empty_file_is_xml_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as fh:
            p = fh.name
        try:
            r = run([p])
            self.assertEqual(r.returncode, 2)
            self.assertNotIn("Traceback", r.stderr)
        finally:
            os.unlink(p)


class CliJsonTest(unittest.TestCase):
    def test_json_shape(self):
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as fh:
            fh.write(VALID_XML)
            p = fh.name
        try:
            r = run(["--json", p])
            self.assertEqual(r.returncode, 0)
            data = json.loads(r.stdout)
            self.assertIsInstance(data, list)
            self.assertEqual(data[0]["file"], p)
            self.assertTrue(data[0]["valid"])
            self.assertEqual(data[0]["codes"], [])
        finally:
            os.unlink(p)

    def test_json_broken_exit_two(self):
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as fh:
            fh.write(BROKEN_XML)
            p = fh.name
        try:
            r = run(["--json", p])
            self.assertEqual(r.returncode, 2)
            data = json.loads(r.stdout)
            self.assertFalse(data[0]["valid"])
            self.assertIn("BR-03a", data[0]["codes"])
        finally:
            os.unlink(p)

    def test_json_missing_file_records_error(self):
        r = run(["--json", "/no/such/x.xml"])
        self.assertEqual(r.returncode, 1)
        data = json.loads(r.stdout)
        self.assertEqual(data[0]["error"], "not a file")

    def test_json_multiple_files_order_preserved(self):
        paths = []
        try:
            for xml in (VALID_XML, BROKEN_XML):
                fh = tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False)
                fh.write(xml)
                fh.close()
                paths.append(fh.name)
            r = run(["--json"] + paths)
            data = json.loads(r.stdout)
            self.assertEqual([d["file"] for d in data], paths)
            self.assertEqual([d["valid"] for d in data], [True, False])
            self.assertEqual(r.returncode, 2)
        finally:
            for p in paths:
                os.unlink(p)

    def test_flag_before_and_after_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as fh:
            fh.write(VALID_XML)
            p = fh.name
        try:
            self.assertEqual(run([p, "--json"]).returncode, 0)
            self.assertEqual(run(["--json", p]).returncode, 0)
        finally:
            os.unlink(p)


class ZipappCliTest(unittest.TestCase):
    """The shipped standalone .pyz must behave identically to the source CLI."""

    def setUp(self):
        if not os.path.exists(ZIPAPP):
            self.skipTest("ublcheck.pyz not built")

    def test_pyz_valid(self):
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as fh:
            fh.write(VALID_XML)
            p = fh.name
        try:
            r = subprocess.run([sys.executable, ZIPAPP, p],
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        finally:
            os.unlink(p)

    def test_pyz_broken_exit_two(self):
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as fh:
            fh.write(BROKEN_XML)
            p = fh.name
        try:
            r = subprocess.run([sys.executable, ZIPAPP, "--json", p],
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("BR-03a", r.stdout)
        finally:
            os.unlink(p)

    def test_pyz_no_args(self):
        r = subprocess.run([sys.executable, ZIPAPP],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
