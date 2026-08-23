# Roadmap

Direction, not promises — ordered by what makes the tool more trustworthy,
which beats making it bigger. Shaped substantially by early adopter feedback
(see [#1](https://github.com/sealandseacat/dbmask/issues/1) for the kind of
input that moves things here).

## Next (v0.2.x)

- **PostgreSQL & MySQL integration tests** in CI (testcontainers), turning
  "supported by construction" into "verified on every commit". SQL Server /
  Oracle in a nightly/manual matrix after that.
- **Run manifests**: record exactly what a run touched (tables, columns,
  strategies, row counts, config hash) → idempotency guards ("this target
  was already masked by run X"), resumability, and an audit artifact.
- **Detection benchmark**: a public, versioned dataset with per-rule
  precision/recall/F1 and published false-positive/negative examples, so
  detection quality is a measured number, not an adjective.
- **Stable public API**: a small `dbmask.scan() / apply() / verify()`
  surface with typed reports and a deprecation policy, so the library story
  stops leaning on internal modules.

## After that (v0.3.x)

- **Performance**: bulk seed-map lookups/writes, set-based updates
  (`executemany`), bounded parallelism per table.
- **Governance export**: publish classification results (column →
  sensitivity → rule → decision source) to OpenMetadata / DataHub, so
  dbmask's findings feed the catalogs organizations already run.
- **Locale packs**: dictionaries and patterns beyond the US-centric starter
  set.
- **Machine-readable audit reports** for scan/mask/validate in one schema.

## Toward 1.0

The bar 1.0 has to clear, in one sentence each:

- no known way to make the CLI write when it said it wouldn't;
- no path that reports success over unverified data;
- a documented threat model (see [Security model](security-model.md)) with
  the claims tested;
- integration tests against at least three real engines;
- a stable API under a deprecation policy;
- independent adopters on record ([ADOPTERS.md](https://github.com/sealandseacat/dbmask/blob/main/ADOPTERS.md)).

## How to influence this

Real-world reports beat feature ideas. The single most useful thing:
[adopter feedback](https://github.com/sealandseacat/dbmask/issues/new?template=adopter_feedback.yml)
from an actual attempt — including the attempt that made you pick a
different tool.
