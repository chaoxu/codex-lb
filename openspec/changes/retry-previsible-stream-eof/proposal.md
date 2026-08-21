# Why

An HTTP Responses stream can end before its first upstream event when the upstream connection closes without a terminal event. The proxy currently emits `stream_incomplete` immediately even though no output has reached the client and the existing same-account transient retry path can safely replay the request.

# What Changes

- Retry an eventless upstream EOF through the bounded same-account transient retry path when that path is enabled.
- Reset per-attempt settlement state before every retry.
- Preserve terminal `stream_incomplete` behavior after retry exhaustion and for every stream that has emitted output.

# Capabilities

### Modified Capabilities

- `responses-api-compat`: pre-visible eventless EOF receives bounded transparent recovery.

# Impact

The change affects only streaming Responses attempts that end before their first upstream event. Requests with visible output, tool effects, or exhausted retry budgets keep their existing failure behavior.
