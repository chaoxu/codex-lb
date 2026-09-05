## Why

Astra usage recorded before the pricing fix has null costs. Its requests already contribute to lifetime and time-bucket aggregates, so repairing raw rows alone leaves dashboard totals inconsistent.

## What Changes

- Add a data migration that prices previously unpriced Astra rows and adds matching cost deltas to folded aggregates in the same transaction.
- Preserve existing costs, all token/request counts, and rollup history whose source rows have been pruned.
- Stop if affected API keys have cost-limit counters requiring a separate settlement repair.

## Impact

The app release's existing consistent backup and rollback procedure protects the migration. Rows with incomplete usage remain unpriced. No schema changes are required.
