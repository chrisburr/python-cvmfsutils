# -*- coding: utf-8 -*-
"""
Tests for SHAKE128 content-hash support.
"""

import hashlib
import io
import unittest

import cvmfs
from cvmfs.catalog import CatalogReference
from cvmfs.root_file import parse_hash_string


class TestParseHashString(unittest.TestCase):
    def test_bare_hex_is_sha1(self):
        hex_digest, algo = parse_hash_string(
            "044206fcff4545283aaa452b80edfd5d8c740b20"
        )
        self.assertEqual(hex_digest, "044206fcff4545283aaa452b80edfd5d8c740b20")
        self.assertEqual(algo, "sha1")

    def test_shake128_suffix(self):
        hex_digest, algo = parse_hash_string(
            "ca091b24e7a2a466592a71511cf9f5fae04a7263-shake128"
        )
        self.assertEqual(hex_digest, "ca091b24e7a2a466592a71511cf9f5fae04a7263")
        self.assertEqual(algo, "shake128")

    def test_rmd160_suffix_is_recognised(self):
        # rmd160 is listed as recognised (no hashlib factory) so that manifests
        # using it parse without error even when we can't verify their signatures.
        hex_digest, algo = parse_hash_string(
            "0123456789abcdef0123456789abcdef01234567-rmd160"
        )
        self.assertEqual(algo, "rmd160")
        self.assertEqual(hex_digest, "0123456789abcdef0123456789abcdef01234567")

    def test_strips_surrounding_whitespace(self):
        hex_digest, algo = parse_hash_string(
            "  044206fcff4545283aaa452b80edfd5d8c740b20\n"
        )
        self.assertEqual(hex_digest, "044206fcff4545283aaa452b80edfd5d8c740b20")
        self.assertEqual(algo, "sha1")

    def test_rejects_short_hex(self):
        self.assertRaises(
            cvmfs.IncompleteRootFileSignature, parse_hash_string, "abcd"
        )

    def test_rejects_uppercase_hex(self):
        self.assertRaises(
            cvmfs.IncompleteRootFileSignature,
            parse_hash_string,
            "044206FCFF4545283AAA452B80EDFD5D8C740B20",
        )

    def test_rejects_unknown_algorithm(self):
        self.assertRaises(
            cvmfs.IncompleteRootFileSignature,
            parse_hash_string,
            "044206fcff4545283aaa452b80edfd5d8c740b20-md5",
        )

    def test_rejects_empty_hex_before_suffix(self):
        self.assertRaises(
            cvmfs.IncompleteRootFileSignature, parse_hash_string, "-shake128"
        )


class _StubManifest:
    def __init__(self, algorithm):
        self.hash_algorithm = algorithm


class _StubRepository:
    """Minimum surface of Repository needed to exercise hash_algo_infix."""

    def __init__(self, algorithm):
        self.manifest = _StubManifest(algorithm)

    # Borrow the real implementation so we're testing the code that ships.
    from cvmfs.repository import Repository

    hash_algo_infix = Repository.hash_algo_infix


class TestHashAlgoInfix(unittest.TestCase):
    def test_sha1_manifest_no_infix(self):
        repo = _StubRepository("sha1")
        self.assertEqual(repo.hash_algo_infix(), "")
        self.assertEqual(repo.hash_algo_infix("sha1"), "")

    def test_shake128_manifest_adds_infix(self):
        repo = _StubRepository("shake128")
        self.assertEqual(repo.hash_algo_infix(), "-shake128")

    def test_explicit_algorithm_overrides_manifest(self):
        repo = _StubRepository("shake128")
        self.assertEqual(repo.hash_algo_infix("sha1"), "")
        repo = _StubRepository("sha1")
        self.assertEqual(repo.hash_algo_infix("shake128"), "-shake128")

    def test_defaults_to_sha1_when_manifest_lacks_algorithm(self):
        class _EmptyManifest:
            pass

        repo = _StubRepository("sha1")
        repo.manifest = _EmptyManifest()
        self.assertEqual(repo.hash_algo_infix(), "")


