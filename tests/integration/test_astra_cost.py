from __future__ import annotations

import pytest

from app.db.models import RequestLog
from app.db.session import SessionLocal
from app.modules.request_logs.repository import RequestLogsRepository

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tier", "input_tokens", "cached_tokens", "expected"),
    [("default", 100_000, 80_000, 0.33), ("fast", 300_000, 200_000, 4.95)],
)
async def test_astra_cost_persists_and_reaches_request_logs_api(
    async_client, db_setup, tier, input_tokens, cached_tokens, expected
):
    async with SessionLocal() as session:
        log = await RequestLogsRepository(session).add_log(
            account_id=None,
            request_id="astra-cost-regression",
            model="gpt-6-astra",
            service_tier=tier,
            input_tokens=input_tokens,
            cached_input_tokens=cached_tokens,
            output_tokens=1_000,
            latency_ms=100,
            status="success",
            error_code=None,
        )
        log_id = log.id

    async with SessionLocal() as session:
        stored = await session.get(RequestLog, log_id)
        assert stored is not None
        assert stored.cost_usd == pytest.approx(expected)

    response = await async_client.get("/api/request-logs?limit=1")
    assert response.status_code == 200
    row = response.json()["requests"][0]
    assert row["model"] == "gpt-6-astra"
    assert row["costUsd"] == pytest.approx(expected)
    assert row["costBreakdown"]["totalUsd"] == pytest.approx(expected)
