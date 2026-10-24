# Issue #33 — reliable Stellar Testnet backup backreferences

**Status:** reproducible *local-byte* reference implemented; independent chain-authenticity proof and the meaning of “round 44 / Cassandra contrar” remain unresolved. This is research and an offline utility, **not** a deployed backup service or an assertion that older testnet data can always be recovered.

## Findings

1. A Stellar Testnet reset starts a new chain history and clears existing accounts, transactions, smart-contract state, and historical data from Stellar Core, Horizon, and Stellar RPC. Old transaction IDs or ledger numbers alone cannot identify an artifact across resets. [Stellar network documentation](https://developers.stellar.org/docs/networks#testnet-and-futurenet-data-reset)
2. Stellar's public AWS ledger data lake uses a **distinct prefix for each Testnet reset**: `s3://aws-public-blockchain/v1.1/stellar/ledgers/testnet/<reset-date>`. Some earlier prefixes lack `.config.json`; exporters may use `.xdr.zstd` rather than `.xdr.zst`. There is **no guarantee every historical range has been published**, and an archive's oldest available ledger must be checked. [Galexie data lake format](https://developers.stellar.org/docs/data/indexers/build-your-own/galexie/data-lake-format)
3. Galexie objects are Zstandard-compressed `LedgerCloseMetaBatch` XDR, with object-key ledger ranges and metadata identifying the network, ledger bounds, and protocol version. Consult the applicable `.config.json` before calculating a batch key, rather than assuming one fixed layout. [Galexie format and SEP-54 reference](https://developers.stellar.org/docs/data/indexers/build-your-own/galexie/data-lake-format)
4. **Object checksums are not proof of canonical Stellar history.** SEP-54's data format does not itself prove that records were closed by consensus; a separate trusted validator checkpoint/hash, verified replay, or comparable consensus-rooted evidence is required for that stronger claim. [Data integrity section](https://developers.stellar.org/docs/data/indexers/build-your-own/galexie/data-lake-format#data-integrity) · [Stellar Core history verification](https://github.com/stellar/stellar-core/blob/master/docs/quick-reference.md)
5. If independently archiving, node operators must not have multiple nodes publish to the *same* writable history archive; each publisher needs its own archive, with backfilling and verification managed separately. [Publishing history archives](https://developers.stellar.org/docs/validators/admin-guide/publishing-history-archives)

## Stable reference shape

Store the reference next to (or separately from) the actual exported bytes, **outside this public issue-tracker repository**. Never commit secrets, private keys, or potentially sensitive transaction datasets here. A minimum backreference records:

| Field | Purpose |
| --- | --- |
| `network_passphrase`, `network_id` | Distinguish Stellar Testnet from other networks |
| `reset_date` | Disambiguate identical ledger numbers across resets |
| `ledger_range.first` / `.last` | Identify the covered ledgers |
| `source_uri` | Record the exact object or original export location (optionally include S3 version ID elsewhere) |
| `artifact_sha256`, `artifact_size_bytes` | Detect byte changes to the *saved file* |
| `captured_at_utc` | Timestamp local capture, not necessarily the ledger-close time |
| External trusted checkpoint/ledger hash | **Still required** if asserting consensus authenticity, not supplied or checked by this utility |

The local SHA-256 should additionally be pinned somewhere independent and immutable or signed; otherwise an attacker who edits both artifact and manifest can forge their consistency.

## Offline helper (standard-library Python, no network access)

After obtaining an export from a **verified reset-specific path**, make a manifest for the exact compressed bytes you saved:

```sh
python3 tools/testnet_backref.py capture ./batch.xdr.zst \
  --reset-date YYYY-MM-DD \
  --source-uri 's3://aws-public-blockchain/v1.1/stellar/ledgers/testnet/YYYY-MM-DD/<partition>/<batch>.xdr.zst' \
  --first-ledger 2 --last-ledger 63 \
  --out ./batch.backref.json

python3 tools/testnet_backref.py verify ./batch.xdr.zst \
  --manifest ./batch.backref.json \
  --expected-sha256 '<digest-pinned-independently>'

python3 -m unittest discover -s tests -v
```

The ledger numbers and file name in this **illustrative** command are placeholders; derive them from the actual selected batch and configuration. The helper never downloads an object, decodes XDR, validates the ledger coverage, authenticates the source, signs the manifest, checks S3 versioning, or asserts a canonical chain. A successful run only verifies that locally stored file bytes agree with the manifest (and, if supplied, an independently obtained SHA-256).

## Further verification needed before calling this a reliable historical proof

- Resolve the target Testnet **reset date**, exact ledger/transaction range, and any requested “round 44” identifier. A round number must **not** silently be interpreted as a Stellar ledger sequence or checkpoint.
- Resolve what **“Cassandra contrar”** refers to: a named contract, a Cassandra-backed service, or something else. The issue text does not identify a verifiable claim of impossibility; no such claim is established here.
- Verify the target object actually exists in the specific reset prefix; independently capture the exact object key, ETag/version ID if applicable, and SHA-256. Note that an S3 ETag is **not reliably a SHA-256**.
- If the goal is legal/technical proof rather than repeatable bytes, obtain and cross-check an independently trusted ledger/checkpoint hash (and/or perform verified replay); retain evidence of validation.
- Test a real export and its decoded ledger bounds against the recorded manifest before using this for production-quality preservation. The included unit tests only exercise bytes and manifest validation.

## Primary references

- [Stellar network identities and reset semantics](https://developers.stellar.org/docs/networks)
- [Stellar Galexie data lake: key format, reset-specific prefixes, integrity limitation](https://developers.stellar.org/docs/data/indexers/build-your-own/galexie/data-lake-format)
- [Stellar validator history archive administration](https://developers.stellar.org/docs/validators/admin-guide/publishing-history-archives)
- [Stellar Core command-line history and archive verification](https://github.com/stellar/stellar-core/blob/master/docs/quick-reference.md)
- [Stellar Core archive configuration examples](https://github.com/stellar/stellar-core/blob/master/docs/stellar-core_example.cfg)
- [Stellar testnet/futurenet reset automation guide](https://developers.stellar.org/docs/build/guides/basics/automate-reset-data)
