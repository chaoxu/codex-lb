from __future__ import annotations

import logging
import operator
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


class TimeoutSettings(Protocol):
    upstream_connect_timeout_seconds: float
    proxy_request_budget_seconds: float
    http_responses_stream_request_budget_seconds: float
    compact_request_budget_seconds: float
    stream_idle_timeout_seconds: float
    sse_keepalive_interval_seconds: float
    token_refresh_timeout_seconds: float
    token_refresh_claim_ttl_seconds: float
    usage_fetch_timeout_seconds: float
    usage_refresh_interval_seconds: int
    rate_limit_reset_credits_refresh_interval_seconds: int
    http_responses_session_bridge_request_budget_seconds: float
    http_responses_session_bridge_idle_ttl_seconds: float
    http_responses_session_bridge_codex_idle_ttl_seconds: float
    http_responses_session_bridge_stuck_gate_retire_after_seconds: float
    http_responses_session_bridge_clean_close_retry_jitter_max_seconds: float
    proxy_admission_wait_timeout_seconds: float
    proxy_account_lease_ttl_seconds: float
    proxy_refresh_failure_cooldown_seconds: float
    timeout_invariant_validation_strict: bool


@dataclass(frozen=True, slots=True)
class TimeoutOperand:
    label: str
    evaluate: Callable[[TimeoutSettings], float]
    code_anchor: str


@dataclass(frozen=True, slots=True)
class TimeoutInvariantRule:
    id: str
    lhs: TimeoutOperand
    relation: str
    rhs: TimeoutOperand
    rationale: str


@dataclass(frozen=True, slots=True)
class TimeoutInvariantViolation:
    rule: TimeoutInvariantRule
    lhs_value: float
    rhs_value: float

    def format(self) -> str:
        return (
            f"{self.rule.id}: {self.rule.lhs.label}={self.lhs_value:g} "
            f"{self.rule.relation} {self.rule.rhs.label}={self.rhs_value:g} violated; "
            f"{self.rule.rationale} "
            f"(lhs: {self.rule.lhs.code_anchor}; rhs: {self.rule.rhs.code_anchor})"
        )


class TimeoutInvariantError(RuntimeError):
    def __init__(self, violations: Sequence[TimeoutInvariantViolation]) -> None:
        self.violations = tuple(violations)
        super().__init__("\n".join(violation.format() for violation in self.violations))


def _field(name: str, anchor: str) -> TimeoutOperand:
    return TimeoutOperand(name, lambda settings: float(getattr(settings, name)), anchor)


def _expr(label: str, anchor: str, evaluate: Callable[[TimeoutSettings], float]) -> TimeoutOperand:
    return TimeoutOperand(label, evaluate, anchor)


