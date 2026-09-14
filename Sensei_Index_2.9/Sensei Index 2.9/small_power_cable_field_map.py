# -*- coding: utf-8 -*-
"""
Maps each small_power_cable_schema.py field id to the actual AcroForm
field name inside Small_Power_and_Control_Cable_Inspection_and_Test_Record_
TEMPLATE.pdf.

REVISION 2: this template is now built directly from the user's own real,
official source PDF (YCQE-EI-113 Rev.0) - not reconstructed from a
hand-filled scan. That source PDF already had its own correctly-positioned
AcroForm fields (41 of them - one per fillable cell, authored by whoever
built the original Word/PDF form), so build_small_power_cable_template.py
does no whiteout for those: it takes the real PDF byte-for-byte and only
renames each field's internal /T name to this schema's own id (an
identity mapping below, same shape every other Electrical form's
field_map.py already uses) - see that script's own docstring for the
exact rename table.

REVISION 3: yanda_rep_signature/client_rep_signature added. The real PDF
still has no signature field of its own for either representative - only
a printed "Signature:" label and blank line - but build_small_power_cable
_template.py now merges 2 brand new fields on top of those 2 blank lines
(same merge-overlay technique transformer_test/general_equip_install use
for forms whose real source has no fields at all, just applied here to 2
specific cells on a source that otherwise already had its own 41). Both
new ids map to themselves too, same identity shape as every other field.

Every field is a plain text widget - no checkbox/ATC/multi-widget special
cases (the "Initial /NA" verification columns and "TORQUE MARKED"-style
Yes checkboxes some other forms have don't exist on this one; every cell
here really is free text on the real source PDF).
"""

import small_power_cable_schema

FIELD_MAP = {f["id"]: f["id"] for f in small_power_cable_schema.FIELDS}
# "location" is the one schema id that does NOT match its real PDF field
# name - Project/Job No were left with their original real names since
# they're not modeled as schema fields at all (see the schema's own
# docstring), but Location IS a real per-row field, and its real PDF field
# name kept its original capitalization ("Location") rather than being
# renamed to match every other (already-lowercase) field id.
FIELD_MAP["location"] = "Location"

YES_NO_CHECKBOXES = {}

# Nothing unmapped - yanda_rep_signature/client_rep_signature are new
# fields merged onto the real PDF (see this module's own docstring,
# REVISION 3), not hand-signed-only fields with no backing field at all.
UNMAPPED_NOTE = None