class TestCatalogReferenceAlgorithm(unittest.TestCase):
    def test_default_algorithm_is_sha1(self):
        ref = CatalogReference("/sw", "044206fcff4545283aaa452b80edfd5d8c740b20")
        self.assertEqual(ref.algorithm, "sha1")

    def test_algorithm_preserved(self):
        ref = CatalogReference(
            "/.cvmfs",
            "b81dd6309454da7d3c88345e3425e452ea399c21",
            51200,
            "shake128",
        )
        self.assertEqual(ref.algorithm, "shake128")

    def test_retrieve_from_passes_algorithm(self):
        # Verify CatalogReference.retrieve_from forwards its algorithm to
        # Repository.retrieve_catalog, so mixed-mode repos route each nested
        # catalog through the correct CAS path.
        ref = CatalogReference("/x", "a" * 40, 0, "shake128")
        received = {}

        class _FakeRepo:
            def retrieve_catalog(self, catalog_hash, algorithm=None):
                received["hash"] = catalog_hash
                received["algorithm"] = algorithm
                return "catalog"

        self.assertEqual(ref.retrieve_from(_FakeRepo()), "catalog")
        self.assertEqual(received["hash"], "a" * 40)
        self.assertEqual(received["algorithm"], "shake128")


class TestMixedModeListNested(unittest.TestCase):
    """Nested catalog references may carry per-entry hash algorithms.

    When a repository is migrated from SHA-1 to SHAKE128 (e.g. ilc.desy.de),
    old nested catalogs keep a bare-hex value in the schema-named "sha1"
    column while new ones carry "<hex>-shake128". list_nested must parse
    each row independently so the CAS path is correct for every reference.
    """

    def _build_catalog(self, nested_rows):
        import os
        import sqlite3
        import tempfile

        fd, path = tempfile.mkstemp(suffix=".catalog")
        os.close(fd)
        conn = sqlite3.connect(path)
        conn.executescript(
            """
            CREATE TABLE properties (key TEXT, value TEXT);
            INSERT INTO properties VALUES ('schema', '2.5');
            INSERT INTO properties VALUES ('schema_revision', '7');
            INSERT INTO properties VALUES ('revision', '1');
            INSERT INTO properties VALUES ('last_modified', '1700000000');
            INSERT INTO properties VALUES ('root_prefix', '/');
            CREATE TABLE nested_catalogs (path TEXT, sha1 TEXT, size INTEGER);
            """
        )
        conn.executemany(
            "INSERT INTO nested_catalogs (path, sha1, size) VALUES (?, ?, ?)",
            nested_rows,
        )
        conn.commit()
        conn.close()
        self.addCleanup(os.remove, path)
        # Catalog takes a file object it can .name / .close.
        return cvmfs.Catalog(open(path, "rb"))

    def test_mixed_sha1_and_shake128_rows(self):
        catalog = self._build_catalog([
            ("/sw", "6cac522bbdb433fd9bbd7d22f3c607d45cd547c1", 4044800),
            ("/.cvmfs", "b81dd6309454da7d3c88345e3425e452ea399c21-shake128", 51200),
        ])
        refs = {r.root_path: r for r in catalog.list_nested()}
        self.assertEqual(
            refs["/sw"].hash, "6cac522bbdb433fd9bbd7d22f3c607d45cd547c1"
        )
        self.assertEqual(refs["/sw"].algorithm, "sha1")
        self.assertEqual(
            refs["/.cvmfs"].hash,
            "b81dd6309454da7d3c88345e3425e452ea399c21",
        )
        self.assertEqual(refs["/.cvmfs"].algorithm, "shake128")


class TestShake128Whitelist(unittest.TestCase):
    def _build_whitelist(self):
        body_lines = [
            b"20260422000000",
            b"E20260523000000",
            b"Nsoft.computecanada.ca",
            b"C1:2C:2F:7B:B6:8E:82:CF:50:8A:1D:2B:05:5F:14:1B:69:E6:44:E4",
        ]
        content = b"\n".join(body_lines) + b"\n"
        checksum = hashlib.shake_128(content).hexdigest(20) + "-shake128"
        return io.BytesIO(
            content + b"--\n" + checksum.encode() + b"\nSIGNATURE-BYTES"
        )

    def test_shake128_whitelist_parses(self):
        whitelist = cvmfs.Whitelist(self._build_whitelist())
        self.assertEqual(whitelist.repository_name, "soft.computecanada.ca")
        self.assertEqual(whitelist.signature_hash_algorithm, "shake128")
        self.assertTrue(whitelist.signature_checksum.endswith("-shake128"))
        self.assertEqual(whitelist.signature, b"SIGNATURE-BYTES")


if __name__ == "__main__":
    unittest.main()
