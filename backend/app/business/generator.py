"""Pure, reproducible commerce generation: all money uses Decimal."""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

CENT = Decimal("0.01")
TIMEZONE = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class GenerationOptions:
    as_of: datetime
    days: int = 365
    orders: int = 10_000
    seed: int = 42

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("参考时间必须带时区，例如 2026-10-08T12:00:00+08:00。")
        if not 1 <= self.days <= 3650:
            raise ValueError("days 必须为 1 至 3650。")
        if not 2 <= self.orders <= 100_000:
            raise ValueError("orders 必须为 2 至 100000，以保证近期有已支付订单。")


@dataclass
class Dataset:
    rows: dict[str, list[dict[str, Any]]]
    summary: dict[str, Any]


def generate_dataset(options: GenerationOptions) -> Dataset:
    rng = random.Random(options.seed)
    as_of = options.as_of.astimezone(TIMEZONE).replace(microsecond=0)
    start = as_of - timedelta(days=options.days)
    names = ("数码", "家居", "服饰", "食品", "运动", "美妆")
    rows: dict[str, list[dict[str, Any]]] = {
        "customers": [
            {"id": i, "name": f"客户{i:04d}", "region": ("华东", "华南", "华北", "西部")[i % 4]}
            for i in range(1, min(500, options.orders) + 1)
        ],
        "categories": [{"id": i, "name": name} for i, name in enumerate(names, 1)],
        "products": [
            {
                "id": i,
                "category_id": (i - 1) // 10 + 1,
                "name": f"{names[(i - 1) // 10]}商品{i:02d}",
                "price": Decimal(rng.randint(1500, 120000)) / 100,
            }
            for i in range(1, 61)
        ],
        "orders": [],
        "order_items": [],
        "refunds": [],
    }
    # A weighted day distribution creates observable weekday and seasonal variation.
    day_count = options.days + 1
    weights = []
    for offset in range(day_count):
        day = start + timedelta(days=offset)
        weights.append((1.4 if day.weekday() >= 5 else 1.0) * (1.6 if day.month == 11 else 1.0))
    for order_id in range(1, options.orders + 1):
        if order_id <= 2:
            # Guaranteed recent sales, including a record on the reference date.
            midnight = as_of.replace(hour=0, minute=0, second=0)
            paid_at = max(start, midnight + (as_of - midnight) / 2).replace(microsecond=0)
            if order_id == 2:
                paid_at = max(start, as_of - timedelta(days=min(3, options.days) / 2))
        else:
            offset = rng.choices(range(day_count), weights=weights)[0]
            lower = start + timedelta(days=offset)
            upper = min(lower + timedelta(days=1), as_of)
            paid_at = lower + timedelta(
                seconds=rng.randint(0, int((upper - lower).total_seconds()))
            )
        ordered_at = max(start, paid_at - timedelta(minutes=rng.randint(0, 120)))
        is_paid = order_id <= 2 or rng.random() >= 0.07
        total = Decimal("0.00")
        for _ in range(rng.randint(1, 4)):
            product = rng.choices(
                rows["products"],
                weights=[[6, 4, 3, 5, 2, 3][p["category_id"] - 1] for p in rows["products"]],
            )[0]
            quantity = rng.randint(1, 3)
            amount = (
                (product["price"] * quantity * Decimal(rng.randint(85, 100)) / 100).quantize(CENT)
                if is_paid
                else Decimal("0.00")
            )
            item_id = len(rows["order_items"]) + 1
            rows["order_items"].append(
                {
                    "id": item_id,
                    "order_id": order_id,
                    "product_id": product["id"],
                    "quantity": quantity,
                    "unit_price": product["price"],
                    "paid_amount": amount,
                }
            )
            total += amount
            if is_paid and paid_at < as_of and rng.random() < 0.09:
                available = int((as_of - paid_at).total_seconds())
                requested = paid_at + timedelta(seconds=rng.randint(0, min(available, 86400 * 14)))
                success = rng.random() < 0.85
                succeeded = (
                    requested
                    + timedelta(seconds=rng.randint(0, int((as_of - requested).total_seconds())))
                    if success
                    else None
                )
                rows["refunds"].append(
                    {
                        "id": len(rows["refunds"]) + 1,
                        "order_item_id": item_id,
                        "status": "success" if success else "pending",
                        "requested_at": requested,
                        "succeeded_at": succeeded,
                        "amount": (amount * Decimal(rng.randint(10, 100)) / 100).quantize(CENT),
                    }
                )
        rows["orders"].append(
            {
                "id": order_id,
                "customer_id": rng.randint(1, len(rows["customers"])),
                "status": "paid" if is_paid else "unpaid",
                "ordered_at": ordered_at,
                "paid_at": paid_at if is_paid else None,
                "paid_amount": total,
            }
        )
    recent = [
        row
        for row in rows["orders"]
        if row["paid_at"] is not None and row["paid_at"] >= as_of - timedelta(days=30)
    ]
    summary = {
        "version": 1,
        "as_of": as_of.isoformat(),
        "coverage_start": start.isoformat(),
        "coverage_end": as_of.isoformat(),
        "days": options.days,
        "orders": options.orders,
        "seed": options.seed,
        "row_counts": {name: len(values) for name, values in rows.items()},
        "recent_30_days_paid_orders": len(recent),
        "recent_30_days_sales": str(sum((row["paid_amount"] for row in recent), Decimal("0.00"))),
    }
    return Dataset(rows=rows, summary=summary)
