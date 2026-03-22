---
description: Beads-first intake for fuzzy requests; create or reuse an overall goal before OpenSpec
agent: hybrid-planner
---

Use this command when the request is still fuzzy.

"Overall goal" means the top-level Beads container for related work.

This command keeps provisional scope in Beads first and avoids creating OpenSpec artifacts until the request is stable.

**Input**

The argument after `/opsx-goal` is a rough idea, problem, or desired outcome.
If no input is provided, ask:
> "What outcome do you want to achieve? A rough description is enough."

---

## `/opsx-goal` flow

1. **Capture the intent in plain terms**
   - Summarize the requested outcome in 1-3 sentences.
   - Surface key unknowns, boundaries, and likely adjacent work.

2. **Find an existing Beads overall goal first**
   - Run from project root:
   ```bash
   bd list --json
   ```
   - Prefer an existing matching top-level goal over creating a duplicate.
   - If the request clearly fits under an existing goal, attach work there instead of creating another top-level goal.
   - If no suitable goal exists, create one top-level goal as the overall container.

3. **Create a discovery/spec task under that goal when needed**
   - Add a focused child task for discovery/spec definition, not implementation, when scope is not yet stable.
   - Keep assumptions, provisional scope, and open questions in the Beads task text.
   - Make the task about clarifying scope, capabilities, success criteria, and non-goals.

4. **Do not create OpenSpec yet unless stable**
   - Only propose OpenSpec creation when success criteria, boundaries, and capability-level intent are clear enough to act as a durable contract.
   - If the request is still fuzzy, stop after the Beads intake steps and next-step guidance.

5. **Guide the next command explicitly**
   - If still fuzzy: say that the work is currently tracked in Beads and continue discovery there.
   - Once stable: tell the user to run `/opsx-propose <stable-change-name>` to create OpenSpec artifacts.

**Output**

- Overall goal used, whether reused or newly created, and its Beads identifier
- Any child discovery/spec task created and its identifier
- Clear statement that scope is currently tracked in Beads, not OpenSpec
- Exact next command recommendation once stable

**Guardrails**

- Beads-first intake for fuzzy work is mandatory.
- Prefer reusing an existing matching overall goal over creating a duplicate.
- Keep language non-jargony; explain terms when needed.
- Avoid premature OpenSpec creation.
