# -*- coding: utf-8 -*-
"""
Reads "Instrumentation Master List.xlsx" - the actual engineering
instrument list for the whole project, far bigger than what any one
series' tracker sheets hold - and classifies every real instrument tag
into a (family, discipline) pair for the Overall Index screen
(overall_index_view.py). This is the one place that touches the master
list workbook, the same way data_access.py is the one place that touches
Equipment_Inspection_Tracker.xlsx; nothing else imports openpyxl for it.

THE TAXONOMY (TAXONOMY below) is deliberately one flat, ordered table -
first matching pattern wins. Every screen that needs a family or
discipline name reads it from here, never re-implements its own
guessing. Unmatched raw strings fall through to ("Unclassified",
"Unclassified") rather than raising or being silently dropped - see
classify_type(). As of the current workbook that's exactly one row (a
document-control label that landed in the Instrument Type Description
column by data-entry mistake, not a real gap in the table - see
read_master_list_rows()'s docstring).

"Recorded" / "Open" / "No form" (record_state on each row) is decided
empirically, not by guessing which families "should" have a PDF form:
a family counts as form-having if at least one real tag of that family
is actually sitting in a Transmitter/Valve/Gauge Log sheet somewhere in
the tracker today. That's the only ground truth available - the three
equipment types' "type" fields are freeform text, entered independently
of this workbook's own spelling, so nothing here tries to string-match
them.
"""
import re
from collections import Counter, defaultdict

import openpyxl

from paths import HERE

MASTER_LIST_PATH = HERE / "Instrumentation Master List.xlsx"

# Human-facing area name for each sheet, in the order they should list/
# group in the UI. Every sheet in the workbook must have an entry here -
# read_master_list_rows() raises on a sheet it doesn't recognize instead
# of silently skipping a whole area, so an added sheet gets noticed.
AREA_SHEETS = {
    "29103-K1B Pad": "K1B Pad",
    "29151 Drain 1": "Drain Tank 1",
    "29152 Drain 2": "Drain Tank 2",
    "KIB AREA 29203 FLOWLINE": "K1B Flowline",
    "29901 Injection Well 03-13": "Injection Well 03-13",
    "29902 Injection Well 12-14": "Injection Well 12-14",
    "9050 SUS": "SUS",
    "K1A PRODUCED EMULSION": "K1A Produced Emulsion",
    "K1A STEAM GENERATION": "K1A Steam Generation",
}

DISCIPLINES = (
    "Temperature", "Valve", "Pressure", "Flow", "Level",
    "Rotating equipment", "Discrete", "Electrical", "Analyzer",
)
UNCLASSIFIED = "Unclassified"

