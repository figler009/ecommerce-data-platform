resource "snowflake_account_role" "data_engineer" {
  provider = snowflake.securityadmin
  name     = "DATA_ENGINEER"
}

resource "snowflake_account_role" "data_analyst" {
  provider = snowflake.securityadmin
  name     = "DATA_ANALYST"
}

resource "snowflake_grant_privileges_to_account_role" "engineer_bronze_silver" {
  provider          = snowflake.securityadmin
  account_role_name = snowflake_account_role.data_engineer.name
  privileges = ["ALL"]
  on_schema {
    schema_name = "${snowflake_database.raw_db.name}.${snowflake_schema.bronze.name}"
  }
}

resource "snowflake_grant_privileges_to_account_role" "analyst_gold_usage" {
  provider          = snowflake.securityadmin
  account_role_name = snowflake_account_role.data_analyst.name
  privileges = ["USAGE"]
  on_schema {
    schema_name = "${snowflake_database.analytics_db.name}.${snowflake_schema.gold.name}"
  }
}

resource "snowflake_grant_privileges_to_account_role" "analyst_gold_select_tables" {
  provider          = snowflake.securityadmin
  account_role_name = snowflake_account_role.data_analyst.name
  privileges = ["SELECT"]
  on_schema_object {
    all {
      object_type_plural = "TABLES"
      in_schema           = "${snowflake_database.analytics_db.name}.${snowflake_schema.gold.name}"
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "analyst_gold_select_future_tables" {
  provider          = snowflake.securityadmin
  account_role_name = snowflake_account_role.data_analyst.name
  privileges = ["SELECT"]
  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_schema           = "${snowflake_database.analytics_db.name}.${snowflake_schema.gold.name}"
    }
  }
}