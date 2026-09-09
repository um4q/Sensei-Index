INSTINDEX - IMPORT DATASHEET PDF - UPDATE PATCH (v2)
==========================================================

WHAT THIS IS
------------------
An incremental patch on top of the original Import Datasheet PDF patch.
It updates the same 3 files (gui_app.py, datasheet_reader.py,
WHATS_NEW_THIS_UPDATE.txt) in your EXISTING InstINDEX installation -
nothing else is touched. Safe to apply whether or not you already
applied the first version of this patch.

WHAT'S NEW IN v2
--------------------
The datasheet reader now also recognizes:
    - On/Off Valve            (XV, KV, ... with or without a Positioner)
    - Pressure Transmitter    (PIT)
    - Guided Wave Radar Level Transmitter   (LIT)

...on top of the original Control Valve, Temp Trans Element and TW, and
Vortex Flowmeter support. See WHATS_NEW_THIS_UPDATE.txt (after applying)
for the full details on what each type fills in and what it deliberately
leaves blank.

A couple of extraction bugs found while adding these were also fixed for
the ORIGINAL three types too, in this same patch - most notably a rare
case where a Control Valve's Seat Material could come back blank instead
of its actual value, and a Service field on some sheets picking up
stray text from the next column over.


HOW TO APPLY IT
--------------------
1. Move (or extract, if this is still zipped) this WHOLE folder -
   "InstINDEX_Datasheet_Import_Patch_v2", including the _patch_files
   subfolder inside it - into your InstINDEX installation folder. That's
   the same folder that already has gui_app.py, data_access.py,
   START_INSTINDEX.bat, your Equipment_Inspection_Tracker.xlsx, etc. in
   it. It should end up sitting right alongside those files, as a
   subfolder.

2. Double-click APPLY_UPDATE.bat, INSIDE that folder.

3. It'll show you exactly what it's about to do and ask you to confirm
   (type Y and press Enter). Since gui_app.py already mentions
   datasheet_reader from the first patch, it'll ask you to confirm a
   second time before re-applying - that's expected, just confirm again.
   Your current gui_app.py gets backed up automatically before anything
   is overwritten.

4. That's it - close the window when it says "Done", then start
   InstINDEX the normal way (START_INSTINDEX.bat). No rebuild, no
   reinstall, nothing else changes about how you run it.

You can delete the "InstINDEX_Datasheet_Import_Patch_v2" folder
afterward if you want to tidy up - once it's applied, the app doesn't
need it anymore.


IF SOMETHING GOES WRONG
----------------------------
Your gui_app.py from right before this patch is saved at:
    _backup_before_datasheet_import_patch\gui_app.py
(inside your InstINDEX folder - this gets overwritten each time you run
a patch, so it always holds your most recent pre-patch version, not
necessarily your very first one)

To undo just this patch, copy that file back over gui_app.py in the main
InstINDEX folder.


WHAT'S ACTUALLY IN THIS FOLDER
-----------------------------------
    APPLY_UPDATE.bat              - run this
    README_PATCH.txt              - this file
    _patch_files\gui_app.py             - the updated app file
    _patch_files\datasheet_reader.py    - the updated datasheet-reading module
    _patch_files\WHATS_NEW_THIS_UPDATE.txt   - updated changelog
