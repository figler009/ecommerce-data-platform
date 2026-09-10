from snowflake.snowpark import DataFrame, Session
from snowflake.snowpark.functions import col, current_timestamp


def transform_bronze_events(stream_df: DataFrame) -> DataFrame:
    """Parse, type-cast, validate, and dedupe raw Bronze event rows into
    Silver ORDERS shape.
    """
    return (
        stream_df.select(
            col("RAW_PAYLOAD")["order_id"].cast("string").alias("ORDER_ID"),
            col("RAW_PAYLOAD")["customer_id"]
            .cast("string")
            .alias("CUSTOMER_ID"),
            col("RAW_PAYLOAD")["product_id"]
            .cast("string")
            .alias("PRODUCT_ID"),
            col("RAW_PAYLOAD")["order_date"]
            .cast("string")
            .try_cast("date")
            .alias("ORDER_DATE"),
            col("RAW_PAYLOAD")["quantity"]
            .cast("string")
            .try_cast("number")
            .alias("QUANTITY"),
            col("RAW_PAYLOAD")["unit_price"]
            .cast("string")
            .try_cast("number(10,2)")
            .alias("UNIT_PRICE"),
            col("RAW_PAYLOAD")["region_id"].cast("string").alias("REGION_ID"),
            current_timestamp().alias("LOAD_TIMESTAMP"),
        )
        .filter(
            col("ORDER_ID").is_not_null() & col("CUSTOMER_ID").is_not_null()
        )
        .dropDuplicates(["ORDER_ID"])
    )


def bronze_to_silver_orders(session: Session) -> str:
    stream_df = session.table("RAW_DB.BRONZE.BRONZE_EVENTS_STREAM")
    parsed_df = transform_bronze_events(stream_df)
    parsed_df.write.mode("append").save_as_table("ANALYTICS_DB.SILVER.ORDERS")
    return "SILVER_ORDERS_SPROC completed successfully"
