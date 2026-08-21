## ADDED Requirements

### Requirement: Pre-visible eventless stream EOF receives bounded recovery

When an HTTP Responses stream ends before producing its first upstream event, the proxy MUST use the existing bounded same-account transient retry path when transient retry is enabled. Each attempt MUST begin with fresh settlement state. The proxy MUST NOT use this recovery after any downstream-visible event, and MUST surface `stream_incomplete` when the retry budget is exhausted.

#### Scenario: Eventless EOF retries before output

- **GIVEN** an HTTP Responses stream with transient retry enabled
- **AND** the first upstream attempt ends before producing any event
- **WHEN** the bounded retry budget remains available
- **THEN** the proxy retries the request on the same account
- **AND** no terminal failure from the first attempt is emitted downstream
- **AND** the retry uses fresh settlement state

#### Scenario: Midstream EOF remains terminal

- **GIVEN** an HTTP Responses stream has emitted a downstream-visible event
- **WHEN** upstream closes before a terminal event
- **THEN** the proxy does not transparently replay the request
- **AND** the downstream stream terminates with `stream_incomplete`
