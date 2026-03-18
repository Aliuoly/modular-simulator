from __future__ import annotations

from pathlib import Path
import sys
from typing import Annotated

from astropy.units import Unit

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from examples.unit_process_flowsheet import (
    complex_5_dual_feed_blend_reaction,
    complex_8_pressure_flash_recovery,
)
from modular_simulation.components import AbstractCalculation, DataValue, PointMetadata, TagType


ROOT = REPO_ROOT


class _SummingCalculation(AbstractCalculation):
    output_tag: Annotated[str, PointMetadata(type=TagType.OUTPUT, unit=Unit(""))]
    input_a: Annotated[str, PointMetadata(type=TagType.INPUT, unit=Unit(""))]
    input_b: Annotated[str, PointMetadata(type=TagType.INPUT, unit=Unit(""))]

    def _calculation_algorithm(self, t: float, inputs_dict: dict[str, float]) -> dict[str, float]:
        del t
        return {self.output_tag: inputs_dict[self.input_a] + inputs_dict[self.input_b]}


def test_abstract_calculation_fault_propagation_requires_all_inputs_ok() -> None:
    calculation = _SummingCalculation(output_tag="sum", input_a="a", input_b="b")
    calculation._initialized = True
    calculation._input_data_getters = {
        "a": lambda: DataValue(time=1.0, value=2.0, ok=True),
        "b": lambda: DataValue(time=1.0, value=3.0, ok=False),
    }

    outputs = calculation._calculate(t=1.0)

    assert calculation.ok is False
    assert outputs["sum"].value == 5.0
    assert outputs["sum"].ok is False


def test_curated_docs_describe_terminal_unit_outlets() -> None:
    readme = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    catalog = (ROOT / "docs/examples_catalog.md").read_text(encoding="utf-8")

    assert "terminal unit outlets rather than high-level boundary sinks" not in readme
    assert "boundary sinks" in readme
    assert "explicit boundary feeds, boundary sinks" in catalog


def test_complex_5_wording_matches_reference_only_catalog_status() -> None:
    module_doc = complex_5_dual_feed_blend_reaction.__doc__
    assert module_doc is not None
    assert module_doc.startswith("Reference flowsheet example")

    catalog = (ROOT / "docs/examples_catalog.md").read_text(encoding="utf-8")
    assert (
        "`examples/unit_process_flowsheet/complex_5_dual_feed_blend_reaction.py` | reference-only |"
    ) in catalog


def test_complex_8_pressure_flash_recovery_example_runs_and_returns_report() -> None:
    """Regression test: complex_8 example uses current Flowsheet API and produces valid output."""
    report = complex_8_pressure_flash_recovery.run_example(steps=5, dt=0.15, make_plot=False)

    assert isinstance(report, dict)
    assert "final_time_s" in report
    assert "feed_to_preheat_flow_mol_s" in report
    assert "flash_vapor_fraction" in report
    assert "mixed_product_temperature_K" in report
    assert all(isinstance(v, float) for v in report.values())


def test_reference_examples_use_junctions_sinks_and_line_installs_instead_of_wrapper_units() -> (
    None
):
    complex_5_source = (
        ROOT / "examples/unit_process_flowsheet/complex_5_dual_feed_blend_reaction.py"
    ).read_text(encoding="utf-8")
    complex_6_source = (
        ROOT / "examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py"
    ).read_text(encoding="utf-8")
    complex_7_source = (
        ROOT / "examples/unit_process_flowsheet/complex_7_unipol_simplified_purge_bin.py"
    ).read_text(encoding="utf-8")
    complex_8_source = (
        ROOT / "examples/unit_process_flowsheet/complex_8_pressure_flash_recovery.py"
    ).read_text(encoding="utf-8")

    for source in (complex_5_source, complex_6_source, complex_7_source, complex_8_source):
        assert " Mixer" not in source
        assert " Splitter" not in source
        assert "Pump(" not in source
        assert "Valve(" not in source
        assert "add_junction(" in source

    assert "PumpInstall(" in complex_5_source
    assert "PumpInstall(" in complex_6_source
    assert "add_sink(" in complex_5_source
    assert "add_sink(" in complex_6_source
    assert "add_sink(" in complex_7_source
    assert "add_sink(" in complex_8_source
