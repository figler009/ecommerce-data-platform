terraform {
  required_version = ">= 0.12"
  required_providers {
    snowflake = {
      source = "snowflakedb/snowflake",
      version = "~> 0.94"
    }
  }
}

provider "snowflake" {
  organization_name = "TRVOUCB"
  account_name      = "SKC77256"
  role              = "SYSADMIN"
  # user/password (or other auth) are read from SNOWFLAKE_USER / SNOWFLAKE_PASSWORD env vars
}

# role/grant management requires SECURITYADMIN, not SYSADMIN
provider "snowflake" {
  alias              = "securityadmin"
  organization_name  = "TRVOUCB"
  account_name       = "SKC77256"
  role               = "SECURITYADMIN"
}