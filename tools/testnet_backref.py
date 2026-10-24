#!/usr/bin/env python3
"""Create and check local, hash-bound references to Stellar Testnet exports.

This checks byte integrity, NOT whether an export belongs to canonical consensus.
"""

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

SCHEMA = "stellar-testnet-backref-v1"
PASSPHRASE = "Test SDF Network ; September 2015"
NETWORK_ID = hashlib.sha256(PASSPHRASE.encode("utf-8")).hexdigest()
HEX_SHA256 = re.compile(r"[a-f0-9]{64}\Z")


def file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_reset_date(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("reset date must be YYYY-MM-DD")
    dt.date.fromisoformat(value)
    return value


def make_manifest(artifact, reset_date, source_uri, first_ledger, last_ledger):
    validate_reset_date(reset_date)
    if first_ledger < 2 or last_ledger < first_ledger:
        raise ValueError("ledger range must be ordered and begin at ledger 2 or later")
    if not source_uri.strip():
        raise ValueError("source URI is required")
    path = Path(artifact)
    if not path.is_file():
        raise ValueError("artifact must be a regular file")
    return {
        "schema": SCHEMA,
        "network_passphrase": PASSPHRASE,
        "network_id": NETWORK_ID,
        "reset_date": reset_date,
        "ledger_range": {"first": first_ledger, "last": last_ledger},
        "source_uri": source_uri,
        "artifact_name": path.name,
        "artifact_size_bytes": path.stat().st_size,
        "artifact_sha256": file_digest(path),
        "captured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "verification_scope": "local byte integrity only; NOT consensus authenticity",
    }


def verify(artifact, manifest_path, expected_sha256=None):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise ValueError("unsupported manifest schema")
    if manifest.get("network_passphrase") != PASSPHRASE or manifest.get("network_id") != NETWORK_ID:
        raise ValueError("manifest network identity mismatch")
    validate_reset_date(manifest["reset_date"])
    bounds = manifest["ledger_range"]
    if (not isinstance(bounds["first"], int) or isinstance(bounds["first"], bool)
            or not isinstance(bounds["last"], int) or isinstance(bounds["last"], bool)
            or bounds["first"] < 2 or bounds["last"] < bounds["first"]):
        raise ValueError("invalid ledger range")
    if not isinstance(manifest.get("source_uri"), str) or not manifest["source_uri"].strip():
        raise ValueError("missing source URI")
    recorded = manifest.get("artifact_sha256")
    if not isinstance(recorded, str) or not HEX_SHA256.fullmatch(recorded):
        raise ValueError("invalid recorded digest")
    if expected_sha256 is not None:
        expected_sha256 = expected_sha256.lower()
        if not HEX_SHA256.fullmatch(expected_sha256) or recorded != expected_sha256:
            raise ValueError("manifest does not match independent expected SHA-256")
    path = Path(artifact)
    if path.stat().st_size != manifest.get("artifact_size_bytes"):
        raise ValueError("artifact size differs from manifest")
    if file_digest(path) != recorded:
        raise ValueError("artifact digest differs from manifest")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    capture = sub.add_parser("capture", help="Record a locally saved export's digest")
    capture.add_argument("artifact", type=Path)
    capture.add_argument("--reset-date", required=True)
    capture.add_argument("--source-uri", required=True)
    capture.add_argument("--first-ledger", type=int, required=True)
    capture.add_argument("--last-ledger", type=int, required=True)
    capture.add_argument("--out", type=Path, required=True)
    check = sub.add_parser("verify", help="Verify local bytes against a saved manifest")
    check.add_argument("artifact", type=Path)
    check.add_argument("--manifest", type=Path, required=True)
    check.add_argument("--expected-sha256", help="SHA-256 pinned separately from the manifest")
    args = parser.parse_args()
    try:
        if args.command == "capture":
            entry = make_manifest(args.artifact, args.reset_date, args.source_uri,
                                  args.first_ledger, args.last_ledger)
            # Prevent accidental overwrites of a prior record.
            with args.out.open("x", encoding="utf-8") as destination:
                json.dump(entry, destination, indent=2, sort_keys=True)
                destination.write("\n")
            print(f"Recorded SHA-256: {entry['artifact_sha256']}")
        else:
            entry = verify(args.artifact, args.manifest, args.expected_sha256)
            print(f"Byte integrity OK: {entry['artifact_sha256']}")
            print("This does not establish consensus authenticity.")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    main()
