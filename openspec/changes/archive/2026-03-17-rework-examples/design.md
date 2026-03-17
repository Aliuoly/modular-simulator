## Context

The repository currently has many example scripts spanning multiple styles (dynamic API demos, connection experiments, and full flowsheet scenarios), which makes onboarding noisy and inconsistent. The requested direction is to keep a small set of representative examples that all use one modeling style: boundary feed streams connected to process ports, explicit inter-unit connections, control elements placed on relevant edges, and internal-only unit states (no unit-level actuators). Product draws should be modeled with explicit boundary sinks when the high-level flowsheet API supports them; until then, terminal unit outlets are the documented product handoff.

## Goals / Non-Goals

**Goals:**
- Define objective criteria for retaining, removing, or refactoring existing examples.
- Produce a curated examples catalog with consistent flowsheet structure and control placement.
- Keep retained examples runnable and documented with clear purpose statements.

**Non-Goals:**
- Changing simulation engine APIs or solver behavior.
- Reworking non-example library internals unless required to keep curated examples functional.
- Preserving every legacy example variant.

## Decisions

1. Curate to a small canonical set instead of incremental cleanup.
   - Rationale: The issue asks for a "handful" of purposefully designed examples; explicit selection avoids gradual scope creep.
   - Alternative considered: keep all examples and add labels. Rejected because discoverability and style consistency remain weak.

2. Apply a strict flowsheet conformance checklist to every retained example.
   - Rationale: A checklist makes conformance testable and avoids subjective interpretation of style requirements.
   - Alternative considered: narrative style guidance only. Rejected because it is hard to enforce over time.

3. Prefer refactoring high-value examples over retaining parallel duplicate demos.
   - Rationale: Fewer examples with stronger explanatory value better showcase capabilities.
   - Alternative considered: preserve duplicate examples for breadth. Rejected because it increases maintenance and user confusion.

4. Co-locate short "intent" documentation with each retained example entrypoint.
   - Rationale: Users should immediately understand what capability each curated example demonstrates.
   - Alternative considered: central index only. Rejected because local context is needed when opening a single file directly.

5. Match the OpenSpec wording to the current high-level `Flowsheet` capability instead of implying runtime features that are only available in lower-level connection APIs.
   - Rationale: review found that the curated examples correctly use boundary feeds and explicit unit-to-unit connections, but the high-level `Flowsheet` helper currently exposes only boundary sources, not boundary sinks.
   - Alternative considered: expand the engine/API in this change. Rejected because the proposal explicitly scoped out runtime/API changes.

6. Represent recycle examples with an explicit return edge in the topology, even if the current high-level flowsheet runtime still treats recycle convergence as a validation-time warning rather than a dedicated solved feature.
   - Rationale: review found that the ammonia example was mislabeled as a recycle loop while actually using a second external feed. An explicit recycle edge keeps the example honest about topology without inventing new high-level runtime helpers.
   - Alternative considered: keep the second feed and only downgrade the name. Rejected because the current `Flowsheet` API can already express the recycle leg as an explicit connection.

## Risks / Trade-offs

- Removing examples may frustrate users who depend on legacy scripts -> Mitigation: Keep migration notes mapping removed examples to curated replacements.
- Strict conformance may require non-trivial rewrites for complex demos -> Mitigation: Prioritize highest-value examples first and track follow-up rewrites as linked issues.
- Curated set may underrepresent edge-case capabilities -> Mitigation: Include one advanced flowsheet example that demonstrates composability without violating style constraints.
- Recycle-loop examples can still converge to zero recycle flow under the current high-level runtime because compile-time cycle detection does not add new hydraulic constraints -> Mitigation: document the example as explicit recycle topology, verify the return edge in tests, and avoid overstating solved recycle behavior.
