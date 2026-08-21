# Verification

The two EOF regression tests pass on the deployed v1.23 maintenance lineage: one pre-visible eventless EOF retries successfully, while one midstream EOF remains terminal.

The complete `tests/unit/test_proxy_utils.py` file produced 980 passes and 10 failures. Every failure is in the v1.23 live overlay's WebSocket session-anchor tests and raises because a test settings stub lacks `websocket_session_anchor_enabled`. This change touches only the HTTP streaming mixin, its two EOF tests, and this OpenSpec change; it does not modify the failing WebSocket helper or settings fixtures.

Strict validation passed for `retry-previsible-stream-eof`, and all 49 capability specs on this lineage passed validation.
