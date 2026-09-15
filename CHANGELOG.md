# Changelog

Latest entry first.

## Unreleased - Repository cleanup, pending datasheet-reader fixes merged

**Cleanup:**
- Removed everything that didn't belong in source control: `__pycache__`,
  a compiled Windows `.exe` build artifact, two superseded
  "InstINDEX_Datasheet_Import_Patch" delivery folders (their changes were
  already applied to `gui_app.py`/`datasheet_reader.py`), a stale
  pre-patch backup of `gui_app.py`, a leftover 0-byte script, a stray
  temp-preview PDF, and leftover binary metadata a "Bat To Exe Converter"
  tool had injected at the top of `START_INSTINDEX.bat`.
- Flattened the redundant doubly-nested project folder
  (`Sensei_Index_1.9/Sensei Index 1.9/...`) so the app now lives directly
  at the project root.
- Moved the workbook and every JSON state file into `data/`, and both PDF
  form templates into `templates/`, instead of sitting loose alongside the
  `.py` files. `assets/` (icons, signature image) is unchanged.
- Consolidated four overlapping text files (`README.txt`,
  `READ_ME_FIRST.txt`, `WHATS_NEW_THIS_UPDATE.txt`,
  `PUT_THIS_FILE_IN_YOUR_INSTINDEX_FOLDER.txt`) into this changelog plus a
  single `README.md`.
- Added `.gitignore` and `requirements.txt`; reformatted all `.py` files
  with `black` for consistent style.

