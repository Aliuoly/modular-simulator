from __future__ import annotations

from modular_simulation.gameplay import economics, sandbox_session


def test_sandbox_session_smoke_gas_buy_advance_sell() -> None:
    sandbox_session.start_sandbox()
    economics.open_cash_ledger(initial_cash=2_000.0)

    sep_receipt = economics.record_equipment_purchase("place_heater_cooler", config={})
    sandbox_session.install_catalog_item(
        "place_inlet_gas_separator",
        config={"process_id": "sep_1"},
        equipment_receipt_id=sep_receipt.receipt_id,
    )
    line_1 = economics.record_equipment_purchase(
        "build_process_line",
        config={"length_m": 3.0, "radius_m": 0.05},
    )
    sandbox_session.install_catalog_item(
        "build_process_line",
        config={
            "source": "sweet_wet_gas",
            "target": "sep_1.inlet",
            "length_m": 3.0,
            "radius_m": 0.05,
        },
        equipment_receipt_id=line_1.receipt_id,
    )
    line_2 = economics.record_equipment_purchase(
        "build_process_line",
        config={"length_m": 3.0, "radius_m": 0.05},
    )
    sandbox_session.install_catalog_item(
        "build_process_line",
        config={
            "source": "sep_1.vapor_outlet",
            "target": "separator_gas",
            "length_m": 3.0,
            "radius_m": 0.05,
        },
        equipment_receipt_id=line_2.receipt_id,
    )

    feed_receipt = economics.record_feed_purchase("sweet_wet_gas", quantity_mol=2.0)
    sandbox_session.load_feed_inventory(
        "sweet_wet_gas",
        2.0,
        procurement_receipt_id=feed_receipt.receipt_id,
    )
    step = sandbox_session.advance(1.0)
    assert step.product_production_by_product_id.get("separator_gas", 0.0) > 0.0
