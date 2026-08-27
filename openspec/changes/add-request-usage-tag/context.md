# Request usage attribution

`api_key_id` identifies the authenticated caller. `usage_tag` identifies a caller-defined unit of work such as an experiment attempt. Keeping these dimensions separate lets one trusted runner use a stable API key while assigning each request to `guidance-v1/baseline--r02/attempt-1`.

The tag is accounting metadata, not authorization or routing input. codex-lb validates it before proxy work, carries it through retries and terminal failures, writes it with the request log, and removes the client header from every upstream transport. Cross-replica HTTP bridge forwarding uses a separate signed internal field so another codex-lb owner retains attribution without receiving or forwarding the raw client header. Tagged bridge requests bind the tag into both signatures and fail closed on an old owner, while untagged signatures remain byte-compatible during rolling upgrades. A missing tag produces the same request and log behavior as the current release.

The initial patch intentionally omits dashboard controls and a public aggregation endpoint. Operators can group `request_logs` by `usage_tag`, and a later change can expose that query without changing ingestion semantics.

Malformed tags fail before upstream dispatch. This prevents silent attribution loss caused by whitespace, truncation, or inconsistent normalization.
