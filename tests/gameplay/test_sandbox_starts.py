from __future__ import annotations

from pathlib import Path
import sys

from modular_simulation.gameplay.starts import build_start


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_phase1_start_scaffold_is_gas_first() -> None:
    start = build_start(start_id="phase1_process_sandbox_v1")
    scaffold = start.learner_start_scaffold
    assert scaffold.named_feed_ids == ("sweet_wet_gas",)
    assert scaffold.named_sink_ids == (
        "separator_gas",
        "unstabilized_condensate",
        "dry_gas",
        "ngl_liquids",
        "stabilized_condensate",
    )


def test_tutorial_starts_remain_unchanged() -> None:
    heater = build_start(start_id="heater_flash_tutorial_start_v1")
    assert heater.learner_start_scaffold.named_feed_ids == ("feed",)
    assert heater.learner_start_scaffold.named_sink_ids == ("vapor_product", "liquid_product")
