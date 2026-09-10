# Enterprise E-Commerce Analytics Pipeline — Step-by-Step Learning Guide

This guide walks through building a **Multi-Tenant E-Commerce Data Platform (ELT)** on Snowflake, using the **Medallion Architecture** (Bronze → Silver → Gold), automated with **Terraform** (IaC) and **GitHub Actions** (CI/CD), and accelerated with **Gemini AI**.

Follow the phases in order. Each phase explains _what_ you're doing, _why_ it matters, and gives concrete artifacts (SQL, HCL, YAML) you can adapt.

---

## Phase 0 — Prerequisites & Environment Setup

**Goal:** Get all accounts and tools ready before writing any pipeline code.

1. **Snowflake account** — Sign up for a trial account (any cloud/region). You'll need `ACCOUNTADMIN` access to create databases, roles, and warehouses.
2. **AWS account** — Create an S3 bucket (e.g., `ecommerce-raw-events`) to simulate the source system dropping JSON/CSV event files.
3. **GitHub repository** — Create a repo (e.g., `ecommerce-data-platform`) with two branches: `main` (protected, production) and a convention for `feature/*` branches.
4. **Terraform CLI** — Install locally (`brew install terraform`) and get familiar with the [Snowflake Terraform Provider](https://registry.terraform.io/providers/Snowflake-Labs/snowflake/latest/docs).
5. **Python environment** — Install `snowflake-connector-python`, `snowflake-snowpark-python`, `pytest`, and `sqlfluff` in a virtual environment.
6. **Gemini API access** — Get an API key (or use the Gemini CLI/IDE integration) for later use in SQL generation, test generation, and documentation.

**Why this order:** Every later phase depends on credentials and tool access set up here. Doing this first avoids getting blocked mid-build.

**Suggested repo folder structure** (create this now, fill in as you go):

```
ecommerce-data-platform/
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── warehouses.tf
│   ├── databases.tf
│   ├── rbac.tf
│   └── outputs.tf
├── sql/
│   ├── bronze/
│   ├── silver/
│   └── gold/
├── snowpark/
│   └── transforms/
├── tests/
│   └── test_transforms.py
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── cd.yml
└── docs/
    └── data_dictionary.md
```

---

## Phase 1 — Understand the Architecture Before Coding

**Goal:** Internalize the data flow so every later step makes sense.

```
[Raw Event Streams & S3 CSV/JSON]
               │
               ▼
   [Snowflake Bronze Layer] (Variant / Raw Landing)
               │  (Streams & Tasks / Snowpipe)
               ▼
   [Snowflake Silver Layer] (Cleaned, Standardized, Conformed)
               │  (SQL / Snowpark Python Transformations)
               ▼
   [Snowflake Gold Layer]   (Star Schema Data Marts)
```

- **Bronze** = "landing zone." Store data exactly as received (no transformation) so you never lose information and can always replay/reprocess.
- **Silver** = "cleaned & conformed." Deduplicated, typed, validated data — still close to source grain, but trustworthy.
- **Medallion Architecture** = you never overwrite raw data; each layer is a **new, derived** table, so mistakes downstream never corrupt upstream history.
- **Gold** = "business-ready." Dimensional star schema optimized for BI tools and analysts to query directly.

**Why it matters in an interview:** Be ready to explain _why_ each layer exists — it's about progressively increasing trust and query performance while preserving an immutable audit trail at the bottom.

---

## Phase 2 — Infrastructure as Code: Provision Snowflake with Terraform

**Goal:** Define every Snowflake object (databases, schemas, warehouses, roles) as code instead of clicking in the UI, so environments are reproducible and reviewable via pull requests.

### Step 2.1 — Configure the provider

`terraform/main.tf`:

```hcl
terraform {
  required_providers {
    snowflake = {
      source  = "Snowflake-Labs/snowflake"
      version = "~> 0.94"
    }
  }
}

provider "snowflake" {
  role = "SYSADMIN"
}
```

### Step 2.2 — Create databases and schemas

`terraform/databases.tf`:

```hcl
resource "snowflake_database" "raw_db" {
  name = "RAW_DB"
}

resource "snowflake_database" "analytics_db" {
  name = "ANALYTICS_DB"
}

resource "snowflake_schema" "bronze" {
  database = snowflake_database.raw_db.name
  name     = "BRONZE"
}

resource "snowflake_schema" "silver" {
  database = snowflake_database.analytics_db.name
  name     = "SILVER"
}

resource "snowflake_schema" "gold" {
  database = snowflake_database.analytics_db.name
  name     = "GOLD"
}
```

### Step 2.3 — Define workload-isolated warehouses

`terraform/warehouses.tf`:

```hcl
resource "snowflake_warehouse" "ingest_wh" {
  name           = "INGEST_WH"
  warehouse_size = "XSMALL"
  auto_suspend   = 60
  auto_resume    = true
}

resource "snowflake_warehouse" "transform_wh" {
  name                    = "TRANSFORM_WH"
  warehouse_size          = "MEDIUM"
  auto_suspend            = 300
  auto_resume             = true
  enable_query_acceleration = true
}
```

**Why:** Separating warehouses stops a heavy batch transform job from starving fast, cheap ingestion. Auto-suspend at 60s means you don't pay for idle compute.

### Step 2.4 — Define RBAC (roles & grants)

`terraform/rbac.tf`:

```hcl
resource "snowflake_role" "data_engineer" {
  name = "DATA_ENGINEER"
}

resource "snowflake_role" "data_analyst" {
  name = "DATA_ANALYST"
}

resource "snowflake_grant_privileges_to_role" "engineer_bronze_silver" {
  role_name  = snowflake_role.data_engineer.name
  privileges = ["ALL"]
  on_schema {
    schema_name = "${snowflake_database.raw_db.name}.${snowflake_schema.bronze.name}"
  }
}

resource "snowflake_grant_privileges_to_role" "analyst_gold_readonly" {
  role_name  = snowflake_role.data_analyst.name
  privileges = ["USAGE", "SELECT"]
  on_schema {
    schema_name = "${snowflake_database.analytics_db.name}.${snowflake_schema.gold.name}"
  }
}
```

**Why:** Analysts should never write to raw/silver layers or see un-cleansed data; engineers need full control of Bronze/Silver but not necessarily Gold. This is least-privilege access control.

### Step 2.5 — Apply

```bash
cd terraform
terraform init
terraform plan   # review the diff — nothing should apply blindly
terraform apply
```

**Checkpoint:** You should now see `RAW_DB.BRONZE`, `ANALYTICS_DB.SILVER`, `ANALYTICS_DB.GOLD`, two warehouses, and two roles in Snowflake — all created without touching the UI.

---

## Phase 3 — Bronze Layer: Ingest Raw Data with Snowpipe

**Goal:** Land raw JSON events from S3 into Snowflake with **zero transformation and zero data loss**.

### Step 3.1 — Create the raw landing table

```sql
USE SCHEMA RAW_DB.BRONZE;

CREATE OR REPLACE TABLE RAW_EVENTS (
    RAW_PAYLOAD   VARIANT,
    FILE_NAME     STRING,
    LOAD_TIMESTAMP TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
```

**Why `VARIANT`:** It stores semi-structured JSON as-is. You defer schema decisions until Silver, so a source system adding a new field never breaks ingestion.

### Step 3.2 — Create an external stage pointing at S3

```sql
CREATE OR REPLACE STORAGE INTEGRATION S3_INT
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::<account_id>:role/snowflake-s3-role'
  STORAGE_ALLOWED_LOCATIONS = ('s3://ecommerce-raw-events/');

CREATE OR REPLACE STAGE BRONZE_STAGE
  URL = 's3://ecommerce-raw-events/'
  STORAGE_INTEGRATION = S3_INT
  FILE_FORMAT = (TYPE = JSON);
```

### Step 3.3 — Create the Snowpipe

```sql
CREATE OR REPLACE PIPE BRONZE_PIPE
  AUTO_INGEST = TRUE
AS
COPY INTO RAW_EVENTS (RAW_PAYLOAD, FILE_NAME)
FROM (
  SELECT $1, METADATA$FILENAME FROM @BRONZE_STAGE
)
FILE_FORMAT = (TYPE = JSON);
```

### Step 3.4 — Wire S3 event notifications to the pipe

Get the pipe's `notification_channel` (SQS ARN) with `DESC PIPE BRONZE_PIPE;` and configure it as an **S3 Event Notification** on the bucket (via AWS Console or Terraform `aws_s3_bucket_notification`). Whenever a new file lands in S3, Snowpipe auto-ingests it within seconds — no polling, no scheduled batch job.

**Checkpoint:** Drop a sample JSON file into the S3 bucket, wait a few seconds, then run `SELECT * FROM RAW_EVENTS;` — you should see the raw payload land automatically.

---

## Phase 4 — Silver Layer: CDC with Streams & Tasks + Snowpark Transformations

**Goal:** Turn raw, messy Bronze data into clean, typed, deduplicated Silver tables — automatically, on a schedule, using **only the new/changed rows** (CDC).

### Step 4.1 — Create a Stream on the Bronze table

```sql
CREATE OR REPLACE STREAM BRONZE_EVENTS_STREAM ON TABLE RAW_DB.BRONZE.RAW_EVENTS;
```

**Why a Stream:** It tracks INSERT/UPDATE/DELETE changes since it was last consumed, like a changelog. Downstream tasks only process _new_ rows instead of rescanning the entire Bronze table every run — this is what makes the pipeline incremental and cheap.

### Step 4.2 — Create the Silver target table with enforced types & constraints

```sql
USE SCHEMA ANALYTICS_DB.SILVER;

CREATE OR REPLACE TABLE ORDERS (
    ORDER_ID       STRING NOT NULL,
    CUSTOMER_ID    STRING NOT NULL,
    PRODUCT_ID     STRING NOT NULL,
    ORDER_DATE     DATE NOT NULL,
    QUANTITY       NUMBER,
    UNIT_PRICE     NUMBER(10,2),
    REGION_ID      STRING,
    LOAD_TIMESTAMP TIMESTAMP_NTZ,
    PRIMARY KEY (ORDER_ID)
);
```

### Step 4.3 — Write the Snowpark Python transformation

`snowpark/transforms/bronze_to_silver_orders.py`:

```python
from snowflake.snowpark import Session
from snowflake.snowpark.functions import col, to_date

def bronze_to_silver_orders(session: Session) -> None:
    stream_df = session.table("RAW_DB.BRONZE.BRONZE_EVENTS_STREAM")

    parsed_df = stream_df.select(
        col("RAW_PAYLOAD")["order_id"].cast("string").alias("ORDER_ID"),
        col("RAW_PAYLOAD")["customer_id"].cast("string").alias("CUSTOMER_ID"),
        col("RAW_PAYLOAD")["product_id"].cast("string").alias("PRODUCT_ID"),
        to_date(col("RAW_PAYLOAD")["order_date"].cast("string")).alias("ORDER_DATE"),
        col("RAW_PAYLOAD")["quantity"].cast("number").alias("QUANTITY"),
        col("RAW_PAYLOAD")["unit_price"].cast("number(10,2)").alias("UNIT_PRICE"),
        col("RAW_PAYLOAD")["region_id"].cast("string").alias("REGION_ID"),
    ).filter(
        col("ORDER_ID").is_not_null() & col("CUSTOMER_ID").is_not_null()
    ).dropDuplicates(["ORDER_ID"])

    parsed_df.write.mode("append").save_as_table("ANALYTICS_DB.SILVER.ORDERS")
```

**Why Snowpark (not pure SQL) here:** Complex parsing/validation logic is easier to unit-test in Python (Phase 7 uses `pytest` against this exact function), while still executing inside Snowflake's compute — no data ever leaves the warehouse.

### Step 4.4 — Schedule it with a Task

```sql
CREATE OR REPLACE TASK SILVER_ORDERS_TASK
  WAREHOUSE = TRANSFORM_WH
  SCHEDULE = '5 MINUTE'
WHEN
  SYSTEM$STREAM_HAS_DATA('RAW_DB.BRONZE.BRONZE_EVENTS_STREAM')
AS
  CALL SILVER_ORDERS_SPROC();

ALTER TASK SILVER_ORDERS_TASK RESUME;
```

**Why `WHEN SYSTEM$STREAM_HAS_DATA`:** The task doesn't even spin up the warehouse if there's nothing new to process — saving credits.

**Checkpoint:** After a Bronze insert, within 5 minutes `SILVER.ORDERS` should contain a clean, deduplicated, typed row — and `BRONZE_EVENTS_STREAM` should show 0 pending rows (fully consumed).

---

## Phase 5 — Gold Layer: Build the Star Schema

**Goal:** Model Silver data into a dimensional schema that's fast and intuitive for BI/analyst queries.

### Step 5.1 — Dimension tables

```sql
USE SCHEMA ANALYTICS_DB.GOLD;

CREATE OR REPLACE TABLE DIM_CUSTOMERS AS
SELECT DISTINCT CUSTOMER_ID, /* other descriptive attributes */ CURRENT_TIMESTAMP() AS LOADED_AT
FROM ANALYTICS_DB.SILVER.CUSTOMERS;

CREATE OR REPLACE TABLE DIM_PRODUCTS AS
SELECT DISTINCT PRODUCT_ID, /* other descriptive attributes */ CURRENT_TIMESTAMP() AS LOADED_AT
FROM ANALYTICS_DB.SILVER.PRODUCTS;
```

### Step 5.2 — Fact tables

```sql
CREATE OR REPLACE TABLE FACT_ORDERS (
    ORDER_ID     STRING,
    CUSTOMER_ID  STRING,
    PRODUCT_ID   STRING,
    ORDER_DATE   DATE,
    REGION_ID    STRING,
    QUANTITY     NUMBER,
    REVENUE      NUMBER(12,2)
)
CLUSTER BY (ORDER_DATE, REGION_ID);

INSERT INTO FACT_ORDERS
SELECT ORDER_ID, CUSTOMER_ID, PRODUCT_ID, ORDER_DATE, REGION_ID,
       QUANTITY, QUANTITY * UNIT_PRICE AS REVENUE
FROM ANALYTICS_DB.SILVER.ORDERS;
```

**Why `CLUSTER BY (ORDER_DATE, REGION_ID)`:** Most analytical queries filter by date range and region. Explicit clustering keys keep Snowflake's micro-partition pruning effective as the table grows into the terabytes, avoiding full-table scans.

### Step 5.3 — Star schema recap

```
        DIM_CUSTOMERS
              │
DIM_PRODUCTS ─┼─ FACT_ORDERS ── FACT_INVENTORY
              │
         (REGION_ID, ORDER_DATE grain)
```

**Checkpoint:** Query `FACT_ORDERS` joined to `DIM_CUSTOMERS`/`DIM_PRODUCTS` and confirm sub-second response for a single day/region filter.

---

## Phase 6 — Performance & Cost Optimization

**Goal:** Learn to diagnose and fix slow/expensive queries — this is what separates "it works" from "it's production-grade."

1. **Query Profile:** Open a query's profile in Snowsight. Look for:
   - **Bytes scanned vs. partitions scanned** — a huge mismatch means clustering/pruning isn't helping.
   - **Spillage to local/remote disk** — means the warehouse is undersized for the query's working set; consider a bigger warehouse or rewriting the query to reduce intermediate result size.
2. **Warehouse right-sizing:** Start small (`X-Small`/`Small`), watch query time and spillage, and scale up only when you have evidence (not by guessing).
3. **Auto-suspend everywhere:** Every warehouse should suspend quickly (60–300s) when idle — this is the single biggest lever for cost control.
4. **Clustering keys:** Re-visit `FACT_ORDERS` clustering periodically with `SELECT SYSTEM$CLUSTERING_INFORMATION('FACT_ORDERS');` to check clustering depth as data grows.
5. **Resource Monitors:** Set credit quotas so a runaway query/task can't blow the budget:

```sql
CREATE OR REPLACE RESOURCE MONITOR TRANSFORM_MONITOR
  WITH CREDIT_QUOTA = 500
  TRIGGERS ON 80 PERCENT DO NOTIFY
           ON 100 PERCENT DO SUSPEND;

ALTER WAREHOUSE TRANSFORM_WH SET RESOURCE_MONITOR = TRANSFORM_MONITOR;
```

**Why this phase matters for interviews:** "Optimization" questions test whether you _diagnose with data_ (Query Profile) rather than blindly upsizing warehouses.

---

## Phase 7 — CI/CD: GitHub Actions + Terraform

**Goal:** Every schema/infra change goes through review, automated linting/testing, and a `terraform plan` preview before it's ever applied to production.

### Step 7.1 — Branching strategy

- Work happens on `feature/*` branches.
- Open a PR into `main`.
- `main` is protected: requires passing CI checks + at least one review before merge.

### Step 7.2 — CI workflow (runs on every PR)

`.github/workflows/ci.yml`:

```yaml
name: CI
on:
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install SQLFluff
        run: pip install sqlfluff

      - name: Lint SQL
        run: sqlfluff lint sql/ --dialect snowflake

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Python deps
        run: pip install -r requirements.txt

      - name: Run Snowpark unit tests
        run: pytest tests/ -v

  terraform-plan:
    runs-on: ubuntu-latest
    needs: lint-and-test
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - name: Terraform Init
        run: terraform -chdir=terraform init
      - name: Terraform Plan
        run: terraform -chdir=terraform plan -no-color
        env:
          SNOWFLAKE_ACCOUNT: ${{ secrets.SNOWFLAKE_ACCOUNT }}
          SNOWFLAKE_USER: ${{ secrets.SNOWFLAKE_USER }}
          SNOWFLAKE_PASSWORD: ${{ secrets.SNOWFLAKE_PASSWORD }}
```

**Why:** SQLFluff catches style/syntax issues before they hit Snowflake; pytest validates Snowpark transformation logic in isolation; `terraform plan` shows _exactly_ what infra will change, visible in the PR before merge — no surprises.

### Step 7.3 — CD workflow (runs on merge to `main`)

`.github/workflows/cd.yml`:

```yaml
name: CD
on:
  push:
    branches: [main]

jobs:
  terraform-apply:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - name: Terraform Init
        run: terraform -chdir=terraform init
      - name: Terraform Apply
        run: terraform -chdir=terraform apply -auto-approve
        env:
          SNOWFLAKE_ACCOUNT: ${{ secrets.SNOWFLAKE_ACCOUNT }}
          SNOWFLAKE_USER: ${{ secrets.SNOWFLAKE_USER }}
          SNOWFLAKE_PASSWORD: ${{ secrets.SNOWFLAKE_PASSWORD }}
```

**Why only on merge:** `apply` should never run against production from an unreviewed branch. Secrets live in GitHub Actions Secrets, never in code.

**Checkpoint:** Open a PR that adds a new warehouse in Terraform + a new SQL view. Confirm CI blocks the merge if a test fails, and that merging triggers an automatic `apply`.

---

## Phase 8 — AI Acceleration with Gemini

**Goal:** Use Gemini as a force-multiplier for the tedious parts of the pipeline — not to replace understanding, but to speed up drafting and keep documentation current.

1. **Complex SQL generation:** Prompt Gemini with a plain-English business requirement (e.g., "calculate rolling 12-month customer lifetime value using a window function") and have it draft the window function / recursive CTE. Review and adapt — always validate against `EXPLAIN`/Query Profile.
2. **Automated test generation:** Feed Gemini the Snowpark transformation function (like `bronze_to_silver_orders`) and ask it to generate `pytest` edge cases (nulls, malformed JSON, duplicate keys, type mismatches). Add these to `tests/test_transforms.py`.
3. **Data governance / self-documenting schema:** Prompt Gemini with a table's DDL + sample rows to generate column-level descriptions, then apply them:

```sql
ALTER TABLE ANALYTICS_DB.GOLD.FACT_ORDERS
  MODIFY COLUMN REVENUE COMMENT 'Order revenue = quantity * unit_price, generated by Gemini-assisted documentation pass';
```

Keep `docs/data_dictionary.md` updated from these comments (can even script an export via `SHOW COLUMNS`/`INFORMATION_SCHEMA`).

**Why this matters for interviews:** Be ready to explain _where_ you draw the line — Gemini drafts, a human reviews and validates against real query plans/test runs before merging.

---

## Phase 9 — Wrap-Up: How to Present This in an Interview

Use this table as your talking-points cheat sheet:

| Phase          | Technology                     | What you'd say you built                                                                                          |
| -------------- | ------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| Ingestion      | S3, Snowpipe, `VARIANT`        | Auto-ingested high-volume webhooks into Bronze with zero data loss and no schema-on-write                         |
| Transformation | Streams, Tasks, Snowpark       | Incremental CDC processing that dedupes, types, and validates data into Silver, then models Gold star schema      |
| Optimization   | Query Profile, clustering keys | Diagnosed spillage/pruning issues data-first, then rightsized warehouses and set clustering keys                  |
| DevOps & IaC   | Terraform, GitHub Actions      | Fully automated, peer-reviewed deployment pipeline: PR → lint/test → plan → merge → apply                         |
| Productivity   | Gemini AI                      | Accelerated SQL/test drafting and kept the data dictionary self-documenting, with human review as the safety gate |

**Suggested learning order to actually build this hands-on:**

1. Phase 2 (Terraform foundations) → 2. Phase 3 (Bronze/Snowpipe) → 3. Phase 4 (Silver/Streams+Tasks+Snowpark) → 4. Phase 5 (Gold star schema) → 5. Phase 6 (optimization) → 6. Phase 7 (CI/CD) → 7. Phase 8 (Gemini acceleration, applied throughout).
