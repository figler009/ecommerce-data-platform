# Data Dictionary

Auto-generated from Snowflake `INFORMATION_SCHEMA` — do not edit by hand.

## RAW_DB.BRONZE.RAW_EVENTS
_Bronze landing table: raw event payloads as received from S3, zero transformation._

| Column | Type | Description |
|---|---|---|
| RAW_PAYLOAD | VARIANT | Full raw event JSON payload exactly as received, no schema-on-write. |
| FILE_NAME | TEXT | Source S3 object name, captured via METADATA$FILENAME at ingest time. |
| LOAD_TIMESTAMP | TIMESTAMP_NTZ | Timestamp the row was ingested into Bronze by Snowpipe. |

## ANALYTICS_DB.GOLD.DIM_CUSTOMERS
_Gold dimension: customer descriptive attributes for BI joins/filters._

| Column | Type | Description |
|---|---|---|
| CUSTOMER_ID | TEXT | Unique customer identifier, joins to FACT_ORDERS.CUSTOMER_ID. |
| CUSTOMER_NAME | TEXT | Customer full name. |
| EMAIL | TEXT | Customer email address. |
| REGION_ID | TEXT | Customer's home region. |
| CUSTOMER_SEGMENT | TEXT | Business segment, e.g. Retail or Wholesale. |
| LOADED_AT | TIMESTAMP_LTZ | Timestamp this dimension row was (re)built. |

## ANALYTICS_DB.GOLD.DIM_PRODUCTS
_Gold dimension: product descriptive attributes for BI joins/filters._

| Column | Type | Description |
|---|---|---|
| PRODUCT_ID | TEXT | Unique product identifier, joins to FACT_ORDERS.PRODUCT_ID. |
| PRODUCT_NAME | TEXT | Product display name. |
| CATEGORY | TEXT | Top-level product category. |
| BRAND | TEXT | Product brand. |
| LIST_PRICE | NUMBER | Standard list price, 2 decimal places. |
| LOADED_AT | TIMESTAMP_LTZ | Timestamp this dimension row was (re)built. |

## ANALYTICS_DB.GOLD.FACT_ORDERS
_Gold fact: one row per order, clustered by (ORDER_DATE, REGION_ID) for BI query pruning._

| Column | Type | Description |
|---|---|---|
| ORDER_ID | TEXT | Unique order identifier. |
| CUSTOMER_ID | TEXT | Foreign key to DIM_CUSTOMERS.CUSTOMER_ID. |
| PRODUCT_ID | TEXT | Foreign key to DIM_PRODUCTS.PRODUCT_ID. |
| ORDER_DATE | DATE | Calendar date the order was placed; part of the clustering key. |
| REGION_ID | TEXT | Region the order was placed in; part of the clustering key. |
| QUANTITY | NUMBER | Units ordered. |
| REVENUE | NUMBER | QUANTITY * UNIT_PRICE at order time. |

## ANALYTICS_DB.SILVER.CUSTOMERS
_Silver: customer master data (mocked seed data, no upstream CRM source in this project)._

| Column | Type | Description |
|---|---|---|
| CUSTOMER_ID | TEXT | Unique customer identifier, primary key. |
| CUSTOMER_NAME | TEXT | Customer full name. |
| EMAIL | TEXT | Customer email address. |
| REGION_ID | TEXT | Customer's home region. |
| SIGNUP_DATE | DATE | Date the customer account was created. |
| CUSTOMER_SEGMENT | TEXT | Business segment, e.g. Retail or Wholesale. |
| LOAD_TIMESTAMP | TIMESTAMP_NTZ | Timestamp the row was loaded into Silver. |

## ANALYTICS_DB.SILVER.ORDERS
_Silver: cleaned, typed, deduplicated order events parsed from Bronze RAW_EVENTS._

| Column | Type | Description |
|---|---|---|
| ORDER_ID | TEXT | Unique order identifier, primary key, deduplicated on load. |
| CUSTOMER_ID | TEXT | Foreign key to SILVER.CUSTOMERS / GOLD.DIM_CUSTOMERS. |
| PRODUCT_ID | TEXT | Foreign key to SILVER.PRODUCTS / GOLD.DIM_PRODUCTS. |
| ORDER_DATE | DATE | Calendar date the order was placed, parsed from the raw event payload. |
| QUANTITY | NUMBER | Units of the product ordered. |
| UNIT_PRICE | NUMBER | Price per unit at time of order, 2 decimal places. |
| REGION_ID | TEXT | Region the order was placed in. |
| LOAD_TIMESTAMP | TIMESTAMP_NTZ | Timestamp the row was written into Silver by SILVER_ORDERS_SPROC. |

## ANALYTICS_DB.SILVER.PRODUCTS
_Silver: product master data (mocked seed data, no upstream PIM source in this project)._

| Column | Type | Description |
|---|---|---|
| PRODUCT_ID | TEXT | Unique product identifier, primary key. |
| PRODUCT_NAME | TEXT | Product display name. |
| CATEGORY | TEXT | Top-level product category. |
| BRAND | TEXT | Product brand. |
| LIST_PRICE | NUMBER | Standard list price, 2 decimal places. |
| LOAD_TIMESTAMP | TIMESTAMP_NTZ | Timestamp the row was loaded into Silver. |
