# -*- coding: utf-8 -*-
"""
Reads CNOOC/Oilsands-style engineering "DS-" data sheets (the two-page-per-
instrument PDFs with a numbered-row layout: Control Valve, Temp Trans
Element and Thermowell, Vortex Flowmeter) and pulls out the subset of
fields that map onto InstINDEX's own Add New form, so a new row can be
opened pre-filled instead of retyped by hand.

This is intentionally NOT a general-purpose PDF form reader. It only
recognizes the three datasheet layouts above (detected from their own
title block text) and only extracts fields InstINDEX actually has a
column for. Everything else on the datasheet - dimensions, materials,
test requirements, the full notes page, and so on - stays exactly where
it already is: on the datasheet PDF itself, unchanged, one click away for
anyone who needs the full spec. Fields it can't confidently find, or that
come back looking corrupted by the PDF text extractor, are left blank
rather than shown wrong, the same "leave it blank unless it's actually
known" rule the rest of the app follows for dates.

Every field is found by its (row number, label text) pair together, never
either alone - e.g. row 62's "Model No." on a valve sheet is the
Actuator's, but row 63's "Model No." on a transmitter sheet is the
Purchase section's. Requiring both to match directly avoids the earlier,
much simpler version of this reader accidentally treating an ordinary
numeric VALUE ("88", "316", "3 in") as if it were a row marker.

Two fields are a judgment call rather than a direct read, because the
datasheet's own vocabulary doesn't map onto InstINDEX's fixed pick-lists
one-to-one: `signal_type` (guessed from whether "HART" appears anywhere on
the sheet) and, for valves, `valve_type` (guessed from the tag prefix -
LV/FV/PV/XV - against ESDV/FCV/LCV/PCV). Both come back tagged in
`guessed` on the returned record so the calling UI can flag them for a
second look. `System` / `System Number` is deliberately NOT guessed at
all - the datasheet's fluid/service wording doesn't map onto the existing
System pick-list reliably enough to auto-fill safely, so that field is
always left for a human to set.

Public API:
    read_datasheet_pdf(path) -> list[DatasheetRecord]
    read_datasheet_pdfs(paths) -> list[DatasheetRecord]

DatasheetRecord is a plain dict:
    {
        "equip_key": "valve" | "transmitter",
        "tag": "29103-LV-0957",
        "doc_no": "DS-29103-LV-0957",
        "kind_label": "Control Valve" | "Temperature Transmitter" | "Vortex Flowmeter",
        "area_code": "29103",            # leading digits of the tag, for series matching
        "fields": {schema_field_id: value, ...},   # ready for EditDialog(prefill=...)
        "guessed": {field_id: True, ...},          # which of the above were inferred, not read
        "source_file": "/path/to/file.pdf",
        "source_page": 0,                # 0-based index of the page the data table was on
    }
"""
import re
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - pypdf is already a hard dependency of the app
    PdfReader = None


def _page_texts(pdf_path):
    reader = PdfReader(str(pdf_path))
    texts = []
    for page in reader.pages:
        try:
            texts.append(page.extract_text(extraction_mode="layout") or "")
        except Exception:
            texts.append(page.extract_text() or "")
    return texts


def _detect_kind(text):
    t = text.upper()
    if "CONTROL VALVE" in t:
        return "valve"
    if "VORTEX FLOWMETER" in t or "VORTEX FLOW METER" in t:
        return "fit"
    if "TEMP TRANS ELEMENT" in t or "TEMP TRANS" in t or "THERMOWELL" in t:
        return "tit"
    return None


_KIND_LABELS = {
    "valve": "Control Valve",
    "fit": "Vortex Flowmeter",
    "tit": "Temperature Transmitter",
}


def _row_label_value(text, row_num, label, stop_text=None):
    """Finds ROW_NUM immediately followed by LABEL (the row number and the
    label text have to be adjacent - this is what makes it safe against
    ordinary numeric values elsewhere on the line being mistaken for a row
    marker) and returns whatever comes after the label, up to `stop_text`
    if given and found (the start of the label sharing that physical line
    in the other column), otherwise up to a generic "<number> <Title Case
    word>" boundary, otherwise the rest of the line. A plain automatic
    boundary can't be made airtight on its own - some VALUES look exactly
    like a small row number followed by a capitalized word too (e.g.
    "316 SS/Stellite") - so any field that's actually run into that is
    given its known neighbor's label explicitly instead of relying on the
    generic guess."""
    pattern = re.compile(
        r"(?<!\d)" + re.escape(str(row_num)) + r"\s+" + re.escape(label) + r"(.*)",
        re.MULTILINE,
    )
    m = pattern.search(text)
    if not m:
        return ""
    val = m.group(1).split("\n")[0]
    if stop_text:
        idx = val.find(stop_text)
        if idx != -1:
            val = val[:idx]
    else:
        m2 = re.search(r"\s{4,}\d{1,3}\s+[A-Z]", val)
        if m2:
            val = val[:m2.start()]
    return val.strip(" .:\t")


