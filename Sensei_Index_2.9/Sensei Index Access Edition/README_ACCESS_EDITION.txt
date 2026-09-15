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

   Or, if you'd rather not install Python at all: use the standalone
   "Sensei Index Access Edition.exe" instead (built by .github/workflows/
   build-access-edition-exe.yml on real Windows, same PyInstaller
   approach "Sensei Index 2.9"'s own Sensei Index 2.95.exe already uses -
   see SenseiIndexAccessEdition.spec's own docstring). Drop the .exe into
   THIS folder, next to SenseiIndex.accdb, and run it same as any other
   program - the sibling "Sensei Index 2.9" folder (assets/, the PDF
   templates) still needs to stay present one level up either way, exe
   or not; only the ~60 Python modules themselves are baked into the
   .exe, none of the data files are.

WHAT'S HERE
---------------
    access_schema.py                  - table/column definitions, derived from the Excel edition's own schema.py files
    access_db.py                      - the generic database engine (CRUD, parent tables, settings, activity log, status)
    access_data_access.py             - Instrumentation domain module (transmitter, valve)
    access_electrical_data_access.py  - Electrical domain module (the other 7 kinds)
    access_gui_app.py                 - the app itself - see below, this is gui_app.py, not a rewrite
    build_access_database.py          - one-time SenseiIndex.accdb generator (Windows only)
    SenseiIndexAccessEdition.spec     - PyInstaller spec for the standalone .exe (Windows only, see its own docstring)
    tests/                            - SQLite-backed logic tests (see below - what these do and don't prove)
    SHAREPOINT_CLOUD_SETUP.txt        - how to host the database in the cloud for multi-user access

WHY access_gui_app.py IS gui_app.py, NOT A REWRITE
--------------------------------------------------------
An earlier version of this edition shipped with its own simplified,
generic schema-driven form/table UI instead of the Excel edition's real
one - functional, but a visible downgrade from the polished app people
already knew. That approach has been dropped entirely. access_gui_app.py
is now gui_app.py itself, copied close to byte-for-byte: same sidebar,
same Dashboard, same Coverage/reconciliation page, same Populating
Wizard, same Master List import, same global search (Ctrl+K), same
per-row edit history, same hand-laid-out per-form Edit dialogs, same
Export dialogs, same Backups dialog, same keyboard shortcuts, same
Undo/Redo - all of it. What actually changed is two import lines
(pointed at this edition's own Access-backed access_data_access.py/
access_electrical_data_access.py, which expose the EXACT SAME call
surface as data_access.py/electrical_data_access.py - no explicit
connection argument, identical function names and signatures - so
every UI class in gui_app.py runs against them completely unmodified),
the app title, and a handful of QLabel/QMessageBox strings that named
Excel-only concepts with no Access equivalent (sheet tabs, "Unhide",
archive-by-hiding-a-sheet - this edition does a REAL relational delete
instead, so those warnings now say so plainly). Grep access_gui_app.py
for "Access Edition note" to find every one of those spots.

Two genuine behavioral differences from the Excel edition, both
deliberate, both documented in the code where they matter:
    - remove_series()/remove_zone() permanently delete the series/zone
      and its rows - no archive-by-hiding-a-sheet recovery path exists
      for a real relational database the way it does for an Excel
      sheet. The confirm dialogs say this plainly.
    - count_all_by_type() is a genuine global total across every
      series/zone (data_access.py's own version takes no series_number
      argument either, for Instrumentation) - there's no per-sheet
      "hasn't been created yet" state a shared database table needs to
      track the way a per-series Excel worksheet does.

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

A second, separate gap the SQLite-backed tests/ suite alone doesn't
cover: it exercises the DATA layer, not access_gui_app.py's own
widget-building code - nothing there imports PySide6 at all. Since
access_gui_app.py is gui_app.py verbatim (see above), its Qt classes
expect the exact same dict/tuple SHAPES data_access.py/electrical_
data_access.py return - not just the same function names. Two real bugs
shipped exactly this way during the redo (series_type_summary()/series_
progress_summary() returning a bare dict instead of the (count, {...})
tuple and {'avg_percent','at_0','partial','at_100'} dict the sidebar/
Dashboard actually unpack; list_backups() returning raw Path objects
instead of the {'path','name','mtime','size'} dicts BackupsDialog
indexes) - both were caught by actually constructing MainWindow and
every dialog class under QT_QPA_PLATFORM=offscreen (no real display
needed) against a SQLite-backed connection, not by the CRUD-level
tests/ suite, which had no reason to know those shapes mattered. Do the
same after touching any da./eda. function access_gui_app.py's UI code
reads structured data from - construct the relevant page/dialog class
directly (skip .exec() on a QDialog, it blocks waiting for real input)
and see it actually build.
