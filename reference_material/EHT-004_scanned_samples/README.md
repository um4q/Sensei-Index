# EHT-004 scanned samples — reference material

This folder is a **standalone verification artifact**. Nothing here is ever
read by the live app (Sensei_Index_2.9/), and nothing here is ever imported
into `Electrical_Inspection_Tracker.xlsx`. It exists purely so a human can
manually cross-check the app's understanding of the EHT & RTD Pre-Insulation
Installation Report form (YCQE-EHT-004 Rev.0) against the real, hand-filled
scans it was built from — per the user's own request: *"i am doing this to
ensure whatever you scan is entirely correct and not a misread."*

## Files

- **`Sharp_Scanner_20260908_122854.pdf`**, **`Sharp_Scanner_20260908_123001_1.pdf`**
  — the two original scanned PDFs (21 pages total). 19 pages are EHT-004
  instances; `Sharp_Scanner_20260908_123001_1.pdf` pages 1-2 are an
  `eht_removal` instance (already implemented separately, not part of this
  transcription).
- **`EHT-004_Hand_Filled_Reference.xlsx`** — one row per scanned EHT-004
  instance (19 rows), one column per field on the form, plus `Source PDF`/
  `Source Page` columns tracing every value back to its exact scan and page.
  Each of the 19 instances was read independently **twice** (two separate
  passes, each blind to the other), then reconciled field-by-field. Any
  field where the two passes disagreed, or where either pass flagged its own
  reading as uncertain (messy handwriting, smudged ink, a scratched-out
  value), is:
  - listed in that row's **"Flagged / Uncertain Fields"** column,
  - highlighted (yellow row fill),
  - and — if the two passes actually gave different text — the second
    pass's alternate reading is recorded in the **"Pass-2 Alternate
    Reading"** column, so nothing is silently thrown away.

  **Use this to manually verify the transcription is correct** — the
  highlighted rows/columns are exactly the ones worth double-checking
  against the original PDF by eye first.
- **`eht004_transcribed_rows.json`** — the raw, structured transcription
  data the spreadsheet above was generated from (one independent read pass
  1 + read pass 2 + reconciliation, produced by a background Workflow run).
  Kept so the spreadsheet can be regenerated (or restyled) without redoing
  the transcription itself.
- **`build_eht004_reference_workbook.py`** — the generator script:
  ```
  python3 build_eht004_reference_workbook.py eht004_transcribed_rows.json EHT-004_Hand_Filled_Reference.xlsx
  ```

## Provenance

Transcription was done by two fully independent read passes over all 19
page instances (each a separate agent call, neither seeing the other's
answer), followed by a field-by-field reconciliation pass. 136 individual
field values across the 19 instances were flagged as uncertain or
disagreeing between the two passes — see the spreadsheet's highlighted
rows. This is a deliberately conservative process: when in doubt, a field
is flagged rather than silently resolved one way or the other.
