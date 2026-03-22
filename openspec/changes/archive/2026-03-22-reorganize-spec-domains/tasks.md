## Wave 1 — Reorganize live domains and preserve contracts

- [x] 1.1 Create and populate live domain specs with exact approved names: `connection`, `observability`, `examples`, `units-and-components`, `tutorials`, `session`, `economics`, `client-godot`.
- [x] 1.2 Merge live contracts from `flowsheet-junction-line-api`, `hydraulic-network-solving-semantics`, and `recycle-loop-validation` into `connection`.
- [x] 1.3 Split mixed work-item specs into durable domains:
  - tutorial requirements into `tutorials`
  - player-buildable item/start catalog requirements into `units-and-components`
  - session requirements into `session`
  - economics requirements into `economics`
  - Godot slice requirements into `client-godot`
- [x] 1.4 Remove live `educational-backend-positioning` behavioral spec.

## Wave 2 — Add writing rules and migration notes

- [x] 2.1 Update `openspec/config.yaml` with a durable plain-language artifact rule (prefer plain language, avoid jargon).
- [x] 2.2 Add a migration note mapping old live spec names to the new domain names.

## Wave 3 — Validate

- [x] 3.1 Run `openspec validate --specs --strict --no-interactive`.
- [x] 3.2 Run `openspec validate reorganize-spec-domains --strict --no-interactive`.
- [x] 3.3 Run `uv run pytest tests/test_rework_examples_review_alignment.py`.
