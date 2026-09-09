# -*- coding: utf-8 -*-
"""
Reads CNOOC/Oilsands-style engineering "DS-" data sheets (the two-page-per-
instrument PDFs with a numbered-row layout) and pulls out the subset of
fields that map onto InstINDEX's own Add New form, so a new row can be
opened pre-filled instead of retyped by hand.

Recognized datasheet types, detected from each sheet's own title block:
    Valves:
        Control Valve                (LV, PV, FV, ...)
        On/Off Valve                 (XV, KV, ... - with or without a
                                       Positioner section)
    Transmitters:
        Temp Trans Element and TW    (TIT)
        Vortex Flowmeter             (FIT)
        Pressure Transmitter         (PIT)
        Guided Wave Radar Level Xmtr (LIT)

This is intentionally NOT a general-purpose PDF form reader. It only
recognizes the layouts above and only extracts fields InstINDEX actually
has a column for. Everything else on the datasheet - dimensions,
materials, test requirements, the full notes page, and so on - stays
exactly where it already is: on the datasheet PDF itself, unchanged, one
click away for anyone who needs the full spec. Fields it can't
confidently find, or that come back looking corrupted by the PDF text
extractor, are left blank rather than shown wrong, the same "leave it
blank unless it's actually known" rule the rest of the app follows for
dates.

Fields are found by (row number, label text) together, never either
alone - e.g. row 62's "Model No." on a Control Valve sheet is the
Actuator's, but row 63's "Model No." on a transmitter sheet is the
Purchase section's. Requiring both avoids mistaking an ordinary numeric
VALUE ("88", "316", "3 in") for a row marker. The On/Off Valve family
specifically doesn't keep a perfectly fixed row numbering even between
two examples of its own template (an extra or missing line upstream
shifts everything below it by one row), so those fields are matched
against a small tolerant row range instead of one exact number - see
_label_value_in_range.

Two fields are a judgment call rather than a direct read, because the
datasheet's own vocabulary doesn't map onto InstINDEX's fixed pick-lists
one-to-one: `signal_type` (guessed from whether "HART" appears anywhere on
the sheet) and, for valves, `valve_type` (guessed from the tag prefix -
LV/FV/PV/XV/KV - against ESDV/FCV/LCV/PCV). Both come back tagged in
`guessed` on the returned record so the calling UI can flag them for a
second look. `System` / `System Number` is deliberately NOT guessed at
all - the datasheet's fluid/service wording doesn't map onto the existing
System pick-list reliably enough to auto-fill safely, so that field is
always left for a human to set. On/Off (ball/rotary) valves also
deliberately leave Travel blank - their "Rated Travel" is a rotation in
degrees, and Travel Unit only has Inch/Metric to choose from, so filling
either in would misrepresent what the datasheet says.

Public API:
    read_datasheet_pdf(path) -> list[DatasheetRecord]
    read_datasheet_pdfs(paths) -> list[DatasheetRecord]

DatasheetRecord is a plain dict:
    {
        "equip_key": "valve" | "transmitter",
        "tag": "29103-LV-0957",
        "doc_no": "DS-29103-LV-0957",
        "kind_label": "Control Valve" | "On/Off Valve" | "Temperature Transmitter"
                       | "Vortex Flowmeter" | "Pressure Transmitter"
                       | "Guided Wave Radar Level Transmitter",
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
    if "ON/OFF VALVE" in t:
        return "onoff_valve"
    if "CONTROL VALVE" in t:
        return "valve"
    if "VORTEX FLOWMETER" in t or "VORTEX FLOW METER" in t:
        return "fit"
    if "TEMP TRANS ELEMENT" in t or "TEMP TRANS" in t or "THERMOWELL" in t:
        return "tit"
    if "PRESSURE TRANSMITTER" in t:
        return "pit"
    if "GUIDED WAVE RADAR" in t or "LEVEL XMTR" in t:
        return "lit"
    return None


_KIND_LABELS = {
    "valve": "Control Valve",
    "onoff_valve": "On/Off Valve",
    "fit": "Vortex Flowmeter",
    "tit": "Temperature Transmitter",
    "pit": "Pressure Transmitter",
    "lit": "Guided Wave Radar Level Transmitter",
}


def _row_label_value(text, row_num, label, stop_text=None):
    """Finds ROW_NUM immediately followed by LABEL (the row number and the
    label text have to be adjacent - this is what makes it safe against
    ordinary numeric values elsewhere on the line being mistaken for a row
    marker) and returns whatever comes after the label, up to the EARLIER
    of: `stop_text` (if given and found - the start of the label sharing
    that physical line in the other column, when we know it by name) or a
    generic "<number> <Title Case word>" boundary. Both are tried and the
    nearer one wins, rather than stop_text alone - some sheets jam the
    right-column text on with zero separating whitespace at all (no gap
    for the generic pattern to find), so relying on stop_text exclusively
    would silently skip the generic fallback exactly when it's needed
    most."""
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
    else:
        idx = -1
    if idx != -1:
        # A known, specific neighbor was found - trust it outright rather
        # than also checking the generic boundary below. Some captured
        # values are themselves a "label ... value ... label ... value"
        # pair on one line (e.g. "Model No.   Type   88   Spring &
        # Diaphragm"), where the actual value legitimately contains a
        # short number followed by an uppercase word ("88 Spring") that
        # would otherwise look exactly like the generic boundary this
        # function also watches for - cutting there would sever the
        # value before a caller's own regex ever got to see the part it
        # needed.
        cut_at = idx
    else:
        cut_at = len(val)
        m2 = re.search(r"\s{4,}\d{1,3}\s+[A-Z]", val)
        # Only trust the generic boundary if there's actual content
        # before it - a value like "316 SS" (a stainless grade) matches
        # the same shape a true row marker does ("<= 3 digits> <space>
        # <capital letter>"), and if that "marker" sits right at the
        # very start, applying it would wipe out the entire value rather
        # than trim a trailing intruder.
        if m2 and val[:m2.start()].strip():
            cut_at = m2.start()
    val = val[:cut_at]
    return val.strip(" .:\t")


# Right-column header labels that can bleed through and read as if they
# were the LEFT field's own value when that left field is genuinely blank
# (e.g. row 5 "Line No." with nothing entered, immediately followed on
# the same physical line by "Construction Work Package" - itself often
# also blank). Checked as a prefix rather than exact match since the PDF
# text layer sometimes renders "Work" as "W ork" (a stray internal
# space).
_HEADER_BLEED_PREFIXES = (
    "Construction Work", "Construction W ork", "Amb. Temp", "Project Name",
    "Plant Name", "Area Name", "Unit Name", "Sour Service", "Atm. Press", "SIL",
)


def _is_header_bleed(value):
    return any(value.startswith(p) for p in _HEADER_BLEED_PREFIXES)


def _first_segment(text):
    parts = re.split(r"\s{2,}", text.strip())
    return parts[0].strip() if parts and parts[0].strip() else ""


def _label_value_in_range(text, label, row_min, row_max, stop_text=None):
    """Like _row_label_value, but for the On/Off Valve family, where the
    same logical field can land on a different row number between two
    tags of the exact same datasheet template (e.g. "Seat / Ring
    Material" is row 56 on one example and row 57 on another - an extra
    or missing line earlier on the page shifts everything below it by
    one). Tries every row number in the given range and returns the first
    one that actually has this exact label next to it, which is still
    just as safe against false positives as a single exact row number -
    it only ever matches a row that both falls in the expected
    neighborhood AND carries the exact label - just tolerant of that
    neighborhood being a few rows wide instead of a single fixed number."""
    for row_num in range(row_min, row_max + 1):
        val = _row_label_value(text, row_num, label, stop_text=stop_text)
        if val:
            return val
    return ""


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
    service = _first_segment(_row_label_value(text, 3, "Service", stop_text="Area Name"))
    line_no = _first_segment(_row_label_value(text, 5, "Line No."))
    if _is_header_bleed(line_no):
        line_no = ""
    if not line_no:
        # On some sheets row 5's own number gets separated from "Line No."
        # by an unusually wide gap (typically when the row's paired
        # right-column field is blank) - the label text itself is still
        # there and still unambiguous, just not adjacent to its row
        # number anymore, so fall back to finding it directly.
        m = re.search(r"Line No\.(\S.*)", text)
        if m:
            candidate = _first_segment(m.group(1))
            line_no = "" if _is_header_bleed(candidate) else candidate
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


def _extract_onoff_valve(text, doc_no):
    """XV/KV-style On/Off Valve sheets - a genuinely different row layout
    from the Control Valve sheets _extract_valve handles (Body starts
    around row 32-35 here instead of row 34-40, Actuator around row
    60-64 instead of row 61-62, and a couple of labels are worded
    differently - "Seat / Ring Material" instead of "Seat Material", for
    instance). The row numbers also aren't perfectly fixed even within
    this one family - an extra or missing line earlier on the page can
    shift everything below it by one row between two examples of the
    exact same template - so this uses _label_value_in_range instead of
    a single fixed row number for the fields below row 30 or so.

    Travel is deliberately left blank here: these are ball/rotary valves
    whose "Rated Travel" is a rotation in degrees (e.g. "90\u00b0"), and
    the Travel Unit field only has Inch/Metric to choose from - filling
    it with either would misrepresent what the datasheet actually says."""
    tag, pid, service, line_no = _extract_common(text)

    trim_plug = _first_segment(_label_value_in_range(
        text, "Plug / Ball / Disk Material", 52, 58))
    trim_seat = _first_segment(_label_value_in_range(
        text, "Seat / Ring Material", 53, 59))

    size_line = _label_value_in_range(text, "Size", 31, 37)
    ansi_m = re.search(r"(\d+)\s*#", size_line)
    ansi_rating = ansi_m.group(1) if ansi_m else ""

    leak_value = (_label_value_in_range(text, "ANSI / FCI Leakage Class", 85, 106)
                  or _label_value_in_range(text, "Leakage Class", 85, 106))
    leak_m = re.search(r"\b(VI|IV|V|III|II|I)\b", leak_value)
    valve_class = leak_m.group(1) if leak_m else ""

    end_line = _label_value_in_range(text, "End Con In:", 36, 42).upper()
    if "FLG" in end_line or "FLANGE" in end_line:
        body_style = "Flanged"
    elif "NPT" in end_line or "THRD" in end_line or "THREAD" in end_line:
        body_style = "Threaded"
    else:
        body_style = ""

    actuator_val = _label_value_in_range(text, "Model No.", 58, 64, stop_text="P.O. No.")
    actuator_model = _first_segment(actuator_val)

    # Only the XV-style (w/Positioner) sheets have a Positioner section at
    # all - the solenoid-actuated KV-style sheets have no such section,
    # but a "Model No." does still exist around the same row numbers
    # there too (the Solenoid's own), so this has to be gated on the
    # title block actually saying "w/POSITIONER" rather than just trying
    # the row range and hoping nothing else occupies it.
    if "W/POSITIONER" in text.upper():
        positioner_val = _label_value_in_range(text, "Model No.", 73, 79)
        positioner_m = re.search(r"Type\s+(\S+)", positioner_val)
        positioner_model = positioner_m.group(1) if positioner_m else _first_segment(positioner_val)
    else:
        positioner_model = ""

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

    if kind == "tit":
        make = _first_segment(_row_label_value(text, 62, "Manufacturer"))
        model = _first_segment(_row_label_value(text, 63, "Model No."))
        transmitter_type = "Temperature Transmitter"
        cal_range = _extract_range(_row_label_value(text, 24, "Calibrated Range"))
        inst_range = _extract_range(_row_label_value(text, 23, "Instrument Range"))
        local_display = "Yes" if "LCD Display" in text or "Integral Meter" in text else ""
    elif kind == "fit":
        make = _first_segment(_row_label_value(text, 62, "Manufacturer"))
        model = _first_segment(_row_label_value(text, 63, "Model No."))
        transmitter_type = "Vortex Flow Meter"
        cal_range = _extract_range(_row_label_value(text, 32, "Calibrated Instrument Range"))
        inst_range = _extract_range(_row_label_value(text, 31, "Instrument Range or Element Range"))
        local_display = ""
    elif kind == "pit":
        # Single-column layout (no left/right row-jamming like TIT/FIT),
        # so the plain row-anchored lookups need no extra care here.
        make = _first_segment(_row_label_value(text, 60, "Manufacturer"))
        model = _first_segment(_row_label_value(text, 61, "Model No."))
        transmitter_type = "Pressure Transmitter"
        cal_range = _extract_range(_row_label_value(text, 19, "Calibrated Range"))
        inst_range = _extract_range(_row_label_value(text, 20, "Instrument Range @ Accuracy"))
        local_display = "Yes" if "LCD Display" in text or "Integral Meter" in text else ""
    else:  # lit
        make = _first_segment(_row_label_value(text, 48, "Manufacturer"))
        model = _first_segment(_row_label_value(text, 50, "Reference Probe Model Number"))
        transmitter_type = "Guided Wave Radar Level Transmitter"
        cal_range = _extract_range(_row_label_value(text, 19, "Calibrated Range"))
        inst_range = _extract_range(_row_label_value(text, 37, "Transmitter Range"))
        local_display = "Yes" if _row_label_value(text, 43, "Local Indicator").strip() else ""

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
        if kind in ("valve", "onoff_valve"):
            extractor = _extract_valve if kind == "valve" else _extract_onoff_valve
            tag, fields, guessed = extractor(text, doc_no)
            equip_key = "valve"
            kind_label = _KIND_LABELS[kind]
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
