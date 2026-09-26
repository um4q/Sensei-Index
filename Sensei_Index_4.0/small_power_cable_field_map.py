# -*- coding: utf-8 -*-
"""
Maps each small_power_cable_schema.py field id to the actual AcroForm
field name inside
Small_Power_and_Control_Cable_Inspection_and_Test_Record_TEMPLATE.pdf.

This template is built directly from the user's own real, official source
PDF (YCQE-EI-113 Rev.0) - not reconstructed from a hand-filled scan. That
source PDF already had its own correctly-positioned AcroForm fields (one
per fillable cell, authored by whoever built the original Word/PDF form),
so the build step that produced this template does no whiteout and draws
no new fields at all: it takes the real PDF byte-for-byte and only
renames each field's internal /T name to this schema's own id - so this
is an identity mapping below, same shape every other Electrical form's
field_map.py uses.

Every field is a plain text widget - no checkbox/multi-widget special
cases (the "Initial /NA" verification columns don't exist as checkboxes
on this form; every cell here really is free text on the real source
PDF).
"""

FIELD_MAP = {f["id"]: f["id"] for f in __import__("small_power_cable_schema").FIELDS}
# "location" is the one schema id that does NOT match its real PDF field
# name - Project/Job No were left with their original real names since
# they're not modeled as schema fields at all (see the schema's own
# docstring), but Location IS a real per-row field, and its real PDF field
# name kept its original capitalization ("Location") rather than being
# renamed to match every other (already-lowercase) field id.
FIELD_MAP["location"] = "Location"

YES_NO_CHECKBOXES = {}

# No signature field exists on the real PDF for either representative -
# hand-sign both after exporting, same convention transformer_test's own
# client_rep_signature already uses.
UNMAPPED_NOTE = (
    "Both Yanda Representative and Client Representative signatures have "
    "no digital field on the real source PDF - hand-sign those after "
    "exporting."
)