UPSTREAM_CONNECT = _field("upstream_connect_timeout_seconds", "app/core/clients/proxy.py:318")
PROXY_BUDGET = _field("proxy_request_budget_seconds", "app/core/config/settings.py:260")
STREAM_BUDGET = _field(
    "http_responses_stream_request_budget_seconds",
    "app/modules/proxy/_service/streaming/helpers.py:724",
)
COMPACT_BUDGET = _field("compact_request_budget_seconds", "app/modules/proxy/_service/compact.py:585")
STREAM_IDLE = _field("stream_idle_timeout_seconds", "app/modules/proxy/_service/streaming/retry.py:188")
SSE_KEEPALIVE = _field("sse_keepalive_interval_seconds", "app/modules/proxy/api.py:3930")
TOKEN_REFRESH = _field("token_refresh_timeout_seconds", "app/modules/accounts/auth_manager.py:1123")
TOKEN_CLAIM_TTL = _field("token_refresh_claim_ttl_seconds", "app/core/config/settings.py:660")
USAGE_FETCH = _field("usage_fetch_timeout_seconds", "app/core/clients/usage.py:75")
USAGE_REFRESH_INTERVAL = _field("usage_refresh_interval_seconds", "app/core/usage/refresh_scheduler.py:282")
RESET_CREDITS_INTERVAL = _field(
    "rate_limit_reset_credits_refresh_interval_seconds",
    "app/core/usage/reset_credits_refresh_scheduler.py:388",
)
BRIDGE_BUDGET = _field(
    "http_responses_session_bridge_request_budget_seconds",
    "app/modules/proxy/_service/http_bridge/helpers.py:2469",
)
BRIDGE_IDLE_TTL = _field(
    "http_responses_session_bridge_idle_ttl_seconds",
    "app/modules/proxy/_service/http_bridge/helpers.py:2458",
)
BRIDGE_CODEX_IDLE_TTL = _field(
    "http_responses_session_bridge_codex_idle_ttl_seconds",
    "app/modules/proxy/_service/http_bridge/session_registry.py:151",
)
BRIDGE_STUCK_GATE_RETIRE = _field(
    "http_responses_session_bridge_stuck_gate_retire_after_seconds",
    "app/modules/proxy/service.py:1317",
)
BRIDGE_CLEAN_CLOSE_JITTER = _field(
    "http_responses_session_bridge_clean_close_retry_jitter_max_seconds",
    "app/modules/proxy/_service/http_bridge/request_submit.py:294",
)
ADMISSION_WAIT = _field("proxy_admission_wait_timeout_seconds", "app/modules/proxy/service.py:768")
ACCOUNT_LEASE_TTL = _field("proxy_account_lease_ttl_seconds", "app/modules/proxy/load_balancer.py:1846")
REFRESH_FAILURE_COOLDOWN = _field(
    "proxy_refresh_failure_cooldown_seconds",
    "app/modules/accounts/auth_manager.py:216",
)
ADMISSION_PLUS_CONNECT = _expr(
    "proxy_admission_wait_timeout_seconds + upstream_connect_timeout_seconds",
    "app/modules/proxy/service.py:1282 + app/core/clients/proxy.py:318",
    lambda settings: settings.proxy_admission_wait_timeout_seconds + settings.upstream_connect_timeout_seconds,
)
TOKEN_CLAIM_FLOOR = _expr(
    "proxy_admission_wait_timeout_seconds + 2 * token_refresh_timeout_seconds",
    "app/core/config/settings.py:667",
    lambda settings: settings.proxy_admission_wait_timeout_seconds + 2.0 * settings.token_refresh_timeout_seconds,
)


