## ADDED Requirements

### Requirement: Historical Astra costs are repaired atomically
The system SHALL backfill null costs for canonical Astra rows with recorded input and output or reasoning tokens using the published rates frozen at 2026-09-05. Existing non-null costs and rows without sufficient usage SHALL remain unchanged. The migration SHALL update folded lifetime account/API-key costs and hourly/quarter-hour cost measures in the same transaction, using their existing deduplication, deletion, warmup, and watermark semantics. Token counts, request counts, other models, and aggregate history without retained raw rows SHALL remain unchanged. Repeating the repair SHALL have no further effect.

#### Scenario: Folded history and live tail
- **WHEN** an unpriced Astra row is already folded into an aggregate
- **THEN** its cost delta SHALL be added to that aggregate and to its raw row atomically
- **AND** rows above the watermark SHALL be priced only in raw history until the normal fold runs

#### Scenario: Migration cannot safely repair all affected state
- **WHEN** an expected folded aggregate is missing or an affected key has a cost-limit counter
- **THEN** the migration SHALL fail and roll back all cost changes
