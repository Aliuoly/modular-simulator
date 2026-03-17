## 1. Compile-Time Recycle Validation

- [ ] 1.1 Extend high-level `Flowsheet` compile validation to enumerate all directed recycle loops and inspect each loop for the supported line-installed pump positive initial boost rule per the canonical hydraulic semantics.
- [ ] 1.2 Replace the current recycle warning-only path with a validation error for any loop that lacks supported positive line-installed pump boost, including deterministic reporting of the offending loop path(s) and the required user action (add a pump/pressure-boosting stage on the recycle path).
- [ ] 1.3 Preserve existing behavior for non-cyclic topologies and for cycles that satisfy the positive line-installed pump-boost rule.

## 2. Spec And Migration Alignment

- [ ] 2.1 Align this change's proposal/design with `define-canonical-hydraulic-solving-semantics` to clarify that recycle validation enforces line-owned pump semantics and the canonical network-solve model.
- [ ] 2.2 Explicitly mark this change as dependent on `canonicalize-hydraulic-junction-api` for the final public API (junction and line-element definitions), and clarify that code/example rewrites depend on that API landing first.
- [ ] 2.3 Update curated example specs to describe recycle loops as using line-installed pump boost elements aligned with the canonical model, while deferring actual code rewrites until the sibling API is available.

## 3. Verification

- [ ] 3.1 Add automated tests that reject recycle loops with no supported positive line-installed pump boost and assert the validation message content.
- [ ] 3.2 Add an explicit regression test for a recycle loop that includes pump metadata but zero configured initial boost and confirm it still fails validation.
- [ ] 3.3 Add a regression test for a topology with mixed valid and invalid recycle loops and confirm compilation fails deterministically on the invalid path.
- [ ] 3.4 Add placeholder or stub coverage for the curated ammonia recycle example using line-installed pump boost; finalize full example execution once the sibling public API lands and example code can be updated.
- [ ] 3.5 Add a non-cyclic topology regression to confirm the new validation does not introduce unrelated compile failures.

