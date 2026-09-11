resource "snowflake_warehouse" "ingest_wh" {
  name = "INGEST_WH"
  warehouse_size = "XSMALL"
  auto_suspend = 60
  auto_resume = true
}

resource "snowflake_warehouse" "transform_wh" {
  name = "TRANSFORM_WH"
  warehouse_size = "XSMALL"
  auto_suspend = 300
  auto_resume = true
  enable_query_acceleration = true
}