## Why

Local experiment runners need to attribute token usage to one logical attempt without creating an API key for every run. codex-lb already persists authoritative request-level usage, but it has no caller-supplied accounting dimension below `api_key_id`.

## What Changes

- Accept one optional `X-Codex-LB-Usage-Tag` header on proxy requests.
- Validate a bounded identifier grammar, persist the normalized value on every resulting request-log row, and index the column for later aggregation.
- Consume the header inside codex-lb so it never reaches OpenAI or another configured upstream.
- Preserve current behavior for clients that omit the header.

## Impact

- Adds one nullable indexed column to `request_logs`.
- Adds no setting, dashboard surface, authentication mode, or key lifecycle.
- The first version exposes the tag through direct database queries only.
