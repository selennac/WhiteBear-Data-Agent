from datetime import datetime

import psycopg
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.business.generator import GenerationOptions
from app.business.storage import store_dataset
from app.business.tables import SCHEMA_MARKER
from app.core.config import Settings
from app.db.connections import connection_string, engine_for, parse_url
from app.db.initialize import initialize_database
from app.main import create_app


def test_provisioning_is_repeatable_and_initializes_checkpoints(
    database_settings: Settings,
) -> None:
    assert initialize_database(database_settings)["checkpoints"] == "ready"
    engine = engine_for(database_settings.app_database_url, "APP_DATABASE_URL")
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT to_regclass('public.checkpoints')")).scalar()
            assert (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
                == "0002"
            )
    finally:
        engine.dispose()


def test_generation_schema_metadata_permissions_and_scoped_reset(
    database_settings: Settings,
) -> None:
    options = GenerationOptions(as_of=datetime.fromisoformat("2026-10-08T12:00:00+08:00"))
    summary = store_dataset(database_settings, options)
    assert summary["row_counts"]["orders"] == 10000
    assert summary["recent_30_days_paid_orders"] >= 2
    with pytest.raises(ValueError, match="--reset"):
        store_dataset(database_settings, options)

    writer = engine_for(database_settings.business_database_url, "BUSINESS_DATABASE_URL")
    try:
        with writer.begin() as connection:
            connection.execute(text("CREATE TABLE public.reset_sentinel (id integer PRIMARY KEY)"))
            connection.execute(text("INSERT INTO public.reset_sentinel VALUES (7)"))
            mismatches = connection.execute(
                text("""
                SELECT COUNT(*) FROM whitebear_business.orders o
                JOIN (SELECT order_id, SUM(paid_amount) amount FROM whitebear_business.order_items
                      GROUP BY order_id) i ON i.order_id=o.id WHERE i.amount != o.paid_amount
            """)
            ).scalar_one()
            assert mismatches == 0
            assert (
                connection.execute(
                    text("""
                SELECT COUNT(*) FROM whitebear_business.order_items i JOIN
                (SELECT order_item_id, SUM(amount) amount FROM whitebear_business.refunds
                 GROUP BY order_item_id)
                r ON r.order_item_id=i.id WHERE r.amount > i.paid_amount
            """)
                ).scalar_one()
                == 0
            )
        with TestClient(create_app(database_settings)) as client:
            schema = client.get("/api/v1/datasources/business/schema")
            assert schema.status_code == 200, schema.text
            assert len(schema.json()["tables"]) == 6
            assert len(schema.json()["metrics"]["metrics"]) == 4
            assert any(
                column["data_type"] == "TIMESTAMP WITH TIME ZONE"
                for table in schema.json()["tables"]
                for column in table["columns"]
            )
            assert schema.json()["dataset"]["row_counts"]["orders"] == 10000
            assert client.post("/api/v1/datasources/business/sync").status_code == 200
            patch = {
                "tables": {"orders": "我的订单口径"},
                "columns": {"orders": {"paid_at": "成交时间"}},
            }
            assert (
                client.patch("/api/v1/datasources/business/metadata", json=patch).status_code == 200
            )
            result = client.get("/api/v1/datasources/business/schema").json()
            assert result["schema_version"] != schema.json()["schema_version"]
            order_table = next(table for table in result["tables"] if table["name"] == "orders")
            assert order_table["description"] == "我的订单口径"
            assert (
                next(column for column in order_table["columns"] if column["name"] == "paid_at")[
                    "description"
                ]
                == "成交时间"
            )
            assert (
                client.patch(
                    "/api/v1/datasources/business/metadata", json={"tables": {"unknown": "bad"}}
                ).status_code
                == 422
            )
            assert (
                client.post("/api/v1/datasources/business/sync").json()["tables"][3]["description"]
                == "我的订单口径"
            )
        repeated = store_dataset(database_settings, options, reset=True)
        assert {k: v for k, v in repeated.items() if k != "generated_at"} == {
            k: v for k, v in summary.items() if k != "generated_at"
        }
        with writer.connect() as connection:
            assert (
                connection.execute(text("SELECT id FROM public.reset_sentinel")).scalar_one() == 7
            )
            assert (
                connection.execute(
                    text("SELECT obj_description('whitebear_business.orders'::regclass)")
                ).scalar_one()
                != "我的订单口径"
            )
        with writer.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE public.reset_reference (customer_id integer "
                    "REFERENCES whitebear_business.customers(id))"
                )
            )
            connection.execute(text("INSERT INTO public.reset_reference VALUES (1)"))
        with pytest.raises(DBAPIError):
            store_dataset(database_settings, options, reset=True)
        with writer.begin() as connection:
            assert (
                connection.execute(
                    text("SELECT COUNT(*) FROM whitebear_business.orders")
                ).scalar_one()
                == 10000
            )
            assert (
                connection.execute(
                    text("SELECT COUNT(*) FROM whitebear_business.dataset_info")
                ).scalar_one()
                == 1
            )
            connection.execute(text("DROP TABLE public.reset_reference"))
            connection.execute(text("COMMENT ON SCHEMA whitebear_business IS 'not managed'"))
        with pytest.raises(ValueError, match="项目标记"):
            store_dataset(database_settings, options, reset=True)
        with writer.begin() as connection:
            connection.execute(text(f"COMMENT ON SCHEMA whitebear_business IS '{SCHEMA_MARKER}'"))
    finally:
        writer.dispose()

    reader = engine_for(
        database_settings.business_readonly_database_url, "BUSINESS_READONLY_DATABASE_URL"
    )
    try:
        with reader.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT COUNT(*) FROM whitebear_business.orders")
                ).scalar_one()
                == 10000
            )
        for statement in (
            "INSERT INTO whitebear_business.customers VALUES (99999, 'bad', 'bad')",
            "CREATE TABLE whitebear_business.forbidden (id integer)",
            "CREATE TABLE public.forbidden (id integer)",
        ):
            with reader.connect() as connection:
                # Even disabling the transaction default cannot bypass actual database privileges.
                connection.execute(text("SET TRANSACTION READ WRITE"))
                with pytest.raises(DBAPIError):
                    connection.execute(text(statement))
    finally:
        reader.dispose()


def test_conflicting_database_is_rejected_before_creating_roles(
    database_settings: Settings,
) -> None:
    app_url = parse_url(database_settings.app_database_url, "APP_DATABASE_URL")
    unused_role = str(app_url.username) + "_unowned"
    conflict = database_settings.model_copy()
    conflict.app_database_url = SecretStr(
        app_url.set(username=unused_role).render_as_string(hide_password=False)
    )
    with pytest.raises(ValueError, match="其他账号"):
        initialize_database(conflict)
    admin = parse_url(database_settings.admin_database_url, "ADMIN_DATABASE_URL")
    with psycopg.connect(connection_string(admin)) as connection:
        assert (
            connection.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (unused_role,)).fetchone()
            is None
        )
