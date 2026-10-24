"""Offline tests: python3 -m unittest discover -s tests -v"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import testnet_backref as backref  # noqa: E402


class TestBackref(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "batch.xdr.zst"
        self.path.write_bytes(b"fixture only, not valid Stellar XDR")
        self.manifest = Path(self.temp.name) / "reference.json"
        self.record = backref.make_manifest(self.path, "2026-08-14", "s3://example/testnet/2026-08-14/batch.xdr.zst", 2, 63)
        self.manifest.write_text(json.dumps(self.record), encoding="utf-8")

    def test_same_bytes_verify(self):
        self.assertEqual(backref.verify(self.path, self.manifest)["artifact_sha256"], backref.file_digest(self.path))

    def test_mutation_rejected(self):
        self.path.write_bytes(self.path.read_bytes() + b"x")
        with self.assertRaises(ValueError):
            backref.verify(self.path, self.manifest)

    def test_independent_digest_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            backref.verify(self.path, self.manifest, "0" * 64)

    def test_invalid_dates_and_ledger_ranges(self):
        for date in ("2026-02-30", "today", "2026-8-14"):
            with self.assertRaises(ValueError):
                backref.make_manifest(self.path, date, "source", 2, 3)
        for first, last in ((1, 2), (10, 9)):
            with self.assertRaises(ValueError):
                backref.make_manifest(self.path, "2026-08-14", "source", first, last)

    def test_wrong_network_rejected(self):
        self.record["network_id"] = "0" * 64
        self.manifest.write_text(json.dumps(self.record), encoding="utf-8")
        with self.assertRaises(ValueError):
            backref.verify(self.path, self.manifest)

    def test_digest_without_matching_bytes_rejected(self):
        self.record["artifact_sha256"] = "0" * 64
        self.manifest.write_text(json.dumps(self.record), encoding="utf-8")
        with self.assertRaises(ValueError):
            backref.verify(self.path, self.manifest)


if __name__ == "__main__":
    unittest.main()
