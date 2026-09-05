from __future__ import annotations

import importlib
from datetime import datetime

import pytest
import sqlalchemy as sa

from app.db.models import Base

repair = importlib.import_module("app.db.alembic.versions.20260905_000000_backfill_astra_cost").repair
pytestmark = pytest.mark.integration
TABLES = (
    "account_usage_rollups",
    "api_key_usage_rollups",
    "request_usage_hourly_rollups",
    "request_demand_quarter_rollups",
)


@pytest.fixture
def seeded():
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        t = Base.metadata.tables
        conn.execute(
            t["account_usage_rollup_state"]
            .insert()
            .values(
                id=1,
                folded_through=datetime(2026, 9, 5, 11, 30),
                hourly_folded_through=datetime(2026, 9, 5, 11),
            )
        )
        base = dict(
            account_id="account",
            api_key_id="key",
            model="gpt-6-astra",
            service_tier="default",
            requested_at=datetime(2026, 9, 5, 10),
            status="success",
            request_kind="normal",
            input_tokens=100_000,
            cached_input_tokens=80_000,
            output_tokens=1_000,
        )
        changes = [
            {"request_id": "duplicate"},
            {"request_id": "duplicate"},
            {"service_tier": "fast", "input_tokens": 300_000, "cached_input_tokens": 200_000},
            {"deleted_at": datetime(2026, 9, 5, 12)},
            {"request_kind": "warmup"},
            {"requested_at": datetime(2026, 9, 5, 12)},
            {"requested_at": datetime(2026, 9, 5, 11)},
            {"requested_at": datetime(2026, 9, 5, 11, 30)},
            {"cost_usd": 7.0},
            {"input_tokens": None, "output_tokens": None},
            {"output_tokens": None, "reasoning_tokens": 1_000},
            {"model": "gpt-6-unknown"},
        ]
        for i, change in enumerate(changes, 1):
            conn.execute(t["request_logs"].insert().values(**(base | {"id": i, "request_id": str(i)} | change)))
        conn.execute(
            t["account_usage_rollups"].insert().values(account_id="account", total_cost_usd=123, request_count=42)
        )
        conn.execute(t["api_key_usage_rollups"].insert().values(api_key_id="key", total_cost_usd=234, request_count=43))
        epoch = int((datetime(2026, 9, 5, 10) - datetime(1970, 1, 1)).total_seconds())
        for tier, kind, deleted in [
            ("default", "normal", False),
            ("fast", "normal", False),
            ("default", "normal", True),
            ("default", "warmup", False),
        ]:
            dimensions = dict(
                account_id="account",
                api_key_id="key",
                model="gpt-6-astra",
                request_kind=kind,
                is_deleted=deleted,
                request_count=42,
                cost_usd=10,
            )
            conn.execute(
                t["request_usage_hourly_rollups"]
                .insert()
                .values(
                    **dimensions,
                    bucket_epoch=epoch,
                    service_tier=tier,
                    cost_count=5,
                )
            )
        # Demand groups have no service-tier dimension, so normal Fast and
        # Standard traffic share the same existing bucket.
        for kind, deleted in [("normal", False), ("normal", True), ("warmup", False)]:
            conn.execute(
                t["request_demand_quarter_rollups"]
                .insert()
                .values(
                    slot_epoch=epoch,
                    account_id="account",
                    api_key_id="key",
                    model="gpt-6-astra",
                    reasoning_effort="\x1f",
                    request_kind=kind,
                    status="success",
                    is_deleted=deleted,
                    request_count=42,
                    cost_usd=10,
                )
            )
    yield engine
    engine.dispose()


def snapshot(conn):
    return {
        name: [dict(row) for row in conn.execute(sa.select(Base.metadata.tables[name])).mappings()]
        for name in (*TABLES, "request_logs", "account_usage_rollup_state")
    }


def test_backfill_preserves_pruned_history_counts_and_watermarks(seeded):
    with seeded.begin() as conn:
        before = snapshot(conn)
        assert repair(conn) == 9
        after = snapshot(conn)
        assert after["account_usage_rollups"][0]["total_cost_usd"] == pytest.approx(123 + 6.27)
        assert after["api_key_usage_rollups"][0]["total_cost_usd"] == pytest.approx(234 + 6.93)
        hourly = after["request_usage_hourly_rollups"]
        assert sum(r["cost_usd"] for r in hourly) == pytest.approx(40 + 6.6)
        assert sum(r["cost_count"] for r in hourly) == 20 + 6
        assert sum(r["cost_usd"] for r in after["request_demand_quarter_rollups"]) == pytest.approx(30 + 6.6)
        for old, new in zip(before["request_logs"], after["request_logs"], strict=True):
            if old["id"] in (9, 10, 12):
                assert old["cost_usd"] == new["cost_usd"]
            else:
                assert new["cost_usd"] == pytest.approx(4.95 if old["id"] == 3 else 0.33)
        for name in before:
            for old, new in zip(before[name], after[name], strict=True):
                assert {k: v for k, v in old.items() if "cost" not in k} == {
                    k: v for k, v in new.items() if "cost" not in k
                }
        assert repair(conn) == 0
        assert snapshot(conn) == after


@pytest.mark.parametrize("failure", ["missing_bucket", "cost_limit"])
def test_backfill_failure_rolls_back(seeded, failure):
    with seeded.begin() as conn:
        if failure == "missing_bucket":
            conn.execute(Base.metadata.tables["request_demand_quarter_rollups"].delete())
        else:
            conn.execute(
                Base.metadata.tables["api_key_limits"]
                .insert()
                .values(
                    api_key_id="key",
                    limit_type="cost_usd",
                    limit_window="daily",
                    max_value=1000,
                    reset_at=datetime(2026, 9, 6),
                )
            )
        before = snapshot(conn)
    with pytest.raises(RuntimeError):
        with seeded.begin() as conn:
            repair(conn)
    with seeded.connect() as conn:
        assert snapshot(conn) == before


def test_backfill_preserves_already_priced_duplicate(seeded):
    with seeded.begin() as conn:
        logs = Base.metadata.tables["request_logs"]
        conn.execute(logs.update().where(logs.c.id == 2).values(cost_usd=9))
        assert repair(conn) == 8
        account = conn.execute(sa.select(Base.metadata.tables["account_usage_rollups"])).first()
        assert account.total_cost_usd == pytest.approx(123 + 5.94)
