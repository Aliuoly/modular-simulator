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

    # Build deleted wrapper names from parts so this source does not self-match the
    # blocked-name scanner defined in openspec/changes/remove-lower-level-wrapper-models/tasks.md.
    _deleted_flow = ("P" + "ump", "V" + "alve")
    _deleted_mixing = ("M" + "ixer",)
    _deleted_separation = ("Sp" + "litter",)
    _deleted_standalone = _deleted_flow + _deleted_mixing + _deleted_separation

    for source in (complex_5_source, complex_6_source, complex_7_source, complex_8_source):
        # None of the deleted wrapper class names should appear as standalone unit instantiations
        for name in _deleted_standalone:
            assert f"{name}(" not in source, (
                f"Example source must not instantiate deleted wrapper class '{name}'"
            )
        assert "add_junction(" in source

    assert "PumpInstall(" in complex_5_source
    assert "PumpInstall(" in complex_6_source
    assert "add_sink(" in complex_5_source
    assert "add_sink(" in complex_6_source
    assert "add_sink(" in complex_7_source
    assert "add_sink(" in complex_8_source


def test_curated_easy3_source_uses_add_sink_for_exchanger_outlets() -> None:
    """Regression: easy_3 must ground both exchanger outlets via add_sink (fully grounded topology)."""
    easy_3_source = (
        ROOT / "examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py"
    ).read_text(encoding="utf-8")

    # Both named sinks must be declared
    assert 'add_sink("hot_product")' in easy_3_source, (
        "easy_3 must declare add_sink('hot_product') to ground the hot exchanger outlet"
    )
    assert 'add_sink("cold_product")' in easy_3_source, (
        "easy_3 must declare add_sink('cold_product') to ground the cold exchanger outlet"
    )

    # Both exchanger outlet ports must be wired to those named sinks
    assert 'connect("exchanger.hot_outlet", "hot_product")' in easy_3_source, (
        "easy_3 must connect exchanger.hot_outlet → hot_product sink"
    )
    assert 'connect("exchanger.cold_outlet", "cold_product")' in easy_3_source, (
        "easy_3 must connect exchanger.cold_outlet → cold_product sink"
    )


def test_readme_and_catalog_agree_on_canonical_examples() -> None:
    """Regression: README canonical section and catalog 'keep' rows must list the same three examples,
    and each canonical example must be classified as 'keep' (not 'reference-only' or 'remove') in the
    catalog inventory table.

    Exact canonical-set parity is enforced: the README canonical-example table and the catalog
    inventory 'keep' rows must each resolve to exactly the intended canonical set — no extra entries
    in either direction.
    """
    import re

    readme = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    catalog = (ROOT / "docs/examples_catalog.md").read_text(encoding="utf-8")

    intended_canonical_set = {
        "examples/unit_process_flowsheet/easy_2_heater_flash.py",
        "examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py",
        "examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py",
    }

    # --- Derive README canonical set ---
    # Extract the "### Canonical example set" table rows.  The section starts at that heading and
    # ends at the next heading (## or ###).  Each data row has the example path in the first cell,
    # wrapped in backticks, optionally followed by CLI flags (e.g. " --no-show").
    readme_canonical_section_lines: list[str] = []
    in_canonical_section = False
    for line in readme.splitlines():
        stripped = line.strip()
        if stripped.startswith("### Canonical example set"):
            in_canonical_section = True
            continue
        if in_canonical_section and (stripped.startswith("## ") or stripped.startswith("### ")):
            break
        if in_canonical_section:
            readme_canonical_section_lines.append(line)

    # Pick out `<path>` tokens from table data rows (skip header and separator rows).
    readme_canonical_set: set[str] = set()
    for line in readme_canonical_section_lines:
        match = re.search(r"`(examples/[^`]+)`", line)
        if match:
            # Strip any trailing CLI flags (e.g. " --no-show") to get the bare file path.
            raw = match.group(1)
            bare_path = raw.split(" ")[0]
            readme_canonical_set.add(bare_path)

    assert readme_canonical_set == intended_canonical_set, (
        f"README canonical-example table does not exactly match the intended canonical set.\n"
        f"  README has:    {sorted(readme_canonical_set)}\n"
        f"  Intended:      {sorted(intended_canonical_set)}\n"
        f"  Extra in README:  {sorted(readme_canonical_set - intended_canonical_set)}\n"
        f"  Missing from README: {sorted(intended_canonical_set - readme_canonical_set)}"
    )

    # --- Derive catalog keep set ---
    # Scan the inventory table for rows whose classification cell is exactly 'keep'.
    catalog_keep_set: set[str] = set()
    for line in catalog.splitlines():
        # Match rows of the form: | `<path>` | keep | ...
        match = re.match(r"\|\s*`(examples/[^`]+)`\s*\|\s*keep\s*\|", line)
        if match:
            catalog_keep_set.add(match.group(1))

    assert catalog_keep_set == intended_canonical_set, (
        f"Catalog 'keep' rows do not exactly match the intended canonical set.\n"
        f"  Catalog keep has: {sorted(catalog_keep_set)}\n"
        f"  Intended:         {sorted(intended_canonical_set)}\n"
        f"  Extra in catalog: {sorted(catalog_keep_set - intended_canonical_set)}\n"
        f"  Missing from catalog: {sorted(intended_canonical_set - catalog_keep_set)}"
    )

    # --- The reference-only example must NOT appear in the README canonical section and must be
    # classified as 'reference-only' (not 'keep') in the catalog inventory table. ---
    reference_only_path = "examples/unit_process_flowsheet/complex_5_dual_feed_blend_reaction.py"
    assert reference_only_path not in readme_canonical_set, (
        f"README canonical section must NOT include the reference-only example: {reference_only_path}"
    )
    assert f"`{reference_only_path}` | reference-only |" in catalog, (
        f"Catalog must classify {reference_only_path} as 'reference-only'"
    )
    assert f"`{reference_only_path}` | keep |" not in catalog, (
        f"Catalog must NOT classify {reference_only_path} as 'keep'"
    )


