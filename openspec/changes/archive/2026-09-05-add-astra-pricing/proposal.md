## Why

The production pricing catalog has no `gpt-6-astra` entry. Requests retain token usage but persist `cost_usd = NULL`, so aggregate costs omit Astra traffic.

## What Changes

- Add Astra's published Standard, Flex, and Fast rates, including the long-context multiplier above 272,000 input tokens.
- Verify persisted costs through the request-log API and cover tier and threshold boundaries.
- Document historical repair separately because persisted costs feed lifetime and time-bucket rollups.

## Impact

The change prices new Astra request logs and API-key usage. Existing stored costs and other model rates retain their current values. Historical aggregate repair and production activation are separate operations.
