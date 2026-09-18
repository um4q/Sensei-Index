SENSEI INDEX 4.0 - WHAT CHANGED FROM 1.9
=============================================

This folder is a new, separate version - 1.9 is untouched, sitting next to
this one in Sensei_Index_1.9/. Nothing here can break what already works.

Run it the same way as before: python gui_app.py (needs PySide6, openpyxl,
pypdf, reportlab - same dependencies 1.9 already needed).


1. SCOPE: K1B IS THE FOCUS, K1A IS OUT (EXCEPT DRAIN TANK 2)
-----------------------------------------------------------------
Per direction from the project owner: K1A is out of scope for this tool
entirely, except Drain Tank 2 (series 29152), which stays in. K1B is the
area this tool is built around.

    KEPT (K1B):     Mod 100, Mod 200, Mainline Separator (29103),
                     K1B Flowline (29203), CMM (400), SUS Cooler (500),
                     K1B Pad - Additional (29104, new), SUS (9050, new)
    KEPT (K1A exception): Drain Tank 2 (29152)
    REMOVED:        Drain Tank 1 (29151) - archived, not deleted (see
                     below), and K1A Produced Emulsion / K1A Steam
                     Generation / the 29901 & 29902 injection wells, none
                     of which were ever tracked in 1.9's workbook, so
                     there was nothing to remove for those - they're just
                     not imported from the master list.

"Archived, not deleted" means Drain Tank 1's two sheets are still
physically in Equipment_Inspection_Tracker.xlsx, renamed with a "DEL "
prefix and hidden, and it's unregistered from series_registry.json. Same
convention the app's own Settings > Remove Series already used in 1.9 -
nothing about this rebuild introduced a new way to lose data. Unhide it
in Excel (right-click a sheet tab > Unhide) if you ever need it back.


2. THE MASTER LIST GOT CROSS-REFERENCED INTO THE TRACKER
-----------------------------------------------------------------
"Instrumentation Master List.xlsx" (in this folder) is the actual
engineering instrument list for the whole project - far bigger than what
1.9's tracker had ever been populated with. K1B Pad alone lists 1120
instruments; the tracker only had a few hundred logged.

tools/build_v4_tracker.py cross-referenced the two: every tag already in
the tracker was left completely untouched (checked - 357 pre-existing
rows, zero changes), and every K1B / Drain Tank 2 tag from the master
list that WASN'T already tracked got added as a new blank row, ready for
the field crew to fill in as they inspect it:

    K1B Pad (29103) -> new series "K1B Pad — Additional" (29104):
        +39 transmitters, +67 valves
    K1B Flowline (29203) -> appended to the existing series:
        +0 transmitters, +2 valves
    Drain Tank 2 (29152) -> appended to the existing series:
        +0 transmitters, +5 valves
    9050 SUS -> new series "SUS" (9050), never tracked before:
        +22 transmitters, +4 valves

At the time this ETL ran, only Transmitters and Valves had PDF templates
in this app, so only those two equipment types were imported (Gauges were
added later, as their own separate import - see EQUIPMENT_TYPES in
data_access.py, which now lists three types, not two). A
"Positioner" row in the master list isn't imported as its own record;
it's matched to its parent valve (same area + loop number) and folded
into that valve's Positioner Model field, the same place the Valve Check
Record already had room for it. Every one of the 101 positioner rows in
K1B/Drain 2 scope matched cleanly.

Everything else the master list lists - gauges, switches, thermowells,
downhole fiber temperature elements, motor/VFD signals, relief and
manual valves, analyzer elements, and so on (757 rows across the K1B +
Drain Tank 2 scope) - has no PDF test record in this system at all, so
it was never silently dropped: open the "Not Tracked (Reference)" sheet
in the workbook to see the full list, grouped by type, with counts. If
you want one of those types tracked properly one day, data_access.py's
own header comment explains exactly how to add a new equipment type
(schema + field map + PDF export module + one entry in EQUIPMENT_TYPES) -
the same pattern the existing Transmitter/Valve pair already follows.

Re-running it: if the master list gets updated, re-run
    python tools/build_v4_tracker.py
from inside this folder. It's safe to run again - it never overwrites a
cell that already has a value, it only appends genuinely new tags.


