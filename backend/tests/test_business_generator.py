from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.business.generator import GenerationOptions, generate_dataset


@pytest.mark.parametrize(
    "as_of,days", [("2026-10-08T12:00:00+08:00", 365), ("2026-10-10T00:00:00+08:00", 1)]
)
def test_data_is_reproducible_and_preserves_time_money_and_refund_constraints(
    as_of: str, days: int
) -> None:
    options = GenerationOptions(as_of=datetime.fromisoformat(as_of), days=days, orders=300)
    dataset = generate_dataset(options)
    assert generate_dataset(options) == dataset
    start = options.as_of - timedelta(days=days)
    order_by_id = {row["id"]: row for row in dataset.rows["orders"]}
    item_by_id = {row["id"]: row for row in dataset.rows["order_items"]}
    totals = {order_id: Decimal("0.00") for order_id in order_by_id}
    refund_totals = {item_id: Decimal("0.00") for item_id in item_by_id}
    for item in dataset.rows["order_items"]:
        assert isinstance(item["paid_amount"], Decimal)
        assert item["paid_amount"] <= item["unit_price"] * item["quantity"]
        totals[item["order_id"]] += item["paid_amount"]
    for order in dataset.rows["orders"]:
        assert start <= order["ordered_at"] <= options.as_of
        assert order["paid_amount"] == totals[order["id"]]
        if order["status"] == "paid":
            assert order["ordered_at"] <= order["paid_at"] <= options.as_of
        else:
            assert order["paid_at"] is None
            assert order["paid_amount"] == 0
    for refund in dataset.rows["refunds"]:
        item = item_by_id[refund["order_item_id"]]
        order = order_by_id[item["order_id"]]
        assert order["paid_at"] <= refund["requested_at"] <= options.as_of
        if refund["status"] == "success":
            assert refund["requested_at"] <= refund["succeeded_at"] <= options.as_of
        else:
            assert refund["succeeded_at"] is None
        refund_totals[item["id"]] += refund["amount"]
        assert refund_totals[item["id"]] <= item["paid_amount"]
    assert dataset.summary["recent_30_days_paid_orders"] >= 2
    assert any(
        order["paid_at"] and order["paid_at"].date() == options.as_of.date()
        for order in dataset.rows["orders"]
    )


@pytest.mark.parametrize(
    "values", [{"days": 0}, {"orders": 1}, {"orders": 100001}, {"as_of": datetime(2026, 10, 8)}]
)
def test_invalid_generation_options(values: dict[str, object]) -> None:
    kwargs = {"as_of": datetime.fromisoformat("2026-10-08T12:00:00+08:00"), **values}
    with pytest.raises(ValueError):
        GenerationOptions(**kwargs)  # type: ignore[arg-type]
