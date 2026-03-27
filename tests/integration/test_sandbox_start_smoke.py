from __future__ import annotations

from pathlib import Path
import sys

from modular_simulation.gameplay.starts import build_start


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_sandbox_start_smoke_gas_seed_alignment() -> None:
    start = build_start(start_id="phase1_process_sandbox_v1")
    assert start.seed_source_paths == (
        "examples/unit_process_flowsheet/gas_1_inlet_separator.py",
        "examples/unit_process_flowsheet/gas_2_teg_dehydration.py",
        "examples/unit_process_flowsheet/gas_3_jt_low_temperature_separation.py",
        "examples/unit_process_flowsheet/gas_4_condensate_stabilizer.py",
    )
    assert set(start.seed_instances_by_path) == set(start.seed_source_paths)