def _first_segment(text):
    parts = re.split(r"\s{2,}", text.strip())
    return parts[0].strip() if parts and parts[0].strip() else ""


def _extract_tag(value_text):
    """Tolerant of the tag prefix and sequence number being printed in
    separate boxes with a couple of spaces between them
    ("29103-LV  -0957"), which a plain 2-space split would cut in half."""
    m = re.match(r"\s*(\S+)(?:\s{1,3}(-\d\S*))?", value_text)
    if not m:
        return ""
    return m.group(1) + (m.group(2) or "")


def _extract_range(value_text):
    """Range-style values ("0 to 100 m3/h @flow") are printed with wide,
    irregular internal spacing for visual alignment, which makes a plain
    "split on 2+ spaces" wrongly treat the value as several separate
    fields. This looks for the specific "NUMBER [to NUMBER] [unit]" shape
    directly, tolerating any amount of internal whitespace."""
    m = re.match(
        r"\s*(-?[\d.]+)\s*(?:to\s*(-?[\d.]+))?\s*((?:[^\s]+\s*){0,4}?)(?=\s{4,}|$)",
        value_text,
    )
    if not m or not m.group(1):
        return ""
    lo, hi, unit = m.group(1), m.group(2), (m.group(3) or "").strip()
    if hi:
        return f"{lo} to {hi}" + (f" {unit}" if unit else "")
    return lo + (f" {unit}" if unit else "")


def _looks_garbled(value):
    if not value:
        return False
    return bool(re.match(r"^to-?\d", value.strip(), re.IGNORECASE))


def _fix_hyphen_spacing(tag):
    return re.sub(r"\s+-", "-", tag or "").strip()


def _doc_no(text):
    m = re.search(r"DS-[\w-]+", text)
    return m.group(0) if m else ""


def _area_code(tag):
    m = re.match(r"(\d+)", tag or "")
    return m.group(1) if m else ""


def _extract_common(text):
    tag = _fix_hyphen_spacing(_extract_tag(_row_label_value(text, 1, "Tag No.")))
    pid = _first_segment(_row_label_value(text, 2, "P&ID No."))
    service = _first_segment(_row_label_value(text, 3, "Service"))
    line_no = _first_segment(_row_label_value(text, 5, "Line No."))
    if not line_no:
        # On some sheets row 5's own number gets separated from "Line No."
        # by an unusually wide gap (typically when the row's paired
        # right-column field is blank) - the label text itself is still
        # there and still unambiguous, just not adjacent to its row
        # number anymore, so fall back to finding it directly.
        m = re.search(r"Line No\.(\S.*)", text)
        if m:
            line_no = _first_segment(m.group(1))
    return tag, pid, service, line_no


def _extract_valve(text, doc_no):
    tag, pid, service, line_no = _extract_common(text)

    row50 = _row_label_value(text, 50, "Size", stop_text="ANSI / FCI Leakage Class")
    travel_nums = re.findall(r"(-?\d+(?:\.\d+)?)\s*in\b", row50)
    travel_value = travel_nums[-1] if travel_nums else ""

    trim_plug = _first_segment(_row_label_value(text, 55, "Plug / Ball / Disk Material"))
    trim_seat = _first_segment(_row_label_value(text, 56, "Seat Material",
                                                 stop_text="Coil Rating / Power Supply"))

    ansi_line = _first_segment(_row_label_value(text, 36, "ANSI Class"))
    ansi_m = re.search(r"\d+", ansi_line)
    ansi_rating = ansi_m.group(0) if ansi_m else ""

    leak_value = _first_segment(_row_label_value(text, 95, "ANSI / FCI Leakage Class"))
    leak_m = re.search(r"\b(VI|IV|V|III|II|I)\b", leak_value)
    valve_class = leak_m.group(1) if leak_m else ""

    end_line = _row_label_value(text, 40, "End").upper()
    if "FLG" in end_line or "FLANGE" in end_line:
        body_style = "Flanged"
    elif "NPT" in end_line or "THRD" in end_line or "THREAD" in end_line:
        body_style = "Threaded"
    else:
        body_style = ""

    actuator_val = _row_label_value(text, 62, "Model No.", stop_text="P.O. No.")
    actuator_m = re.search(r"Type\s+(\S+)", actuator_val)
    actuator_model = actuator_m.group(1) if actuator_m else ""

    positioner_val = _row_label_value(text, 76, "Model No.")
    positioner_m = re.search(r"Type\s+(\S+)", positioner_val)
    positioner_model = positioner_m.group(1) if positioner_m else ""

    has_hart = "HART" in text.upper() or "SMART" in text.upper()
    signal_type = "4-20 mA / HART" if has_hart else ""

    valve_type_map = {"LV": "LCV", "FV": "FCV", "PV": "PCV", "XV": "ESDV", "KV": "ESDV"}
    prefix_m = re.search(r"-([A-Z]{2})-\d", tag)
    valve_type = valve_type_map.get(prefix_m.group(1), "") if prefix_m else ""

    fields = {
        "equip_number": tag,
        "pid_number": pid,
        "line_number": line_no,
        "service": service,
        "actuator_model": actuator_model,
        "positioner_model": positioner_model,
        "trim_plug": trim_plug,
        "trim_seat": trim_seat,
        "travel_unit": "Inch" if travel_value else "",
        "travel_value": travel_value,
        "ansi_rating": ansi_rating,
        "valve_class": valve_class,
        "body_style": body_style,
        "signal_type": signal_type,
        "valve_type": valve_type,
        "comments": f"See engineering datasheet {doc_no} for full spec." if doc_no else "",
    }
    guessed = {"valve_type": True, "signal_type": True}
    return tag, fields, guessed


