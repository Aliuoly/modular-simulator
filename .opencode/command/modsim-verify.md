---
description: Review an implementation against its OpenSpec contract and linked Beads work.
agent: reviewer
---

Verify that an implementation matches the change contract and is ready to close.

**Input**: Optionally specify a change name after `/modsim-verify` (for example `/modsim-verify add-auth`). If omitted, infer it only when the context is clear. Otherwise use the `question` tool to let the user choose.

---

## `/modsim-verify` Flow

1. **Resolve the target change**
   - If no change name is provided, run `openspec list --json`.
   - Show the most relevant active changes with schema and status.
   - Do not guess when multiple candidates exist.

2. **Check status to understand the schema**
   ```bash
   openspec status --change "<name>" --json
   ```
   Parse the JSON to understand:
   - `schemaName`
   - which artifacts exist for the change
   - whether `beads-identity.md` is present

3. **Load the change artifacts**
   ```bash
   openspec instructions apply --change "<name>" --json
   ```
   Read all available artifacts from `contextFiles`.

4. **Load linked execution context**
   - Read `beads-identity.md` when present.
   - Inspect linked Beads tasks or closure evidence when relevant.
   - Gather verification outputs, diff scope, and any task packet details available.

5. **Initialize the verification dimensions**
   Review across these dimensions:
   - **Completeness**: required artifacts, linked execution work, verification evidence, and review prerequisites are present
   - **Correctness**: requirements and scenarios appear correctly implemented and tested
   - **Coherence**: design decisions, code patterns, and execution linkage remain internally consistent

6. **Verify completeness**
   Check for:
   - missing required artifacts
   - stale or incomplete Beads linkage
   - missing verification evidence
   - missing review prerequisites for archive
   - tasks or planning waves that appear unaccounted for in linked execution work

7. **Verify correctness**
   For each requirement from the delta specs:
   - search the codebase for implementation evidence
   - note likely implementation files and line ranges
   - assess whether implementation matches requirement intent
   - check whether scenarios appear covered by code or tests
   - flag missing or divergent behavior clearly

8. **Verify coherence**
   - Check whether implementation follows `design.md` decisions when present.
   - Review new code for consistency with repo patterns.
   - Check whether Beads linkage and implementation scope still match the contract.
   - If `simulation-realism-required: true` is present, include simulation and engineering realism review.

9. **Generate the review result**
   Follow the reviewer output contract:
   - `VERDICT: approved` or `VERDICT: changes-requested`
   - `Spec compliance:` short assessment
   - `Strengths:` brief bullets
   - `Issues:` grouped by Critical, Important, Minor with file references
   - `Realism assessment:` when required
   - `Realism issues:` when required
   - `Next action:` one short recommendation

**Verification heuristics**

- Prefer direct evidence over inference.
- Treat unmet requirements as more important than code-style issues.
- When uncertain, label the uncertainty.
- Do not auto-approve missing or stale evidence.
- Prefer a short list of decisive findings over weak nits.

Finish with the `question` tool and concrete next-step options.
