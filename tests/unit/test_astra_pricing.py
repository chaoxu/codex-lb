from __future__ import annotations

import pytest

from app.core.usage.pricing import UsageTokens, calculate_cost_from_usage, get_pricing_for_model

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("tier", "input_tokens", "cached_tokens", "expected"),
    [
        (None, 100_000, 80_000, 0.33),
        ("default", 100_000, 80_000, 0.33),
        ("auto", 100_000, 80_000, 0.33),
        ("flex", 100_000, 80_000, 0.165),
        ("fast", 100_000, 80_000, 0.66),
        ("priority", 100_000, 80_000, 0.66),
        ("default", 272_000, 200_000, 0.97),
        ("default", 272_001, 200_000, 1.91502),
        ("default", 300_000, 200_000, 2.475),
        ("flex", 300_000, 200_000, 1.2375),
        ("fast", 300_000, 200_000, 4.95),
        ("priority", 300_000, 200_000, 4.95),
        (" FAST ", 300_000, 200_000, 4.95),
    ],
)
def test_astra_published_rates(tier, input_tokens, cached_tokens, expected):
    resolved = get_pricing_for_model("gpt-6-astra")
    assert resolved is not None
    canonical, price = resolved
    assert canonical == "gpt-6-astra"
    cost = calculate_cost_from_usage(
        UsageTokens(input_tokens=input_tokens, cached_input_tokens=cached_tokens, output_tokens=1_000),
        price,
        service_tier=tier,
    )
    assert cost == pytest.approx(expected)


def test_unknown_gpt6_model_is_not_assigned_astra_pricing():
    assert get_pricing_for_model("gpt-6-unknown") is None
