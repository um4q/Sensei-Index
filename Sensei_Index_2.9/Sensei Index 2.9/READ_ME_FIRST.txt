INSTINDEX - QUICK START
=========================

1. Put this whole folder somewhere normal, like your Desktop or Documents.
   (Don't split it up - everything in here needs to stay together.)

2. Double-click "Sensei Index 2.95.exe"

That's it - no separate Python install, no first-time package setup.
The whole app is one file now; everything else in this folder (the
.xlsx workbooks, the .json config files, the PDF templates, the assets
folder) just needs to stay sitting right next to it, exactly like it
already needs to sit next to gui_app.py today - the app looks for all
of it relative to its own location either way.

The app window can take 20-30 seconds to appear the very first time you
open it after adding data - that's normal, not a freeze.

If something goes wrong and the app closes unexpectedly, check for a
crash_log.txt file that appears right next to the exe - it has the full
error, and is the most useful thing to share if you need help.

RUNNING FROM SOURCE INSTEAD (only if you need to - e.g. to make your own
code changes)
--------------------------------------------------------------------------
Double-click START_INSTINDEX.bat instead of the exe. First time, it'll
quietly install the required Python packages (needs Python already
installed - the .bat file will tell you exactly what to do if it isn't).
Run_Export_Transmitters.bat and Run_Export_Valves.bat still work the
same way too, if you'd rather export PDFs from the command line.

WHERE TO PUT THIS FOLDER (IMPORTANT)
----------------------------------------
Put this whole InstINDEX folder somewhere your Windows account can write
to WITHOUT needing "Run as administrator" - this app saves the workbook,
settings, and series list right next to itself on every single edit, so
this matters. Good options:
    C:\Users\Public\InstINDEX      (shared - every account on this PC can use it)
    C:\Users\<you>\Desktop\InstINDEX
    C:\Users\<you>\Documents\InstINDEX
Do NOT put it inside "C:\Program Files" or "C:\Program Files (x86)" -
those need admin rights to write to, and every save would fail (or need
you to run as admin every single time) until you move it out. The
startup script below will actually warn you if it detects this.

WHAT'S NEW IN THIS VERSION
-----------------------------
- Nothing here should ever need administrator rights anymore. The
  one-time package setup now installs into your own Windows account
  (pip install --user) instead of the shared, admin-protected location -
  this matters because Python's official installer defaults to "install
  for all users," which is exactly what forces pip to need admin. And if
  the app's folder itself still needs admin to write to (usually because
  it got placed inside Program Files), every save now tells you that
  plainly and tells you where to move it, instead of a cryptic crash.
- Much faster: opening the app went from ~35-40 seconds down to about 2,
  by loading the workbook once and reusing it instead of re-parsing the
  whole file 20-30+ times on every launch.
- Multi-select in the row table (Ctrl/Shift-click, or "Select All"), plus
  "Remove Selected". Removing clears a row's data rather than physically
  deleting the spreadsheet row, so it can never disturb dropdowns or
  conditional formatting - the freed row is reused automatically.
- Toggle Installed / Submitted / the new Toggle Accepted all now work on
  however many rows are selected at once. Any row marked Accepted is
  highlighted green across the whole row.
- Right-click a series in the sidebar, or right-click any row in the
  table, for a context menu (Rename/Remove a series; View/Edit/Export/
  Toggle status/Remove on a row) - no need to hunt for the toolbar button.
- Series no longer show as "Series 100" everywhere - give one a name
  (Settings > Manage Series, the sidebar right-click, or when creating a
  new one) and that name is what shows up throughout the app instead.
  Unnamed ones just show their bare number.
- Export now respects whatever filter the Index view is currently showing
  - so drilling into a System via the sidebar's "By System" tree, then
  hitting Export, exports only that system's rows instead of everything.
- Dashboard has a new "Quick Tips" card: a reminder that logging new
  equipment is fastest done directly in Excel (bulk entry, autofill,
  copy/paste), and an "Excel Sheets" button that opens a Transmitter
  Log / Valve Log menu - pick any sheet to jump Excel straight to that
  tab. (If the workbook's already open in Excel, this just brings that
  window forward rather than switching its tab - Excel won't re-read a
  file it already has open.)
- Removing a series still doesn't destroy data - it archives (renames +
  hides) its sheets rather than deleting them, and asks you to type the
  series number to confirm before doing anything.
