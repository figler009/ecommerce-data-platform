from datetime import date
from decimal import Decimal

import pytest
from snowflake.snowpark import Row, Session
from snowflake.snowpark.types import (
    StringType,
    StructField,
    StructType,
    VariantType,
)

from snowpark.transforms.bronze_to_silver_orders import transform_bronze_events

RAW_EVENTS_SCHEMA = StructType(
    [
        StructField("RAW_PAYLOAD", VariantType()),
        StructField("FILE_NAME", StringType()),
    ]
)


@pytest.fixture(scope="module")
def session() -> Session:
    session = Session.builder.configs({"local_testing": True}).create()
    yield session
    session.close()


def _make_stream_df(session: Session, payloads: list[dict]):
    rows = [
        Row(RAW_PAYLOAD=payload, FILE_NAME="test.json") for payload in payloads
    ]
    return session.create_dataframe(rows, schema=RAW_EVENTS_SCHEMA)


def test_happy_path_parses_and_casts_types(session):
    stream_df = _make_stream_df(
        session,
        [
            {
                "order_id": "ORD1",
                "customer_id": "CUST001",
                "product_id": "PROD001",
                "order_date": "2024-01-15",
                "quantity": 2,
                "unit_price": 19.99,
                "region_id": "REGION_NA",
            }
        ],
    )

    result = transform_bronze_events(stream_df).collect()

    assert len(result) == 1
    row = result[0]
    assert row["ORDER_ID"] == "ORD1"
    assert row["ORDER_DATE"] == date(2024, 1, 15)
    assert row["QUANTITY"] == 2
    assert row["UNIT_PRICE"] == Decimal("19.99")


def test_null_order_id_is_filtered_out(session):
    stream_df = _make_stream_df(
        session,
        [
            {
                "order_id": None,
                "customer_id": "CUST001",
                "product_id": "PROD001",
                "order_date": "2024-01-15",
                "quantity": 1,
                "unit_price": 9.99,
                "region_id": "REGION_NA",
            }
        ],
    )

    assert transform_bronze_events(stream_df).count() == 0


def test_null_customer_id_is_filtered_out(session):
    stream_df = _make_stream_df(
        session,
        [
            {
                "order_id": "ORD2",
                "customer_id": None,
                "product_id": "PROD001",
                "order_date": "2024-01-15",
                "quantity": 1,
                "unit_price": 9.99,
                "region_id": "REGION_NA",
            }
        ],
    )

    assert transform_bronze_events(stream_df).count() == 0


def test_duplicate_order_ids_are_deduped(session):
    duplicate_payload = {
        "order_id": "ORD3",
        "customer_id": "CUST001",
        "product_id": "PROD001",
        "order_date": "2024-01-15",
        "quantity": 1,
        "unit_price": 9.99,
        "region_id": "REGION_NA",
    }
    stream_df = _make_stream_df(
        session, [duplicate_payload, duplicate_payload]
    )

    assert transform_bronze_events(stream_df).count() == 1


def test_missing_region_id_still_passes_through(session):
    stream_df = _make_stream_df(
        session,
        [
            {
                "order_id": "ORD4",
                "customer_id": "CUST001",
                "product_id": "PROD001",
                "order_date": "2024-01-15",
                "quantity": 1,
                "unit_price": 9.99,
                "region_id": None,
            }
        ],
    )

    result = transform_bronze_events(stream_df).collect()

    assert len(result) == 1
    assert result[0]["REGION_ID"] is None


def test_malformed_order_date_becomes_null_instead_of_erroring(session):
    stream_df = _make_stream_df(
        session,
        [
            {
                "order_id": "ORD5",
                "customer_id": "CUST001",
                "product_id": "PROD001",
                "order_date": "not-a-date",
                "quantity": 1,
                "unit_price": 9.99,
                "region_id": "REGION_NA",
            }
        ],
    )

    result = transform_bronze_events(stream_df).collect()

    assert len(result) == 1
    assert result[0]["ORDER_DATE"] is None


def test_non_numeric_quantity_becomes_null_instead_of_erroring(session):
    stream_df = _make_stream_df(
        session,
        [
            {
                "order_id": "ORD6",
                "customer_id": "CUST001",
                "product_id": "PROD001",
                "order_date": "2024-01-15",
                "quantity": "not-a-number",
                "unit_price": 9.99,
                "region_id": "REGION_NA",
            }
        ],
    )

    result = transform_bronze_events(stream_df).collect()

    assert len(result) == 1
    assert result[0]["QUANTITY"] is None