TIMEOUT_INVARIANT_RULES: tuple[TimeoutInvariantRule, ...] = (
    TimeoutInvariantRule(
        "upstream-connect-within-proxy-budget",
        UPSTREAM_CONNECT,
        "<=",
        PROXY_BUDGET,
        "Connect timeout must fit inside the non-stream proxy request deadline or connect failures can be "
        "misclassified.",
    ),
    TimeoutInvariantRule(
        "upstream-connect-within-stream-budget",
        UPSTREAM_CONNECT,
        "<=",
        STREAM_BUDGET,
        "Responses streams use the stream budget, so connect cannot outlive the stream request envelope.",
    ),
    TimeoutInvariantRule(
        "upstream-connect-within-compact-budget",
        UPSTREAM_CONNECT,
        "<=",
        COMPACT_BUDGET,
        "Compact requests run under the compact budget; a longer connect wait would bypass compact failover timing.",
    ),
    TimeoutInvariantRule(
        "upstream-connect-within-bridge-budget",
        UPSTREAM_CONNECT,
        "<=",
        BRIDGE_BUDGET,
        "HTTP bridge startup and submit paths are bounded by the bridge request budget, including upstream connect.",
    ),
    TimeoutInvariantRule(
        "admission-plus-connect-within-proxy-budget",
        ADMISSION_PLUS_CONNECT,
        "<=",
        PROXY_BUDGET,
        "Admission may run before upstream connect; their sum must fit the non-stream proxy budget.",
    ),
    TimeoutInvariantRule(
        "admission-plus-connect-within-compact-budget",
        ADMISSION_PLUS_CONNECT,
        "<=",
        COMPACT_BUDGET,
        "Compact preflight can pay admission before upstream connect, so the compact budget must cover both.",
    ),
    TimeoutInvariantRule(
        "admission-wait-within-proxy-budget",
        ADMISSION_WAIT,
        "<=",
        PROXY_BUDGET,
        "Global admission waits must not consume more than the request budget they protect.",
    ),
    TimeoutInvariantRule(
        "admission-wait-within-stream-budget",
        ADMISSION_WAIT,
        "<=",
        STREAM_BUDGET,
        "Streaming retries wait for capacity inside the stream budget and must leave room for the stream attempt.",
    ),
    TimeoutInvariantRule(
        "admission-wait-within-compact-budget",
        ADMISSION_WAIT,
        "<=",
        COMPACT_BUDGET,
        "Compact response-create admission must not outlive the compact request budget.",
    ),
    TimeoutInvariantRule(
        "admission-wait-within-bridge-budget",
        ADMISSION_WAIT,
        "<=",
        BRIDGE_BUDGET,
        "HTTP bridge gate and capacity waits are retried inside one bridge request budget.",
    ),
    TimeoutInvariantRule(
        "stream-idle-within-stream-budget",
        STREAM_IDLE,
        "<=",
        STREAM_BUDGET,
        "The stream idle watchdog must not outlive the Responses stream request budget.",
    ),
    TimeoutInvariantRule(
        "stream-idle-within-bridge-budget",
        STREAM_IDLE,
        "<=",
        BRIDGE_BUDGET,
        "HTTP bridge streams use the bridge request deadline, so the idle watchdog must fit inside it.",
    ),
    TimeoutInvariantRule(
        "sse-keepalive-before-stream-idle",
        SSE_KEEPALIVE,
        "<",
        STREAM_IDLE,
        "Downstream keepalives must arrive before the stream idle watchdog closes a healthy stream.",
    ),
    TimeoutInvariantRule(
        "sse-keepalive-within-stream-budget",
        SSE_KEEPALIVE,
        "<",
        STREAM_BUDGET,
        "A keepalive interval at or beyond the stream budget cannot preserve client liveness.",
    ),
    TimeoutInvariantRule(
        "sse-keepalive-within-bridge-budget",
        SSE_KEEPALIVE,
        "<",
        BRIDGE_BUDGET,
        "HTTP bridge keepalives must fire before the bridge request deadline is exhausted.",
    ),
    TimeoutInvariantRule(
        "token-refresh-claim-covers-admission-and-exchange",
        TOKEN_CLAIM_TTL,
        ">=",
        TOKEN_CLAIM_FLOOR,
        "A refresh claim that expires during admission or OAuth exchange can let two replicas reuse one single-use "
        "refresh token.",
    ),
    TimeoutInvariantRule(
        "refresh-failure-cooldown-within-claim-ttl",
        REFRESH_FAILURE_COOLDOWN,
        "<=",
        TOKEN_CLAIM_TTL,
        "Transient refresh-failure caching must not outlive the cross-replica claim window.",
    ),
    TimeoutInvariantRule(
        "token-refresh-exchange-within-claim-ttl",
        TOKEN_REFRESH,
        "<=",
        TOKEN_CLAIM_TTL,
        "The OAuth exchange must complete before the refresh claim can expire under a healthy claimant.",
    ),
    TimeoutInvariantRule(
        "usage-fetch-within-refresh-interval",
        USAGE_FETCH,
        "<=",
        USAGE_REFRESH_INTERVAL,
        "Usage fetches must not overrun the scheduler cadence and stack refresh pressure.",
    ),
    TimeoutInvariantRule(
        "usage-fetch-within-reset-credits-interval",
        USAGE_FETCH,
        "<=",
        RESET_CREDITS_INTERVAL,
        "Reset-credit polling shares the usage client timeout class and must not overlap its cadence by default.",
    ),
    TimeoutInvariantRule(
        "compact-budget-within-proxy-budget",
        COMPACT_BUDGET,
        "<=",
        PROXY_BUDGET,
        "Compact is a shorter proxy lane and must not exceed the generic proxy deadline used by settlement.",
    ),
    TimeoutInvariantRule(
        "bridge-idle-ttl-within-bridge-budget",
        BRIDGE_IDLE_TTL,
        "<=",
        BRIDGE_BUDGET,
        "A reusable bridge idle TTL must not outlive the request budget that bounds bridge continuity recovery.",
    ),
    TimeoutInvariantRule(
        "bridge-codex-idle-ttl-within-bridge-budget",
        BRIDGE_CODEX_IDLE_TTL,
        "<=",
        BRIDGE_BUDGET,
        "Codex prompt-cache bridge reuse must stay inside the bridge request budget envelope.",
    ),
    TimeoutInvariantRule(
        "bridge-stuck-gate-retire-after-admission",
        BRIDGE_STUCK_GATE_RETIRE,
        ">=",
        ADMISSION_WAIT,
        "Stuck gate retirement must not fire before one configured bridge admission wait can complete.",
    ),
    TimeoutInvariantRule(
        "bridge-stuck-gate-retire-within-bridge-budget",
        BRIDGE_STUCK_GATE_RETIRE,
        "<",
        BRIDGE_BUDGET,
        "Stuck gate retirement must happen before the bridge request budget is exhausted.",
    ),
    TimeoutInvariantRule(
        "bridge-clean-close-jitter-within-admission",
        BRIDGE_CLEAN_CLOSE_JITTER,
        "<=",
        ADMISSION_WAIT,
        "Clean-close retry jitter must not consume the whole next admission attempt window.",
    ),
    TimeoutInvariantRule(
        "bridge-clean-close-jitter-within-bridge-budget",
        BRIDGE_CLEAN_CLOSE_JITTER,
        "<",
        BRIDGE_BUDGET,
        "Clean-close retry jitter must stay small enough to retry before the bridge request deadline.",
    ),
    TimeoutInvariantRule(
        "account-lease-ttl-covers-proxy-budget",
        ACCOUNT_LEASE_TTL,
        ">=",
        PROXY_BUDGET,
        "Response-create leases use the raw lease TTL, so stale reclaim must not precede a healthy non-stream "
        "request deadline.",
    ),
    TimeoutInvariantRule(
        "account-lease-ttl-covers-compact-budget",
        ACCOUNT_LEASE_TTL,
        ">=",
        COMPACT_BUDGET,
        "Compact response-create leases must not be stale-reclaimed before the compact request budget expires.",
    ),
)

