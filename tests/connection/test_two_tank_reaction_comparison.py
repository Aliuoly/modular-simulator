from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

# Imports of the example module are performed inside tests to ensure
# the repository root is on sys.path in all environments.

# Bootstrap test path for module imports without importing before imports
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_connection_layer_two_tank_cascade_tracks_ad_hoc_coupled_rhs() -> None:
    # Local import to ensure import path setup is handled at runtime
    from pathlib import Path
    import sys

    ROOT = Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from examples.connection_layer.two_tank_reaction_comparison import TankCascadeConfig, run_demo

    result = run_demo(TankCascadeConfig(horizon_s=5.0, dt_s=0.05))

    assert result.max_abs_error_a <= 1.0e-7
    assert result.max_abs_error_b <= 2.5e-3
    assert result.rmse_b <= 2.0e-3

    tank_b_connection = result.tank_b_connection
    tank_b_reference = result.tank_b_reference
    assert abs(float(tank_b_connection[-1] - tank_b_reference[-1])) <= 2.0e-3


def test_two_tank_cascade_shows_expected_decay_and_lag_trends() -> None:
    # Local import to ensure import path setup is handled at runtime
    from pathlib import Path
    import sys

    ROOT = Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from examples.connection_layer.two_tank_reaction_comparison import TankCascadeConfig, run_demo

    result = run_demo(TankCascadeConfig(horizon_s=5.0, dt_s=0.05))
    tank_a = result.tank_a_connection
    tank_b = result.tank_b_connection

    assert result.monotonic_decay_a
    assert result.monotonic_decay_b
    assert result.b_lag_steps >= 1

    assert abs(float(tank_a[0] - 1.0)) <= 1.0e-12
    assert abs(float(tank_b[0] - 1.0)) <= 1.0e-12
    assert tank_a[-1] < tank_a[0]
    assert tank_b[-1] < tank_b[0]

    assert tank_b[4] > tank_a[4]


def test_example_uses_connected_plant_runtime_abstraction_without_placeholders() -> None:
    # Local import to ensure import path setup is handled at runtime
    from pathlib import Path
    import sys

    ROOT = Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    module = import_module("examples.connection_layer.two_tank_reaction_comparison")
    module_file = module.__file__
    assert module_file is not None
    source = Path(module_file).read_text(encoding="utf-8")

    assert "ConnectionNetwork" in source
    assert "SubsystemRuntimeDescriptor" in source
    assert "Subsystem" in source
    assert "ConnectedPlantOrchestrator" in source
    assert "ConnectedPlantPhaseHooks" in source
    assert "ConnectionRuntimeOrchestrator" in source
    assert "ProcessModelAdapter" not in source
    assert "class SubsystemDescriptor" not in source
    assert "return _simulate_connection_layer(cfg_simple)" not in source
    assert "_input_streams" not in source
    assert "_output_streams" not in source


def test_subsystem_abstraction_path_parity() -> None:
    # Local import to ensure import path setup is handled at runtime
    from pathlib import Path
    import sys
    import numpy as np

    ROOT = Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from examples.connection_layer.two_tank_reaction_comparison import TankCascadeConfig, run_demo

    base = run_demo(TankCascadeConfig(horizon_s=5.0, dt_s=0.05, use_subsystem_abstraction=False))
    sub = run_demo(TankCascadeConfig(horizon_s=5.0, dt_s=0.05, use_subsystem_abstraction=True))

    assert base.max_abs_error_a <= 1.0e-7
    assert base.max_abs_error_b <= 2.5e-3
    assert base.rmse_b <= 2.0e-3
    assert sub.max_abs_error_a <= 1.0e-7
    assert sub.max_abs_error_b <= 2.5e-3
    assert sub.rmse_b <= 2.0e-3
    assert base.monotonic_decay_a
    assert base.monotonic_decay_b
    assert base.b_lag_steps >= 1
    assert sub.monotonic_decay_a
    assert sub.monotonic_decay_b
    assert sub.b_lag_steps >= 1

    assert np.allclose(sub.times_s, base.times_s)
    assert np.allclose(sub.tank_a_connection, base.tank_a_connection, atol=1e-12)
    assert np.allclose(sub.tank_b_connection, base.tank_b_connection, atol=1e-12)
    assert np.allclose(sub.tank_a_reference, base.tank_a_reference, atol=1e-12)
    assert np.allclose(sub.tank_b_reference, base.tank_b_reference, atol=1e-12)
    assert abs(sub.max_abs_error_a - base.max_abs_error_a) <= 1.0e-12
    assert abs(sub.max_abs_error_b - base.max_abs_error_b) <= 1.0e-12
    assert abs(sub.rmse_b - base.rmse_b) <= 1.0e-12
    assert sub.b_lag_steps == base.b_lag_steps
    assert sub.monotonic_decay_a == base.monotonic_decay_a
    assert sub.monotonic_decay_b == base.monotonic_decay_b
    assert abs(sub.b_not_below_a_fraction - base.b_not_below_a_fraction) <= 1.0e-12
