## 1. Compile-Time Recycle Validation

- [x] 1.1 Extend high-level `Flowsheet` compile validation to enumerate all directed recycle loops and inspect each loop for the supported line-installed pump positive initial boost rule per the canonical hydraulic semantics.
- [x] 1.2 Replace the current recycle warning-only path with a validation error for any loop that lacks supported positive line-installed pump boost, including deterministic reporting of the offending loop path(s) and the required user action (add a pump/pressure-boosting stage on the recycle path).
- [x] 1.3 Preserve existing behavior for non-cyclic topologies and for cycles that satisfy the positive line-installed pump-boost rule.

## 2. Spec And Migration Alignment

- [x] 2.1 Align this change's proposal/design with `define-canonical-hydraulic-solving-semantics` to clarify that recycle validation enforces line-owned pump semantics and the canonical network-solve model.
- [x] 2.2 Explicitly mark this change as dependent on `canonicalize-hydraulic-junction-api` for the final public API (junction and line-element definitions), and clarify that code/example rewrites depend on that API landing first.
- [x] 2.3 Update curated example specs to describe recycle loops as using line-installed pump boost elements aligned with the canonical model, while deferring actual code rewrites until the sibling API is available.

## 3. Verification

- [x] 3.1 Add automated tests that reject recycle loops with no supported positive line-installed pump boost and assert the validation message content.
- [x] 3.2 Add an explicit regression test for a recycle loop that includes pump metadata but zero configured initial boost and confirm it still fails validation.
- [x] 3.3 Add a regression test for a topology with mixed valid and invalid recycle loops and confirm compilation fails deterministically on the invalid path.
- [x] 3.4 Add automated coverage for the curated ammonia recycle example using line-installed pump boost, and keep the shipped example execution aligned with the current high-level API while any future canonical migration details track the sibling API change.
- [x] 3.5 Add a non-cyclic topology regression to confirm the new validation does not introduce unrelated compile failures.
