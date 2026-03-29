# Examples Catalog

This catalog intentionally keeps the canonical user-facing path small. The retained set favors recognized process patterns, explicit boundary feeds, boundary sinks, named junction topology, and explicit connection edges over one-off API or actuator demonstrations.

`examples/connection_layer/two_tank_reaction_comparison.py` remains in-repo as a proof/verification reference, not as a canonical onboarding example.

## Canonical examples

| Example | Capability demonstrated | Why it stays canonical |
| --- | --- | --- |
| `examples/unit_process_flowsheet/easy_2_heater_flash.py` | Single-feed heater plus flash separation | Smallest grounded flowsheet with one feed, two unit operations, and explicit product split |
| `examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py` | Dual-feed heat exchange | Shows multi-branch flowsheet wiring with two boundary feeds and explicit exchanger ports |
| `examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py` | Explicit recycle-topology composability with separation, purge handling, and line-installed recycle boost | Demonstrates a larger but still readable flowsheet with an explicit recycle return edge, junction-owned branching, a line-installed recycle pump, and boundary sinks |

## Selection rules

- Keep the canonical set to a handful of examples with distinct teaching value.
- Prefer examples with explicit boundary feeds, boundary sinks, named junction topology, and explicit unit-to-unit connections.
- Remove overlapping variants from the primary path even when they remain useful as deep references.
- Keep control- and API-heavy examples as secondary references until they match the same flowsheet conventions.

## Inventory decisions

| Example or group | Classification | Notes |
| --- | --- | --- |
| `examples/unit_process_flowsheet/easy_2_heater_flash.py` | keep | Canonical smallest flowsheet |
| `examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py` | keep | Canonical multi-feed flowsheet |
| `examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py` | keep | Canonical advanced flowsheet with an explicit recycle return edge, line-installed recycle pump, junction-owned branching, and boundary sinks |
| `examples/connection_layer/two_tank_reaction_comparison.py` | reference-only | Connected-plant parity benchmark retained as proof/verification material |
| `examples/unit_process_flowsheet/flowsheet_demo.py` | remove | Overlaps with the retained flowsheet set and uses unit-local control wiring |
| `examples/unit_process_flowsheet/complex_5_dual_feed_blend_reaction.py` | reference-only | Useful as a non-canonical reference, but the reactor path still diverges from the current flowsheet runtime contract |
| `examples/unit_process_flowsheet/complex_7_unipol_simplified_purge_bin.py` | remove | Valuable advanced reference, but too large for the canonical path |
| `examples/unit_process_flowsheet/complex_8_pressure_flash_recovery.py` | remove | Valuable advanced reference, but too large for the canonical path |
| `examples/dynamic_api_cli/*.py` | remove | Useful API/runtime references, but not flowsheet-first onboarding examples |
| `examples/connection_layer/pump_causality_demo.py` | remove | Specialized connection behavior reference |
| `examples/connection_layer/split_reversal_demo.py` | remove | Specialized connection behavior reference |
| `examples/connection_layer/benchmarks/macro_coupling_benchmark.py` | remove | Benchmark utility, not a canonical learning path |
| `examples/dynamic_simulation_demos/*.py` | remove | Broader equipment demos, but not part of the curated path |
| `examples/van_de_vusse_cstr/*.py` | remove | Classical reference, but not aligned with the canonical flowsheet-first style |
| `examples/simple_irreversible_system/*.py` | remove | Deeper process-model reference rather than canonical example |
| `examples/simple_irreversible_energy_balance_system/*.py` | remove | Rich staged-control reference, but not canonical while unit-local actuators remain embedded |
| `examples/simplified_gas_phase_system/*.py` | remove | Deeper process-model reference |
| `examples/gas_phase_polymerization/*.py` | remove | Deeper process-model reference |

## Migration map

| If you previously used | Start here now |
| --- | --- |
| `examples/dynamic_api_cli/minimal_command_quickstart.py` | `examples/unit_process_flowsheet/easy_2_heater_flash.py` for the smallest grounded topology |
| `examples/dynamic_api_cli/minimal_control_loop_save_load.py` | `examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py` for a maintained advanced topology path |
| `examples/dynamic_api_cli/minimal_spec_quickstart.py` | `examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py` for explicit multi-branch port wiring |
| `examples/unit_process_flowsheet/flowsheet_demo.py` | `examples/unit_process_flowsheet/easy_2_heater_flash.py` or `examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py` |
| `examples/van_de_vusse_cstr/run_simulation.py` | `examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py` for an advanced grounded process train |
| `examples/simple_irreversible_energy_balance_system/three_tank_staged_connected_control.py` | `examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py` until a fully compliant controlled flowsheet example lands |

## Reference-only examples

The remaining examples stay in the repository as advanced references, benchmarks, or migration aids. They are intentionally not the default user-facing path.
