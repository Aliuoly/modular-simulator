from __future__ import annotations

from modular_simulation.gameplay import economics, sandbox_session


def run_demo() -> dict[str, object]:
    start_snapshot = sandbox_session.start_sandbox()
    initial_ledger = economics.open_cash_ledger(initial_cash=2_000.0)

    equipment_receipt = economics.record_equipment_purchase(
        "build_process_line",
        config={"length_m": 3.0, "radius_m": 0.05},
    )
    install_result = sandbox_session.install_catalog_item(
        "build_process_line",
        config={"length_m": 3.0, "radius_m": 0.05},
        equipment_receipt_id=equipment_receipt.receipt_id,
    )

    feed_receipt = economics.record_feed_purchase("feed_a", quantity_mol=1.0)
    load_result = sandbox_session.load_feed_inventory(
        "feed_a",
        1.0,
        procurement_receipt_id=feed_receipt.receipt_id,
    )

    step = sandbox_session.advance(1.0)
    withdrawal = sandbox_session.withdraw_product_inventory("product_a", 0.1)
    sale = economics.record_product_sale(withdrawal.withdrawal_id)

    final_state = sandbox_session.get_simulation_state()
    final_ledger = economics.get_cash_ledger()

    return {
        "start_id": start_snapshot.active_start_id,
        "initial_cash": initial_ledger.cash_balance,
        "equipment_receipt_id": equipment_receipt.receipt_id,
        "feed_receipt_id": feed_receipt.receipt_id,
        "installed_count": len(install_result.snapshot.installed_item_instance_ids),
        "loaded_feed_a_mol": load_result.snapshot.feed_inventory_by_material_id.get("feed_a", 0.0),
        "step_elapsed_time_s": step.snapshot.elapsed_time_s,
        "withdrawal_id": withdrawal.withdrawal_id,
        "sale_receipt_id": sale.receipt_id,
        "sale_revenue": sale.gross_revenue,
        "remaining_product_a_mol": final_state.product_inventory_by_product_id.get(
            "product_a", 0.0
        ),
        "cash_balance": final_ledger.cash_balance,
    }


if __name__ == "__main__":
    print(run_demo())
