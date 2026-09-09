WHAT'S IN THIS FOLDER
==========================

1. Equipment_Inspection_Tracker.xlsx
   - TIT Calibration Range / Instrument Range now filled in wherever it
     was blank (see below for why it was blank and how it got fixed).

2. series_registry.json
   - Same series names as last time (Mod 100, Mod 200, CMM, SUS Cooler,
     Mainline Separator, Drain Tank 1, Drain Tank 2, K1B Flowline) -
     only included again in case you're applying this fresh.

3. _patch_files/datasheet_reader.py
   - The updated datasheet reader with the TIT range fix baked in, so
     any NEW TIT you import from here on gets this automatically instead
     of coming back blank.

Put all three in your InstINDEX folder, overwriting what's there.


WHY THE TIT RANGES WERE BLANK, AND HOW THIS FIXES IT
---------------------------------------------------------
On every TIT data sheet, the PDF's own text renders the Instrument Range
and Calibrated Range cells with the "to" printed before the negative
number instead of after it, with no space between the numbers - so
"-200 to 600" was coming out of the PDF's text layer as "to-200600".
That's not readable as a range at all, so the importer was leaving it
blank rather than guess.

I rendered several of these PDFs as images and read the cells directly
(bypassing the broken text extraction entirely) to check what the real
values were. Two things came out of that:
  - Instrument Range is always -200 to 600 degC on every TIT sheet in
    this project - it's the fixed full-scale range of the PT-100 sensor
    element, not something that varies per instrument. Confirmed on 4
    different sheets across 3 different tags.
  - Calibrated Range does vary per instrument, but always splits as
    exactly 2 digits after the minus sign for the low value and the rest
    for the high value - also confirmed on 4 different sheets.

Both are now decoded automatically. I went back and filled in the 5 TIT
rows already in your tracker that were sitting blank for this exact
reason (29103-TIT-1300, 29103-TIT-0001, 29103-TIT-0906, 29203-TIT-0100A,
29203-TIT-0100B) - all pulled straight from the same ds23.pdf they were
originally imported from, not guessed.
