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

Only two equipment types get imported - Transmitters and Valves, the
same two the PDF templates in this app have always supported. A
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


3. THE RUN - A NEW PRIMARY SCREEN
-----------------------------------------------------------------
The app now opens straight into "The Run" instead of the Dashboard (the
Dashboard is still there in the sidebar, unchanged). It's one flat list
across every series and both equipment types, built for moving fast
through a stack of tags in the field:

    Up / Down      move
    Space          advance one stage (Not started -> Installed ->
                   Submitted -> Accepted)
    Shift+Space    step back one stage
    A              jump straight to Accepted
    E              toggle the row's export queue
    Ctrl+Z          undo (same undo stack the rest of the app already uses)
    /              jump to search
    F              Field mode - bigger rows and text for reading on a
                   phone/tablet in the field, same shortcuts either way

Filter boards along the top (Everything / Needs install / Ready to
submit / Awaiting client / Flagged) mirror the sidebar's own counts.

A Check column runs two live checks on every row, same as the workbook
always could have told you but never did:
    - "Range exceeds instrument span" - the calibrated range doesn't fit
      inside the instrument's own full-scale range
    - "No serial number" / "Submitted, no serial" - missing serial, worse
      once it's already gone to the client with nothing on it
Checks never block anything - purely informational, same philosophy as
every other check-style feature already in this app.

The Journal panel (toggle from the header) is a new, permanent, stamped
log of every stage change and export-queue toggle made from the Run
screen - who, what, when. It's separate from the app's Ctrl+Z (which only
lives in memory for the current session): undoing something adds a new
journal line rather than erasing the old one, since for a QA record
"installed, then stepped back" is more honest than making the first
entry disappear. Set your name once in Settings > Run Journal so entries
are attributed to you instead of "Unnamed crew member."


4. ACCESSIBILITY
-----------------------------------------------------------------
Stage is always shown as a word next to the fill, never color alone. The
Run list's row-status checkboxes and the new Run screen's controls carry
accessible names that include which row they're on ("29103-PIT-1014,
Submitted"), not just which column, so a screen reader doesn't read three
unlabeled cells - it reads one sentence per row. This pass covered the
Run screen (built accessible from the start) and the Index view's
per-row status checkboxes, which was the concrete example called out in
the accessibility redesign. A full pass over every remaining dialog in
the app is a reasonable next increment, not done here.


5. FILES ADDED IN THIS FOLDER (vs. 1.9)
-----------------------------------------------------------------
    run_view.py                 - the Run screen (new)
    tools/masterlist_etl.py     - classification + cross-reference logic,
                                   read-only, importable, has its own
                                   report mode (python tools/masterlist_etl.py)
    tools/build_v4_tracker.py   - runs the ETL and writes the workbook +
                                   series_registry.json (what actually
                                   built this folder's tracker)
    data_access.py               - unchanged functions untouched; added
                                   read_run_rows/set_run_stage/get_run_stage
                                   and the Run journal (append_journal/
                                   read_journal) at the end of the file
    gui_app.py                   - added the Run nav item and boot-into-Run,
                                   generalized the two refresh methods that
                                   used to assume "Index page or Dashboard"
                                   to also cover Run, added a "Your name"
                                   field to Settings
