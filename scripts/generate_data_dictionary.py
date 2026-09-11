"""Generate docs/data_dictionary.md from Snowflake table/column COMMENTs
(Phase 8).

Usage:
    .venv/bin/python3 scripts/generate_data_dictionary.py -C trvoucb-skc77256
"""

import argparse
from pathlib import Path

import tomli
from snowflake.connector import connect

DATABASES = ["RAW_DB", "ANALYTICS_DB"]
DOCS_PATH = (
    Path(__file__).resolve().parent.parent / "docs" / "data_dictionary.md"
)
CONNECTIONS_FILE = Path.home() / ".snowflake" / "connections.toml"
# Only pass through keys the connector's connect() actually accepts.
KNOWN_CONNECT_KEYS = {
    "account",
    "user",
    "password",
    "role",
    "warehouse",
    "database",
    "schema",
    "authenticator",
}

TABLES_QUERY = """
SELECT table_catalog, table_schema, table_name, comment
FROM {database}.INFORMATION_SCHEMA.TABLES
WHERE table_schema NOT IN ('INFORMATION_SCHEMA', 'SCHEMACHANGE')
ORDER BY table_schema, table_name
"""

COLUMNS_QUERY = """
SELECT table_schema, table_name, column_name, data_type, comment
FROM {database}.INFORMATION_SCHEMA.COLUMNS
WHERE table_schema NOT IN ('INFORMATION_SCHEMA', 'SCHEMACHANGE')
ORDER BY table_schema, table_name, ordinal_position
"""


def fetch_metadata(conn, database: str):
    cur = conn.cursor()
    tables = cur.execute(TABLES_QUERY.format(database=database)).fetchall()
    columns = cur.execute(COLUMNS_QUERY.format(database=database)).fetchall()
    cur.close()
    return tables, columns


def render_markdown(all_tables: list, all_columns: list) -> str:
    columns_by_table: dict = {}
    for schema, table, column, dtype, comment in all_columns:
        columns_by_table.setdefault((schema, table), []).append(
            (column, dtype, comment)
        )

    lines = [
        "# Data Dictionary",
        "",
        "Auto-generated from Snowflake `INFORMATION_SCHEMA` — do not edit by hand.",
        "",
    ]
    for database, schema, table, table_comment in all_tables:
        lines.append(f"## {database}.{schema}.{table}")
        if table_comment:
            lines.append(f"_{table_comment}_")
        lines.append("")
        lines.append("| Column | Type | Description |")
        lines.append("|---|---|---|")
        for column, dtype, comment in columns_by_table.get(
            (schema, table), []
        ):
            lines.append(f"| {column} | {dtype} | {comment or ''} |")
        lines.append("")

    return "\n".join(lines)


def load_connection_params(connection_name: str) -> dict:
    with open(CONNECTIONS_FILE, "rb") as f:
        connections = tomli.load(f)
    config = connections[connection_name]
    return {k: v for k, v in config.items() if k in KNOWN_CONNECT_KEYS}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-C",
        "--connection-name",
        required=True,
        help="connections.toml connection name",
    )
    args = parser.parse_args()

    conn = connect(**load_connection_params(args.connection_name))
    all_tables, all_columns = [], []
    for database in DATABASES:
        tables, columns = fetch_metadata(conn, database)
        all_tables.extend(tables)
        all_columns.extend(columns)
    conn.close()

    DOCS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOCS_PATH.write_text(render_markdown(all_tables, all_columns))
    print(f"Wrote {DOCS_PATH}")


if __name__ == "__main__":
    main()
