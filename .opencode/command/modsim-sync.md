---
description: Sync delta specs from a modsim change to main specs.
---

Sync delta specs from a change to main specs.

This is an agent-driven operation. Read delta specs and directly edit the main specs to apply the changes intelligently.

**Input**: Optionally specify a change name after `/modsim-sync` (for example `/modsim-sync add-auth`). If omitted, infer it only when the context is clear. Otherwise use the `question` tool.

---

## `/modsim-sync` Flow

1. **Resolve the target change**
   - If no change name is provided, run `openspec list --json`.
   - Show changes that have delta specs under `openspec/changes/<name>/specs/`.
   - Do not guess when multiple candidates exist.

2. **Find delta specs**
   Look for delta spec files in `openspec/changes/<name>/specs/*/spec.md`.

   Each delta spec file can contain:
   - `## ADDED Requirements`
   - `## MODIFIED Requirements`
   - `## REMOVED Requirements`
   - `## RENAMED Requirements`

   If no delta specs are found, inform the user and stop.

3. **For each delta spec, apply changes to the main specs**

   For each capability with a delta spec at `openspec/changes/<name>/specs/<capability>/spec.md`:

   a. **Read the delta spec** to understand the intended changes

   b. **Read the main spec** at `openspec/specs/<capability>/spec.md` when it exists

   c. **Apply changes intelligently**

   **ADDED Requirements**
   - If the requirement does not exist in the main spec, add it.
   - If the requirement already exists, update it to match the delta intent.

   **MODIFIED Requirements**
   - Find the requirement in the main spec.
   - Apply the changes without throwing away unrelated scenarios.
   - Preserve content the delta does not change.

   **REMOVED Requirements**
   - Remove the requirement block from the main spec.

   **RENAMED Requirements**
   - Find the `FROM` requirement and rename it to `TO`.

   d. **Create a new main spec** if the capability does not exist yet
   - Create `openspec/specs/<capability>/spec.md`
   - Add a short Purpose section
   - Add the new requirements from the delta

4. **Show summary**
   Report:
   - which capabilities were updated
   - which requirements were added, modified, removed, or renamed
   - whether any ambiguity or manual follow-up remains

**Delta spec format reference**

```markdown
## ADDED Requirements

### Requirement: New Feature
The system SHALL do something new.

#### Scenario: Basic case
- **WHEN** user does X
- **THEN** system does Y

## MODIFIED Requirements

### Requirement: Existing Feature
#### Scenario: New scenario to add
- **WHEN** user does A
- **THEN** system does B

## REMOVED Requirements

### Requirement: Deprecated Feature

## RENAMED Requirements

- FROM: `### Requirement: Old Name`
- TO: `### Requirement: New Name`
```

**Guardrails**

- Read both delta and main specs before editing.
- Preserve existing content not mentioned in the delta.
- Keep the merge idempotent.
- Ask only when the delta is genuinely ambiguous.

Finish with the `question` tool and concrete next-step options.
