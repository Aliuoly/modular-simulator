## Why

The live `openspec/specs/` tree grew as work-item slices. That made long-term ownership harder because behavioral contracts were split across milestone names instead of durable product domains.

The approved direction is to keep only plain-language domain specs as live capabilities, merge related slices into those domains, and move project positioning guidance out of behavioral specs.

## What Changes

- Reorganize live specs into these exact domains:
  - `connection`
  - `observability`
  - `examples`
  - `units-and-components`
  - `tutorials`
  - `session`
  - `economics`
  - `client-godot`
- Merge `flowsheet-junction-line-api`, `hydraulic-network-solving-semantics`, and `recycle-loop-validation` into `connection`.
- Split session/economics/tutorial/build-catalog/client contracts into the new durable domains.
- Remove `educational-backend-positioning` as a live spec and keep positioning in config/docs context.
- Add a plain-language rule in `openspec/config.yaml` so OpenSpec artifacts avoid jargon.
- Add a migration note mapping old live spec names to new domains.

## Impact

- Affected live specs: `openspec/specs/**/spec.md`
- Affected OpenSpec config: `openspec/config.yaml`
- Affected change artifacts: `openspec/changes/reorganize-spec-domains/**`
- No archive migration and no source-code behavior changes.
