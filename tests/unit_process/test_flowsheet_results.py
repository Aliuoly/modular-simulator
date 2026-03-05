from __future__ import annotations

# pyright: reportMissingTypeStubs=false

import numpy as np
import pytest

from modular_simulation.flowsheet import Flowsheet
from modular_simulation.thermodynamics.runtime_context import SimulationRuntimeContext
from modular_simulation.thermodynamics.stream import StreamData
from modular_simulation.unit_processes import HeaterCooler


def test_results_access() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context, dt=0.2)

    heater = HeaterCooler(n_species=2, mode="duty", duty_setpoint=0.0)
    cooler = HeaterCooler(n_species=2, mode="duty", duty_setpoint=0.0)
    flowsheet.add_unit("heater", heater)
    flowsheet.add_unit("cooler", cooler)
    flowsheet.add_feed_from_values(
        "feed",
        T=320.0,
        P=140000.0,
        z=(0.5, 0.5),
        flow=2.0,
    )
    flowsheet.chain("feed", "heater", "cooler")

    results = flowsheet.run(steps=3)

    assert np.allclose(results.time_points, np.asarray([0.2, 0.4, 0.6]))

    unit_result = results.get_unit("heater")
    assert unit_result.unit_id == "heater"
    assert "outlet" in unit_result.outlet_streams
    assert isinstance(unit_result.outlet_streams["outlet"], StreamData)
    assert "outlet_temperature" in unit_result.state_history
    assert unit_result.state_history["outlet_temperature"].shape[0] == 3

    feed_to_heater = results.get_stream("feed", "heater")
    assert feed_to_heater.flow_rate.shape == (3,)
    assert feed_to_heater.temperature.shape == (3,)
    assert feed_to_heater.pressure.shape == (3,)
    assert feed_to_heater.composition.shape == (3, 2)

    summary = results.summary()
    assert "FlowsheetResults(steps=3" in summary
    assert "heater" in summary
    assert "feed->heater.inlet" in summary


def test_results_access_errors_are_clear() -> None:
    context = SimulationRuntimeContext.create(species_names=["water", "ethanol"])
    flowsheet = Flowsheet(context=context)
    flowsheet.add_unit("heater", HeaterCooler(n_species=2, mode="duty", duty_setpoint=0.0))
    flowsheet.add_feed_from_values("feed", T=300.0, P=101325.0, z=(0.5, 0.5), flow=1.0)
    flowsheet.connect("feed", "heater")

    results = flowsheet.run(steps=1)

    with pytest.raises(ValueError, match="unknown unit 'missing'"):
        _ = results.get_unit("missing")

    with pytest.raises(ValueError, match="unknown stream connection 'feed->missing'"):
        _ = results.get_stream("feed", "missing")