# TODO(timeout_sem_001): database_migration_lock_timeout_seconds is independent startup DB migration policy.
# TODO(timeout_sem_008): proxy_downstream_websocket_idle_timeout_seconds has no verified ordering with bridge TTL.
# TODO(timeout_sem_009): oauth_timeout_seconds is used in OAuth/client flows, not a verified proxy-path deadline.
# TODO(timeout_sem_015): openai_cache_affinity_max_age_seconds participates with dashboard prompt-cache TTL in
# cleanup retention.
# TODO(timeout_sem_021): upstream_route_cache_ttl_seconds is invalidation freshness policy; no timeout inequality
# verified.
# TODO(timeout_sem_022): model_registry_snapshot_max_age_seconds relation to refresh cadence is qualitative in
# current code.
# TODO(timeout_sem_023): firewall_ip_cache_ttl_seconds has no verified timeout owner beyond trust-cache freshness.
# TODO(timeout_sem_024): leader_election_ttl_seconds renewal is derived internally as ttl//3, not a cross-setting
# inequality.
# TODO(timeout_sem_027): proxy_account_cap_partition_scale_down_seconds is a stability window; exact heartbeat relation
# is internal.
# TODO(timeout_sem_029): usage_refresh_auth_failure_cooldown_seconds is policy cooldown, not a verified scheduler
# inequality.
# TODO(timeout_sem_030): shutdown_drain_timeout_seconds depends on deployment termination grace outside Settings.
# TODO(timeout_sem_031): durable bridge retry circuit TTL is a module constant, not a Settings-field rule.
# TODO(timeout_sem_032/033): SQLite busy retry constants are module-local and not Settings-field rules.
# TODO(timeout_sem_034/035): account-selection recovery caps are module constants clamped by request deadlines at
# runtime.

_RELATIONS: dict[str, Callable[[float, float], bool]] = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


def find_timeout_invariant_violations(settings: TimeoutSettings) -> list[TimeoutInvariantViolation]:
    violations: list[TimeoutInvariantViolation] = []
    for rule in TIMEOUT_INVARIANT_RULES:
        lhs_value = rule.lhs.evaluate(settings)
        rhs_value = rule.rhs.evaluate(settings)
        if not _RELATIONS[rule.relation](lhs_value, rhs_value):
            violations.append(TimeoutInvariantViolation(rule, lhs_value, rhs_value))
    return violations


def validate_timeout_invariants(
    settings: TimeoutSettings,
    *,
    strict: bool = False,
    log: bool = True,
) -> list[TimeoutInvariantViolation]:
    violations = find_timeout_invariant_violations(settings)
    if violations and log:
        for violation in violations:
            logger.critical("timeout invariant violation: %s", violation.format())
    if strict and violations:
        raise TimeoutInvariantError(violations)
    return violations


def validate_runtime_timeout_invariants(settings: TimeoutSettings) -> list[TimeoutInvariantViolation]:
    return validate_timeout_invariants(
        settings,
        strict=settings.timeout_invariant_validation_strict,
        log=True,
    )


def main() -> int:
    from app.core.config.settings import get_settings

    violations = validate_timeout_invariants(get_settings(), strict=False, log=False)
    if not violations:
        print(f"OK: {len(TIMEOUT_INVARIANT_RULES)} timeout invariant rules satisfied")
        return 0
    for violation in violations:
        print(violation.format(), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
