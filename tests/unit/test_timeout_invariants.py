from __future__ import annotations

import logging

import pytest

from app.core.config.settings import Settings
from app.core.timeout_invariants import (
    TIMEOUT_INVARIANT_RULES,
    TimeoutInvariantError,
    find_timeout_invariant_violations,
    main,
    validate_runtime_timeout_invariants,
    validate_timeout_invariants,
)

pytestmark = pytest.mark.unit


def test_default_settings_satisfy_timeout_invariants() -> None:
    settings = Settings()
    assert len(TIMEOUT_INVARIANT_RULES) >= 20
    assert find_timeout_invariant_violations(settings) == []


def test_inverted_config_names_specific_rule() -> None:
    settings = Settings(proxy_request_budget_seconds=5.0)

    violations = find_timeout_invariant_violations(settings)

    assert any(violation.rule.id == "upstream-connect-within-proxy-budget" for violation in violations)
    formatted = "\n".join(violation.format() for violation in violations)
    assert "upstream-connect-within-proxy-budget" in formatted
    assert "upstream_connect_timeout_seconds=8" in formatted


def test_non_strict_startup_validation_logs_critical(caplog: pytest.LogCaptureFixture) -> None:
    settings = Settings(proxy_request_budget_seconds=5.0)

    with caplog.at_level(logging.CRITICAL, logger="app.core.timeout_invariants"):
        violations = validate_runtime_timeout_invariants(settings)

    assert violations
    assert "timeout invariant violation: upstream-connect-within-proxy-budget" in caplog.text


def test_strict_mode_raises() -> None:
    settings = Settings(
        proxy_request_budget_seconds=5.0,
        timeout_invariant_validation_strict=True,
    )

    with pytest.raises(TimeoutInvariantError) as exc_info:
        validate_runtime_timeout_invariants(settings)

    assert "upstream-connect-within-proxy-budget" in str(exc_info.value)


def test_explicit_strict_validation_raises() -> None:
    settings = Settings(proxy_request_budget_seconds=5.0)

    with pytest.raises(TimeoutInvariantError, match="upstream-connect-within-proxy-budget"):
        validate_timeout_invariants(settings, strict=True, log=False)


def test_ci_entrypoint_accepts_defaults(capsys: pytest.CaptureFixture[str]) -> None:
    assert main() == 0
    captured = capsys.readouterr()
    assert "timeout invariant rules satisfied" in captured.out
