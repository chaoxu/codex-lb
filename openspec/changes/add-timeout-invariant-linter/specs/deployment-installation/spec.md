## ADDED Requirements

### Requirement: Timeout invariants are validated at startup and in CI

The application SHALL define executable timeout-invariant rules over effective
Settings fields for verified relationships between request budgets, idle
timeouts, TTLs, refresh deadlines, admission waits, and retry jitter. Each rule
SHALL name the compared settings or expression, the relation, and a one-line
rationale describing the runtime failure prevented. Unverified timeout inventory
entries SHALL NOT be enforced until their code relationship is verified.

At startup, the application SHALL validate the effective settings against the
rule table. By default, startup SHALL log every violation at CRITICAL and
continue. When `timeout_invariant_validation_strict` is true, startup SHALL raise
after logging the violations. The project SHALL expose a runnable CI entrypoint
that validates the same rule table and exits nonzero when any rule is violated.

#### Scenario: Default settings satisfy timeout invariants

- **WHEN** timeout-invariant validation runs against default settings
- **THEN** every enforced rule passes
- **AND** the CI entrypoint exits successfully

#### Scenario: Non-strict startup reports violations without failing

- **WHEN** effective settings violate one or more timeout-invariant rules
- **AND** strict timeout-invariant validation is disabled
- **THEN** startup validation logs every violated rule at CRITICAL
- **AND** startup may continue

#### Scenario: Strict startup rejects violations

- **WHEN** effective settings violate one or more timeout-invariant rules
- **AND** `timeout_invariant_validation_strict` is true
- **THEN** startup validation raises an error that includes the violated rule ids