3. THE RUN - BUILT, THEN CUT
-----------------------------------------------------------------
A "Run" primary screen (one flat list across every series/equipment type,
with keyboard-driven stage advancing, filter boards, a Check column, and
a permanent Journal log) was designed and partly built, then reverted -
it never shipped, and the app opens into the Dashboard, unchanged, same
as before. This section used to describe it as if it existed; it didn't,
and this rewrite is the correction (see also GUI audit Part 3, defects
1-3). The Check column's own two live checks weren't wasted, though -
they're exactly what index_view.py's per-row flag now runs on the Index
table (data_access.run_row_flag): "Range exceeds instrument span" and
"No serial number" / "Submitted, no serial." Building a real Run screen
is still a reasonable thing to want; if that happens, it should read from
data_access.stage_from_status/set_run_stage/get_run_stage/run_row_flag,
which are real, live, still here, and already what the Index table itself
runs on.


4. ACCESSIBILITY
-----------------------------------------------------------------
Stage is always shown as a word next to the fill, never color alone. The
Index table's Stage cell (index_view.StageCell) carries an accessible name
that includes which row it's on ("29103-PIT-1014, Submitted"), not just
the stage word alone, so a screen reader doesn't read an unlabeled cell in
isolation - it reads one sentence per row. A full pass over every
remaining dialog in the app is a reasonable next increment, not done here.


5. FILES ADDED IN THIS FOLDER (vs. 1.9)
-----------------------------------------------------------------
    tools/masterlist_etl.py     - classification + cross-reference logic,
                                   read-only, importable, has its own
                                   report mode (python tools/masterlist_etl.py)
    tools/build_v4_tracker.py   - runs the ETL and writes the workbook +
                                   series_registry.json (what actually
                                   built this folder's tracker)
    data_access.py               - added stage_from_status/set_run_stage/
                                   get_run_stage/bulk_set_stage/run_row_flag,
                                   which the Index table's own Stage column
                                   and per-row flag now run on (see section 3
                                   above - not run_view.py/read_run_rows/the
                                   Run journal, which were built for the Run
                                   screen and removed with it)
    gui_app.py                   - unchanged in this area; see index_view.py
                                   (plate 6a's Index table) for the Stage
                                   column and bulk actions instead
    master_list.py               - reads Instrumentation Master List.xlsx
                                   directly (all 9 sheets/areas, not just
                                   the K1B-focused subset above) and
                                   classifies every raw "Instrument Type
                                   Description" string into a (family,
                                   discipline) pair - see section 6.
    overall_index_view.py        - the Overall Index screen (section 6).


6. OVERALL INDEX (GUI audit Part 3, Section 3)
-----------------------------------------------------------------
A new sidebar page, above the per-series ones, showing every real
instrument tag in the master list workbook - not just the three
equipment types (Transmitter/Valve/Gauge) this app can generate a PDF
record for. As of the current workbook: 1,686 tags across 9 areas, 100
distinct raw type strings normalized into 28 families over 9 disciplines
(Temperature/Pressure/Flow/Level/Valve/Rotating equipment/Discrete/
Electrical/Analyzer), with exactly one string left Unclassified - see
master_list.py's own docstring for what it is (a document-control label
that landed in the Instrument Type Description column by mistake, a real
data-entry defect in the source workbook, not a gap in the taxonomy).

These numbers are bigger than the GUI audit document that asked for this
screen expected (it quoted 1,332 tags / 8 areas / 75 type strings) -
checked against the real workbook rather than assumed, since several of
that same document's other claims turned out to be wrong earlier in this
pass. Every one of its named spelling collisions (CONTROL VALVE - ON/OFF
vs CONTROL VALVE, ON/OFF; TEMPTERATURE GAUGE; the four hand-switch
spellings; and the rest) is real and present in the current data with
higher counts than quoted - strong evidence the master list has simply
grown since that document was written, not that the numbers were
invented. The screen reflects the live workbook, not the stale snapshot.

Recorded/Open/No-form is decided empirically per family (does the
tracker actually have a real example of this family logged anywhere
today), not guessed from the type name - see overall_index_rows()'s
docstring in master_list.py. Read-and-triage only: this screen never
edits a cell. A virtualized QAbstractTableModel + QStyledItemDelegate
(no per-row QTableWidgetItem/cell widgets), because at this size "only
the visible rows exist" stopped being optional.

While building this, the same dark-theme-unreadable pattern GUI audit
Part 3 already found and fixed in the per-series Index table (near-white
"ink" text on a surface that's pinned white in every theme) turned out to
also affect every QLineEdit/QComboBox/QTextEdit in the entire app -
typed text in any search box or form field was rendering essentially
invisible in dark theme. Fixed at the source (theme.py's shared control
QSS now pins that text to LIGHT's ink, same as the index table), not
patched locally per screen.
