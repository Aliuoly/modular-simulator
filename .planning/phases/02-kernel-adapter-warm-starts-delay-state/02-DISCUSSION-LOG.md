# Phase 2: Kernel Adapter, Warm Starts & Delay State - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md; this log preserves the alternatives considered.

**Date:** 2026-03-29T20:36:41-04:00
**Phase:** 02-kernel-adapter-warm-starts-delay-state
**Areas discussed:** Adapter surface, Warm-start sources, Delay-state treatment

---

## Adapter Surface

### Shared contract scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full contract first | Every candidate plugs into one seam covering state, residual, Jacobian, bounds, initialization, warm start, and telemetry. | ✓ |
| Minimal step seam first | Start narrow and add advanced solver hooks later. | |
| Two-tier contract | Core required API plus optional advanced hooks. | |

**User's choice:** Full contract first
**Notes:** User accepted the recommended disciplined contract so downstream comparison does not drift into uneven adapter surfaces.

### Current split runtime treatment

| Option | Description | Selected |
|--------|-------------|----------|
| Wrap it fully | Refactor the current split kernel to implement the same full adapter contract as new candidates. | ✓ |
| Wrap core only | Share init/step/warm-start/telemetry while some internals remain bespoke. | |
| Keep special-cased | Leave the current runtime outside the adapter seam. | |

**User's choice:** Wrap it fully
**Notes:** User initially asked for clarification, then chose the fully wrapped baseline so comparison remains fair.

### Telemetry requirement

| Option | Description | Selected |
|--------|-------------|----------|
| Mandatory now | Require comparable step diagnostics from the start. | ✓ |
| Basic now, expand later | Only require accepted/rejected status now. | |
| Optional per candidate | Let each candidate expose ad hoc telemetry. | |

**User's choice:** Mandatory now
**Notes:** User accepted the recommendation that Phase 3 benchmarking should not need a second telemetry retrofit.

### Higher-layer contract posture

| Option | Description | Selected |
|--------|-------------|----------|
| Keep facades stable | Preserve current session/gameplay-facing facades. | |
| Allow small facade extensions | Permit narrow generic hooks above the substrate. | |
| Allow visible session changes | Let Phase 2 reshape higher-layer session APIs if useful. | |
| Substrate-first | Keep changes behind the substrate by default, but allow higher-layer changes for clear technical reasons. | ✓ |
| Open to reshaping | Treat public session/API changes as normal design tools. | |
| Avoid constraint here | Leave the amount of contract change fully open. | |

**User's choice:** Substrate-first, with openness to change when justified
**Notes:** User said they are not married to the gameplay service or API contract and are open to changes if there is good reason.

---

## Warm-start Sources

### Required warm-start paths

| Option | Description | Selected |
|--------|-------------|----------|
| Last accepted state | Resume from the most recent accepted plant snapshot during normal stepping. | |
| Checkpoint restore | Resume from persisted checkpoint payloads through the shared seam. | ✓ |
| Post-edit recovery | Reinitialize after runtime topology edits through the same adapter path. | |
| Fresh init only | Only guarantee cold initialization in Phase 2. | |

**User's choice:** Checkpoint restore, reframed as the canonical path
**Notes:** User questioned the need for multiple restore paths and emphasized save/load game as the expected restore story.

### Canonical warm-start model

| Option | Description | Selected |
|--------|-------------|----------|
| Canonical checkpoint path | Use checkpoint-style accepted snapshots as the one canonical restore mechanism underneath normal resume, save/load, and post-edit recovery. | ✓ |
| Explicit multiple paths | Keep last accepted state, checkpoint restore, and post-edit recovery as distinct first-class paths. | |
| Checkpoint only | Only guarantee checkpoint restore and leave other recovery outside the adapter. | |

**User's choice:** Canonical checkpoint path
**Notes:** This preserved the user's save/load mental model while still satisfying the roadmap need to support resume and edit recovery through one underlying mechanism.

### Authoritative warm-start source

| Option | Description | Selected |
|--------|-------------|----------|
| Accepted plant snapshot | Use one accepted coupled state as the source of truth. | ✓ |
| Adapter-owned state bundle | Let each candidate own a private restore bundle. | |
| Mixed source reconstruction | Rebuild from checkpoints, caches, and helper state as needed. | |

**User's choice:** Accepted plant snapshot
**Notes:** User accepted the recommendation that restore should anchor on one accepted coupled state rather than mixed reconstruction.

### Unsafe restore behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Fail explicitly | Reject incompatible or unsafe warm starts with a clear reason. | ✓ |
| Fallback to cold init | Reinitialize from scratch when restore is incompatible. | |
| Best-effort repair | Patch missing state and continue if possible. | |

**User's choice:** Fail explicitly
**Notes:** User accepted the recommendation to avoid silent downgrade or lossy repair.

---

## Delay-state Treatment

### Candidate delay representation

| Option | Description | Selected |
|--------|-------------|----------|
| External history by default | Keep transport lag and deadtime external unless justified otherwise. | |
| Per-candidate choice | Let each candidate decide whether delay is external history, augmented state, or hybrid. | ✓ |
| Augmented state target | Push candidates toward internal solver-state delay representation. | |

**User's choice:** Per-candidate choice
**Notes:** User wanted delay/deadtime treatment left open enough for real exploration.

### Divergent delay-treatment requirement

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit mapping + restore rules | Document what replaces current delay state and prove safe restore behavior. | ✓ |
| Behavioral equivalence only | Only require similar visible behavior. | |
| No extra requirement | Leave candidate-specific delay handling implicit. | |

**User's choice:** Explicit mapping + restore rules
**Notes:** User accepted the recommendation that alternative delay treatments must still be restorable and explicitly documented.

### Delay semantic consistency

| Option | Description | Selected |
|--------|-------------|----------|
| Preserve current semantics unless justified | Prefer current transport/deadtime behavior by default. | |
| Allow credible alternatives | Permit physically credible semantic changes with restore discipline. | |
| Open exploration | Do not lock delay-semantics consistency yet. | ✓ |

**User's choice:** Open exploration
**Notes:** User did not want Phase 2 to lock candidate kernels to the current delay semantics prematurely.

---

## the agent's Discretion

- Exact adapter type and artifact shapes.
- Exact minimum justified session/API widening under the substrate-first posture.
- Exact candidate-specific format for delay-state mapping and restore documentation.

## Deferred Ideas

None.
