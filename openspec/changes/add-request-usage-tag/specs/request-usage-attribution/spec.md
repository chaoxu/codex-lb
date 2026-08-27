## ADDED Requirements

### Requirement: Proxy clients can attach a bounded usage tag

codex-lb MUST accept an optional `X-Codex-LB-Usage-Tag` header on authenticated proxy requests. A tag MUST begin with an ASCII alphanumeric character, contain only ASCII alphanumeric characters and `.`, `_`, `:`, `/`, `@`, `+`, or `-`, and contain at most 128 characters. codex-lb MUST reject a present tag that does not satisfy this grammar before opening an upstream request.

#### Scenario: A valid experiment attempt tag is accepted

- **GIVEN** an authenticated proxy request carries `X-Codex-LB-Usage-Tag: guidance-v1/baseline--r02/attempt-1`
- **WHEN** codex-lb processes the request
- **THEN** the request proceeds with `guidance-v1/baseline--r02/attempt-1` as its usage tag

#### Scenario: A malformed tag fails before dispatch

- **GIVEN** an authenticated proxy request carries a blank, whitespace-bearing, non-ASCII, or longer-than-128-character usage tag
- **WHEN** codex-lb processes the request
- **THEN** codex-lb returns a client error
- **AND** no upstream request is opened

### Requirement: Request logs preserve usage attribution

Every request-log row produced by a tagged proxy request MUST store the exact validated tag in `request_logs.usage_tag`, including rows for upstream retries, terminal errors, cancellation, and requests with incomplete terminal usage. Rows produced by untagged requests MUST store `NULL`. The column MUST be indexed for exact-tag aggregation.

#### Scenario: A tagged request has measured terminal usage

- **GIVEN** a tagged proxy request receives terminal token usage from upstream
- **WHEN** codex-lb persists the request log
- **THEN** the row stores both the usage tag and the measured token fields

#### Scenario: A tagged request fails without terminal usage

- **GIVEN** a tagged proxy request fails before terminal token usage is available
- **WHEN** codex-lb persists the failure row
- **THEN** the row stores the usage tag
- **AND** unavailable token fields remain `NULL`

### Requirement: Usage tags remain local to codex-lb

codex-lb MUST remove `X-Codex-LB-Usage-Tag` case-insensitively from every HTTP and WebSocket header set sent to an upstream provider or another proxy owner. The tag MUST NOT affect authentication, account selection, affinity, request payloads, retries, or response contents.

#### Scenario: Tagged headers are not forwarded upstream

- **GIVEN** a proxy request carries a valid usage tag
- **WHEN** codex-lb constructs HTTP or WebSocket upstream headers
- **THEN** the upstream header set does not contain `X-Codex-LB-Usage-Tag` in any casing

### Requirement: Untagged clients retain existing behavior

Omitting `X-Codex-LB-Usage-Tag` MUST require no configuration and MUST preserve existing proxy and request-log behavior except for the nullable `usage_tag` field.

#### Scenario: Existing client omits the tag

- **GIVEN** a proxy client sends no usage-tag header
- **WHEN** codex-lb serves and logs the request
- **THEN** proxy behavior is unchanged
- **AND** the request-log row stores `usage_tag=NULL`
