# Verified Astra historical repair

The implementation uses SQLAlchemy inside the application's Alembic migration transaction. It freezes the 2026-09-05 input/cache-read/output rates, adds only missing costs, and applies grouped deltas to lifetime account/API-key totals and hourly/quarter-hour cost measures. The migration preserves counts and historical contributions whose raw rows have been pruned. It refuses affected API-key cost limits because replaying their settlement windows requires a separate repair. Jupiter had none at preflight and migration time.

Validation passed: 103 tests, with five PostgreSQL-only tests skipped on SQLite. Coverage includes tier and threshold pricing, persisted API costs, migration policy and schema drift, duplicate selection, warmup and deletion rules, both watermark boundaries, idempotence, and transaction rollback after a missing aggregate. Ruff lint and formatting passed. Strict OpenSpec validation passed.

Jupiter activated source commit `068dd6905936b3b008fbf6026795587770df7da7` through Fleet commit `25ca68e7e4645ea3d9412b1d039dfd636167a1f3` on 2026-09-05. The exact image ID is `sha256:c81189056cb94e52459c52ef04077744ca68c8cbb0d797315e3cb2b733ee1fb1`, and the active Alembic revision is `20260905_000000_backfill_astra_cost`.

Read-only comparison against the protected pre-release backup found 6,488 repaired rows and USD 3,674.358348 restored. Zero repair candidates remained unpriced, zero existing populated costs changed, and zero affected usage-token fields changed. All eight affected account totals and the affected API-key total matched the expected deltas with unchanged counts. Hourly costs matched retained Astra rows within floating-point tolerance (absolute difference below 1e-12), with matching cost counts. Quarter-hour costs matched exactly. All three fresh requests with usage at the verification snapshot had populated costs.

The protected rollback directory remains on Jupiter at `/srv/codex-lb-rollback/20260905T134642569Z-ixEFvA`. The app release command verified the image, migration, unchanged encryption key, and HTTPS route. HTTP reachability is 200. The browser requires admin sign-in, so the rendered dashboard totals were not visually verified. The historical and live database values supporting those totals were verified directly.

Prices remain API-equivalent estimates under the existing accounting contract. Separate cache-write tokens were not retained in historical rows and cannot be reconstructed by this repair.
