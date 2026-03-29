# Planning State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-03-29)

**Core value:** Deliver a grounded, composable process-simulation backend that stays physically credible enough for teaching while still usable as a realtime game substrate.
**Current focus:** Milestone v1.0 Kernel stability

## Current Position

Phase: Not started (defining requirements)
Plan: -
Status: Defining requirements
Last activity: 2026-03-29 - Milestone v1.0 started

## Accumulated Context

- `.planning/codebase/` contains the brownfield codebase map and is the current source of architecture, stack, concerns, and conventions context.
- The existing simulator already supports flowsheet composition, connected-plant hydraulics/runtime coupling, runtime editing, and gameplay-facing session/API layers.
- This milestone is focused on whether the current split unit-step plus connection macro-step kernel is introducing stale-coupling instability, and whether a more coupled flowsheet-wide solve direction is the better long-term backend kernel.
