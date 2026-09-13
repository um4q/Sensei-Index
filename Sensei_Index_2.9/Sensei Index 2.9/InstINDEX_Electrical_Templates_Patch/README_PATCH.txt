INSTINDEX - ELECTRICAL FORMS REAL-SOURCE REBUILD - UPDATE PATCH
==========================================================================

WHAT THIS IS
------------------
Rebuilds 3 Electrical forms - Transformer Test Record, Small Power and
Control Cable Inspection & Test Record, and General Electrical Equipment
Installation & Test Report - directly from the real, official versions
of those documents, instead of the hand-filled scan sample they were
originally built from. This is what fixes the "white spots" / whiteout-
inconsistency issue on these 3 forms.

Every exported PDF from these 3 forms should now look EXACTLY like your
real paperwork - same layout, same fonts, same logos, nothing altered -
with the fillable fields sitting precisely on top of the real form.


WHAT'S NEW
--------------
- Transformer Test Record and Small Power and Control Cable ITR: rebuilt
  on top of the real PDFs you sent, pixel/point-accurate to the source.
- General Electrical Equipment Installation & Test Report: rebuilt on
  top of your real Word document (converted to PDF). One thing to know:
  that conversion naturally splits the form onto 2 pages instead of 1
  (the Torqueing Log's last 3 rows, Comments, and the Sign-Off block
  land on page 2) - a pagination/margin difference from the conversion,
  not a content change. Exporting a filled copy of this form now
  produces a 2-page PDF; nothing on it is missing or reordered.
- Along the way, a couple of real bugs in the earlier scan-based
  versions were fixed for good, not just papered over - most notably a
  whiteout box on the General Electrical Equipment Installation form
  that was clearing the real printed "LOCATION:" label along with the
  sample text next to it. See WHATS_NEW_THIS_UPDATE.txt (after applying)
  for the full writeup.

WHAT'S STILL OUTSTANDING
------------------------------
The Yes/N-A style columns on these forms (and the other checklist-style
forms) are still plain fillable text boxes, not real clickable
checkboxes - that's a separate, not-yet-started change.


HOW TO APPLY IT
--------------------
1. Move (or extract, if this is still zipped) this WHOLE folder -
   "InstINDEX_Electrical_Templates_Patch", including the _patch_files
   subfolder (and its own assets subfolder) inside it - into your
   InstINDEX installation folder. That's the same folder that already
   has gui_app.py, data_access.py, START_INSTINDEX.bat, your
   Equipment_Inspection_Tracker.xlsx, etc. in it. It should end up
   sitting right alongside those files, as a subfolder.

2. Double-click APPLY_UPDATE.bat, INSIDE that folder.

3. It'll show you exactly what it's about to do and ask you to confirm
   (type Y and press Enter). Your current copies of everything it's
   about to touch get backed up automatically before anything is
   overwritten or removed.

4. That's it - close the window when it says "Done", then start
   InstINDEX the normal way (START_INSTINDEX.bat). No rebuild, no
   reinstall, nothing else changes about how you run it.

You can delete the "InstINDEX_Electrical_Templates_Patch" folder
afterward if you want to tidy up - once it's applied, the app doesn't
need it anymore.


IF SOMETHING GOES WRONG
----------------------------
Everything this patch touched, from right before you applied it, is
saved at:
    _backup_before_electrical_templates_patch\
(inside your InstINDEX folder - this gets overwritten each time you run
this specific patch, so it always holds your most recent pre-patch
version, not necessarily your very first one)

To undo this patch, copy those files back over their originals in the
main InstINDEX folder (the 3 background .jpg files go back inside its
assets subfolder).


WHAT'S ACTUALLY IN THIS FOLDER
-----------------------------------
    APPLY_UPDATE.bat                        - run this
    README_PATCH.txt                        - this file
    _patch_files\electrical_data_access.py                                            - updated
    _patch_files\build_transformer_test_template.py                                   - updated
    _patch_files\build_small_power_cable_template.py                                  - updated
    _patch_files\build_general_equip_install_template.py                              - updated
    _patch_files\export_transformer_test_to_pdf.py                                    - updated
    _patch_files\export_small_power_cable_to_pdf.py                                   - updated
    _patch_files\export_general_equip_install_to_pdf.py                               - updated
    _patch_files\transformer_test_field_positions.py                                  - updated
    _patch_files\small_power_cable_field_map.py                                       - updated
    _patch_files\small_power_cable_schema.py                                          - updated
    _patch_files\general_equip_install_field_positions.py                             - updated
    _patch_files\general_equip_install_field_map.py                                   - updated
    _patch_files\general_equip_install_schema.py                                      - updated
    _patch_files\Transformer_Test_Record_TEMPLATE.pdf                                 - updated
    _patch_files\Small_Power_and_Control_Cable_Inspection_and_Test_Record_TEMPLATE.pdf - updated
    _patch_files\General_Electrical_Equipment_Installation_and_Test_Report_TEMPLATE.pdf - updated
    _patch_files\WHATS_NEW_THIS_UPDATE.txt                                            - updated
    _patch_files\assets\transformer_test_source.pdf                                   - new file
    _patch_files\assets\small_power_cable_source.pdf                                  - new file
    _patch_files\assets\general_equip_install_source.pdf                              - new file
