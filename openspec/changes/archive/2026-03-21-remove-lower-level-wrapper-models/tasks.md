## Wave 1 — Freeze the stronger removal contract in OpenSpec

- [x] 1.1 Add the delta spec for `flowsheet-junction-line-api` documenting that live non-archive repository content no longer ships or mentions the lower-level deleted unit-process wrapper models anywhere.
- [x] 1.2 Keep this task pack execution-ready: exact files, exact verification commands, and explicit live-vs-archive scope.

## Wave 2 — Remove the live wrapper-model source surfaces

- [x] 2.1 Delete these lower-level wrapper source files from the live repository:
  - `src/modular_simulation/unit_processes/flow/pump.py`
  - `src/modular_simulation/unit_processes/flow/valve.py`
  - `src/modular_simulation/unit_processes/mixing/mixer.py`
  - `src/modular_simulation/unit_processes/separation/splitter.py`
- [x] 2.2 Rewrite package surfaces so they no longer preserve wrapper-name guidance in live code:
  - `src/modular_simulation/unit_processes/__init__.py`
  - `src/modular_simulation/unit_processes/flow/__init__.py`
  - `src/modular_simulation/unit_processes/mixing/__init__.py`
  - `src/modular_simulation/unit_processes/separation/__init__.py`
- [x] 2.3 Remove wrapper-name handling from:
  - `src/modular_simulation/measurables/process_model.py`
  - `src/modular_simulation/thermodynamics/hydraulic_adapters.py`

## Wave 3 — Rewrite or retire live tests and docs that still mention the wrapper models

- [x] 3.1 Remove or rewrite dedicated wrapper-name tests so live tests no longer mention the deleted models:
  - `tests/unit_process/test_canonical_wrapper_removal.py`
  - `tests/test_save_load_minimal.py`
- [x] 3.2 Rewrite behavior/regression tests that still directly import or instantiate the deleted wrapper models using supported surfaces, direct hydraulic primitives, or local synthetic fixtures:
  - `tests/unit_process/test_layer4_pump_valve.py`
  - `tests/unit_process/test_layer4_mixer_splitter.py`
  - `tests/unit_process/test_flowsheet_validation.py`
  - `tests/connection/test_hydraulic_compile.py`
  - `tests/connection/test_thermo_coupling_runtime_store.py`
  - `tests/controller_contract_harness.py`
- [x] 3.3 Remove remaining live docs mentions:
  - `docs/README.md`
  - any non-archive docs under `docs/` that still mention the deleted wrapper model names

## Wave 4 — Verification and search gates

- [x] 4.1 Run the targeted test matrix:
  - `uv run pytest tests/connection/test_hydraulic_compile.py tests/connection/test_thermo_coupling_runtime_store.py tests/unit_process/test_flowsheet_validation.py tests/controller_contract_harness.py tests/test_rework_examples_review_alignment.py`
- [x] 4.2 Run live-repo search verification with this exact command and confirm it prints no matches:
  - `uv run python - <<'PY'
from pathlib import Path
import re

root = Path('.')
# Build the pattern from parts so this scanner source does not self-match
_deleted = ['P' + 'ump', 'V' + 'alve', 'M' + 'ixer', 'Sp' + 'litter']
blocked = re.compile(r'\b(' + '|'.join(_deleted) + r')\b')
allowed_prefixes = (
    Path('openspec/changes/archive'),
    Path('openspec/changes/remove-lower-level-wrapper-models'),
    Path('.worktrees'),
    Path('.venv'),
    Path('dist'),
)
hits = []
for path in root.rglob('*'):
    if not path.is_file():
        continue
    rel = path.relative_to(root)
    if any(rel == prefix or prefix in rel.parents for prefix in allowed_prefixes):
        continue
    if rel.suffix not in {'.py', '.md'}:
        continue
    text = path.read_text(encoding='utf-8', errors='ignore')
    for line_no, line in enumerate(text.splitlines(), start=1):
        if blocked.search(line):
            hits.append(f'{rel}:{line_no}:{line.strip()}')
if hits:
    raise SystemExit('\n'.join(hits))
PY`
- [x] 4.3 Run `openspec validate remove-lower-level-wrapper-models --strict`.

## Wave 5 — Sync the settled spec

- [x] 5.1 After implementation and verification are green, sync the delta spec into `openspec/specs/flowsheet-junction-line-api/spec.md` so the main spec reflects the stronger full-removal contract.
