from __future__ import annotations

# pyright: reportUnknownMemberType=false
from typing import cast

import pytest

from examples.unit_process_flowsheet.flowsheet_demo import run_flowsheet_demo


def test_multi_unit_flowsheet_demo_uses_network_coupling() -> None:
    kpis = run_flowsheet_demo(print_results=False)

    feed_temperature = cast(float, kpis["feed_temperature"])
    heater_outlet_temperature = cast(float, kpis["heater_outlet_temperature"])
    flash_vapor_fraction = cast(float, kpis["flash_vapor_fraction"])
    flash_vapor_flow = cast(float, kpis["vapor_flow_mol_s"])
    flash_total_flow = cast(float, kpis["flash_total_flow"])
    flash_vapor_composition = cast(tuple[float, ...], kpis["flash_vapor_composition"])
    flash_liquid_composition = cast(tuple[float, ...], kpis["flash_liquid_composition"])
    updated_port_keys = cast(tuple[str, ...], kpis["last_updated_port_keys"])

    assert heater_outlet_temperature >= feed_temperature - 1.0e-5
    assert 0.0 < flash_vapor_fraction < 1.0
    assert flash_vapor_composition[0] > flash_liquid_composition[0]
    assert sum(flash_vapor_composition) == pytest.approx(1.0, abs=1.0e-8)
    assert sum(flash_liquid_composition) == pytest.approx(1.0, abs=1.0e-8)
    assert {"flash.inlet", "vapor_trim.inlet", "liquid_trim.inlet"}.issubset(set(updated_port_keys))
    assert flash_vapor_flow < flash_total_flow
