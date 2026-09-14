#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-time generator for SenseiIndex.accdb - the Access Edition's real
Microsoft Access database file.

WINDOWS ONLY. Access itself doesn't need to be installed, but the free
Microsoft Access Database Engine Redistributable does - it provides both
the ACE OLEDB provider (used here, via ADOX, just to create a new blank
.accdb file - there's no other way to create one from nothing without
either that or Access itself installed) and the ODBC driver
access_data_access.py/access_electrical_data_access.py use at runtime.
Download it from Microsoft (search "Microsoft Access Database Engine
Redistributable", get the version - 32 or 64-bit - matching your Python
install) if this fails with a "Provider cannot be found" or
"no ODBC driver" style error.

Two steps:
    1. Create a blank .accdb (ADOX, via pywin32's COM bridge - pyodbc
       alone can't create a NEW database file, only work with one that
       already exists).
    2. Run CREATE TABLE/CREATE INDEX for every table access_schema.py
       defines (pyodbc, against the file ADOX just created).

Run once:
    pip install pywin32 pyodbc
    python build_access_database.py
Regenerates SenseiIndex.accdb next to this script (deletes and rebuilds
it from scratch every time - this is a SCHEMA generator, not a
migration tool; it is never meant to run against a database that
already has real data in it - see README_ACCESS_EDITION.txt for the
actual one-time-setup instructions aimed at an end user, which this
script is NOT).
"""
import sys
from pathlib import Path

from access_schema import all_create_statements, CORE_TABLES, TABLES

HERE = Path(__file__).resolve().parent
OUT_PATH = HERE / "SenseiIndex.accdb"


def create_blank_accdb(path):
    """ADOX.Catalog.Create is the standard way to make a brand new,
    empty .accdb from nothing - it only needs the ACE OLEDB provider
    (part of the free Access Database Engine Redistributable), not a
    real Access install."""
    import win32com.client

    if path.exists():
        path.unlink()
    catalog = win32com.client.Dispatch("ADOX.Catalog")
    conn_str = f"Provider=Microsoft.ACE.OLEDB.12.0;Data Source={path}"
    catalog.Create(conn_str)
    print(f"Created blank database: {path}")


def run_ddl(path):
    import pyodbc

    conn_str = (
        r"Driver={Microsoft Access Driver (*.mdb, *.accdb)};"
        f"Dbq={path};"
    )
    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()

    table_count = 0
    index_count = 0
    for table_name, create_sql, index_sql in all_create_statements():
        try:
            cursor.execute(create_sql)
            table_count += 1
        except pyodbc.Error as exc:
            print(f"FAILED creating table {table_name}:")
            print(create_sql)
            raise RuntimeError(f"CREATE TABLE failed for {table_name}: {exc}") from exc
        for stmt in index_sql:
            try:
                cursor.execute(stmt)
                index_count += 1
            except pyodbc.Error as exc:
                raise RuntimeError(f"CREATE INDEX failed for {table_name}: {exc}\n{stmt}") from exc

    conn.close()
    print(f"Created {table_count} tables, {index_count} indexes")


def verify(path):
    """Round-trip sanity check: connect fresh, confirm every table
    access_schema.py expects is actually present and queryable (an empty
    SELECT, not a real data check - this only proves the schema itself
    took, not that the app works end to end - see build-windows-exe.yml's
    own launch-and-check step for the equivalent full-app smoke test,
    which is a separate CI job for this edition)."""
    import pyodbc

    conn_str = (
        r"Driver={Microsoft Access Driver (*.mdb, *.accdb)};"
        f"Dbq={path};"
    )
    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()

    expected_tables = list(CORE_TABLES.keys()) + [e["table_name"] for e in TABLES.values()]
    missing = []
    for table_name in expected_tables:
        try:
            cursor.execute(f"SELECT TOP 1 * FROM [{table_name}]")
            cursor.fetchall()
        except pyodbc.Error as exc:
            missing.append((table_name, str(exc)))
    conn.close()

    if missing:
        for table_name, err in missing:
            print(f"VERIFY FAILED: {table_name}: {err}")
        raise RuntimeError(f"{len(missing)} table(s) failed verification")
    print(f"Verified all {len(expected_tables)} tables are present and queryable")


def build():
    if sys.platform != "win32":
        sys.exit(
            "ERROR: this script only runs on Windows (it needs the Microsoft "
            "Access Database Engine's ACE OLEDB provider + ODBC driver, both "
            "Windows-only). See README_ACCESS_EDITION.txt."
        )
    create_blank_accdb(OUT_PATH)
    run_ddl(OUT_PATH)
    verify(OUT_PATH)
    print(f"\nDone: {OUT_PATH}")


if __name__ == "__main__":
    build()