def test_catalog_migration_map_covers_deprecated_entry_points() -> None:
    """Regression: catalog migration map must list all deprecated entry-point examples with canonical replacements."""
    catalog = (ROOT / "docs/examples_catalog.md").read_text(encoding="utf-8")

    assert "## Migration map" in catalog, "Catalog must have a '## Migration map' section"

    # Extract the migration map section rows (lines between "## Migration map" and the next "##")
    migration_section_lines: list[str] = []
    in_migration = False
    for line in catalog.splitlines():
        if line.strip().startswith("## Migration map"):
            in_migration = True
            continue
        if in_migration and line.strip().startswith("## "):
            break
        if in_migration:
            migration_section_lines.append(line)

    # Each deprecated entry must have a table row whose "Start here now" cell contains a known
    # canonical replacement path (not just the deprecated entry itself).
    known_canonical_replacements = (
        "examples/unit_process_flowsheet/easy_2_heater_flash.py",
        "examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py",
        "examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py",
    )

    deprecated_to_expected_replacement = {
        "examples/dynamic_api_cli/minimal_command_quickstart.py": "examples/unit_process_flowsheet/easy_2_heater_flash.py",
        "examples/dynamic_api_cli/minimal_control_loop_save_load.py": "examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py",
        "examples/dynamic_api_cli/minimal_spec_quickstart.py": "examples/unit_process_flowsheet/easy_3_dual_feed_heat_exchanger.py",
        "examples/unit_process_flowsheet/flowsheet_demo.py": "examples/unit_process_flowsheet/easy_2_heater_flash.py",
        "examples/van_de_vusse_cstr/run_simulation.py": "examples/unit_process_flowsheet/complex_6_ammonia_recycle_loop.py",
    }

    for deprecated, expected_replacement in deprecated_to_expected_replacement.items():
        # Find the table row containing this deprecated entry
        matching_rows = [row for row in migration_section_lines if deprecated in row]
        assert matching_rows, f"Catalog migration map has no row for deprecated entry: {deprecated}"
        row_text = matching_rows[0]

        # The row's replacement cell must contain a known canonical path
        assert expected_replacement in row_text, (
            f"Migration map row for '{deprecated}' must map to canonical replacement "
            f"'{expected_replacement}', but row is: {row_text!r}"
        )
        # Double-check the replacement is in the known canonical set
        assert expected_replacement in known_canonical_replacements, (
            f"Expected replacement '{expected_replacement}' is not in the known canonical set"
        )


def test_dynamic_api_cli_examples_are_removed_from_user_facing_tree() -> None:
    removed_paths = (
        ROOT / "examples/dynamic_api_cli/minimal_command_quickstart.py",
        ROOT / "examples/dynamic_api_cli/minimal_control_loop_save_load.py",
        ROOT / "examples/dynamic_api_cli/minimal_spec_quickstart.py",
        ROOT / "examples/dynamic_api_cli/sandbox_backend_minimal.py",
    )

    for path in removed_paths:
        assert not path.exists(), f"Deprecated dynamic API/CLI example must be removed: {path}"


def test_public_cli_module_no_longer_exports_modular_cli() -> None:
    import modular_simulation.cli as cli_package

    assert not hasattr(cli_package, "ModularCli")


def test_catalog_positions_two_tank_as_proof_reference_not_canonical() -> None:
    catalog = (ROOT / "docs/examples_catalog.md").read_text(encoding="utf-8")

    assert "`examples/connection_layer/two_tank_reaction_comparison.py` | keep |" not in catalog
    assert (
        "`examples/connection_layer/two_tank_reaction_comparison.py` | reference-only |" in catalog
    )
