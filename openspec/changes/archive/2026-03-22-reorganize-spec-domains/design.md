## Context

The current live OpenSpec tree uses work-item and phase names. This change rewrites the live tree so each spec is a durable domain.

User-approved target domains are fixed and must be used exactly:

- `connection`
- `observability`
- `examples`
- `units-and-components`
- `tutorials`
- `session`
- `economics`
- `client-godot`

## Decisions

1. Keep behavior requirements, remove milestone packaging
   - Existing requirement text is retained unless it only describes packaging/history.

2. Merge connection-adjacent specs into one domain
   - `flowsheet-junction-line-api` + `hydraulic-network-solving-semantics` + `recycle-loop-validation` become `connection`.

3. Split mixed gameplay specs by ownership
   - Session-only behavior goes to `session`.
   - Ledger/pricing behavior goes to `economics`.
   - Build catalog and start catalog behavior goes to `units-and-components`.
   - Tutorial goal contracts go to `tutorials`.
   - Godot client bridge and slice behavior goes to `client-godot`.

4. Remove positioning as a live behavioral spec
   - `educational-backend-positioning` is removed from live specs.
   - Project framing remains in OpenSpec config/docs context.

5. Writing style rule lives in config
   - `openspec/config.yaml` gains plain-language guidance for OpenSpec artifacts.

## Migration mapping

- `flowsheet-junction-line-api` → `connection`
- `hydraulic-network-solving-semantics` → `connection`
- `recycle-loop-validation` → `connection`
- `observability-snapshot-api` → `observability`
- `curated-flowsheet-examples` → `examples`
- `phase1-sandbox-build-catalog` → `units-and-components` (+ tutorial parts moved to `tutorials`)
- `sandbox-session-and-heuristic-economics` → split into `session` + `economics`
- `phase1-realtime-godot-vertical-slice` → `client-godot`
- `educational-backend-positioning` → removed from live specs (positioning in config/docs)
