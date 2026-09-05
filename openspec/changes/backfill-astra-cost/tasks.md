## Implementation

- [x] Implement the migration with frozen Astra rates and aggregate deltas.
- [x] Test folded and live-tail rows, deduplication, deletion, tier boundaries, idempotence, and rollback on missing aggregates or cost-limit counters.
- [x] Validate migrations, pricing tests, and OpenSpec.
- [ ] Deploy the exact source and Fleet image pins through the app release command.
- [ ] Verify historical aggregate totals and newly recorded Astra costs on Jupiter.
