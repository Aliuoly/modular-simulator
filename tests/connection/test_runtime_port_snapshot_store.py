from __future__ import annotations

# pyright: reportMissingImports=false

from copy import deepcopy
from typing import cast

import pytest

from modular_simulation.connection.runtime.runtime_port_snapshot_store import (
    RuntimePortSnapshotStore,
)
from modular_simulation.connection.domain.state import MaterialState, PortCondition


def _condition(
    *,
    pressure: float,
    temperature: float,
    flow: float,
    composition: tuple[float, ...] = (0.6, 0.4),
    macro_step_time_s: float | None = None,
) -> PortCondition:
    species_ids = ("a", "b")
    return PortCondition(
        state=MaterialState(
            pressure=pressure,
            temperature=temperature,
            mole_fractions=composition,
            species_ids=species_ids,
            phase="liquid",
            enthalpy_molar=1250.0,
            entropy_molar=8.5,
        ),
        species_ids=species_ids,
        through_molar_flow_rate=flow,
        macro_step_time_s=macro_step_time_s,
    )


def _payload(condition: PortCondition) -> dict[str, object]:
    return cast(dict[str, object], condition.model_dump(mode="python"))


def test_store_owns_latest_inlet_condition_by_port_key() -> None:
    store = RuntimePortSnapshotStore()
    original = _condition(pressure=101325.0, temperature=300.0, flow=1.25)
    replacement = _condition(pressure=125000.0, temperature=315.0, flow=2.5)
    outlet = _condition(pressure=90000.0, temperature=330.0, flow=-0.4)

    store.record_inlet("reactor", "feed", original)
    store.record_outlet("reactor", "feed", outlet)
    store.record_inlet("reactor", "feed", replacement)

    assert store.get_inlet("reactor", "feed") == replacement
    assert store.get_outlet("reactor", "feed") == outlet


def test_snapshot_payload_is_deterministic_and_namespaced() -> None:
    store = RuntimePortSnapshotStore()
    inlet_a = _condition(pressure=150000.0, temperature=298.0, flow=0.8)
    inlet_b = _condition(pressure=120000.0, temperature=305.0, flow=1.1)
    inlet_c = _condition(pressure=118000.0, temperature=302.0, flow=0.6)
    outlet_a = _condition(pressure=110000.0, temperature=320.0, flow=0.9)
    outlet_b = _condition(pressure=108000.0, temperature=325.0, flow=0.4)

    store.record_outlet("separator", "vapour", outlet_b)
    store.record_inlet("reactor", "recycle", inlet_b)
    store.record_inlet("absorber", "solvent", inlet_a)
    store.record_outlet("reactor", "product", outlet_a)
    store.record_inlet("reactor", "feed", inlet_c)

    assert store.snapshot_payload() == {
        "inlets": {
            "absorber": {"solvent": _payload(inlet_a)},
            "reactor": {
                "feed": _payload(inlet_c),
                "recycle": _payload(inlet_b),
            },
        },
        "outlets": {
            "reactor": {"product": _payload(outlet_a)},
            "separator": {"vapour": _payload(outlet_b)},
        },
    }


def test_store_clear_and_restore_round_trip_normalizes_port_conditions() -> None:
    store = RuntimePortSnapshotStore()
    inlet = _condition(
        pressure=140000.0,
        temperature=312.0,
        flow=1.75,
        composition=(0.25, 0.75),
        macro_step_time_s=4.0,
    )
    outlet = _condition(
        pressure=135000.0,
        temperature=318.0,
        flow=1.5,
        composition=(0.55, 0.45),
        macro_step_time_s=4.0,
    )
    store.record_inlet("reactor", "feed", inlet)
    store.record_outlet("reactor", "product", outlet)

    baseline_payload = store.snapshot_payload()
    restored_payload = deepcopy(baseline_payload)
    inlet_payload = cast(dict[str, object], restored_payload["inlets"]["reactor"]["feed"])
    inlet_state_payload = cast(dict[str, object], inlet_payload["state"])
    inlet_payload["species_ids"] = ["a", "b"]
    inlet_state_payload["mole_fractions"] = [0.25, 0.75]
    inlet_state_payload["species_ids"] = ["a", "b"]

    outlet_payload = cast(
        dict[str, object],
        restored_payload["outlets"]["reactor"]["product"],
    )
    outlet_state_payload = cast(dict[str, object], outlet_payload["state"])
    outlet_payload["species_ids"] = ["a", "b"]
    outlet_state_payload["mole_fractions"] = [0.55, 0.45]
    outlet_state_payload["species_ids"] = ["a", "b"]

    store.clear()

    assert store.snapshot_payload() == {"inlets": {}, "outlets": {}}

    store.restore_from_payload(restored_payload)

    assert store.get_inlet("reactor", "feed") == inlet
    assert store.get_outlet("reactor", "product") == outlet
    assert store.snapshot_payload() == baseline_payload


def test_store_restore_rejects_invalid_port_condition_payload_shape() -> None:
    store = RuntimePortSnapshotStore()
    existing = _condition(pressure=101325.0, temperature=300.0, flow=1.0)
    store.record_inlet("reactor", "feed", existing)
    baseline_payload = store.snapshot_payload()

    with pytest.raises(
        ValueError,
        match=(
            r"invalid runtime port snapshot payload: field "
            + r"'inlets\.reactor\.feed\.state\.temperature' is invalid: Field required"
        ),
    ):
        store.restore_from_payload(
            {
                "inlets": {
                    "reactor": {
                        "feed": {
                            "state": {
                                "pressure": 101325.0,
                                "mole_fractions": (0.6, 0.4),
                            },
                            "through_molar_flow_rate": 1.0,
                        }
                    }
                },
                "outlets": {},
            }
        )

    assert store.snapshot_payload() == baseline_payload
