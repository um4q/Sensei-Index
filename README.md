# Sensei Index

A single-window PySide6 desktop app for tracking instrumentation equipment
(transmitters and valves) through inspection, calibration, and sign-off -
backed by an Excel workbook, with one-click PDF export of the filled
inspection/check-record forms.

Originally shipped as "InstINDEX"; some file names, window titles, and
messages still say InstINDEX - that's the same app.

## What it does

- **Dashboard** - totals and per-system/per-series breakdowns of everything
  logged, at a glance.
- **Index views** - one spreadsheet-style table per equipment type/series,
  editable in place (click a cell and type, or use Excel-style
  copy/paste/fill-down across a selection). Installed / Submitted /
  Accepted / Export are per-row checkboxes.
- **Add / Edit** - a focused form for every field on the paper record,
  grouped into the same sections as the printed form.
- **Import Datasheet PDF** - pulls Tag, P&ID #, service, make/model, ranges,
  and similar fields straight from an engineering data sheet PDF into a
  pre-filled Add New form, instead of retyping them by hand. See
  [CHANGELOG.md](CHANGELOG.md) for exactly which data sheet families and
  fields it recognizes.
- **Export** - fills the matching blank PDF template (transmitter or valve)
  with a row's data, optionally stamps a signature image, and can flatten
  the result or merge several rows into one combined PDF.
- **Populating Wizard** - bulk-enter a batch of similar equipment quickly,
  carrying repeated field values forward between entries.
- **Undo/redo, keyboard shortcuts, light/dark theme, Excel-file shortcuts** -
  see [CHANGELOG.md](CHANGELOG.md) for the full list.

## Requirements

- Python 3.9+
- [PySide6](https://pypi.org/project/PySide6/), [openpyxl](https://pypi.org/project/openpyxl/),
  [pypdf](https://pypi.org/project/pypdf/), [reportlab](https://pypi.org/project/reportlab/)
  (see [requirements.txt](requirements.txt))

## Quick start

**Windows, no command line needed:** double-click `START_INSTINDEX.bat`. The
first run installs the required packages into your own account
(`pip install --user`, no admin rights needed) and then opens the app;
every run after that just opens the app.

**From a terminal, any OS:**

```
pip install -r requirements.txt
python gui_app.py
```

### Where to put this folder

Put the whole project folder somewhere your account can write to *without*
needing "Run as administrator" - the app saves the workbook, settings, and
series list right next to itself on every edit. Good choices:

- `C:\Users\Public\SenseiIndex` (shared - every account on the PC can use it)
- Your Desktop or Documents folder

Avoid `C:\Program Files` (or `Program Files (x86)`) - those need elevation
to write to, and every save would fail (or need "Run as administrator")
until the folder is moved out. `START_INSTINDEX.bat` warns you if it
detects this.

Don't split the folder up - `gui_app.py` looks for `data/`, `templates/`,
and `assets/` relative to its own location, so everything needs to stay
together.

## Project layout

```
gui_app.py                  Main application (run this, or via START_INSTINDEX.bat)
data_access.py               All reading/writing of the workbook and the JSON files
theme.py                      Light/dark stylesheets
datasheet_reader.py           Parses engineering data sheet PDFs for "Import Datasheet PDF"
transmitter_schema.py         Transmitter column/field definitions
transmitter_field_map.py      Transmitter row -> PDF form field mapping
valve_schema.py                Valve column/field definitions
valve_field_map.py             Valve row -> PDF form field mapping
export_to_pdf.py                Fills a transmitter PDF from the workbook (also a CLI tool)
export_valve_to_pdf.py          Fills a valve PDF from the workbook (also a CLI tool)

assets/                       Icons and the signature image used on exports
templates/                    Blank, fillable PDF forms used as export templates
data/                         The workbook and every JSON file the app reads/writes:
    Equipment_Inspection_Tracker.xlsx   The actual equipment log (the "database")
    Instrumentation Master List.xlsx    Reference workbook, not read by the app
    series_registry.json                Series numbers and their display names
    app_settings.json                    Theme and export preferences
    equipment_status.json                Installed/Submitted/Accepted/Export checkboxes
    wizard_draft.json                    The Populating Wizard's saved-draft slot
    temp_previews/                        "View Details" scratch output (safe to delete)

START_INSTINDEX.bat            Windows: install deps (first run only) and launch the GUI
Run_Export_Transmitters.bat     Windows: command-line export of every flagged transmitter row
Run_Export_Valves.bat           Windows: command-line export of every flagged valve row
```

## Command-line PDF export

For exporting without opening the GUI - `Run_Export_Transmitters.bat` /
`Run_Export_Valves.bat` on Windows, or directly:

```
python export_to_pdf.py [excel_path] [--rows 4,7,12] [--all] [--merge] [--flatten]
python export_valve_to_pdf.py [excel_path] [--rows 4,7,12] [--all] [--merge] [--flatten]
```

With no arguments, both default to every row flagged `Y` in
`data/Equipment_Inspection_Tracker.xlsx`, writing filled PDFs to
`output_pdfs/` next to the script. Run either with `--help` for the full
option list.

## Adding a new equipment type

`gui_app.py` never touches the workbook directly or hardcodes what
"Transmitter" and "Valve" mean - it reads everything from
`EQUIPMENT_TYPES` in `data_access.py`. To add a new type (say, "Gauges"),
write `gauge_schema.py` + `gauge_field_map.py` + `export_gauge_to_pdf.py`
following the existing Transmitter/Valve trio, then add one entry to
`EQUIPMENT_TYPES`. The menu, index table, edit form, and detail-view PDF
are all generic and pick it up automatically.

## Rebuilding a standalone .exe (optional)

Only needed for a taskbar-pinnable, console-free `.exe`, or to hand the app
to someone without Python. On a Windows machine, with this project's
contents in place:

```
python -m pip install --user pyinstaller
python -m PyInstaller --onefile --windowed --name SenseiIndex gui_app.py
```

That produces `dist\SenseiIndex.exe`. Copy it back into the project folder
(next to `data/`, `templates/`, and `assets/`) before using it - like the
Python version, it needs everything else here sitting right next to it.

## Version history

See [CHANGELOG.md](CHANGELOG.md).
