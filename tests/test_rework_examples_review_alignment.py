from __future__ import annotations

from pathlib import Path
from typing import Annotated

from astropy.units import Unit

from examples.unit_process_flowsheet import (
    complex_5_dual_feed_blend_reaction,
    complex_8_pressure_flash_recovery,
)
from modular_simulation.components import AbstractCalculation, DataValue, PointMetadata, TagType


ROOT = Path(__file__).resolve().parents[1]


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

    assert "boundary feeds/products" not in catalog
    assert "terminal unit outlets rather than high-level boundary sinks" in readme
    assert "explicit boundary feeds, clearly documented terminal unit outlets" in catalog


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