# ---------------------------------------------------------------------------
# (regex, family, discipline) - checked top to bottom, first match wins.
# Patterns are matched against the raw "Instrument Type Description" text
# after normalize_type() (upper-cased, whitespace collapsed, en/em dashes
# folded to a plain hyphen) - that alone absorbs most of the real spelling
# collisions in this workbook (CONTROL VALVE - ON/OFF vs CONTROL VALVE,
# ON/OFF; TEMPTERATURE GAUGE vs TEMPERATURE GAUGE; the four VIBRATION -
# x/y/z - AXIS variants that mix hyphens and en-dashes). A handful of
# patterns are ordered deliberately because a stricter rule must claim a
# string before a looser one would (e.g. "PRESSURE VALVE POSITION
# TRANSMITTER" contains both "VALVE POSITION TRANSMITTER" and, later,
# would also satisfy the generic Pressure-transmitter pattern).
# ---------------------------------------------------------------------------
TAXONOMY = [
    (r"SWITCH", "Switch", "Discrete"),
    (r"VALVE POSITION TRANSMITTER", "Valve position transmitter", "Valve"),
    (r"REGULATOR SELF CONTAINED", "Self-contained regulator", "Valve"),
    (r"^CONTROL VALVE", "Control valve", "Valve"),
    (r"^POSITIONER$", "Positioner", "Valve"),
    (r"^VALVE - MOTOR OPERATED", "Motor-operated valve", "Valve"),
    (r"^VALVE - MANUAL|PRESSURE RELIEF VALVE|PRESSURE SAF\w* VALVE|RUPTURE DISK", "Manual/relief valve", "Valve"),
    (r"^TEMP\w* ELEMENT", "Temperature element", "Temperature"),
    (r"^THERMOWELL", "Thermowell", "Temperature"),
    (r"^TEMP\w*.*TRANSMITTER", "Temperature transmitter", "Temperature"),
    (r"^TEMPT?ERATURE GAUGE", "Temperature gauge", "Temperature"),
    (r"^DP INDICAT\w* TRANSMITTER", "Pressure transmitter", "Pressure"),
    (r"^PRESSURE.*TRANSMITTER", "Pressure transmitter", "Pressure"),
    (r"^DP INDICATOR", "Pressure gauge", "Pressure"),
    (r"^PRESSURE GAUGE|^FIELD PRESSURE INDICATOR", "Pressure gauge", "Pressure"),
    (r"^LEVEL TRANSMITTER", "Level transmitter", "Level"),
    (r"^LEVEL GAUGE", "Level gauge", "Level"),
    (r"MULTIPHASE", "Multiphase flow", "Flow"),
    (r"^FLOW TRANSMITTER", "Flow transmitter", "Flow"),
    (r"^FLOW ELEMENT|RESTRICTION ORIFICE|^DENSITY ELEMENT", "Flow element", "Flow"),
    (r"FLOW GAUGE|FLOW INDICATOR", "Flow gauge", "Flow"),
    (r"MOTOR (TRIP|RUN)|HARD WIRED MOTOR|^VFD STATUS", "Motor/VFD status", "Rotating equipment"),
    (r"^SPEED", "Speed/VFD signal", "Rotating equipment"),
    (r"VIBRATION", "Vibration monitoring", "Rotating equipment"),
    (r"^ANALYZER ELEMENT", "Analyzer element", "Analyzer"),
    (r"^ANALYZER (TX|INDICATING TRANSMITTER)", "Analyzer transmitter", "Analyzer"),
    (r"SAMPL", "Sample point/station", "Analyzer"),
    (r"BEACON|HORN|TRAFFIC LIGHT|FIRE STROBE|SPEAKER", "Annunciator", "Electrical"),
    (r"VOLTAGE INDICATOR|CURRENT INDICATOR|POWER.*INDICATOR", "Electrical indicator", "Electrical"),
    (r"AUXILIARY CONTROL SIGNAL|SIS CONTROL OUTPUT", "Auxiliary signal", "Discrete"),
]
_COMPILED_TAXONOMY = [(re.compile(pattern), family, discipline) for pattern, family, discipline in TAXONOMY]


def normalize_type(raw):
    """Upper-cases, collapses whitespace, and folds en/em dashes to a
    plain hyphen - enough to absorb every real spelling collision found
    in this workbook without needing a per-typo special case."""
    s = str(raw or "")
    s = s.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip().upper()


def normalize_tag(raw):
    """Upper-cases and strips ALL whitespace, not just leading/trailing -
    some tracker Log sheets have a stray space baked into the tag text
    itself (e.g. '29103-PG -0903'), which would otherwise never match
    this same tag as it appears (space-free) in the master list."""
    s = str(raw or "")
    s = s.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", "", s).upper()


def classify_type(raw_type_desc):
    """(family, discipline) for one raw "Instrument Type Description"
    string. Never raises and never returns None - an unmatched string
    comes back as (UNCLASSIFIED, UNCLASSIFIED) so it stays visible
    (counted, filterable) instead of silently vanishing from the index."""
    t = normalize_type(raw_type_desc)
    for pattern, family, discipline in _COMPILED_TAXONOMY:
        if pattern.search(t):
            return family, discipline
    return UNCLASSIFIED, UNCLASSIFIED


def _parse_tag(raw):
    """'9050-LIT  -957-A' -> ('9050', 'LIT', '957A', '9050-LIT-957A').
    None if it doesn't look like an AREA-FUNC-NUM[-SUFFIX] tag (area must
    be numeric - filters out stray non-tag text some cell held)."""
    t = normalize_type(raw)
    parts = [p.strip() for p in t.split("-") if p.strip() != ""]
    if len(parts) < 3:
        return None
    area = parts[0]
    if not re.match(r"^\d+$", area):
        return None
    func = parts[1]
    num = "".join(parts[2:])
    return area, func, num, f"{area}-{func}-{num}"


def _find_col(norm_headers, *names):
    for want in names:
        for i, h in enumerate(norm_headers):
            if h == want:
                return i
    return None


