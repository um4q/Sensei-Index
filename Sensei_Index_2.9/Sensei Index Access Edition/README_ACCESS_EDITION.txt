SENSEI INDEX - ACCESS EDITION
==================================

WHAT THIS IS
------------------
A separate version of Sensei Index that stores its data in a real
Microsoft Access database (SenseiIndex.accdb) instead of the Equipment_
Inspection_Tracker.xlsx / Electrical_Inspection_Tracker.xlsx workbooks
the regular ("Excel edition") version uses. Same app family, same PDF
templates and exports, same 9 equipment kinds - different backend.

Why a real database instead of Excel: a real database has actual row
identity, real concurrent-write safety, and - most relevantly if you
want multiple people working off the same data from different
locations - it can be hosted so several people use it at once without
"someone else has the file open" problems. See SHAREPOINT_CLOUD_SETUP.
txt for how to actually get that multi-location access working, using
SharePoint.

HOW THIS FOLDER RELATES TO "Sensei Index 2.9" (the Excel edition), NEXT
TO IT
--------------------------------------------------------------------------
This is a genuinely separate app, not a toggle inside the Excel
edition - but it does NOT duplicate that folder's own field
definitions. access_schema.py imports the SAME *_schema.py files the
Excel edition uses (every field, on every one of the 9 equipment kinds,
stays defined in exactly one place - see that module's own docstring),
and every export_<kind>_to_pdf.py module - PDF filling, signature
stamping, the works - is reused completely unmodified, because those
modules only ever operated on a plain {field_id: value} dict; they
never cared whether that dict came from an Excel row or an Access row.
So: this folder MUST stay next to "Sensei Index 2.9" (same parent
folder) - it reads several of that folder's own .py files directly.

FIRST-TIME SETUP
---------------------
1. Get a real SenseiIndex.accdb. Either:
     a) Ask for the one already built and verified by this repo's own
        CI (.github/workflows/build-access-edition.yml runs on real
        Windows with the real Access Database Engine and round-trip
        tests it before delivering it) - this is the reliable path,
        skip straight to step 2 with that file.
     b) Build it yourself: install the free "Microsoft Access Database
        Engine Redistributable" (search that exact phrase on
        microsoft.com, get the 64-bit version if you're on 64-bit
        Python), then:
            pip install -r requirements.txt
            python build_access_database.py
        This creates a blank SenseiIndex.accdb with every table this
        app needs, right next to this script. NOT a migration tool -
        running it again wipes and rebuilds the schema from scratch, so
        never run it against a database that already has real data.

2. pip install -r requirements.txt (skip pywin32 if you already have a
   built .accdb and aren't rebuilding it - it's only needed by
   build_access_database.py itself).

3. python access_gui_app.py

WHAT'S HERE
---------------
    access_schema.py                  - table/column definitions, derived from the Excel edition's own schema.py files
    access_db.py                      - the generic database engine (CRUD, parent tables, settings, activity log, status)
    access_data_access.py             - Instrumentation domain module (transmitter, valve)
    access_electrical_data_access.py  - Electrical domain module (the other 7 kinds)
    access_gui_app.py                 - the app itself
    build_access_database.py          - one-time SenseiIndex.accdb generator (Windows only)
    tests/                            - SQLite-backed logic tests (see below - what these do and don't prove)
    SHAREPOINT_CLOUD_SETUP.txt        - how to host the database in the cloud for multi-user access

WHAT'S NOT HERE YET
------------------------
This covers the core day-to-day workflow - pick a zone/series, browse
equipment by kind, add/edit/delete rows, check installed/submitted/
accepted status, generate a filled PDF - completely and for real, not
as a stub. It does NOT (yet) cover everything the Excel edition's own
gui_app.py does; these were deliberately left for a later pass rather
than attempted half-working:

    - The Master List import/reconciliation engine (reading a client's
      own Instrumentation Master List spreadsheet and matching it
      against existing rows)
    - Import Datasheet PDF (pre-filling a new row from an engineering
      data sheet PDF)
    - Progress report export, cleaned-workbook-style export
    - The global search index (Ctrl+K)
    - Per-row edit history / a dedicated activity log VIEWER (the log
      itself IS being written to on every save - see access_db.py's
      own log_activity() - there's just no window to browse it yet)
    - The Excel edition's own hand-laid-out, per-form edit dialogs -
      this edition's own RowEditDialog builds one straightforward form
      generically from each schema's own field list instead (see
      access_gui_app.py's own docstring for why)

None of this is a "not possible" list - it's a "not built yet" list.
The data layer (access_db.py/access_data_access.py/access_electrical_
data_access.py) already has everything these would need to build on.

HOW THE TESTING STORY WORKS HERE (READ THIS BEFORE TRUSTING A CHANGE)
---------------------------------------------------------------------------
Real Access (the ACE OLEDB provider, the ODBC driver, an actual
.accdb) is Windows-only - there is no way to run or verify any of it on
a Linux machine. Every function in access_db.py takes its own database
connection as a plain parameter rather than opening one itself,
specifically so tests/ can hand it a SQLite connection instead of a
real pyodbc one (both are DB-API 2.0 with the same "?" parameter style)
and exercise the exact same code path. That proves the PYTHON LOGIC is
sound - row marshaling, parent-table lookups, duplicate-key scoping,
generic CRUD - but it does NOT prove the real Access SQL dialect
itself works (DDL syntax in particular - COUNTER, MEMO, YESNO, the
CREATE INDEX syntax - none of that is something SQLite validates the
same way). The ONLY place that gets proven for real is .github/
workflows/build-access-edition.yml, on an actual Windows runner with
the actual Access Database Engine installed - it builds a real .accdb
from access_schema.py, round-trip tests real data through it via
access_electrical_data_access.py/access_data_access.py, and launches
access_gui_app.py against that real file to confirm it stays running.
If you change access_schema.py's own DDL generation or anything in
access_db.py's actual SQL strings, the SQLite-backed tests passing is
NOT enough confidence on its own - that CI workflow needs to pass too.
