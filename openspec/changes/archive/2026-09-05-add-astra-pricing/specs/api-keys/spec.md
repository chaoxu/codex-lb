## ADDED Requirements

### Requirement: GPT-6 Astra token pricing
The system MUST recognize the canonical model `gpt-6-astra`. Per million tokens, Standard rates SHALL be USD 10 for uncached input, USD 1 for cached input, and USD 50 for output. Requests with more than 272,000 input tokens SHALL use USD 20, USD 2, and USD 75 respectively for the full request. Flex SHALL use half the applicable Standard rates. Fast and Priority SHALL use twice the applicable Standard rates. The existing normalization of cached input and output/reasoning tokens SHALL apply.

#### Scenario: Standard Astra cost is persisted and visible
- **WHEN** a Standard Astra request records 100,000 input tokens, 80,000 cached input tokens, and 1,000 output tokens
- **THEN** its persisted and request-log API cost SHALL be USD 0.33

#### Scenario: Fast Astra uses long-context rates
- **WHEN** a Fast Astra request records 300,000 input tokens, 200,000 cached input tokens, and 1,000 output tokens
- **THEN** its persisted and request-log API cost SHALL be USD 4.95

#### Scenario: Exact threshold retains short-context rates
- **WHEN** an Astra request has exactly 272,000 input tokens
- **THEN** the system SHALL use the short-context rates for the selected tier

#### Scenario: Existing historical aggregate values are preserved
- **WHEN** the pricing catalog is updated
- **THEN** existing stored request costs and rollup totals SHALL retain their values until an explicit historical repair runs