def _read_one_sheet(ws, sheet_name, area_name):
    headers = [str(c.value or "").strip().replace("\xa0", " ") for c in next(ws.iter_rows(min_row=1, max_row=1))]
    norm = [re.sub(r"\s+", " ", h).strip().lower() for h in headers]
    tag_i = _find_col(norm, "tag number", "tag_number", "tagnumber")
    if tag_i is None:
        raise ValueError(f"'{sheet_name}' has no Tag Number column - headers were {headers!r}")
    svc_i = _find_col(norm, "service")
    type_i = _find_col(norm, "instrument type description", "instrument_type_desc")
    pid_i = _find_col(norm, "p&id", "p id", "pid")
    line_i = _find_col(norm, "line number", "line_number")
    module_i = _find_col(norm, "module id", "module_id")
    layout_i = _find_col(norm, "location layout", "location_layout")
    issued_i = _find_col(norm, "issued for")
    received_i = _find_col(norm, "received")
    installed_i = _find_col(norm, "installed")
    ewp_i = _find_col(norm, "ewp")
    model_i = _find_col(norm, "model", "model_name")
    mfr_i = _find_col(norm, "manufacturer", "manufacturer_name")

    def cell(row, i):
        v = row[i] if i is not None and i < len(row) else None
        return str(v).strip() if v not in (None, "") else ""

    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        raw_tag = row[tag_i] if tag_i < len(row) else None
        if not raw_tag:
            continue
        parsed = _parse_tag(raw_tag)
        if not parsed:
            continue
        _, _, _, tag = parsed
        type_desc = cell(row, type_i)
        family, discipline = classify_type(type_desc)
        rows.append({
            "area": area_name, "area_sheet": sheet_name, "tag": tag, "raw_tag": str(raw_tag).strip(),
            "service": cell(row, svc_i), "type_desc": type_desc,
            "family": family, "discipline": discipline,
            "pid": cell(row, pid_i), "line": cell(row, line_i), "module_id": cell(row, module_i),
            "location_layout": cell(row, layout_i), "issued_for": cell(row, issued_i),
            "received": cell(row, received_i), "installed_date": cell(row, installed_i),
            "ewp": cell(row, ewp_i), "model": cell(row, model_i), "mfr": cell(row, mfr_i),
        })
    return rows


_ml_cache = {"mtime": None, "rows": None}


def _master_list_mtime():
    try:
        return MASTER_LIST_PATH.stat().st_mtime
    except OSError:
        return None


def read_master_list_rows():
    """One dict per real instrument tag across every sheet (area) in the
    master list workbook - not just the K1B-focused subset the tracker
    itself imports. Cached in memory, reloaded only when the workbook's
    mtime changes, same pattern as data_access._get_cached_workbook.

    The one row that currently comes back with family/discipline ==
    UNCLASSIFIED is 28100-XV-269 (K1A Produced Emulsion): its Instrument
    Type Description cell literally reads "IFC - ISSUED FOR
    CONSTRUCTION" - a document-control label, not an instrument type.
    That's a real data-entry mistake in the source workbook, not a gap
    in TAXONOMY; it's surfaced, not hidden, exactly so it can get fixed
    at the source."""
    current_mtime = _master_list_mtime()
    if current_mtime == _ml_cache["mtime"] and _ml_cache["rows"] is not None:
        return _ml_cache["rows"]

    wb = openpyxl.load_workbook(MASTER_LIST_PATH, read_only=True, data_only=True)
    rows = []
    for sheet_name in wb.sheetnames:
        area_name = AREA_SHEETS.get(sheet_name)
        if area_name is None:
            raise ValueError(f"Master list has an unrecognized sheet '{sheet_name}' - add it to AREA_SHEETS")
        rows.extend(_read_one_sheet(wb[sheet_name], sheet_name, area_name))
    wb.close()

    _ml_cache["mtime"] = current_mtime
    _ml_cache["rows"] = rows
    return rows


def invalidate_cache():
    _ml_cache["mtime"] = None
    _ml_cache["rows"] = None


