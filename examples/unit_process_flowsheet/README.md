# Unit-Process Flowsheet Demo

This example runs a deterministic multi-unit train:

`Feed -> Heater -> CSTR -> FlashDrum -> ShortcutDistillation`

The demo uses the same runtime conventions as the unit-process tests:

- each unit is attached via `attach_system(SimpleNamespace(solver_options={}))`
- thermo-enabled units get `set_property_package(...)`
- the train is wired through `ConnectionNetwork`
- macro-step execution goes through `ConnectedPlantOrchestrator`
- boundary propagation uses thermo auto-coupling (`ThermoBoundaryPropagationStep`)

## Run

```bash
uv run python examples/unit_process_flowsheet/flowsheet_demo.py
```

The script prints key KPIs, including:

- heater and reactor outlet temperature
- flash vapor fraction and phase split behavior
- shortcut-distillation product purities and mass-balance residual

You can also import and run programmatically:

```python
from examples.unit_process_flowsheet.flowsheet_demo import run_flowsheet_demo

kpis = run_flowsheet_demo(print_results=False)
print(kpis["distillate_composition"])
```
