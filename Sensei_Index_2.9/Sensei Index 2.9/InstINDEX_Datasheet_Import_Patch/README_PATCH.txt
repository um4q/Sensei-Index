INSTINDEX - IMPORT DATASHEET PDF - UPDATE PATCH
====================================================

WHAT THIS IS
------------------
A patch, not a full copy of the app - it updates just the 2 files that
needed to change (gui_app.py, WHATS_NEW_THIS_UPDATE.txt) and adds one new
file (datasheet_reader.py) to your EXISTING InstINDEX installation.
Nothing else - not your workbook, not your JSON files, not your PDF
templates - is touched.

See WHATS_NEW_THIS_UPDATE.txt (after applying) for what the new feature
actually does.


HOW TO APPLY IT
--------------------
1. Move (or extract, if this is still zipped) this WHOLE folder -
   "InstINDEX_Datasheet_Import_Patch", including the _patch_files
   subfolder inside it - into your InstINDEX installation folder. That's
   the same folder that already has gui_app.py, data_access.py,
   START_INSTINDEX.bat, your Equipment_Inspection_Tracker.xlsx, etc. in
   it. It should end up sitting right alongside those files, as a
   subfolder.

2. Double-click APPLY_UPDATE.bat, INSIDE that folder.

3. It'll show you exactly what it's about to do and ask you to confirm
   (type Y and press Enter). Your current gui_app.py gets backed up
   automatically before anything is overwritten.

4. That's it - close the window when it says "Done", then start
   InstINDEX the normal way (START_INSTINDEX.bat). No rebuild, no
   reinstall, nothing else changes about how you run it.

You can delete the "InstINDEX_Datasheet_Import_Patch" folder afterward if
you want to tidy up - once it's applied, the app doesn't need it anymore.


IF SOMETHING GOES WRONG
----------------------------
Your original gui_app.py is saved at:
    _backup_before_datasheet_import_patch\gui_app.py
(inside your InstINDEX folder, created the first time you run the patch)

To undo the patch, just copy that file back over gui_app.py in the main
InstINDEX folder. datasheet_reader.py can stay - the app only ever
touches it when the new Import button is actually used, so leaving it
there does nothing on its own.


WHAT'S ACTUALLY IN THIS FOLDER
-----------------------------------
    APPLY_UPDATE.bat              - run this
    README_PATCH.txt              - this file
    _patch_files\gui_app.py             - the updated app file
    _patch_files\datasheet_reader.py    - the new datasheet-reading module
    _patch_files\WHATS_NEW_THIS_UPDATE.txt   - updated changelog