def _extract_transmitter(text, kind, doc_no):
    tag, pid, service, line_no = _extract_common(text)

    make = _first_segment(_row_label_value(text, 62, "Manufacturer"))
    model = _first_segment(_row_label_value(text, 63, "Model No."))

    if kind == "tit":
        transmitter_type = "Temperature Transmitter"
        cal_range = _extract_range(_row_label_value(text, 24, "Calibrated Range"))
        inst_range = _extract_range(_row_label_value(text, 23, "Instrument Range"))
        local_display = "Yes" if "LCD Display" in text or "Integral Meter" in text else ""
    else:
        transmitter_type = "Vortex Flow Meter"
        cal_range = _extract_range(_row_label_value(text, 32, "Calibrated Instrument Range"))
        inst_range = _extract_range(_row_label_value(text, 31, "Instrument Range or Element Range"))
        local_display = ""

    if _looks_garbled(cal_range):
        cal_range = ""
    if _looks_garbled(inst_range):
        inst_range = ""

    signal_type = "4-20 mA / HART" if "HART" in text.upper() else ""

    fields = {
        "tag": tag,
        "pid_number": pid,
        "line_number": line_no,
        "service": service,
        "transmitter_type": transmitter_type,
        "make": make,
        "model": model,
        "calibration_range": cal_range,
        "instrument_range": inst_range,
        "local_display": local_display,
        "signal_type": signal_type,
        "remarks": f"See engineering datasheet {doc_no} for full spec." if doc_no else "",
    }
    guessed = {"signal_type": True}
    return tag, fields, guessed


def read_datasheet_pdf(path):
    if PdfReader is None:
        raise RuntimeError("pypdf is required to read datasheet PDFs.")
    path = Path(path)
    pages = _page_texts(path)
    records = []
    for i, text in enumerate(pages):
        kind = _detect_kind(text)
        if kind is None:
            continue
        if not re.search(r"(?<!\d)1\s+Tag No\.", text):
            continue  # the notes page repeats the title block but has no data table
        doc_no = _doc_no(text)
        if kind == "valve":
            tag, fields, guessed = _extract_valve(text, doc_no)
            equip_key = "valve"
            kind_label = _KIND_LABELS["valve"]
        else:
            tag, fields, guessed = _extract_transmitter(text, kind, doc_no)
            equip_key = "transmitter"
            kind_label = _KIND_LABELS[kind]
        if not tag:
            continue
        records.append({
            "equip_key": equip_key,
            "tag": tag,
            "doc_no": doc_no,
            "kind_label": kind_label,
            "area_code": _area_code(tag),
            "fields": fields,
            "guessed": guessed,
            "source_file": str(path),
            "source_page": i,
        })
    return records


def read_datasheet_pdfs(paths):
    all_records = []
    for p in paths:
        try:
            all_records.extend(read_datasheet_pdf(p))
        except Exception:
            continue
    return all_records


if __name__ == "__main__":
    import sys
    import json
    for p in sys.argv[1:]:
        for rec in read_datasheet_pdf(p):
            print(json.dumps(rec, indent=2, ensure_ascii=False))
