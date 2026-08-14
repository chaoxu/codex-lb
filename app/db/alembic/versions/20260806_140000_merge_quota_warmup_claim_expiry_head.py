"""merge quota warmup claim expiry head with current main

Revision ID: 20260806_140000_merge_quota_warmup_claim_expiry_head
Revises:
- 20260806_030000_add_quota_warmup_claim_expiry
- 20260806_000000_add_anonymous_telemetry
Create Date: 2026-08-06 14:00:00.000000

The quota warmup claim-expiry revision branched from
``20260806_020000_add_usage_history_bulk_covering_indexes``. Current main's
schema lineage has since converged through ``20260806_000000_add_anonymous_telemetry``.
Both sides are additive; this no-op merge records the convergence so startup and
deploy preflight see one canonical Alembic head.
"""

from __future__ import annotations

revision = "20260806_140000_merge_quota_warmup_claim_expiry_head"
down_revision = (
    "20260806_030000_add_quota_warmup_claim_expiry",
    "20260806_000000_add_anonymous_telemetry",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
