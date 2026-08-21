## 1. Implementation

- [x] 1.1 Route eventless upstream EOF through the existing same-account transient retry path.
- [x] 1.2 Reset settlement state at the start of each stream attempt.

## 2. Regression coverage

- [x] 2.1 Assert that a pre-visible EOF retries and a later attempt completes.
- [x] 2.2 Preserve the existing midstream EOF fail-closed test.

## 3. Validation

- [x] 3.1 Run the focused pre-visible and midstream EOF tests.
- [x] 3.2 Run the proxy utility test set and record unrelated baseline failures.
- [x] 3.3 Run strict OpenSpec validation for this change.
