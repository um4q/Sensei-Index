SENSEI INDEX
============

WHAT'S IN THIS FOLDER
----------------------
    SenseiIndex.exe                                    - run this
    _internal\                                         - the app itself
                                                          (leave alone)
    assets\                                             - icon, fonts,
                                                          images the app
                                                          needs to run
    Equipment_Inspection_Tracker.xlsx                  - your data
    Instrumentation Master List.xlsx                  - reference list
    Transmitter_Inspection_Test_Record_TEMPLATE.pdf   - PDF template
    Pneumatically_Actuated_Valve_Check_Record_TEMPLATE.pdf
    app_settings.json, equipment_status.json,          - app state,
    series_registry.json, wizard_draft.json              plain text

Everything above the "your data" line is the application. Everything
from there down is yours: open the .xlsx files directly in Excel any
time, the app reads and writes the same file. PDFs you export land in
whatever folder you pick when exporting - by default, next to this one.

UPGRADING
----------
Running a newer setup.exe over this install replaces the application
files only. Your workbook, settings, and exported data are never
touched or overwritten by an upgrade.

UNINSTALLING
-------------
Use Windows Settings > Apps, or the uninstaller in this folder. It
removes the application only - your .xlsx workbook, the master list,
the PDF templates, and the JSON files are left in place. Delete the
folder yourself afterward if you don't want to keep them.