**Merged from a never-applied patch bundle** (found sitting in
`_patch_files/`, referenced by `PUT_THIS_FILE_IN_YOUR_INSTINDEX_FOLDER.txt`,
but never actually copied over `datasheet_reader.py` - so none of this had
actually taken effect until now):
- Fixed TIT (Temp Trans Element) data sheets' Instrument Range and
  Calibrated Range coming back blank on Import Datasheet PDF. Every TIT
  sheet's text layer renders these two cells with "to" printed *before*
  the negative number with no separating space (e.g. "-200 to 600" reads
  back as "to-200600"), which used to be unreadable enough to leave
  blank. Instrument Range is confirmed fixed at -200 to 600 degC on every
  TIT sheet (the PT-100 element's full-scale range); Calibrated Range
  varies per instrument but reliably splits as 2 digits after the minus
  sign for the low value and the rest for the high value - both are now
  decoded automatically instead of left blank.
- Added recognition of **DP Level Transmitter** data sheets - the same
  differential-pressure sensor template as Pressure Transmitter (PIT),
  just configured for level service.
- Fixed Tag / P&ID # extraction on Level Transmitter sheets that render
  those fields jammed against the label with no separating whitespace
  (falls back to anchoring on the known "Project Name ... OILSANDS" /
  "Plant Name ... KINOSIS" text instead).
- `export_to_pdf.py` / `export_valve_to_pdf.py`: the auto-filled Comments
  / Remarks line ("See engineering datasheet ... for full spec.") is no
  longer generated - it now starts blank like every other narrative field
  on a new row.

## Import Datasheet PDF now covers four more types

`Import Datasheet PDF` (sidebar, or Ctrl+Shift+I) now recognizes four more
data sheet types on top of the original three:

- On/Off Valve (XV, KV, ... with or without a Positioner)
- Pressure Transmitter (PIT)
- Guided Wave Radar Level Transmitter (LIT)

...alongside the original Control Valve, Temp Trans Element/TW, and Vortex
Flowmeter support.

On/Off Valve sheets fill in the same fields Control Valve sheets do
(Actuator/Positioner model, Trim, ANSI Rating, Leakage Class, Body Style,
Valve Type), except Travel - deliberately left blank, since these are
ball/rotary valves whose "Rated Travel" is a rotation in degrees and the
Travel Unit field only offers Inch/Metric. Solenoid-actuated On/Off Valve
sheets (no Positioner section) correctly leave Positioner Model blank
rather than picking up the solenoid's own model number.

**What it can and can't read:** currently recognizes the CNOOC/Oilsands-
style "DS-" data sheets: Control Valve, On/Off Valve, Temp Trans
Element/TW, Vortex Flowmeter, Pressure Transmitter, and Guided Wave Radar
Level Transmitter. Anything else needs to be entered by hand - it says so
plainly rather than guessing at an unfamiliar layout. Only fields the
sheet gives a direct, unambiguous answer for get pre-filled; Signal Type
and (for valves) Valve Type are educated guesses worth a second look
before saving. Everything else on the data sheet stays on the PDF itself,
one click away.

## Import Datasheet PDF (original)

A new way to start a row: pull it straight from an engineering data sheet
PDF instead of retyping everything by hand.

1. Pick one or more PDFs (one file can hold several instruments).
2. Pick which series to bring them into (defaults to whichever existing
   series' number matches most of the detected tags).
3. Tick which detected records to bring in, then "Review & Add Checked" -
   each one opens through the normal Add New form, pre-filled; nothing
   saves until that form's Save button is clicked.

Recognized on release: Control Valve, Temp Trans Element/TW, and Vortex
Flowmeter (CNOOC/Oilsands-style "DS-" sheets).

## Valves get a real QC sign-off date

Valves previously had no trackable sign-off date - only transmitters did
(QA Rep Date / Client Rep Date). Added a real "QC Rep Date" column for
valves, working like every other date field in the app: its own editable
Index column, mass-editable via Mass Edit Dates, and flowing into the
exported PDF through a genuine fillable field added to the valve PDF
template (positioned on the existing printed "Date:" line). The Export
dialog's old "stamp a date on the signature" option is gone for valves -
set the date field ahead of time and export, same as transmitters.

## Excel-style grid editing, dates, export dates

- **Spreadsheet-style editing:** Tag, System, Type, and every date column
  are editable directly in the Index table - click and type, or F2/Enter
  first. Double-click still opens the full Edit form. Mass-edit shortcuts:
  `Ctrl+C`/`Ctrl+V` (broadcast one value across a selection, or paste a
  real multi-cell block from Excel), `Ctrl+D` (fill down), `Backspace`
  (clear column on selection). Tag/Equip # is exempt (edited one cell at a
  time, with a uniqueness check) but carries its row's status flags over
  automatically when changed. Every edit or mass operation is one
  `Ctrl+Z` step.
- **Date fields** are now real, properly-formatted, mass-editable Index
  columns (previously some were stored as bare Excel serial numbers).
- **Mass Edit Dates** (`Ctrl+Shift+D`): set or clear one date field across
  selected rows or every row shown.
- **Export dialog "Dates" section:** optionally append today's date to
  every output filename; valve-only "stamp a date on the signature" is
  now off by default and only stamps a date you explicitly pick.

## Checkboxes, per-row status, wizard, undo/redo

- **Fixed:** a real Qt styling bug where a checked checkbox/radio button
  could look unchecked on some Windows setups. Checkbox/radio drawing is
  now handled directly (solid fill = checked) so this can't recur.
- **Installed / Submitted / Accepted / Export** are now per-row checkboxes
  in the Index table (no more separate Toggle buttons); "Bulk Status" and
  right-click context menus cover many rows at once. Accepted rows
  highlight green.
- **Export** defaults to "rows checked in the Export column" (a queue you
  build with the Export checkbox) instead of the old workbook Y/N flag,
  which still works as a second option. "Queue All Shown" / "Clear Export
  Queue (Shown)" toolbar buttons speed this up.
- **"Show More"** - a read-only, full-row view (every field, grouped like
  the paper form) with an "Edit This Row..." shortcut.
- **Dashboard "BY SERIES"** breakdown: per-series Transmitter/Valve counts
  plus Installed/Submitted/Accepted totals.
- **Populating Wizard** (`Ctrl+Shift+W`): Setup (series, type, area code,
  tag type, system) -> Repetition (tick which fields carry forward between
  entries) -> Entering ("Save & Next" writes the row and opens a fresh,
  pre-filled entry). "Save as Draft & Close" stashes one resumable
  in-progress batch (single slot, not a library).
- **Undo/redo** (`Ctrl+Z` / `Ctrl+Shift+Z` or `Ctrl+Y`), up to 50 steps,
  covering status changes, Add New, Edit, and Remove Selected.
- **More shortcuts:** `Ctrl+N` Add New, `Ctrl+E` Edit selected, `Ctrl+F`
  search, `Delete` remove selected, `Ctrl+Shift+E` Export, `F5` refresh,
  `Ctrl+,` Settings.
- Sidebar/table right-click context menus; series display names (set via
  Settings > Manage Series or the sidebar) instead of "Series 100"
  everywhere; Export respects the current Index filter; removing a series
  archives (renames + hides) its sheets rather than deleting data.

## Data updates (historical, applied directly to the workbook)

- `Equipment_Inspection_Tracker.xlsx`: TIT Instrument Range / Calibrated
  Range backfilled on the 5 rows that were sitting blank because of the
  extraction bug fixed above (29103-TIT-1300, 29103-TIT-0001,
  29103-TIT-0906, 29203-TIT-0100A, 29203-TIT-0100B) - pulled from the
  original source PDFs, not guessed.
- `Equipment_Inspection_Tracker.xlsx`: sheets renamed/reorganized, 24
  instruments moved into their correct series, 14 new instruments added,
  a number of dates corrected; `series_registry.json` restored alongside
  it with series display names (Mod 100, Mod 200, CMM, SUS Cooler,
  Mainline Separator, Drain Tank 1, Drain Tank 2, K1B Flowline).
