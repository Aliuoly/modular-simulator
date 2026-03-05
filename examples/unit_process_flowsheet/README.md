# Unit-Process Flowsheet Demo

This example shows the simplified `Flowsheet` builder API with one feed, chained units, explicit multi-outlet wiring, and system-level sensor/controller installation.

`feed -> heater -> flash -> {vapor_trim, liquid_trim}`

Core flow setup in the demo:

- build a flowsheet via `add_unit(...)`, `add_feed_from_values(...)`, `chain(...)`, and `connect(...)`
- use explicit ports for multi-outlet routing:
  - `connect("flash.vapor_outlet", "vapor_trim")`
  - `connect("flash.liquid_outlet", "liquid_trim")`
- install a sensor and PID controller on `flowsheet.get_system("heater")`
- run with `compile()` and `run()` and query outputs with `FlowsheetResults.get_unit(...)` and `get_stream(...)`

## Run

```bash
uv run python examples/unit_process_flowsheet/flowsheet_demo.py
```

The script prints key KPIs, including:

- final simulation time
- vapor and liquid branch flow rates from the flash split
- ethanol mole fraction in each flash outlet stream

You can also import and run programmatically:

```python
from examples.unit_process_flowsheet.flowsheet_demo import run_flowsheet_demo

summary = run_flowsheet_demo(print_results=False)
print(summary["vapor_flow_mol_s"])
```
