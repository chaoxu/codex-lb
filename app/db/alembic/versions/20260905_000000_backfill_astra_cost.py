"""Backfill Astra cost and folded cost measures without rebuilding history."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision = "20260905_000000_backfill_astra_cost"
down_revision = "20260827_000000_add_request_usage_tag"
branch_labels = None
depends_on = None

_EXCLUDED_KINDS = ("warmup", "limit_warmup")
_EPOCH = datetime(1970, 1, 1)


def _dimension(value: str | None) -> str:
    # Frozen encoding from usage_time_rollup.to_dimension.
    if value is None:
        return "\x1f"
    return "\x1f" + value if value.startswith("\x1f") else value


def _cost(row) -> float:
    # Frozen 2026-09-05 API-equivalent rates, excluding unrecorded cache writes.
    input_tokens = row.input_tokens
    cached = max(0, min(row.cached_input_tokens or 0, input_tokens))
    output = row.output_tokens if row.output_tokens is not None else row.reasoning_tokens
    input_rate, cached_rate, output_rate = (20, 2, 75) if input_tokens > 272_000 else (10, 1, 50)
    tier = (row.service_tier or "").strip().lower()
    multiplier = 2 if tier in ("fast", "priority") else 0.5 if tier == "flex" else 1
    return ((input_tokens - cached) * input_rate + cached * cached_rate + output * output_rate) / 1_000_000 * multiplier


def repair(bind: Connection) -> int:
    metadata = sa.MetaData()

    def table(name: str):
        return sa.Table(name, metadata, autoload_with=bind, resolve_fks=False)

    logs = table("request_logs")
    rows = bind.execute(
        sa.select(logs).where(
            logs.c.model == "gpt-6-astra",
            logs.c.model_source_id.is_(None),
            logs.c.cost_usd.is_(None),
            logs.c.input_tokens.is_not(None),
            sa.or_(logs.c.output_tokens.is_not(None), logs.c.reasoning_tokens.is_not(None)),
        )
    ).all()
    if not rows:
        return 0

    limits = table("api_key_limits")
    affected_keys = {row.api_key_id for row in rows if row.api_key_id is not None}
    if (
        affected_keys
        and bind.execute(
            sa.select(limits.c.id)
            .where(limits.c.api_key_id.in_(affected_keys), limits.c.limit_type == "cost_usd")
            .limit(1)
        ).first()
    ):
        raise RuntimeError("Astra backfill requires cost-limit settlement repair for affected API keys")

    state = table("account_usage_rollup_state")
    watermarks = bind.execute(sa.select(state).where(state.c.id == 1)).first()
    lifetime = watermarks.folded_through if watermarks else _EPOCH
    hourly = watermarks.hourly_folded_through if watermarks else _EPOCH
    # Account totals select the latest eligible duplicate, even when that row
    # is already priced or uses another model. API-key totals do not dedupe.
    account_ids = {row.account_id for row in rows if row.account_id is not None}
    latest_ids = (
        set(
            bind.execute(
                sa.select(sa.func.max(logs.c.id))
                .where(
                    logs.c.account_id.in_(account_ids),
                    logs.c.deleted_at.is_(None),
                    logs.c.request_kind.not_in(_EXCLUDED_KINDS),
                    logs.c.requested_at >= min(row.requested_at for row in rows),
                    logs.c.requested_at <= lifetime,
                )
                .group_by(logs.c.account_id, logs.c.request_id, logs.c.requested_at)
            ).scalars()
        )
        if account_ids
        else set()
    )

    deltas = defaultdict(lambda: [0.0, 0])

    def add(name: str, key: tuple, cost: float) -> None:
        delta = deltas[(name, key)]
        delta[0] += cost
        delta[1] += 1

    updates = []
    for row in rows:
        cost = _cost(row)
        updates.append({"row_id": row.id, "new_cost": cost})
        if row.requested_at <= lifetime and row.request_kind not in _EXCLUDED_KINDS:
            if row.id in latest_ids:
                add("account_usage_rollups", (row.account_id,), cost)
            if row.api_key_id is not None:
                add("api_key_usage_rollups", (row.api_key_id,), cost)
        if row.requested_at < hourly:
            epoch = int((row.requested_at - _EPOCH).total_seconds())
            account, key = _dimension(row.account_id), _dimension(row.api_key_id)
            deleted = row.deleted_at is not None
            add(
                "request_usage_hourly_rollups",
                (
                    epoch // 3600 * 3600,
                    account,
                    key,
                    row.model,
                    _dimension(row.service_tier),
                    row.request_kind,
                    deleted,
                ),
                cost,
            )
            add(
                "request_demand_quarter_rollups",
                (
                    epoch // 900 * 900,
                    account,
                    key,
                    row.model,
                    _dimension(row.reasoning_effort),
                    row.request_kind,
                    row.status,
                    deleted,
                ),
                cost,
            )

    for (name, key), (cost, count) in deltas.items():
        target = table(name)
        keys = list(target.primary_key.columns)
        column = "total_cost_usd" if name in ("account_usage_rollups", "api_key_usage_rollups") else "cost_usd"
        values = {column: target.c[column] + cost}
        if name == "request_usage_hourly_rollups":
            values["cost_count"] = target.c.cost_count + count
        result = bind.execute(
            target.update().where(*(column == value for column, value in zip(keys, key, strict=True))).values(**values)
        )
        if result.rowcount != 1:
            raise RuntimeError(f"Astra backfill expected one folded row in {name}")

    bind.execute(
        logs.update()
        .where(logs.c.id == sa.bindparam("row_id"), logs.c.cost_usd.is_(None))
        .values(cost_usd=sa.bindparam("new_cost")),
        updates,
    )
    return len(rows)


def upgrade() -> None:
    repair(op.get_bind())


def downgrade() -> None:
    # Keep repaired accounting on downgrade. Operational rollback restores the
    # consistent database backup together with its previous application image.
    pass
