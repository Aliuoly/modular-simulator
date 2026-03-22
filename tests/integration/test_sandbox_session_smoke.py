from __future__ import annotations

import pytest

from modular_simulation.gameplay import economics, sandbox_session
from modular_simulation.gameplay.contracts import SandboxRequestError


def test_sandbox_smoke_build_load_step_flow() -> None:
    sandbox_session.start_sandbox()
    economics.open_cash_ledger(initial_cash=2_000.0)

    line_quote = economics.quote_equipment_purchase(
        "build_process_line",
        config={"length_m": 3.0, "radius_m": 0.05},
    )
    assert line_quote.quoted_amount == pytest.approx(42.0)
    line_receipt = economics.record_equipment_purchase(
        "build_process_line",
        config={"length_m": 3.0, "radius_m": 0.05},
    )
    sandbox_session.install_catalog_item(
        "build_process_line",
        config={"length_m": 3.0, "radius_m": 0.05},
        equipment_receipt_id=line_receipt.receipt_id,
    )

    feed_quote = economics.quote_feed_purchase("feed_a", quantity_mol=1.0)
    assert feed_quote.quoted_amount == pytest.approx(2.0)
    feed_receipt = economics.record_feed_purchase("feed_a", quantity_mol=1.0)
    sandbox_session.load_feed_inventory(
        "feed_a",
        1.0,
        procurement_receipt_id=feed_receipt.receipt_id,
    )

    step_result = sandbox_session.advance(1.0)
    assert step_result.snapshot.elapsed_time_s == pytest.approx(1.0)


def test_tutorial_smoke_elapsed_completion_has_no_score() -> None:
    sandbox_session.start_tutorial("heater_flash_guided_build_v1")
    sandbox_session.install_catalog_item("place_heater_cooler", config={})
    sandbox_session.install_catalog_item("place_flash_drum", config={})
    for _ in range(4):
        sandbox_session.install_catalog_item("build_process_line", config={})

    snapshot = sandbox_session.get_simulation_state()
    assert snapshot.tutorial_completion_time_s == pytest.approx(snapshot.elapsed_time_s)
    assert not hasattr(snapshot, "score")


def test_recycle_tutorial_smoke_withdraw_sell_and_replay_rejection() -> None:
    sandbox_session.start_tutorial("recycle_purge_tradeoff_v1")
    economics.open_cash_ledger(initial_cash=2_000.0)

    purge_receipt = economics.record_equipment_purchase("install_line_valve", config={})
    sandbox_session.install_catalog_item(
        "install_line_valve",
        config={},
        equipment_receipt_id=purge_receipt.receipt_id,
    )
    recycle_receipt = economics.record_equipment_purchase("install_line_pump", config={})
    sandbox_session.install_catalog_item(
        "install_line_pump",
        config={},
        equipment_receipt_id=recycle_receipt.receipt_id,
    )

    sandbox_session.advance(1.0)

    withdrawal = sandbox_session.withdraw_product_inventory("product_a", 0.1)
    quote = economics.quote_product_sale("product_a", quantity_mol=0.1)
    assert quote.subject_kind == "product_sale"
    sale = economics.record_product_sale(withdrawal.withdrawal_id)
    assert sale.withdrawal_id == withdrawal.withdrawal_id

    with pytest.raises(SandboxRequestError) as replay:
        economics.record_product_sale(withdrawal.withdrawal_id)
    assert replay.value.error_code == "unknown_withdrawal_id"

    assert not hasattr(sandbox_session, "quote_product_sale")
