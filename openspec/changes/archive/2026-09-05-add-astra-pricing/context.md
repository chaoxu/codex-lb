# Astra cost diagnosis

Jupiter runs `codex-lb-local:5cb2e17383907448f4580ffd2a800d88c8f8ec0c`. A read of the deployed `/app/app/core/usage/pricing.py` confirmed that its catalog begins with GPT-5.6 and has no Astra entry. `calculated_cost_from_log` returns `None` when model resolution fails. The request-log writer persists that value, and aggregate queries sum the stored `cost_usd` column. Adding a model to the upstream model list does not update this static pricing catalog.

A read-only query on 2026-09-05 found 5,801 normal Standard Astra requests with recorded input/output usage and zero populated costs. Of these, 1,848 exceeded 272,000 input tokens. Applying the published input/cache-read/output rates to that snapshot gives USD 3,547.12. This is an API-equivalent token estimate, not a charge against pooled ChatGPT subscriptions. Traffic continued during inspection, so these figures are a snapshot. Prewarm rows were excluded from that estimate.

## Pricing sources and scope

Retrieved on 2026-09-05:

- https://developers.openai.com/api/docs/pricing
- https://developers.openai.com/api/docs/models/gpt-6-astra

Per million tokens, Astra Standard pricing is USD 10 uncached input, USD 1 cached input, and USD 50 output. Above 272,000 input tokens, the full request uses USD 20, USD 2, and USD 75. Fast doubles the applicable rates and Flex halves them. The current documented canonical snapshot is `gpt-6-astra`, so this change does not invent aliases for other GPT-6 models.

The existing usage schema records input, cached input, output, and reasoning tokens. It does not retain a separate cache-write token count. OpenAI also publishes a 1.25x cache-write rate. This patch restores the existing token-estimate accounting contract. Exact accounting for separately billed cache writes requires retaining that upstream usage detail first. Historical cache-write charges cannot be reconstructed from the current token columns.

## Historical repair requirements

The pricing patch changes new writes. Some request-log detail responses can compute a missing cost at read time, but aggregate readers use persisted costs. A historical repair must update the persisted Astra costs and their already-folded cost contributions together.

The production snapshot had a lifetime watermark at `2026-09-05 11:23:18.419876` and an hourly watermark at `2026-09-05 11:00:00`. Therefore the affected requests span both folded history and the live tail. Updating only raw rows would leave aggregate views inconsistent.

The repair must run in the documented release maintenance window against a consistent, protected backup on Jupiter. It must price only Astra rows with null costs and sufficient recorded usage, preserve explicit stored costs, and keep rows without usage nullable. It must preserve each consumer's existing warmup and deletion rules. Lifetime account totals deduplicate `(account_id, request_id, requested_at)` to the latest ID and exclude deleted rows. API-key lifetime totals do not deduplicate and include deleted rows. Both exclude warmups. The hourly and quarter-hour tables carry warmup and deletion dimensions. Their costs, and hourly `cost_count`, need matching deltas below their respective watermarks. Rows above those watermarks will be folded normally after repair.

Apply cost deltas to affected rollups rather than clearing all rollups: raw history may already have been pruned. Keep token/request counts unchanged. Any adjustment to active API-key cost-limit counters must respect the existing reset windows and integer-microdollar settlement semantics. Verify raw totals and all affected aggregate surfaces on a test database containing folded and unfolded rows before production repair. The historical repair is not implemented or applied by this change.

## Release status

Validation passed: 72 pricing and request-log API tests, Ruff lint and formatting, strict validation of this change, and all 57 main OpenSpec capabilities. Existing main-spec placeholder warnings are unrelated to this change.

The patch is based on the exact deployed source commit in a separate worktree. Production source, image, database, and Fleet image pins remain unchanged. Deployment follows `fleet-infra/apps/codex-lb/README.md`: build a pushed source commit on Jupiter, update the reviewed Fleet pin, and use the app release command with its database/key/image rollback procedure.
