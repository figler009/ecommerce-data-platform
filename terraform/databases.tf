resource "snowflake_database" "raw_db" {
  name = "RAW_DB"
}

resource "snowflake_database" "analytics_db" {
  name = "ANALYTICS_DB"
}

resource "snowflake_schema" "bronze" {
  database = snowflake_database.raw_db.name
  name = "BRONZE"
}

resource "snowflake_schema" "silver" {
  database = snowflake_database.analytics_db.name
  name = "SILVER"
}

resource "snowflake_schema" "gold" {
  database = snowflake_database.analytics_db.name
  name = "GOLD"
}