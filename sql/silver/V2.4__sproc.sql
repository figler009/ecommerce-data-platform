USE SCHEMA ANALYTICS_DB.SILVER;

CREATE STAGE IF NOT EXISTS SILVER_SPROC_STAGE;

-- PUT is a client-side staging command, not parseable SQL grammar
-- noqa: disable=PRS
PUT file://snowpark/transforms/bronze_to_silver_orders.py @SILVER_SPROC_STAGE
  AUTO_COMPRESS = FALSE
  OVERWRITE = TRUE;
-- noqa: enable=PRS

CREATE OR REPLACE PROCEDURE SILVER_ORDERS_SPROC()
  RETURNS STRING
  LANGUAGE PYTHON
  RUNTIME_VERSION = '3.10'
  PACKAGES = ('snowflake-snowpark-python')
  IMPORTS = ('@SILVER_SPROC_STAGE/bronze_to_silver_orders.py')
  HANDLER = 'bronze_to_silver_orders.bronze_to_silver_orders';
