# Empty Registry Fail-Closed Property Design

## Context

Issue #128 added generated fail-closed rule-registry properties but intentionally iterates from generator case `1`, leaving the empty default case unexercised. Issue #144 closes that test-coverage gap without changing registry production behavior.

## Design

The fail-closed helper obtains the complete bounded generated sequence and runs all four existing invalid-output families for every case, including case index `0` whose text is empty. A processed-case set is updated only after duplicate source, duplicate finding, incompatible source, and incompatible category checks have all completed for a case. A replay-safe structural invariant then requires empty case `0` to be present in that set.

This retained assertion makes accidental reintroduction of `[1:]` fail with the existing safe generator/seed/case metadata. Empty text needs no special registry implementation path; it must produce the same exception types and privacy-safe diagnostics as other cases.

## Alternatives

- Merely removing `[1:]` is behaviorally sufficient today but offers weaker evidence if the loop is later narrowed again.
- A separate duplicate copy of all four checks for empty input would increase maintenance and could drift from the generated suite.
- Production changes are unnecessary unless the broadened property exposes a defect.

## Verification

First retain the old `[1:]` loop while adding the processed-empty invariant and observe replay-safe RED for case `0`. Then include the full generated sequence and observe GREEN. Run focused registry suites, the complete fast suite, and all static checks.
