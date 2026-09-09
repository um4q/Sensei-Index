# Sensei Index 2.9 — Implementation Prompt

**Hand this entire document to the ultracode session that will implement it.** It is
self-contained: everything needed to execute is either in this file or already committed
in this repo (branch `claude/new-session-rcv1yz`, or wherever it has since been merged to).

This document was prepared by an earlier Claude Code session after reading both source
PDFs page-by-page. It does **not** implement anything itself — it is the planning/spec
document the user asked for, to run through `ultracode` (multi-agent orchestration) as a
separate pass.

---

## 0. Open question — CONFIRM BEFORE STARTING

The user's request contained a contradiction that was never resolved:

> "i want this version to be as sensei index version 2.5, replace all 1.9 stuff with 2.9"

Two different version numbers in one sentence. This document defaults to **"2.9"
everywhere** (folder name, displayed app title, any version string), because that half of
the sentence was the explicit, literal, repeated instruction ("replace **all** 1.9 stuff
with 2.9"), while "version 2.5" reads like a slip. **Before running Phase A, re-confirm
with the user which number they actually want** — a global rename is annoying to redo.
If they say 2.5, swap every "2.9" below for "2.5" (folder name included) and proceed
exactly the same way otherwise.

---

## 1. Context you need before starting

Sensei Index is a PySide6 desktop app for a client (COOEC Canada Ltd., K1B Well Pad
Project) that tracks equipment inspection/test records in Excel and exports them as
filled PDF forms. It currently has two **domains**, each fully independent (own
workbook, own data-access module, own GUI pages) — this independence is a deliberate,
load-bearing architectural choice from the prior session, not incidental:

- **Instrumentation** (the original app): `data_access.py` (aliased `da`),
  `Equipment_Inspection_Tracker.xlsx`, `series_registry.json`, organized by numbered
  "series". Two equipment types: Transmitter, Valve.
- **Electrical** (added in the immediately prior session): `electrical_data_access.py`
  (aliased `eda`), `Electrical_Inspection_Tracker.xlsx`, `electrical_registry.json`,
  organized by free-named "Zone". Two equipment types so far:
  - `eht_removal` — EHT Removal and Reinstatement Report (YCQE-EHT-019 Rev.0)
  - `eht_rtd` — EHT & RTD Installation Inspection Report (YCQE-E&I-004 Rev.0)

  **Do not confuse this with the new form in Phase B below** — YCQE-EHT-004 is a
  different form from YCQE-E&I-004, despite the similar name. See Phase B.

Every equipment type follows the same trio pattern, hand-verified against a real
fillable AcroForm PDF:
- `<key>_schema.py` — `FIELDS`/`LOG_COLUMNS` list: `{id, label, section, ftype, choices}`
  per field, `SECTION_TITLES`, `by_section()`.
- `<key>_field_map.py` — `FIELD_MAP: {schema_id: real_pdf_field_name_or_None}`, plus
  `CHECKBOX_GROUPS`/`YES_NO_CHECKBOXES` for choice fields backed by real PDF checkboxes,
  `CHECKBOX_ON`/`CHECKBOX_OFF`.
- `export_<key>_to_pdf.py` — `HEADER_ROW=3`, `FIRST_DATA_ROW=4`, `SHEET_NAME`,
  `DEFAULT_TEMPLATE` (a blank fillable PDF next to the script), `cell_to_str()`,
  `load_column_map()`, `build_values_for_row()`, `fill_pdf()` (pypdf AcroForm fill, no
  reportlab overlay unless a real signature-image stamp is needed — none of the EHT
  forms have one), plus a CLI `main()` mirroring the others.
- Registered in `ELECTRICAL_EQUIPMENT_TYPES` (`electrical_data_access.py`):
  `{label, schema, export_module, key_field, summary_fields, summary_labels}`. Once
  registered, `ElectricalDashboardPage`/`ElectricalIndexPage`/`ElectricalEditDialog` in
  `gui_app.py` pick it up **automatically** — they're written generic over
  `ELECTRICAL_EQUIPMENT_TYPES`, so a 3rd equipment type needs no new GUI classes, only
  the schema/field-map/export trio + the template PDF + a registry entry.

**Standing safety rules — violating any of these is a regression, not a style choice:**
- Instrumentation (`da`/`Equipment_Inspection_Tracker.xlsx`) and Electrical
  (`eda`/`Electrical_Inspection_Tracker.xlsx`) must never read or write each other's
  workbook/registry. Grep for accidental `da.` vs `eda.` mixups before committing.
- `gui_app.py` never imports `openpyxl` directly — only `data_access.py` and
  `electrical_data_access.py` touch it.
- Never `ws.delete_rows()`/insert/reorder rows in any workbook. Clear cells in place
  instead (see the "Removing rows" comment in `data_access.py` for the exact reasoning:
  row-anchored data-validation/conditional-formatting ranges aren't reliably
  re-anchored by openpyxl on a shift).
- A new equipment type's blank template PDF is copied byte-for-byte via `shutil.copy2`
  (or written directly, for a brand-new template — see Phase B) — an export never opens
  the *live* tracker workbook for writing, only reads it.
- All tests use the `isolated_app_dir` pytest fixture (`conftest.py`) — tmp-dir copies
  only. Never touch the real checked-in `Equipment_Inspection_Tracker.xlsx` or
  `Electrical_Inspection_Tracker.xlsx` directly, even for "just a quick check" — this
  repo has twice had a stray real-file write from an ad-hoc verification script in
  earlier sessions; don't repeat it.
- Run the **full** test suite after every phase (`cd "Sensei_Index_X.X/Sensei Index
  X.X" && python -m pytest -q`) before committing. Commit and push each phase
  separately with a clear message (mirror the style of the existing git log — read
  `git log --oneline -20` for the established tone).
- Before calling any phase done, run an adversarial review pass (a workflow with 2-3
  independent reviewer dimensions + adversarial verification of their findings — this
  is exactly what the prior two sessions did for Phase 18 and the Electrical domain,
  and both times it caught real bugs that direct implementation missed). Fix confirmed
  findings, re-test, re-commit.

---

## Phase A — Rename "Sensei Index 1.9" → "Sensei Index 2.9"

Every occurrence found by `find . -iname "*1.9*"` and `grep -rn "1\.9"` (excluding
false-positive numeric matches like PDF coordinates, e.g. `export_to_pdf.py`'s
`"x=41.9-305.9"`):

1. **Folder rename**: `Sensei_Index_1.9/` → `Sensei_Index_2.9/`, and the inner
   `Sensei_Index_1.9/Sensei Index 1.9/` → `Sensei_Index_2.9/Sensei Index 2.9/`. Use
   `git mv` so history is preserved. Update every relative import/path assumption that
   depends on the folder name (there shouldn't be many — `HERE` is computed from
   `__file__`/`sys.executable`, not hardcoded, but double-check `pytest.ini`,
   `conftest.py`'s `APP_DIR` comment, and any CI/build scripts).
2. **`gui_app.py:36`**: `APP_TITLE = "Sensei Index"` — decide whether this becomes
   `"Sensei Index 2.9"` (shown in the OS window title bar) or stays bare with the
   version shown elsewhere. Recommend appending the version: `"Sensei Index 2.9"`.
3. **`gui_app.py:795`**: `title = QLabel("Sensei Index 1.9")` — the literal sidebar
   title text. Change to `"Sensei Index 2.9"`.
4. **The stale `.exe`**: `Sensei Index 1.9.exe` (98KB — clearly a placeholder/stub, not
   a real PyInstaller build) is tracked in git. Rename the file to `Sensei Index
   2.9.exe` for consistency, but **do not claim it was rebuilt** — actually rebuilding a
   working PyInstaller executable requires a Windows environment and is out of scope
   for a code-only session. Say so explicitly in the phase's commit message/summary so
   the user doesn't assume the .exe is now functional/updated.
5. **Do NOT touch**: the many `"Sensei Index 2.1, Phase N"` comments/docstrings
   scattered through `gui_app.py`/`data_access.py` (e.g. lines ~1152, 1654, 3869, 4458,
   4708). These are accurate **historical** annotations recording which spec phase
   introduced each function — they describe when something was built, not what version
   the app currently is. Rewriting them to "2.9" would make them factually wrong.
6. **Do NOT touch**: `_backup_before_datasheet_import_patch/`,
   `InstINDEX_Datasheet_Import_Patch/`, `InstINDEX_Datasheet_Import_Patch_v2/` — these
   are pre-existing, tracked, frozen historical patch/backup folders unrelated to the
   live app entry point. Renaming strings inside them would corrupt their own
   historical record for no benefit.
7. Update `README`-equivalent text if any exists (check repo root and the app folder
   for a README/CHANGELOG — none was found as of this writing, but check again since
   this phase may run after other changes land).
8. Add a test (or extend an existing one) asserting `gui_app.APP_TITLE` and the sidebar
   title string both contain "2.9", so a future accidental revert is caught.

**Acceptance**: `grep -rn "1\.9"` across the app folder returns only the deliberately
preserved historical Phase-comment references and the frozen patch folders — nothing
else. Full test suite passes.

---

## Phase B — New Electrical form: EHT & RTD Pre-Insulation Installation Report

### 2 things to get right immediately (both already confirmed by reading the source PDFs)

1. **This is a genuinely new, third form** — not a duplicate of `eht_rtd`. Its form
   number is **YCQE-EHT-004 Rev.0**, titled "EHT & RTD PRE-INSULATION INSTALLATION
   REPORT". This is *different* from `eht_rtd`'s form, YCQE-E&I-004 Rev.0, "EHT & RTD
   INSTALLATION INSPECTION REPORT" — similar name, different form number, and
   structurally much simpler (single pre-insulation section only, no post-insulation
   section, no megger-per-voltage checkbox grid — see the field list below).
2. **No blank fillable PDF exists for this form.** Every source page is a hand-filled,
   flatbed-scanned paper form (Sharp scanner output) — there is no AcroForm to extract
   field names from, unlike `eht_removal`/`eht_rtd`, which started from real fillable
   PDFs. **A new fillable AcroForm PDF template must be constructed from scratch** to
   match this form's layout, then a schema/field-map/export trio built against that
   template you just created (field names are therefore whatever you choose when you
   create the AcroForm fields — pick clear ones, e.g. `Trace #` → field name
   `trace_number`, no legacy `Text47`-style naming needed since there's no original to
   match).

### Source material (already committed in this repo)

`reference_material/EHT-004_scanned_samples/` — the two original scanned PDFs, 21
total pages:
- `Sharp_Scanner_20260908_122854.pdf` — 13 pages, all EHT-004 instances.
- `Sharp_Scanner_20260908_123001_1.pdf` — 8 pages: pages 1-2 are an `eht_removal`
  instance (already implemented — useful as a live cross-check sample against the
  existing `eht_removal_schema.py`/`eht_removal_field_map.py`, not something to
  re-implement), pages 3-8 are EHT-004 instances.

So: **19 real hand-filled EHT-004 instances** total across both files, all for the same
client engagement (COOEC Canada Ltd. / K1B Well Pad Project), all legible enough to
transcribe (see Phase D).

### Complete field transcription (verified against every one of the 19 instances — the
### layout is identical across all of them, only the handwritten values differ)

**Header** (static company/document chrome — Yanda logo top-left, COOEC Canada Company
Ltd. logo top-right, title + "YCQE-EHT-004 Rev.0" centered):

| Field | Notes |
|---|---|
| Customer Name | Printed as "COOEC Canada Ltd." on every instance — treat as a client-level default like the other EHT forms, but confirm whether to make it a real fillable field or static text (the other two EHT forms have this as static print text with no fillable field — match that precedent unless there's a reason not to). |
| Project Name | "K1B Well Pad Project" |
| Contract# | "CA23007-SCM-AGC-004" |
| Location | **"Module Yard"** — note this is a *different* default value than `eht_removal`/`eht_rtd`'s "K1B Well Pad" default. Use "Module Yard" as this form's own default, don't copy the other forms' value. |

**Trace Data** block (all real fillable fields, one value per instance):

| id (suggested) | label | notes |
|---|---|---|
| `trace_number` | Trace # | key field (equivalent to `eht_rtd`'s `trace_number`) |
| `eht_controller_number` | EHT Controller # | |
| `trace_part_number` | Trace Part # | |
| `panel_number` | Panel # | |
| `rtds_number` | RTD(s) # | |
| `circuit_number` | Circuit # | |
| `trace_line_number` | Trace Line # | note: this form has "Trace Line #" where `eht_rtd` has "Zone Drawing #" — don't conflate the two |
| `rev` | Rev # | |

**1.0 Pre-Insulation Inspection** — 10 numbered items, each with a "Results
(Initial/N/A)" cell (someone's initials, or "N/A" — plain text, not a checkbox, exactly
as `eht_rtd`'s equivalent "Results" cells are modeled: `ftype="text"`, or `"choice"`
with a permissive/free-entry convention if you want a dropdown-assist — match whatever
`eht_rtd_schema.py` did for its Y/N/NA cells) and a "Comments" cell (free text):

1. EHT Receiving Report has been Completed if required
2. EHT Tag Matches Part # and drawings
3. EHT is Routed and Installed as per specifications
4. RTD's Receiving Report has been Completed if required
5. RTD's are installed as per drawing and specification
6. EHT/RTD's Tags are correctly labelled and installed
7. As-built drawings completed and submitted
8. Terminations are complete with correct wire tags
9. SR/MI Trace Continuity test passed (Record Resistance)
10. EHT/RTD's Released for Insulation

(id convention: `pre_ins_item_N_result` / `pre_ins_item_N_comments`, N=1..10 — mirror
`eht_rtd_schema.py`'s existing `pre_ins_item_1_1_result` naming style closely enough
that the two schemas read consistently side by side, but don't literally reuse "1.1"
numbering since this form's items are numbered 1-10 flat, not 1.1-1.10 like `eht_rtd`.)

**Insulation Testing Equipment**:

| id | label |
|---|---|
| `test_equip_model` | Test Equip. Model # |
| `test_equip_serial` | Test Equip. Serial # |
| `cal_due_date` | Cal. Due Date |

Then a 3-row table (the source document labels this row "1.8 Pre-Insulation Insulation
Test Results" — **a real duplicate of item 1.8's number from the checklist above; this
is a genuine quirk in the client's own form, preserve it as-is in the template, don't
"fix" the numbering**):

| id | label |
|---|---|
| `megger_500_reading` | SR/MI @ 500 VDC — Reading |
| `megger_500_result` | SR/MI @ 500 VDC — (Passed/Fail) |
| `megger_1000_reading` | SR/MI @ 1000 VDC — Reading |
| `megger_1000_result` | SR/MI @ 1000 VDC — (Passed/Fail) |
| `megger_2500_reading` | SR/MI @ 2500 VDC — Reading |
| `megger_2500_result` | SR/MI @ 2500 VDC — (Passed/Fail) |

**Comments**: one multiline field, `comments`.

**Sign-off**:

| id | label |
|---|---|
| `yanda_rep_date` | Yanda Representative — Date (yy/mm/dd) |
| `yanda_rep_signature` | Yanda Representative — Signature *(hand-signed only if no fillable field is built for it — decide when building the template; note the source form has no separate "Print Name" cell for either rep on this particular form, unlike the sign-off blocks on `eht_removal`/`eht_rtd` which do — don't invent one)* |
| `client_rep_date` | Client Representative — Date (yy/mm/dd) |
| `client_rep_signature` | Client Representative — Signature |

**Footer** (present on every instance, bottom-right corner, static text — reproduce
exactly): `YCQE-EHT-003 Rev.0` / `04/06/2026`. **This is a real inconsistency in the
client's own document** — the header says the form is "YCQE-EHT-004 Rev.0" but the
footer stamp says "YCQE-EHT-003 Rev.0". Preserve this exactly as printed on the
original; do not "correct" it to match the header. It's the client's document, not
ours to fix.

**Total field count**: 4 header + 8 trace data + 20 checklist (10 × 2) + 3 equipment
info + 6 megger fields + 1 comments + 4 sign-off = **46 fields**.

### Building the template

The user was explicit about this: *"when creating the template make sure its empty and
polish up as in make it look like the original document, BUT THE SAME FORMAT SAME
IMAGE, SAME FONT IS THE SAME JUST THE ALIGNMENT AND QUALITY LIKE AN ORIGINAL
TEMPLATE."*

Read that as: **do not redesign this form.** Reproduce the scanned layout faithfully —
same table structure, same column widths/proportions, same section order, same header
logos (extract the Yanda and COOEC logos from the scan, or reuse
`assets/oathplatehelm.png`/`oathplatehelm2.png` if those are in fact the same Yanda
mark already used elsewhere in the app — check before assuming), same font family/size
relationships (a plain sans-serif, bold section headers, matching the visual weight of
the scan). The *only* improvement over the scan is what a clean vector/digital
original naturally gives you over a photocopied-and-rescanned paper form: crisp
straight lines, evenly-spaced rows, no skew, no scanner noise/artifacts, precise
alignment — i.e. what the document would have looked like if it were the original
Word/Excel master, not a 10th-generation photocopy. Then make every one of the 46
fields above a real, empty, fillable AcroForm text/choice field at the correct
position, using reportlab to draw the static layout and pypdf (or a library capable of
adding real `/Widget` annotations) to place the fields — this is the same general
approach `build_pdf_template.py`/`build_excel_log.py` are referenced as having used for
the *original* Transmitter/Valve templates (those scripts aren't in this repo — they
were external, one-time tooling — so there's no existing generator to reuse; build this
one directly with reportlab + pypdf's low-level field-creation API, or an equivalent).

Save as `EHT_and_RTD_Pre-Insulation_Installation_Report_TEMPLATE.pdf` next to the other
two EHT template PDFs (same directory as `gui_app.py`).

**Verify the template you built** by loading it back with `pypdf.PdfReader(...).get_fields()`
and confirming: 46 real fields, all currently blank (`/V` is `None`/empty for every
one), no accidental sample data baked in (this bit the prior session once already, for
a different form — see `eht_rtd_field_map.py`'s docstring for what that looked like and
how it was verified safe).

### Code (mirror `eht_rtd_schema.py`/`eht_rtd_field_map.py`/`export_eht_rtd_to_pdf.py` exactly)

- `eht_pre_insulation_schema.py` — the 46 fields above, `SECTION_TITLES` (suggest:
  `header`, `trace_data`, `pre_insulation`, `equipment`, `comments`, `signoff`).
- `eht_pre_insulation_field_map.py` — `FIELD_MAP` (every id → the real field name you
  chose when building the template above — should be a clean 1:1 map, no legacy
  `Text##`-style names to reverse-engineer since you control the naming this time).
- `export_eht_pre_insulation_to_pdf.py` — same shape as the other two export modules.
  `SHEET_NAME = "EHT PreIns Log"`.
- Register in `electrical_data_access.py`'s `ELECTRICAL_EQUIPMENT_TYPES`:
  ```python
  "eht_pre_insulation": {
      "label": "EHT & RTD Pre-Insulation Installation",
      "schema": eht_pre_insulation_schema,
      "export_module": export_eht_pre_insulation_to_pdf,
      "key_field": "trace_number",
      "summary_fields": ["trace_number", "eht_controller_number", "panel_number"],
      "summary_labels": ["Trace #", "EHT Controller #", "Panel #"],
  },
  ```
  Also add `"eht_pre_insulation": "EHT PreIns"` to `SHEET_NAME_PREFIXES` (needs to be
  short enough that `SHEET_NAME_PREFIXES[key] + " - " + zone_name[:budget]` stays under
  Excel's 31-char sheet-name limit with a reasonable amount of room for the zone name —
  "EHT PreIns" is 10 chars, leaving 18 for the zone name after the " - " separator,
  comparable to the existing two).
- Add `import eht_pre_insulation_schema` / `import export_eht_pre_insulation_to_pdf` to
  `electrical_data_access.py`'s imports.

**No GUI code changes should be needed** beyond those two additions —
`ElectricalDashboardPage`/`ElectricalIndexPage`/`ElectricalEditDialog` iterate
`ELECTRICAL_EQUIPMENT_TYPES` generically. If you find yourself needing to touch
`gui_app.py` for this, that's a signal something in the generic design broke — figure
out why before working around it, don't special-case the new type in the GUI layer.

### Tests

Mirror `tests/test_electrical_data_access.py`/`tests/test_electrical_gui.py`'s existing
coverage shape for this third type: zone creation includes the new sheet, save/read
round-trip, PDF export produces a real filled PDF with the right field values, the new
type shows up correctly in `ElectricalDashboardPage`/`ElectricalIndexPage`. Also add a
dedicated **field-mapping fidelity check** analogous to what the prior session did for
`eht_removal`/`eht_rtd`: programmatically confirm every schema field has an entry in
`FIELD_MAP`, and every field name referenced by `FIELD_MAP` actually exists in the
template PDF's `get_fields()` output (load the template you built and assert on it
directly — this is the check that would catch a typo in a hand-chosen field name, since
there's no "original file's real widget names" cross-reference to lean on for a
from-scratch template the way there was for the other two forms).

---

## Phase C — Proper loading/splash screen

Current state: `main()` in `gui_app.py` does `app = QApplication(...)`, applies the
theme stylesheet, constructs `MainWindow()`, calls `.show()`. `MainWindow.__init__`
does real work during construction (rebuilding the sidebar tree, which calls into
`da.list_series()`/`eda.list_zones()`, which lazily load both workbooks) with no visual
feedback before the window appears — on a slow disk or a large workbook this can leave
the user looking at nothing for a moment. The user explicitly said: *"i need a proper
loading screen not just a terminal prompt... with the same logo enlarged."*

Build a real Qt splash screen, shown before `MainWindow` is constructed:

- A `QSplashScreen` (simplest, built-in progress-message support via
  `showMessage()`) or a custom frameless `QWidget` (`Qt.SplashScreen` window flag) if
  you want more layout control than `QSplashScreen`'s single-pixmap-plus-text model
  gives you — either is acceptable, prefer whichever makes the enlarged-logo-plus-
  status-text layout cleanest.
- **The same logo already used in the sidebar** (`assets/oathplatehelm.png` /
  `oathplatehelm2.png`, theme-aware — reuse `MainWindow._set_logo_pixmap`'s
  light/dark selection logic), scaled up significantly larger than its sidebar size
  (that logo is scaled to 42px there; something in the 160–220px range reads as a
  proper splash, not a stretched sidebar icon — use a high-res source if the checked-in
  PNGs support it without visible pixelation, otherwise scale from whichever gives the
  best result).
- **Real status updates tied to actual startup steps**, not decorative/fake progress —
  e.g. "Loading Instrumentation data…", "Loading Electrical data…", "Building
  interface…", "Ready" — each shown via `splash.showMessage(...)` (or your custom
  widget's equivalent) immediately before the corresponding real step runs, with
  `app.processEvents()` called after each update so the splash actually repaints before
  the next (potentially blocking) step executes. Don't fabricate a percentage bar with
  no real basis — if you add a progress bar, drive it from the actual number of
  startup steps completed, not a timer.
- Should display "Sensei Index 2.9" (the version decided in §0) somewhere on the splash.
- Closes (`splash.finish(win)` for `QSplashScreen`, or the equivalent close+deleteLater
  for a custom widget) right after `MainWindow` is constructed and shown, so it's never
  left as a lingering window.
- Must survive `QT_QPA_PLATFORM=offscreen` in the test suite without hanging or
  erroring — a splash screen that blocks on user input, or that never closes without a
  real display, would break every existing GUI test that constructs `MainWindow`. Test
  this explicitly (construct `MainWindow` under `qtbot` the same way the existing tests
  do, and confirm it completes normally).

Add a small test confirming the splash shows the enlarged logo and status text updates
happen in the expected order (mock/spy `showMessage`, or check the pixmap size, per
whichever implementation you choose).

---

## Phase D — Reference transcription folder ("hand filled in sheets")

The user's own words: *"make a completely separate sheet with the HAND FILLED IN
sheets that i just provided to you as a separate folder so i can copy and paste those,
i am doing this to ensure whatever you scan is entirely correct and not a misread."*

This is **not** data that goes into the live `Electrical_Inspection_Tracker.xlsx` — it
is a standalone verification artifact, kept completely separate, whose only purpose is
letting the user manually cross-check that a future automated read of these same scans
(or the general reliability of scan-to-data transcription in this app) is accurate.
Treat it as read-only reference material forever, never auto-imported anywhere.

**What to produce**: a new `.xlsx` workbook (suggest:
`reference_material/EHT-004_scanned_samples/EHT-004_Hand_Filled_Reference.xlsx`, next
to the two source PDFs already committed in this repo) with **one row per scanned page
instance** (19 rows for the EHT-004 form; optionally a second sheet with the 1
`eht_removal` instance from `Sharp_Scanner_20260908_123001_1.pdf` pages 1-2 too, since
it's real filled sample data for an already-implemented form and costs nothing extra to
include), one column per field from the Phase B field list above, plus a `source_pdf`
and `source_page` column recording exactly which file/page each row came from so a
value can always be traced back to the original scan.

**Transcription process — read every value directly from the two PDFs in
`reference_material/EHT-004_scanned_samples/`, do not skip this by assuming defaults.**
Given the entire point of this file is catching misreads, transcribe carefully:

1. Read each page at full resolution.
2. Transcribe every field exactly as written — if handwriting is genuinely ambiguous
   (several instances have hard-to-read resistance values or initials), record your
   best reading AND flag it (e.g. a `_uncertain` suffix column, or a highlighted cell)
   rather than silently guessing. A flagged uncertain reading is far more useful to the
   user than a confident-looking wrong one — the whole point of this file is to catch
   exactly that failure mode.
3. If you have the means to run this as two independent passes (e.g. two separate
   agent reads of the same page) and reconcile disagreements, do that — it directly
   matches the user's stated goal ("ensure whatever you scan is entirely correct") and
   is cheap insurance against a single mis-read propagating uncaught.
4. Preserve the "Trace Data" values verbatim, including hyphens/slashes as written
   (these are structured tag-like identifiers, e.g. `29103-ET-PE1701-2-2` — transcribe
   exactly, don't normalize casing or spacing).

Do not attempt this transcription by re-deriving it from a written description in this
document — go back to the actual PDF pages every time; a paraphrase risks losing
precision this specific task depends on.

---

## Verification checklist (all phases)

- [ ] `grep -rn "1\.9"` in the app folder shows only the deliberately-preserved
      historical Phase-comments and frozen patch folders.
- [ ] App window title and sidebar both show "Sensei Index 2.9" (or 2.5, if §0 was
      resolved that way).
- [ ] `eht_pre_insulation` is a fully working third Electrical equipment type: add a
      zone, add/edit/remove a row, export to PDF, all through the real GUI (not just
      the data layer) — mirror the smoke-test rigor the prior session used for
      `eht_removal`/`eht_rtd`.
- [ ] The new template PDF has all 46 fields, none corrupted/mis-positioned, verified
      by loading it back with `pypdf` and by visually reviewing a filled sample.
- [ ] A splash screen with the enlarged logo appears at startup with real status
      updates, and closes cleanly; the full test suite still passes headless.
- [ ] `reference_material/EHT-004_scanned_samples/EHT-004_Hand_Filled_Reference.xlsx`
      exists with one row per real scanned instance, every field transcribed, any
      genuinely ambiguous reading flagged rather than guessed.
- [ ] Full test suite passes (`python -m pytest -q` from the app directory).
- [ ] Zero changes to Instrumentation's `data_access.py`/`Equipment_Inspection_Tracker.xlsx`
      behavior, and zero changes to the two already-working Electrical forms'
      schema/field-map/export files, except the version-string rename in Phase A.
- [ ] An adversarial review pass was run on the diff before considering any phase done,
      and its confirmed findings were fixed (see "Standing safety rules" above).
- [ ] Each phase committed and pushed separately, with commit messages in the
      established style (read recent `git log` for tone/format before writing yours).
