## 1. Contract and persistence

- [x] 1.1 Define the usage-tag header, grammar, and upstream privacy boundary.
- [x] 1.2 Add a nullable indexed `request_logs.usage_tag` column with an Alembic migration.

## 2. Proxy ingestion

- [x] 2.1 Validate and capture the usage tag on proxy requests.
- [x] 2.2 Persist the tag on successful, failed, retried, and cancelled request-log rows.
- [x] 2.3 Strip the tag from HTTP and WebSocket upstream headers.

## 3. Verification

- [x] 3.1 Add focused validation, persistence, and header-filtering tests.
- [x] 3.2 Prove the migration has a single-head upgrade and downgrade path.
- [x] 3.3 Run a disposable end-to-end proxy request and verify the database row and upstream header set.
- [x] 3.4 Complete independent correctness, security, migration, and simplicity reviews.
