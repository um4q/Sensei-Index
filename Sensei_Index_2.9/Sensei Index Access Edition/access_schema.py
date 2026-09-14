# -*- coding: utf-8 -*-
"""
Single source of truth for the Access Edition's database schema.

This does NOT hand-duplicate every equipment kind's field list - it
imports the SAME *_schema.py files the Excel edition already uses (from
the sibling "Sensei Index 2.9" folder) and derives one Access table per
equipment kind directly from each one's own FIELDS list. That's the
whole point of reusing them: every field this app already tracks (over
700 of them, across 9 equipment kinds) stays defined in exactly ONE
place. Add a field to (say) transformer_test_schema.py in the Excel
edition, rerun build_access_database.py here, and the new column exists
in Access too - nothing to keep in sync by hand.

WHAT THIS MODULE PRODUCES
------------------------------
TABLES: one entry per equipment kind, e.g.:
    TABLES["transformer_test"] = {
        "domain": "electrical",           # "instrumentation" | "electrical"
        "table_name": "TransformerTest",  # the real Access table name
        "key_field": "tag",               # matches the registry's own key_field
        "parent_field": "zone_id",         # "series_id" for instrumentation
        "fields": [...],                   # the schema's own FIELDS list, untouched
    }

DOMAIN_TABLES["instrumentation"] / ["electrical"]: the same entries,
grouped by domain (what access_data_access.py / access_electrical_
data_access.py each need - one domain apiece, same split the Excel
edition itself already uses).

CORE_TABLES: DDL for the small number of tables that AREN'T one per
equipment kind - Series, Zones, ActivityLog, RowStatus, Settings,
Signatures. See each dict entry's own "columns" for the real column
list; build_access_database.py turns all of this (core tables +
per-kind tables) into real CREATE TABLE statements.

WHY AN "id" COLUMN INSTEAD OF "row_num"
--------------------------------------------
The Excel edition's row_num is really "which spreadsheet row this is" -
a positional concept that only exists because Excel has no real row
identity, and the whole "find_first_blank_row / reuse a cleared row"
dance in data_access.py/electrical_data_access.py exists purely to work
around that. A real database has proper row identity for free (an
AUTOINCREMENT primary key) - access_data_access.py's own
find_first_blank_row() is kept as a function NAME for drop-in
compatibility with gui_app.py's calling code, but it just INSERTs a new
row and returns its real id; there's no "blank row reuse" concept to
port, because there's nothing to reuse.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXCEL_EDITION_DIR = HERE.parent / "Sensei Index 2.9"
if str(EXCEL_EDITION_DIR) not in sys.path:
    sys.path.insert(0, str(EXCEL_EDITION_DIR))

import eht_removal_schema
import eht_rtd_schema
import eht_pre_insulation_schema
import torqueing_schema
import transformer_test_schema
import small_power_cable_schema
import general_equip_install_schema
import transmitter_schema
import valve_schema


# (equip_key, domain, table_name, key_field, schema_module)
# key_field mirrors each equipment type's own registry entry in
# data_access.py/electrical_data_access.py (EQUIPMENT_TYPES/
# ELECTRICAL_EQUIPMENT_TYPES) - the field that identifies one real piece
# of equipment (a tag, a serial number, a cable number...).
# key_field values verified directly against data_access.py's own
# EQUIPMENT_TYPES / electrical_data_access.py's own
# ELECTRICAL_EQUIPMENT_TYPES registries - NOT guessed from the field
# list, since several of these don't follow the obvious "tag_number"
# pattern (transmitter's real key is "tag", valve's is "equip_number",
# eht_rtd/eht_pre_insulation's is "trace_number" not "trace_tag").
_REGISTRY = [
    ("transmitter", "instrumentation", "Transmitter", "tag", transmitter_schema),
    ("valve", "instrumentation", "Valve", "equip_number", valve_schema),
    ("eht_removal", "electrical", "EhtRemoval", "trace_tag", eht_removal_schema),
    ("eht_rtd", "electrical", "EhtRtd", "trace_number", eht_rtd_schema),
    ("eht_pre_insulation", "electrical", "EhtPreInsulation", "trace_number", eht_pre_insulation_schema),
    ("torqueing", "electrical", "Torqueing", "torque_record_number", torqueing_schema),
    ("transformer_test", "electrical", "TransformerTest", "tag", transformer_test_schema),
    ("small_power_cable", "electrical", "SmallPowerCable", "cable_tag_number", small_power_cable_schema),
    ("general_equip_install", "electrical", "GeneralEquipInstall", "tag_number", general_equip_install_schema),
]

PARENT_FIELD_BY_DOMAIN = {
    "instrumentation": "series_id",
    "electrical": "zone_id",
}
PARENT_TABLE_BY_DOMAIN = {
    "instrumentation": "Series",
    "electrical": "Zones",
}

TABLES = {}
DOMAIN_TABLES = {"instrumentation": {}, "electrical": {}}

for _equip_key, _domain, _table_name, _key_field, _schema_mod in _REGISTRY:
    _entry = {
        "domain": _domain,
        "table_name": _table_name,
        "key_field": _key_field,
        "parent_field": PARENT_FIELD_BY_DOMAIN[_domain],
        "parent_table": PARENT_TABLE_BY_DOMAIN[_domain],
        "fields": _schema_mod.LOG_COLUMNS,
        "schema_module": _schema_mod,
    }
    _field_ids = {f["id"] for f in _entry["fields"]}
    if _key_field not in _field_ids:
        raise ValueError(
            f"{_equip_key}: key_field {_key_field!r} does not match any real field id "
            f"in {_schema_mod.__name__}.LOG_COLUMNS - check against the real registry "
            f"entry in data_access.py/electrical_data_access.py, don't guess it."
        )
    TABLES[_equip_key] = _entry
    DOMAIN_TABLES[_domain][_equip_key] = _entry


def access_column_type(field):
    """Maps a schema field's ftype to a real Access SQL column type.
    'choice' fields still store one short string (whichever choice was
    picked) - same TEXT(255) as a plain 'text' field, just validated at
    the Python layer (same place the Excel edition's own GUI dropdowns
    already validate them, since Access DDL over ODBC has no reliable
    way to express a real CHECK constraint)."""
    if field.get("ftype") == "multiline":
        return "MEMO"
    return "TEXT(255)"


def quoted_ident(name):
    """Access identifiers get wrapped in [brackets], not double quotes -
    this covers field ids that happen to collide with a SQL reserved
    word (this app has a few: 'date', 'name', 'location', 'system' all
    appear as real field ids across various schemas)."""
    return f"[{name}]"


CORE_TABLES = {
    "Series": {
        "columns": [
            ("id", "COUNTER PRIMARY KEY"),
            ("series_number", "LONG"),
            ("display_name", "TEXT(255)"),
            ("created_at", "DATETIME"),
        ],
    },
    "Zones": {
        "columns": [
            ("id", "COUNTER PRIMARY KEY"),
            ("zone_name", "TEXT(255)"),
            ("created_at", "DATETIME"),
        ],
    },
    "ActivityLog": {
        "columns": [
            ("id", "COUNTER PRIMARY KEY"),
            ("domain", "TEXT(50)"),
            ("equip_key", "TEXT(50)"),
            ("parent_label", "TEXT(255)"),  # the series number or zone name, as text
            ("row_id", "LONG"),
            ("key_value", "TEXT(255)"),
            ("action", "TEXT(100)"),
            ("details", "MEMO"),
            ("source", "TEXT(50)"),
            ("timestamp", "DATETIME"),
        ],
    },
    "RowStatus": {
        # Mirrors equipment_status.json/electrical_status.json's own
        # {installed, submitted, accepted} flags, keyed the same way
        # those files already are (domain + equip_key + the row's own
        # key value - NOT row_id, so status survives a row being
        # deleted and recreated with the same tag, same as today).
        "columns": [
            ("id", "COUNTER PRIMARY KEY"),
            ("domain", "TEXT(50)"),
            ("equip_key", "TEXT(50)"),
            ("key_value", "TEXT(255)"),
            ("installed", "YESNO"),
            ("submitted", "YESNO"),
            ("accepted", "YESNO"),
            ("updated_at", "DATETIME"),
        ],
    },
    "Settings": {
        "columns": [
            ("id", "COUNTER PRIMARY KEY"),
            ("setting_key", "TEXT(255)"),
            ("setting_value", "MEMO"),
        ],
    },
    "Signatures": {
        "columns": [
            ("id", "COUNTER PRIMARY KEY"),
            ("filename", "TEXT(255)"),
            ("display_name", "TEXT(255)"),
            ("is_active", "YESNO"),
            ("uploaded_at", "DATETIME"),
        ],
    },
}


def build_create_table_sql(table_name, columns, indexes=None):
    col_sql = ",\n    ".join(f"{quoted_ident(name)} {coltype}" for name, coltype in columns)
    sql = f"CREATE TABLE {quoted_ident(table_name)} (\n    {col_sql}\n)"
    return sql


def build_equipment_table_ddl(equip_key):
    """Returns (create_table_sql, index_sql_list) for one equipment
    kind's own table - the parent FK column + every one of its own
    schema fields, in the same order the schema module itself lists
    them (so the table reads the same way the Excel sheet's own column
    order already does)."""
    entry = TABLES[equip_key]
    columns = [
        ("id", "COUNTER PRIMARY KEY"),
        (entry["parent_field"], "LONG"),
    ]
    seen = {"id", entry["parent_field"]}
    for field in entry["fields"]:
        fid = field["id"]
        if fid in seen:
            raise ValueError(f"{equip_key}: duplicate field id {fid!r} collides with a reserved column")
        seen.add(fid)
        columns.append((fid, access_column_type(field)))
    columns.append(("created_at", "DATETIME"))
    columns.append(("updated_at", "DATETIME"))

    create_sql = build_create_table_sql(entry["table_name"], columns)
    index_sql = [
        f"CREATE INDEX idx_{entry['table_name']}_parent ON {quoted_ident(entry['table_name'])} "
        f"({quoted_ident(entry['parent_field'])})",
    ]
    if entry["key_field"] in seen:
        index_sql.append(
            f"CREATE INDEX idx_{entry['table_name']}_key ON {quoted_ident(entry['table_name'])} "
            f"({quoted_ident(entry['key_field'])})"
        )
    return create_sql, index_sql


def all_create_statements():
    """Yields (table_name, create_sql, index_sql_list) for every table
    this database needs - core tables first (Series/Zones don't depend
    on anything; the per-kind tables' own FK columns reference them),
    then one per equipment kind."""
    for table_name, spec in CORE_TABLES.items():
        yield table_name, build_create_table_sql(table_name, spec["columns"]), []
    for equip_key in TABLES:
        create_sql, index_sql = build_equipment_table_ddl(equip_key)
        yield TABLES[equip_key]["table_name"], create_sql, index_sql


if __name__ == "__main__":
    total_fields = sum(len(t["fields"]) for t in TABLES.values())
    print(f"{len(TABLES)} equipment-kind tables, {len(CORE_TABLES)} core tables, "
          f"{total_fields} total per-row fields")
    for equip_key, entry in TABLES.items():
        print(f"  {entry['table_name']:20s} ({entry['domain']:15s}) - "
              f"{len(entry['fields'])} fields, key={entry['key_field']}")