def _tracked_tag_lookup():
    """{normalize_tag(tag): (series_number, equip_key, row_num, status)}
    across every registered series and every one of the three PDF-backed
    equipment types - the real, current ground truth for which tags
    already have a record open in the tracker. Imported lazily (not at
    module load) so master_list.py stays importable/testable even in a
    context that hasn't got a tracker workbook next to it."""
    import data_access as da

    lookup = {}
    for series in da.load_config()["series"]:
        series_number = series["number"]
        for equip_key, etype in da.EQUIPMENT_TYPES.items():
            try:
                rows = da.read_index_rows_with_status(series_number, equip_key)
            except KeyError:
                continue
            key_field = etype["key_field"]
            for entry in rows:
                tag = normalize_tag(entry.get(key_field, ""))
                if not tag:
                    continue
                lookup[tag] = (series_number, equip_key, entry["row"], entry)
    return lookup


def overall_index_rows():
    """Every real instrument tag in the master list, joined against the
    tracker's current state. Adds to each row from read_master_list_rows():
      record_state  - "recorded" (tracked AND real progress entered),
                       "open" (tracked but still a blank placeholder), or
                       "no_form" (this family has never had a single real
                       example logged in the tracker, empirically - see
                       module docstring)
      link          - (series_number, equip_key, row_num) to jump to the
                       real record, or None for "no_form" rows
      system        - the tracker's own System / System # field for this
                       tag, when it has one - a human already chose this
                       value at intake, so it's read verbatim rather than
                       re-derived. "" when the tag has never been logged.
      system_source - "recorded" (real value from the tracker) or
                       "not_logged" (never imported, so no System has ever
                       been assigned) - shown in the row-detail panel so
                       "how the System was classified" has a plain, honest
                       answer instead of a guessed one. This module does
                       NOT attempt to infer a System for untracked tags
                       from Service text or anything else in the master
                       list - the existing System vocabulary is a
                       human-entered, per-project pick list with no
                       reliable text signal to reverse-engineer it from.
    One workbook read, one tracker sweep, computed once and returned as a
    plain list - callers that want to cache this across the session (the
    Overall Index page does, per its own mtime-driven reload) do so
    themselves; this function always reflects current disk state."""
    import data_access as da

    tracked = _tracked_tag_lookup()
    rows = read_master_list_rows()
    out = []
    for row in rows:
        hit = tracked.get(normalize_tag(row["tag"]))
        if hit is None:
            state, link, system, system_source = "no_form", None, "", "not_logged"
        else:
            series_number, equip_key, row_num, status_entry = hit
            has_progress = bool(status_entry.get("installed") or status_entry.get("submitted") or status_entry.get("accepted"))
            state = "recorded" if has_progress else "open"
            link = (series_number, equip_key, row_num)
            system_field = da.EQUIPMENT_TYPES[equip_key]["group_fields"][0]
            system = status_entry.get(system_field) or ""
            system_source = "recorded" if system else "not_logged"
        out.append({**row, "record_state": state, "link": link,
                    "system": system, "system_source": system_source})
    return out


def summarize(rows):
    """Header-strip counts for the Overall Index page - always computed
    from the actual row list handed in, never hardcoded, so they can
    never drift from what the table itself is showing."""
    families = set()
    disciplines = set()
    type_strings = set()
    areas = set()
    recorded = open_ = no_form = 0
    by_discipline = defaultdict(lambda: {"tags": 0, "recorded": 0})

    for row in rows:
        families.add(row["family"])
        disciplines.add(row["discipline"])
        type_strings.add(row["type_desc"])
        areas.add(row["area"])
        state = row["record_state"]
        if state == "recorded":
            recorded += 1
        elif state == "open":
            open_ += 1
        else:
            no_form += 1
        by_discipline[row["discipline"]]["tags"] += 1
        if state == "recorded":
            by_discipline[row["discipline"]]["recorded"] += 1

    total = len(rows)
    return {
        "total_tags": total,
        "areas": len(areas),
        "type_strings": len(type_strings),
        "families": len(families - {UNCLASSIFIED}),
        "disciplines": len(disciplines - {UNCLASSIFIED}),
        "unclassified": sum(1 for r in rows if r["family"] == UNCLASSIFIED),
        "recorded": recorded,
        "recorded_pct": round(100 * recorded / total) if total else 0,
        "open": open_,
        "no_form": no_form,
        "by_discipline": dict(by_discipline),
    }


if __name__ == "__main__":
    all_rows = overall_index_rows()
    summary = summarize(all_rows)
    print(summary)
    counts = Counter((r["family"], r["discipline"]) for r in all_rows)
    for (fam, disc), n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {n:5d}  {fam:30s} [{disc}]")
