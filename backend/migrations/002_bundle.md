# Schema v2

v1 columns plus bundle export/import support. `migrate()` in scripts/seed_demo.py is idempotent: create_all, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, backfill.

- `datasets.content_hash` / `plans.content_hash` VARCHAR(64), indexed. SHA-256 of canonical executable content: datasets hash `{sensors, readings}`; plans hash `{steps, dataset content hash}`. Name/description/note are metadata, not identity. Maintained on every save; backfilled for pre-v2 rows at startup.
- `traces.source` VARCHAR(20) NOT NULL DEFAULT 'local': `local` | `imported`.
- `traces.import_key` VARCHAR(80), unique, nullable. Imported traces carry `bundle-v1:<trace checksum>`; re-importing the same package (retry or concurrent) finds the existing row and reuses it instead of duplicating.

Bundle import runs whole-package validation (structure, per-entry checksums, dependency closure, deterministic re-execution check) before a single transaction guarded by `pg_advisory_xact_lock`; the unique `import_key` is the backstop. Any failure rolls back — no partial archive is left behind.
