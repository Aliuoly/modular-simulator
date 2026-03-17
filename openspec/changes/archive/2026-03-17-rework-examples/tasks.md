## 1. Audit And Curate Inventory

- [x] 1.1 Inventory existing examples under `examples/` and classify each as keep, refactor, or remove based on canonical-set goals.
- [x] 1.2 Select a handful of canonical examples that collectively cover core repository capabilities without overlap.
- [x] 1.3 Create a migration map from removed examples to curated replacements.

## 2. Refactor Retained Examples To Flowsheet Style

- [x] 2.1 Update each retained example so external feeds are modeled as boundary streams connected to process ports, while product handoff is documented via terminal unit outlets until the high-level flowsheet API gains boundary sinks.
- [x] 2.2 Ensure all unit-to-unit transfers use explicit connection edges between process ports.
- [x] 2.3 Rework control logic so control elements are attached only to required connection edges.
- [x] 2.4 Remove any unit-level actuator constructs and keep unit process definitions internal-state only.

## 3. Documentation And Validation

- [x] 3.1 Add concise purpose notes for each curated example (capability demonstrated and intended learning outcome).
- [x] 3.2 Update top-level example index/documentation to list only the curated set and its rationale.
- [x] 3.3 Run curated example entrypoints to confirm they execute and still demonstrate intended behavior.

## 4. Review Alignment Follow-up

- [x] 4.1 Align the OpenSpec artifacts with the current flowsheet runtime by requiring explicit boundary feeds and explicit unit-to-unit connections, while treating product streams as documented unit outlets until boundary sinks are supported in the high-level flowsheet API.
- [x] 4.2 Fix review-discovered correctness and documentation issues in the curated examples and shared calculation behavior.
- [x] 4.3 Extend verification so the reviewed examples and calculation fault propagation behavior are exercised by tests.
- [x] 4.4 Restore an automated repository CI workflow for lint/type/smoke coverage and rerun independent review until it passes.
