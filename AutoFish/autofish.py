# -*- coding: utf-8 -*-
"""
AutoFish - hands-free fishing macro for the Roblox "Reel it in!" minigame.

    python autofish.py          (or double-click START_AUTOFISH.bat)

What it does, forever, until you press STOP (or F6):

    1. Casts the line (presses E while the "Cast" prompt is showing).
    2. Waits for a bite - the "Hooked! / Reel it in!" bar pops up by itself.
    3. Watches the bar many times per second and presses E the moment the
       fish pointer is inside the gold zone (aiming for the middle of it).
    4. When the fish is caught (or gets away) it recasts and starts over.

Everything is found on screen by colour, so it works at any resolution and
does not care where the Roblox window is.  Nothing is injected into the game:
it only looks at the screen and presses a key, exactly like you would.

Requirements: Windows, Python 3.9+, and the packages `mss` and `numpy`
(START_AUTOFISH.bat installs them for you).
"""
from __future__ import annotations

import json
import os
import queue
import re
import sys
import threading
import time
import traceback
from collections import deque
from dataclasses import asdict, dataclass, fields
from typing import Callable, List, Optional, Tuple

import numpy as np

APP_NAME = "AutoFish"
APP_VERSION = "1.8.1"
HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(HERE, "autofish_settings.json")
DEBUG_DIR = os.path.join(HERE, "debug_snapshots")
MISS_DIR = os.path.join(HERE, "miss_reports")
ALARM_WAV = os.path.join(HERE, "leviathan_alarm.wav")   # replace it with your own sound if you like
IS_WINDOWS = sys.platform.startswith("win")


# =============================================================================
#  Settings
# =============================================================================
@dataclass
class Settings:
    # --- reel timing -------------------------------------------------------
    lead_ms: float = 30.0          # input lag to plan for until it has been measured
    auto_lead: bool = True         # measure the real press -> game delay and use that
    measured_lead2_ms: float = 0.0  # last measured delay (saved; start value next time, 0 = none)
    zone_margin_pct: float = 18.0  # ignore this % of the gold zone on each side
    min_press_gap_s: float = 0.10 # minimum time between two reel presses
    # --- casting -----------------------------------------------------------
    recast_delay_s: float = 1.0    # pause after a catch before casting again
    bite_timeout_s: float = 45.0   # no bite after this long -> reel in & recast
    # --- input -------------------------------------------------------------
    key: str = "e"                 # key used to cast and to reel
    reel_with_click: bool = False  # press left mouse instead of the key while reeling
    key_hold_ms: float = 35.0      # how long each key press is held
    toggle_hotkey: str = "F6"      # global on/off hotkey
    # --- safety ------------------------------------------------------------
    require_focus: bool = True     # only press keys while Roblox is the active window
    window_title: str = "Roblox"   # title of the game window
    dry_run: bool = False          # detect + log only, never press anything
    stop_on_miss: bool = True      # stop the macro on the first miss (and save a miss report)
    leviathan: bool = False        # only trigger the bite: miss on purpose so the round ends fast
    skip_fish: bool = True         # skip unwanted fish: unequip + re-equip the rod, recast
    keep_hits: str = "3"           # fish needing these numbers of hits are reeled ("3", "2,3" ...)
    keep_only_big: bool = True     # ...and only when the panel says "Something big is pulling!"
    skip_key: str = "3"            # the rod's hotbar key (pressed twice: unequip, equip)
    skip_key_gap_s: float = 0.4    # pause between the two presses
    rod_check: bool = True         # no Cast prompt and no minigame for a while -> press the rod key (equip)
    rod_check_s: float = 1.5       # how long with no prompt at all before equipping
    multi_window: bool = True      # fish in every Roblox window at once (switches between them)
    focus_settle_ms: float = 60.0  # wait after switching windows before pressing
    parallel_minigames: bool = False  # play every window's minigame at the same time
    # --- leviathan alarm ---------------------------------------------------
    leviathan_alarm: bool = True   # sound + flash when a leviathan pulls (while fishing)
    alarm_stops_fishing: bool = True  # stop fishing once you are pulled in (screen goes dark / boss bar)
    alarm_max_s: float = 300.0     # the sound stops by itself after this long (s)
    # --- ui ----------------------------------------------------------------
    always_on_top: bool = True

    @classmethod
    def load(cls, path: str = SETTINGS_PATH) -> "Settings":
        s = cls()
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            names = {f.name: f for f in fields(cls)}
            for k, v in data.items():
                if k in names:
                    default = getattr(s, k)
                    try:
                        if isinstance(default, bool):
                            v = bool(v)
                        elif isinstance(default, float):
                            v = float(v)
                        elif isinstance(default, str):
                            v = str(v)
                        setattr(s, k, v)
                    except (TypeError, ValueError):
                        pass
        except FileNotFoundError:
            pass
        except Exception as exc:  # corrupt file -> defaults
            print(f"[{APP_NAME}] could not read settings ({exc}); using defaults")
        return s

    def save(self, path: str = SETTINGS_PATH) -> None:
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(asdict(self), fh, indent=2)
        except Exception as exc:
            print(f"[{APP_NAME}] could not save settings: {exc}")


# =============================================================================
#  Vision - all colour rules live here
#
#  Measured from a real recording of the minigame:
#     bar background   navy gradient  #0A3051 (top) .. #05233C .. #071320 (bottom)
#     gold zone        #BAA052 with a light left edge #F9EBB6
#     fish pointer     orange #DD6F22 (+ a thin white line through it)
#     panel background #0E171E, progress dots #F0C75F, miss boxes #C4463F
#     action prompt    navy box #111A26 with light-blue border #7EA3B4,
#                      title text cream (#D5D0C9-ish): "Cast" or "Reel in"
#  Every rule is a ratio/difference test, so small colour shifts (gamma,
#  HDR, video compression, brightness) do not break it.
# =============================================================================
def write_png(path: str, rgb: np.ndarray) -> None:
    """Save an HxWx3 uint8 RGB image as PNG (no extra packages needed)."""
    import struct
    import zlib
    img = np.ascontiguousarray(rgb, dtype=np.uint8)
    H, W = img.shape[:2]
    raw = b"".join(b"\x00" + img[y].tobytes() for y in range(H))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)


def channels(rgb: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """HxWx3 uint8 RGB -> three int16 planes (so subtraction can go negative)."""
    a = rgb.astype(np.int16, copy=False)
    return a[..., 0], a[..., 1], a[..., 2]


def mask_navy(r, g, b):
    return (b >= 35) & (b <= 130) & (r <= 50) & (g <= 90) & (b - r >= 25) & (b - g >= 8)


def mask_gold(r, g, b):
    return ((r >= 140) & (g >= 115) & (b <= 190) & (r - b >= 55) & (g - b >= 35)
            & (np.abs(r - g) <= 50))


def mask_light_blue(r, g, b):
    return (b >= 130) & (g >= 105) & (r >= 70) & (b - r >= 30) & (b >= g) & (g >= r)


def runs(mask_1d: np.ndarray, gap: int = 0) -> List[Tuple[int, int]]:
    """(start, end) inclusive runs of True, merging runs split by <= `gap` False pixels."""
    idx = np.flatnonzero(mask_1d)
    if idx.size == 0:
        return []
    brk = np.flatnonzero(np.diff(idx) > gap + 1)
    starts = np.concatenate((idx[:1], idx[brk + 1]))
    ends = np.concatenate((idx[brk], idx[-1:]))
    return list(zip(starts.tolist(), ends.tolist()))


@dataclass
class BarGeom:
    """Where the minigame bar sits, in absolute screen pixels (inclusive)."""
    x0: int
    x1: int
    y0: int
    y1: int

    @property
    def w(self) -> int:
        return self.x1 - self.x0 + 1

    @property
    def h(self) -> int:
        return self.y1 - self.y0 + 1

    def strip_region(self) -> Tuple[int, int, int, int]:
        """Screen region (left, top, width, height) to grab while reeling:
        the bar plus the progress dots / miss boxes underneath it."""
        pad = max(4, self.h // 2)
        left = self.x0 - pad
        top = self.y0 - max(3, int(0.3 * self.h))
        right = self.x1 + pad
        bottom = self.y1 + int(round(1.3 * self.h))
        return left, top, right - left + 1, bottom - top + 1

    def row(self, frac: float) -> int:
        return self.y0 + int(round(frac * (self.h - 1)))


def locate_bar(rgb: np.ndarray, origin: Tuple[int, int] = (0, 0)) -> Optional[BarGeom]:
    """Find the minigame bar anywhere in an image.  Returns None if not visible.

    The bar is a long horizontal navy strip that contains a gold block.  The
    rows near its top and bottom edge are only crossed by the thin pointer
    line, so those rows give a clean, unbroken navy+gold run whose ends are
    the bar's ends.  Rows that agree on those ends form the bar."""
    H, W = rgb.shape[:2]
    if H < 8 or W < 60:
        return None
    # 1) cheap pass on a 2x-subsampled image to find rows with lots of navy
    rs, gs, bs = channels(rgb[::2, ::2])
    sub_counts = mask_navy(rs, gs, bs).sum(axis=1)
    cand_sub = np.flatnonzero(sub_counts >= 25)
    if cand_sub.size == 0:
        return None
    rows = set()
    for yy in cand_sub.tolist():
        for d in (-1, 0, 1, 2):
            y = 2 * yy + d
            if 0 <= y < H:
                rows.add(y)
    rows = sorted(rows)
    # 2) full-resolution analysis of the candidate rows only
    r, g, b = channels(rgb[rows])
    navy = mask_navy(r, g, b)
    gold = mask_gold(r, g, b)
    bright = np.maximum(np.maximum(r, g), b) > 45   # fish / pointer line, not panel background
    good = []  # (y, x0, x1)
    for i, y in enumerate(rows):
        both = navy[i] | gold[i]
        # the fish icon / pointer line can cut a row in two: join pieces that
        # are separated by a gap that is small next to the pieces themselves
        # (never across the dark panel background next to the bar's ends)
        joined: List[Tuple[int, int]] = []
        for s, e in runs(both, gap=4):
            if joined:
                ps, pe = joined[-1]
                gap_px = bright[i, pe + 1:s]
                if (s - pe - 1 <= max(6, 0.12 * (e - ps + 1))
                        and (gap_px.size == 0 or float(gap_px.mean()) >= 0.6)):
                    joined[-1] = (ps, e)
                    continue
            joined.append((s, e))
        for s, e in joined:
            n = e - s + 1
            if n < 60:
                continue
            gc = int(gold[i, s:e + 1].sum())
            nc = int(navy[i, s:e + 1].sum())
            if gc >= 3 and nc >= 0.35 * n and gc <= 0.7 * n:
                good.append((y, s, e))
    if not good:
        return None
    # 3) group rows that agree on where the bar starts and ends
    groups: List[List[Tuple[int, int, int]]] = []
    for item in good:
        y, s, e = item
        tol = max(3, int(0.02 * (e - s)))
        for grp in groups:
            gy, gs_, ge = grp[0]
            if abs(gs_ - s) <= tol and abs(ge - e) <= tol and abs(y - grp[-1][0]) <= max(6, (e - s) // 15):
                grp.append(item)
                break
        else:
            groups.append([item])
    best = None
    for grp in groups:
        if len(grp) < 3:
            continue
        ys = [it[0] for it in grp]
        x0 = int(np.median([it[1] for it in grp]))
        x1 = int(np.median([it[2] for it in grp]))
        w = x1 - x0 + 1
        # measure the bar's true height: rows whose [x0, x1] span is mostly bar
        ym = int(np.median(ys))
        ya, yb = max(0, ym - w // 3), min(H, ym + w // 3 + 1)
        r2, g2, b2 = channels(rgb[ya:yb, x0:x1 + 1])
        cov = (mask_navy(r2, g2, b2) | mask_gold(r2, g2, b2)).mean(axis=1)
        k = ym - ya
        if cov[k] < 0.55:
            continue
        top = k
        while top - 1 >= 0 and cov[top - 1] >= 0.55:
            top -= 1
        bot = k
        while bot + 1 < cov.size and cov[bot + 1] >= 0.55:
            bot += 1
        y0, y1 = ya + top, ya + bot
        h = y1 - y0 + 1
        # the fish can sit on (and hide) an end of the bar: walk outwards (at
        # most ~one bar height) over columns that still show navy/gold above or
        # below the fish, stepping over the thin pointer line
        reach = int(1.2 * h) + 2
        off_x = max(0, x0 - reach)
        rb, gb, bb_ = channels(rgb[y0:y1 + 1, off_x:min(W, x1 + reach + 1)])
        barish = (mask_navy(rb, gb, bb_) | mask_gold(rb, gb, bb_)).mean(axis=0) >= 0.3
        skip = max(3, int(0.2 * h))
        for direction in (-1, 1):
            edge = x0 if direction < 0 else x1
            x, misses_in_row = edge, 0
            while 0 <= x + direction - off_x < barish.size and abs(x + direction - edge) <= reach:
                x += direction
                if barish[x - off_x]:
                    misses_in_row = 0
                    if direction < 0:
                        x0 = x
                    else:
                        x1 = x
                else:
                    misses_in_row += 1
                    if misses_in_row > skip:
                        break
        w = x1 - x0 + 1
        if h < 4 or not (6.0 <= w / h <= 30.0):
            continue
        if len(grp) < 0.25 * h:  # too few rows agree on the ends
            continue
        # the bar sits on the minigame panel's dark background: the rows just
        # above and below it must be dark (rules out sunsets on water, etc.)
        off = max(2, int(round(0.12 * h)))
        dark_ok = True
        for yy in (y0 - off, y1 + off):
            if not (0 <= yy < H):
                dark_ok = False  # the panel always has room above and below the bar
                break
            seg = rgb[yy, x0:x1 + 1].astype(np.int16)
            if float((seg.max(axis=1) <= 70).mean()) < 0.6:
                dark_ok = False
        if not dark_ok:
            continue
        score = len(grp) * w
        if best is None or score > best[0]:
            best = (score, BarGeom(x0 + origin[0], x1 + origin[0], y0 + origin[1], y1 + origin[1]))
    return best[1] if best else None


@dataclass
class MinigameReading:
    visible: bool = False
    zone: Optional[Tuple[float, float]] = None   # gold zone, bar-local x (inclusive)
    pointer: Optional[float] = None              # fish pointer, bar-local x
    width: int = 0                               # bar width in pixels
    filled: int = 0                              # progress dots filled
    total: int = 0                               # progress dots total
    misses: int = 0                              # red miss boxes


def read_minigame(strip: np.ndarray, geom: BarGeom, strip_origin: Tuple[int, int]) -> MinigameReading:
    """Read gold zone / pointer / progress from an image that contains the bar.

    `strip_origin` is the absolute screen position of strip[0, 0]."""
    out = MinigameReading(width=geom.w)
    ox, oy = strip_origin
    lx0 = geom.x0 - ox
    lx1 = geom.x1 - ox
    Hs, Ws = strip.shape[:2]
    if lx0 < 0 or lx1 >= Ws or geom.y0 - oy < 0 or geom.y1 - oy >= Hs:
        return out
    h = geom.h

    def rows_at(fracs):
        ys = sorted({geom.row(f) - oy for f in fracs})
        return [y for y in ys if 0 <= y < Hs]

    # --- gold zone: rows near the top/bottom edge (the fish body never reaches them)
    gy = rows_at((0.10, 0.20, 0.80, 0.90))
    r, g, b = channels(strip[gy, lx0:lx1 + 1])
    gold = mask_gold(r, g, b)
    navy = mask_navy(r, g, b)
    cover = (gold | navy).mean(axis=1)            # fraction of bar that looks like bar
    if cover.size == 0 or float(np.median(cover)) < 0.55:
        return out
    need = 2 if len(gy) >= 3 else 1
    gcols = gold.sum(axis=0) >= need
    best = None
    # there is only one gold zone: pieces split by the pointer line (or a big
    # fish icon) belong together
    for s, e in runs(gcols, gap=max(2, int(round(0.5 * h)))):
        n = e - s + 1
        if n >= max(3, 0.25 * h) and (best is None or n > best[1] - best[0] + 1):
            best = (s, e)
    if best is None:
        return out
    out.zone = (float(best[0]), float(best[1]))
    out.visible = True

    # --- pointer (fish): anything on the middle rows that is neither navy nor gold
    py = rows_at((0.35, 0.45, 0.55))
    r, g, b = channels(strip[py, lx0:lx1 + 1])
    other = ~(mask_navy(r, g, b) | mask_gold(r, g, b))
    counts = other.sum(axis=0)
    pcols = counts >= max(1, len(py) - 1)
    best_p = None
    for s, e in runs(pcols, gap=max(2, int(round(0.12 * h)))):
        n = e - s + 1
        if max(3, 0.3 * h) <= n <= 3.0 * h and (best_p is None or n > best_p[1] - best_p[0] + 1):
            best_p = (s, e)
    if best_p is not None:
        s, e = best_p
        wts = counts[s:e + 1].astype(np.float64)
        xs = np.arange(s, e + 1, dtype=np.float64)
        out.pointer = float((xs * wts).sum() / max(1.0, wts.sum()))

    # --- progress dots (under the left end) and miss boxes (under the right end)
    try:
        y_a = geom.y1 + int(round(0.30 * h)) - oy
        y_b = geom.y1 + int(round(1.15 * h)) - oy
        y_a, y_b = max(0, y_a), min(Hs, y_b + 1)
        if y_b - y_a >= 2:
            span = int(round(0.40 * geom.w))
            left = strip[y_a:y_b, lx0:min(Ws, lx0 + span)]
            rspan = int(round(0.30 * geom.w))
            right = strip[y_a:y_b, max(0, lx1 - rspan + 1):lx1 + 1]
            r, g, b = channels(left)
            filled = (r >= 185) & (g >= 145) & (b <= 160) & (r - b >= 70)
            mx = np.maximum(np.maximum(r, g), b)
            mn = np.minimum(np.minimum(r, g), b)
            empty = (b - r >= 12) & (mx >= 45) & (mx <= 110) & (mx - mn <= 45)
            min_dot = max(2, int(0.2 * h))
            f_best = e_best = 0
            for i in range(left.shape[0]):
                f_best = max(f_best, sum(1 for s, e in runs(filled[i], gap=0) if e - s + 1 >= min_dot))
                e_best = max(e_best, sum(1 for s, e in runs(empty[i], gap=0) if e - s + 1 >= min_dot))
            out.filled = f_best
            out.total = f_best + e_best
            r, g, b = channels(right)
            red = (r >= 130) & (r - g >= 60) & (r - b >= 60)
            # each red box has a dark X across it, which splits single rows of
            # one box into two pieces at high resolutions: project the red
            # pixels onto columns first, so one box always counts once
            rcols = red.sum(axis=0) >= max(1, int(0.15 * h))
            out.misses = sum(1 for s, e in runs(rcols, gap=0) if e - s + 1 >= min_dot)
    except Exception:
        pass
    return out


PROMPT_CAST = "cast"
PROMPT_REEL = "reel"
PROMPT_NONE = None


@dataclass
class PromptReading:
    state: Optional[str] = None                        # "cast", "reel" or None
    box: Optional[Tuple[int, int, int, int]] = None    # x0, y0, x1, y1 (absolute)
    ratio: float = 0.0
    note: str = ""


def read_prompt(rgb: np.ndarray, origin: Tuple[int, int] = (0, 0)) -> PromptReading:
    """Find the "[E] Cast / Reel in" action prompt and tell which one it is.

    The prompt is a dark box with a light-blue border.  Its title is "Cast"
    (short) or "Reel in" (long); the title's width divided by the box height
    is ~0.57 for Cast and ~0.91 for Reel in, at any resolution."""
    H, W = rgb.shape[:2]
    if H < 20 or W < 60:
        return PromptReading(note="image too small")
    # rows that contain a long light-blue line (box top/bottom border)
    rs, gs, bs = channels(rgb[:, ::2])
    lb_sub = mask_light_blue(rs, gs, bs)
    cand = np.flatnonzero(lb_sub.sum(axis=1) >= 20)
    if cand.size == 0:
        return PromptReading(note="no prompt")
    cand_rows = cand.tolist()
    r, g, b = channels(rgb[cand])
    lb = mask_light_blue(r, g, b)
    row_of = {y: i for i, y in enumerate(cand_rows)}
    segs = []
    for i, y in enumerate(cand_rows):
        for s, e in runs(lb[i], gap=2):
            if e - s + 1 >= 40:
                segs.append((y, s, e))
    # A long light-blue run is one border of the box.  The opposite border has
    # an animated shine and the mouse cursor can cut it, so it only has to be
    # partly lit.  Take the farthest such row (the outer border, not the
    # underline beneath "Water").
    boxes = set()
    for (ya, sa, ea) in segs:
        wa = ea - sa + 1
        lo, hi = int(0.2 * wa), int(0.55 * wa)
        below = [y for y in cand_rows if lo <= y - ya <= hi and lb[row_of[y], sa:ea + 1].mean() >= 0.35]
        above = [y for y in cand_rows if lo <= ya - y <= hi and lb[row_of[y], sa:ea + 1].mean() >= 0.35]
        if below:
            boxes.add((sa, ya, ea, max(below)))
        if above:
            boxes.add((sa, min(above), ea, ya))
    if not boxes:
        return PromptReading(note="no prompt")
    # one box per location: prefer the widest, then the tallest
    ordered = sorted(boxes, key=lambda bx: (-(bx[2] - bx[0]), -(bx[3] - bx[1])))
    uniq = []
    for bx in ordered:
        if all(abs((bx[0] + bx[2]) - (u[0] + u[2])) > 2 * 12 or abs(bx[1] - u[1]) > 12 for u in uniq):
            uniq.append(bx)
    cx, cy = W / 2.0, H / 2.0
    uniq.sort(key=lambda bx: (((bx[0] + bx[2]) / 2 - cx) ** 2 + ((bx[1] + bx[3]) / 2 - cy) ** 2))
    truncated = None
    for (x0, y0, x1, y1) in uniq:
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        if bw < 2.5 * bh:
            # the real prompt is ~3.1x as wide as it is tall; a narrower box means
            # something (usually the mouse cursor) cut its border - don't guess
            truncated = (x0 + origin[0], y0 + origin[1], x1 + origin[0], y1 + origin[1])
            continue
        inner = rgb[y0 + 2:y1 - 1, x0 + 2:x1 - 1]
        if inner.size == 0 or float(inner.mean()) > 90:
            continue  # not a dark box
        # the prompt has a gold-framed key icon on its left: one of its frame
        # columns is a tall gold line (rules out other dark boxes, e.g. the
        # minigame panel while it fades out)
        # (search a little left of x0 too: the cursor can cut the border's left end)
        kx0 = max(0, x0 - int(0.3 * bh))
        kr, kg, kb = channels(rgb[y0 + 1:y1, kx0:x0 + max(3, int(0.9 * bh))])
        keygold = ((kr >= 100) & (kg >= 85) & (kr - kb >= 30) & (kg - kb >= 15)
                   & (np.abs(kr - kg) <= 45))
        if keygold.size == 0:
            continue
        tall = np.flatnonzero(keygold.sum(axis=0) >= 0.35 * bh)
        if tall.size == 0:
            continue
        ya = y0 + max(2, int(0.06 * bh))
        yb = y0 + int(0.55 * bh)
        # the title starts just right of the key square's right frame
        xa = kx0 + int(tall[-1]) + max(2, int(0.08 * bh))
        xb = x1 - max(2, int(0.03 * bw))
        if yb <= ya or xb <= xa:
            continue
        rr, gg, bb = channels(rgb[ya:yb, xa:xb])
        mx = np.maximum(np.maximum(rr, gg), bb)
        mn = np.minimum(np.minimum(rr, gg), bb)
        pure_white = int((mn >= 236).sum())  # cursor (white); title text is cream
        # cream title text is nearly grey (chroma <= ~30); the gold key frame (~60) is not
        text = (rr >= 140) & (gg >= 130) & (bb >= 100) & (mx - mn <= 45) & (mn < 236)
        box = (x0 + origin[0], y0 + origin[1], x1 + origin[0], y1 + origin[1])
        if pure_white >= 3:
            return PromptReading(None, box, 0.0, "mouse cursor is over the prompt")
        cols = np.flatnonzero(text.sum(axis=0) >= 1)
        if cols.size < 3:
            return PromptReading(None, box, 0.0, "prompt has no title")
        ratio = (cols[-1] - cols[0] + 1) / float(bh)
        if 0.40 <= ratio <= 0.74:
            return PromptReading(PROMPT_CAST, box, ratio, "Cast")
        if 0.78 <= ratio <= 1.20:
            return PromptReading(PROMPT_REEL, box, ratio, "Reel in")
        return PromptReading(None, box, ratio, f"unreadable prompt (ratio {ratio:.2f})")
    if truncated is not None:
        return PromptReading(None, truncated, 0.0, "prompt partly hidden (mouse cursor?)")
    return PromptReading(note="no prompt")


def title_region(geom: "BarGeom") -> Tuple[int, int, int, int]:
    """The reel panel's title ("Reel it in!" / "Something big is pulling!") above the bar."""
    bw, bh = geom.x1 - geom.x0, max(4, geom.y1 - geom.y0)
    cx = (geom.x0 + geom.x1) / 2.0
    top = int(geom.y0 - 2.6 * bh)
    return (int(cx - 0.45 * bw), top, max(1, int(0.9 * bw)), max(1, geom.y0 - top))


def read_title(img: np.ndarray, bar_w: int) -> Optional[bool]:
    """True = "Something big is pulling!", False = "Reel it in!", None = can't tell.
    Measured on real frames: the title is ~0.2 of the bar's width for "Reel it in!"
    and ~0.5 for "Something big is pulling!"."""
    if img is None or img.size == 0 or bar_w <= 0:
        return None
    reg = img.astype(np.int16)
    lum = reg.max(axis=2)
    bright = (lum >= 150) & (lum - reg.min(axis=2) <= 90)    # the cream title / subtitle text
    rows = bright.sum(axis=1)
    border = np.flatnonzero(rows >= 0.6 * reg.shape[1])      # the panel's top edge
    start = int(border[-1]) + 1 if border.size else 0
    text = [i for i in range(start, len(rows)) if rows[i] >= 2]
    if len(text) < 4:
        return None
    a, b = text[0], text[-1]
    top = bright[a:a + max(2, int(0.4 * (b - a + 1)))]      # the upper part = the title line
    cols = np.flatnonzero(top.any(axis=0))
    w = (cols[-1] - cols[0] + 1) / float(bar_w)
    if 0.38 <= w <= 0.75:
        return True
    if 0.10 <= w <= 0.32:
        return False
    return None


# =============================================================================
#  Leviathan alarm - spot a leviathan pull on screen
#
#  Measured from a real recording of a pull (4 windows):
#     announcement  "<name> was pulled into the deep by the Serpent of the ..."
#                   / "Something vast took the bait." - a wide dark panel
#                   (#0E1418-ish) with a thin teal border (#74B9B2 / #2D757B),
#                   two lines of light text, top centre (about 22%..78% of the
#                   width, 10%..25% of the height).  Shown in the windows of
#                   everyone nearby, ~3 s; the pulled player's own window
#                   shows a cut-scene instead.
#     then          every pulled window turns teal (underwater), then black
#                   for a few seconds, then the arena.
#     boss fight    a thin light-blue health bar (#98DCFC -> #1C72B7) in a
#                   gold frame, about 28%..72% of the width, ~15% from the
#                   top, with "The Serpent of the Sea - Lv 250" above it.
# =============================================================================
def _spans(mask_1d: np.ndarray, gap: int) -> List[Tuple[int, int]]:
    """[start, end) runs of True, merging runs split by <= `gap` False pixels."""
    return [(a, b + 1) for a, b in runs(mask_1d, gap)]


def _small(rgb: np.ndarray) -> Tuple[np.ndarray, int]:
    """Every row (the borders are thin horizontal lines), but only every k-th
    column, so a big window costs about as much as a 640 px wide one."""
    k = max(1, int(rgb.shape[1] // 640))
    return rgb[:, ::k].astype(np.int16), k


def _centred_lines(mask: np.ndarray, W: int, min_frac: float, centre_tol: float,
                   gap: int) -> List[Tuple[int, int, int]]:
    """Rows of `mask` holding one long, roughly centred horizontal run: [(y, x0, x1)]."""
    out = []
    for y in np.flatnonzero(mask.sum(axis=1) >= min_frac * W):
        for a, b in _spans(mask[y], gap):
            if b - a >= min_frac * W and abs((a + b) / 2.0 - W / 2.0) <= centre_tol * W:
                out.append((int(y), int(a), int(b)))
    return out


# The game's UI does not grow with the window (in a quarter-screen window the
# panel is ~55% of the width, fullscreen only ~25%), so sizes are checked
# against the panel's own shape, not the window's.
BANNER_ASPECT = 0.137      # panel height / width
BOSS_ASPECT = 0.035        # health bar height / width


def find_pull_banner(rgb: np.ndarray) -> Optional[dict]:
    """The "... was pulled into the deep by the Serpent ..." announcement panel."""
    a, k = _small(rgb)
    H, W = a.shape[:2]
    y0 = int(0.02 * H)
    reg = a[y0:int(0.45 * H)]
    r, g, b = reg[..., 0], reg[..., 1], reg[..., 2]
    teal = (g >= 85) & (b >= 80) & (g - r >= 40) & (b - r >= 35) & (np.abs(g - b) <= 45) & (b < g + 25)
    lines = _centred_lines(teal, W, 0.16, 0.06, max(3, W // 40))
    if not lines:
        return None
    lum = reg.max(axis=2)
    RH = reg.shape[0]
    tried = set()
    for (y, a0, a1) in lines:
        if not (0.18 * W <= a1 - a0 <= 0.80 * W) or a0 < 0.06 * W:
            continue
        wpx = (a1 - a0) * k                       # the panel's width in screen pixels
        for up in (False, True):              # this line is the top border (panel below it) or the bottom one
            other = [yy for (yy, b0, b1) in lines
                     if 0.6 * BANNER_ASPECT * wpx <= ((yy - y) if not up else (y - yy)) <= 1.8 * BANNER_ASPECT * wpx
                     and min(a1, b1) - max(a0, b0) >= 0.6 * (a1 - a0)]
            hgt = (min(other, key=lambda yy: abs(yy - y)) - y) if other else \
                (-1 if up else 1) * int(BANNER_ASPECT * wpx)
            yt, yb = (y, y + hgt) if not up else (y + hgt, y)
            yt, yb = max(0, yt), min(RH - 1, yb)
            key = (yt // 3, yb // 3, a0 // 8)
            if key in tried or yb - yt < max(10, 0.6 * BANNER_ASPECT * wpx):
                continue
            tried.add(key)
            # the panel's left and right edges are teal too
            e = max(5, (a1 - a0) // 40)
            sides = (teal[yt:yb + 1, max(0, a0 - e):a0 + e].any(axis=1).mean()
                     + teal[yt:yb + 1, max(0, a1 - e):a1 + e].any(axis=1).mean()) / 2.0
            if sides < 0.4:
                continue
            m = max(2, (yb - yt) // 12)
            inner_l = lum[yt + m:yb - m + 1, a0 + 3:a1 - 3]
            if inner_l.size == 0:
                continue
            bright = inner_l >= 150
            fb = float(bright.mean())
            if float(np.median(inner_l)) > 60 or not (0.012 <= fb <= 0.35) \
                    or teal[yt + m:yb - m + 1, a0 + 3:a1 - 3].mean() > 0.08:
                continue                      # not a dark panel holding some light text
            rows = bright.mean(axis=1)
            half = len(rows) // 2
            if rows[:half].max(initial=0) < 0.03 or rows[half:].max(initial=0) < 0.02:
                continue                      # two lines of text
            cols = bright.mean(axis=0)
            n = len(cols)
            if cols[n // 4: 3 * n // 4].mean() < 0.6 * cols.mean():
                continue                      # centred text
            return {"y": round((yt + y0) / H, 3), "h": round((yb - yt) / H, 3),
                    "x0": round(a0 / W, 3), "x1": round(a1 / W, 3), "text": round(fb, 3)}
    return None


def find_boss_bar(rgb: np.ndarray) -> Optional[dict]:
    """A boss health bar: thin, wide, light blue, top centre, the boss's name above it."""
    a, k = _small(rgb)
    H, W = a.shape[:2]
    y0 = int(0.03 * H)
    reg = a[y0:int(0.40 * H)]
    r, g, b = reg[..., 0], reg[..., 1], reg[..., 2]
    blue = (b >= 170) & (b - r >= 60) & (g >= 105) & (b >= g + 10)
    # rows holding a long blue run centred in the window (the health number in the middle is bridged)
    ys = np.array(sorted({y for y, _, _ in _centred_lines(blue, W, 0.14, 0.04, max(3, int(0.08 * W)))}), dtype=int)
    if ys.size == 0:
        return None
    bands, cur = [], [int(ys[0])]
    for y in ys[1:]:
        if y - cur[-1] <= 3:
            cur.append(int(y))
        else:
            bands.append(cur)
            cur = [int(y)]
    bands.append(cur)
    lum = reg.max(axis=2)
    for band in bands:
        top, bot = band[0], band[-1]
        hgt = bot - top + 1
        filled = blue[top:bot + 1].mean(axis=0) >= 0.4
        spans = [(s, e) for s, e in _spans(filled, max(3, int(0.08 * W))) if e - s >= 0.14 * W]
        if not spans:
            continue
        x0, x1 = max(spans, key=lambda s: s[1] - s[0])
        wpx = (x1 - x0) * k
        if not (max(4, 0.6 * BOSS_ASPECT * wpx) <= hgt <= 2.5 * BOSS_ASPECT * wpx):
            continue                          # a bar, not a thin line or a big blue area
        if x0 < 0.10 * W or x1 > 0.90 * W or abs((x0 + x1) / 2.0 - W / 2.0) > 0.04 * W:
            continue                          # exactly centred, inside the window (not sky, water or
                                              # Roblox's network-stats bars)
        strip = reg[top:bot + 1, x0:x1].max(axis=2).mean(axis=1)
        third = max(1, len(strip) // 3)
        if strip[:max(1, len(strip) // 2)].max() - strip[-third:].mean() < 25:   # top rows may be dimmed (stats overlay)
            continue                          # the bar shades from light blue (top) to deep blue
        reach = max(4, int(1.5 * hgt))
        above = blue[max(0, top - reach):max(0, top - 2), x0:x1]
        below = blue[bot + 3:bot + reach, x0:x1]
        if (above.size and above.mean() > 0.3) or (below.size and below.mean() > 0.3):
            continue
        name = lum[max(0, top - 4 * hgt):max(0, top - 2), x0:x1] >= 170
        if not name.size or name.mean() < 0.01:
            continue                          # no name above it
        return {"y": round((top + y0) / H, 3), "x0": round(x0 / W, 3), "x1": round(x1 / W, 3)}
    return None


def _view(rgb: np.ndarray, ignore: Optional[Tuple[int, int, int, int]] = None):
    """The view below Roblox's top bar (every 2nd row / k-th column) and which of its
    pixels count: `ignore` = (x0, y0, x1, y1) in `rgb` pixels is covered by something
    else (the AutoFish window).  (None, None) if too little of the view is visible."""
    sx = max(2, int(rgb.shape[1] // 320))
    a = rgb[::2, ::sx]
    H, W = a.shape[:2]
    y0, x0 = int(0.12 * H), int(0.03 * W)
    reg = a[y0:int(0.97 * H), x0:int(0.97 * W)]
    keep = np.ones(reg.shape[:2], dtype=bool)
    if ignore is not None:
        keep[max(0, ignore[1] // 2 - y0):max(0, ignore[3] // 2 - y0 + 1),
             max(0, ignore[0] // sx - x0):max(0, ignore[2] // sx - x0 + 1)] = False
        if keep.mean() < 0.4:
            return None, None
    return reg, keep


def dark_fraction(rgb: np.ndarray, ignore: Optional[Tuple[int, int, int, int]] = None) -> float:
    """How much of the view (below Roblox's top bar) is black - pulled into the deep."""
    reg, keep = _view(rgb, ignore)
    return 0.0 if reg is None else float((reg.max(axis=2) < 32)[keep].mean())


def flood_fraction(rgb: np.ndarray, ignore: Optional[Tuple[int, int, int, int]] = None) -> float:
    """How much of the view is the bright teal of being dragged under water (every pulled
    window shows it just before it goes black - also the hooked player's own window,
    which never shows the announcement)."""
    reg, keep = _view(rgb, ignore)
    if reg is None:
        return 0.0
    r, g, b = (reg[..., i].astype(np.int16) for i in range(3))
    return float(((g >= 70) & (b >= 70) & (g - r >= 40) & (b - r >= 40) & (np.abs(g - b) <= 30))[keep].mean())


class LeviathanWatch:
    """Turns per-window screenshots into alarm events.

    "pull" - the announcement panel, seen twice in a row in one window
    "dark" - after an announcement, a window went black (you are being pulled in)
    "boss" - a boss health bar, seen twice in a row in one window
    One alarm per leviathan: it re-arms once neither the panel nor a boss bar
    has been seen anywhere for REARM_S seconds."""
    HITS = 2
    CONFIRM_S = 45.0
    REARM_S = 90.0
    DARK = 0.90
    FLOOD = 0.5        # pulled under: the view floods bright teal ...
    FLOOD_S = 4.0      # ... and goes black within this long (night scenes are black too, but never teal)

    def __init__(self) -> None:
        self.hits: dict = {}
        self.banner_t: Optional[float] = None
        self.last_seen = -1e9
        self.fired = False
        self.confirmed = False

    def feed(self, name: str, rgb: np.ndarray, now: float,
             ignore: Optional[Tuple[int, int, int, int]] = None) -> List[Tuple[str, str]]:
        if now - self.last_seen > self.REARM_S:
            self.fired, self.confirmed, self.banner_t = False, False, None
        h = self.hits.setdefault(name, {"pull": 0, "boss": 0, "dark": 0})
        events = []
        banner = find_pull_banner(rgb) is not None
        boss = find_boss_bar(rgb) is not None
        h["pull"] = h["pull"] + 1 if banner else 0
        h["boss"] = h["boss"] + 1 if boss else 0
        if banner or boss:
            self.last_seen = now
        if h["pull"] >= self.HITS:
            self.banner_t = now
            if not self.fired:
                self.fired = True
                events.append(("pull", name))
        if h["boss"] >= self.HITS and not self.confirmed:
            self.fired = self.confirmed = True
            events.append(("boss", name))
        if not self.confirmed and flood_fraction(rgb, ignore) >= self.FLOOD:
            h["flood_t"] = now
        if now - h.get("flood_t", -1e9) <= self.FLOOD_S and not self.confirmed:
            h["dark"] = h["dark"] + 1 if dark_fraction(rgb, ignore) >= self.DARK else 0
            if h["dark"] >= self.HITS:
                self.fired = self.confirmed = True
                self.last_seen = now          # (else the re-arm check would undo this on the next look)
                events.append(("dark", name))
        else:
            h["dark"] = 0
        return events


# =============================================================================
#  Timing - predict where the pointer will be when our key press lands
# =============================================================================
class MotionTracker:
    """Follows something that slides left/right (the fish, or the gold zone).

    The game only moves things when it draws a new frame, and we usually look
    at the screen several times per game frame.  So a sample is only stored
    when the value actually changed, stamped with the time we FIRST saw it -
    that is (to within one loop) when the frame appeared, which makes speed
    and position estimates frame-accurate even at 30 fps."""

    def __init__(self, window: float, bounce_cut: bool, eps: float = 0.3) -> None:
        self.window = window
        self.bounce_cut = bounce_cut
        self.eps = eps
        self.samples: deque = deque(maxlen=64)
        self._first: Optional[float] = None   # first value seen (time unknown)

    def reset(self) -> None:
        self.samples.clear()
        self._first = None

    def add(self, t: float, x: float) -> None:
        if not self.samples:
            # the first value we look at may have been on screen for a while
            # (we poll slowly while waiting for a bite), so its time is unknown:
            # start the track at the first CHANGE, which we see within one loop
            if self._first is None or abs(x - self._first) < self.eps:
                self._first = x
                return
        else:
            t0, x0 = self.samples[-1]
            if abs(x - x0) < self.eps or t <= t0:
                return  # same frame as before
        self.samples.append((t, x))

    def last(self) -> Optional[Tuple[float, float]]:
        return self.samples[-1] if self.samples else None

    def velocity(self, now: float, walls: Optional[Tuple[float, float]] = None) -> Optional[float]:
        """Pixels/second, from the most recent run of one-directional motion.

        Right after a bounce that run is short, so with `walls` (where the
        fish turns around) the speed comes from the recent step sizes - the
        fish keeps its speed through a bounce - and a bounce that happened
        between two frames (invisible as a direction change) is detected by
        checking the newest sample against the walls."""
        if len(self.samples) < 2:
            return None
        pts = list(self.samples)
        t_new, x_new = pts[-1]
        if now - t_new > 0.15:
            return 0.0  # nothing has moved for a while
        run = [pts[-1]]
        direction = 0
        turned = False
        for t, x in reversed(pts[:-1]):
            if t_new - t > self.window:
                break
            if self.bounce_cut:
                step = run[-1][1] - x
                if abs(step) >= 0.75:
                    sgn = 1 if step > 0 else -1
                    if direction == 0:
                        direction = sgn
                    elif sgn != direction:
                        turned = True
                        break
            run.append((t, x))
        if turned and len(run) > 1:
            run.pop()  # the sample at the turn is ambiguous: the fish turned around near it
        if walls is None or not self.bounce_cut:
            if len(run) >= 2:
                return _slope(run)
            t0, x0 = pts[-2]
            if t_new - t0 <= 0 or t_new - t0 > 0.25:
                return None
            return (x_new - x0) / (t_new - t0)
        lo, hi = walls
        t_p, x_p = pts[-2]
        if len(run) >= 3:
            v_prev = _slope(run[1:])
            if v_prev is not None and 0 < t_new - t_p < 0.1:
                # did the fish hit a wall between the last two samples?
                x_unf = x_p + v_prev * (t_new - t_p)
                if (x_unf < lo or x_unf > hi) and abs(reflect(x_unf, lo, hi) - x_new) < abs(x_unf - x_new):
                    return -v_prev
            return _slope(run)
        # short run (just bounced): speed from the recent step sizes
        speeds = sorted(abs(xb - xa) / (tb - ta) for (ta, xa), (tb, xb) in zip(pts[:-1], pts[1:])
                        if tb > ta and t_new - ta <= 0.15 and abs(xb - xa) >= 0.75)
        if not speeds or not (0 < t_new - t_p < 0.25):
            return None
        speed = speeds[len(speeds) // 2] if len(speeds) >= 3 else max(speeds)
        v = speed if x_new >= x_p else -speed
        x_unf = x_p + v * (t_new - t_p)
        if (x_unf < lo or x_unf > hi) and abs(reflect(x_unf, lo, hi) - x_new) < abs(x_unf - x_new):
            return -v
        return v


def _slope(pts) -> Optional[float]:
    """Least-squares slope of (t, x) points."""
    n = len(pts)
    if n < 2:
        return None
    mt = sum(u[0] for u in pts) / n
    mx = sum(u[1] for u in pts) / n
    den = sum((u[0] - mt) ** 2 for u in pts)
    if den <= 1e-12:
        return None
    return sum((u[0] - mt) * (u[1] - mx) for u in pts) / den


# kept for compatibility with older test code
PointerTracker = lambda: MotionTracker(window=0.08, bounce_cut=True)  # noqa: E731


def bounce_wall(sm, width: int) -> Optional[Tuple[str, float]]:
    """Look at the last five fish samples (t, x).  If the fish turned around
    at the middle one, work out exactly where it turned: the steps just
    before and just after the turn give its speed, and the two samples around
    the turn then pin down the turning point.  Returns ("lo" | "hi", x)."""
    if len(sm) < 5:
        return None
    (ta, xa), (t0, x0), (t1, x1), (t2, x2), (tb, xb) = list(sm)[-5:]
    d_pre, d1, d2, d_post = x0 - xa, x1 - x0, x2 - x1, xb - x2
    if min(abs(d_pre), abs(d1), abs(d2), abs(d_post)) < 0.75:
        return None
    if not ((d_pre > 0) == (d1 > 0) and (d2 > 0) == (d_post > 0) and (d1 > 0) != (d2 > 0)):
        return None
    if t0 <= ta or tb <= t2 or t2 <= t0:
        return None
    speed = 0.5 * (abs(d_pre) / (t0 - ta) + abs(d_post) / (tb - t2))
    w1 = float(width - 1)
    if d1 > 0 and x1 > 0.75 * w1:      # right end: x0 + x2 = 2*hi - speed*(t2 - t0)
        pos = 0.5 * (x0 + x2 + speed * (t2 - t0))
        return ("hi", min(max(pos, x1), 1.03 * w1))
    if d1 < 0 and x1 < 0.25 * w1:      # left end
        pos = 0.5 * (x0 + x2 - speed * (t2 - t0))
        return ("lo", max(min(pos, x1), -0.03 * w1))
    return None


def reflect(x: float, lo: float, hi: float) -> float:
    """Fold a predicted position back inside [lo, hi] (the pointer bounces)."""
    if hi <= lo:
        return lo
    period = 2.0 * (hi - lo)
    y = (x - lo) % period
    if y > hi - lo:
        y = period - y
    return lo + y


def miss_verdict(info: dict, rd: "MinigameReading", pics, shown_after: Optional[float]) -> str:
    """One line for the log / miss report: did the game judge the press too
    EARLY or too LATE, and by about how much?

    The miss shows up in the very game frame the press was judged in, so the
    fish and the gold zone on that frame are what the game judged.  The
    recorded frames since the key went down show whether the fish had already
    passed the gold centre (late) or not reached it yet (early)."""
    if rd is None or rd.pointer is None or rd.zone is None:
        return ""
    zl, zr = rd.zone
    c, pm = (zl + zr) / 2.0, rd.pointer
    fr = [(pc[0], pc[2], (pc[3][0] + pc[3][1]) / 2.0) for pc in pics if pc[2] is not None and pc[3] is not None]
    t_press = info.get("t")
    if t_press is not None and fr:
        i0 = max((i for i, f in enumerate(fr) if f[0] <= t_press), default=0)
        fr = fr[i0:]                                  # the frame the press was planned on, and later
    steps = sorted(abs(b[1] - a[1]) / (b[0] - a[0]) for a, b in zip(fr, fr[1:]) if b[0] > a[0])
    v_obs = steps[len(steps) // 2] if steps else None
    lead = float(info.get("lead", 0.0))
    tail = (f" Result showed {shown_after * 1000:.0f}ms after key-down; timing used {lead * 1000:.0f}ms."
            if shown_after is not None else "")
    v_used = info.get("v")
    if v_used is not None and v_obs and abs(abs(v_used) - v_obs) > 0.2 * v_obs:
        tail += f" Fish speed was planned as {abs(v_used):.0f}px/s; the frames show ~{v_obs:.0f}px/s."
    where = f"fish {pm:.0f}, gold {zl:.0f}-{zr:.0f}"
    if zl <= pm <= zr:
        return (f"On the judged frame the fish reads INSIDE the gold zone ({where}): the game judged "
                f"a different moment than this frame (see frames.png).{tail}")
    cross = None
    for a, b in zip(fr, fr[1:]):
        ea, eb = a[1] - a[2], b[1] - b[2]
        if ea == 0 or (ea > 0) != (eb > 0):
            cross = a[0] + (b[0] - a[0]) * (ea / (ea - eb) if ea != eb else 0.0)
    t_res = fr[-1][0] if fr else None
    if cross is not None and t_res is not None:
        return (f"Too LATE: the fish passed the gold centre about {(t_res - cross) * 1000:.0f}ms before "
                f"the frame the game judged ({where}).{tail}")
    e0, e1 = (fr[0][1] - fr[0][2], fr[-1][1] - fr[-1][2]) if fr else (0.0, 0.0)
    if fr and abs(e1) > abs(e0):
        return (f"Too LATE: the fish was already past the gold centre when the key went down and "
                f"moving away ({where}).{tail}")
    spd = abs(v_used) if v_used else (v_obs or 0.0)
    ms = f", ~{abs(pm - c) / spd * 1000:.0f}ms" if spd > 1 else ""
    return (f"Too EARLY: the fish had not reached the gold yet - {abs(pm - c):.0f}px{ms} short of the gold "
            f"centre when judged ({where}).{tail}")


def miss_timing_error(info: dict, rd: "MinigameReading", pics) -> Optional[float]:
    """Signed timing error of a missed press in seconds: negative = the game
    judged it too EARLY (fish short of the gold), positive = too LATE."""
    if rd is None or rd.pointer is None or rd.zone is None or not info:
        return None
    zl, zr = rd.zone
    c, pm = (zl + zr) / 2.0, rd.pointer
    if zl <= pm <= zr:
        return None
    fr = [(pc[0], pc[2], (pc[3][0] + pc[3][1]) / 2.0) for pc in pics if pc[2] is not None and pc[3] is not None]
    t_press = info.get("t")
    if t_press is not None and fr:
        i0 = max((i for i, f in enumerate(fr) if f[0] <= t_press), default=0)
        fr = fr[i0:]
    if len(fr) < 2:
        return None
    for a, b in zip(fr, fr[1:]):
        ea, eb = a[1] - a[2], b[1] - b[2]
        if ea == 0 or (ea > 0) != (eb > 0):
            return max(0.0, fr[-1][0] - (a[0] + (b[0] - a[0]) * (ea / (ea - eb) if ea != eb else 0.0)))
    e0, e1 = fr[0][1] - fr[0][2], fr[-1][1] - fr[-1][2]
    if abs(e1) > abs(e0):
        return None  # already past and moving away: can't size it
    spd = abs(info.get("v") or 0.0)
    if spd < 1:
        return None
    return -abs(pm - c) / spd


def plan_press(p: float, v: float, c0: float, hw: float, vz: float, width: int,
               lead: float, margin_frac: float, tau_now: float, dz: float = 0.0,
               horizon: float = 0.30, step: float = 0.0005,
               walls: Optional[Tuple[float, float]] = None) -> Optional[float]:
    """When must the key go down so the game checks the fish at the CENTRE of
    the gold zone?

    p, v   fish position (bar px) when it was seen, and its speed (px/s)
    c0, hw zone centre / half width when seen (dz = how much later than the
           fish it was seen), vz = zone speed (px/s)
    lead   delay between key-down and the game checking the fish (s)
    tau_now  seconds since the fish position p was on screen
    Works for any speed: it predicts the fish (bouncing off the bar ends) and
    the drifting zone a few hundred ms ahead and finds the exact moment they
    meet.  Returns seconds from now until the key should go down (0 = now),
    or None if this is not the moment (yet)."""
    if hw <= 0.5 or width < 4:
        return None
    w1 = float(width - 1)
    safe = max(0.5, hw * (1.0 - 2.0 * margin_frac))
    n = int(horizon / step) + 1
    t = tau_now + lead + np.arange(n) * step          # when the game checks
    lo, hi = walls if walls is not None else (0.0, w1)
    span = max(1.0, hi - lo)
    u = np.mod(p - lo + v * t, 2.0 * span)
    y = lo + np.where(u > span, 2.0 * span - u, u)    # fish, bouncing between its turn points
    if w1 > 2 * hw:
        c = c0 + vz * (t - dz)                        # zone centre: it bounces off the bar ends
        zspan = w1 - 2.0 * hw
        cu = np.mod(c - hw, 2.0 * zspan)
        c = hw + np.where(cu > zspan, 2.0 * zspan - cu, cu)
    else:
        c = np.full(n, w1 / 2.0)
    e = y - c
    sg = np.sign(e)
    hits = np.flatnonzero(sg[:-1] * sg[1:] <= 0)
    if hits.size:
        i = int(hits[0])
        e0, e1 = float(e[i]), float(e[i + 1])
        frac = e0 / (e0 - e1) if e0 != e1 else 0.0
        return (i + frac) * step
    if abs(float(e[0])) <= safe:
        return 0.0   # already past the centre but still well inside: now
    return None


# =============================================================================
#  Platform layer (Windows).  The bot only talks to this interface, so it can
#  be driven by a simulator in tests.
# =============================================================================
class GameEnv:
    def now(self) -> float: return time.perf_counter()
    def sleep(self, s: float) -> None: time.sleep(max(0.0, s))
    def sleep_precise(self, s: float) -> None: self.sleep(s)
    def ensure_focus(self) -> None: pass
    def focus_age(self) -> float: return 1e9
    def game_region(self) -> Optional[Tuple[int, int, int, int]]: raise NotImplementedError
    def is_game_focused(self) -> bool: raise NotImplementedError
    def focus_game(self) -> bool: return False
    def grab(self, region: Tuple[int, int, int, int]) -> np.ndarray: raise NotImplementedError
    def press_key(self, key: str, hold_s: float) -> None: raise NotImplementedError
    def click(self, hold_s: float) -> None: raise NotImplementedError
    def key_down(self, name: str) -> bool: return False
    def send_input(self, key: str, down: bool) -> None:
        """Key (or "click") down/up without blocking.  Default: tap on down."""
        if down:
            if key == "click":
                self.click(0.0)
            else:
                self.press_key(key, 0.0)
    def close(self) -> None: pass


if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    try:
        _winmm = ctypes.WinDLL("winmm")
    except OSError:
        _winmm = None

    ULONG_PTR = ctypes.c_size_t

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

    INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
    KEYEVENTF_KEYUP, KEYEVENTF_SCANCODE = 0x0002, 0x0008
    MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004

    _user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    _user32.SendInput.restype = wintypes.UINT
    _user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
    _user32.MapVirtualKeyW.restype = wintypes.UINT
    _user32.VkKeyScanW.argtypes = (wintypes.WCHAR,)
    _user32.VkKeyScanW.restype = ctypes.c_short
    _user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
    _user32.GetAsyncKeyState.restype = ctypes.c_short
    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
    _user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    _user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
    _user32.FindWindowW.restype = wintypes.HWND
    _user32.GetClientRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    _user32.ClientToScreen.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))
    _user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    _user32.IsIconic.argtypes = (wintypes.HWND,)
    _user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
    _user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)

    _VK_NAMES = {f"F{i}": 0x6F + i for i in range(1, 25)}
    _VK_NAMES.update({"SPACE": 0x20, "INSERT": 0x2D, "DELETE": 0x2E, "HOME": 0x24, "END": 0x23,
                      "PAGEUP": 0x21, "PAGEDOWN": 0x22, "PAUSE": 0x13, "SCROLLLOCK": 0x91,
                      "ENTER": 0x0D, "TAB": 0x09})

    def vk_from_name(name: str) -> Optional[int]:
        name = (name or "").strip()
        if not name:
            return None
        up = name.upper()
        if up in _VK_NAMES:
            return _VK_NAMES[up]
        if len(name) == 1:
            res = _user32.VkKeyScanW(name.lower())
            if res != -1:
                return res & 0xFF
        return None

    def set_dpi_awareness() -> None:
        """Make screen pixels == capture pixels on scaled (125%/150%) displays."""
        try:
            _user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # per-monitor v2
            return
        except Exception:
            pass
        try:
            ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
            return
        except Exception:
            pass
        try:
            _user32.SetProcessDPIAware()
        except Exception:
            pass

    _user32.EnumWindows.argtypes = (ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM),
                                     wintypes.LPARAM)
    _user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    _user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    _user32.AttachThreadInput.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
    _user32.BringWindowToTop.argtypes = (wintypes.HWND,)
    _kernel32 = ctypes.WinDLL("kernel32")
    _FOCUS_LOCK = threading.Lock()

    def window_title(hwnd) -> str:
        n = _user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(n + 1)
        _user32.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value

    def list_game_windows(title: str) -> List[int]:
        """All visible, non-minimised top-level windows with this exact title,
        sorted top-left to bottom-right (so window 1/2/3/4 stay stable)."""
        found = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def cb(hwnd, _):
            try:
                if (_user32.IsWindowVisible(hwnd) and not _user32.IsIconic(hwnd)
                        and window_title(hwnd).strip() == title):
                    found.append(hwnd)
            except Exception:
                pass
            return True
        _user32.EnumWindows(cb, 0)
        out = []
        for h in found:
            rc = wintypes.RECT()
            _user32.GetClientRect(h, ctypes.byref(rc))
            pt = wintypes.POINT(0, 0)
            _user32.ClientToScreen(h, ctypes.byref(pt))
            if rc.right - rc.left >= 200 and rc.bottom - rc.top >= 150:
                out.append((pt.y // 50, pt.x, h))
        return [h for _, _, h in sorted(out)]

    def force_foreground(hwnd) -> bool:
        """Bring a window to the front so it gets our key presses.  Windows only
        lets the foreground process do that, so borrow the foreground thread's
        input state (AttachThreadInput); fall back to an Alt tap."""
        with _FOCUS_LOCK:
            fg = _user32.GetForegroundWindow()
            if fg == hwnd:
                return True
            if _user32.IsIconic(hwnd):
                _user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            me = _kernel32.GetCurrentThreadId()
            other = _user32.GetWindowThreadProcessId(fg, None) if fg else 0
            attached = False
            try:
                if other and other != me:
                    attached = bool(_user32.AttachThreadInput(me, other, True))
                _user32.BringWindowToTop(hwnd)
                _user32.SetForegroundWindow(hwnd)
            finally:
                if attached:
                    _user32.AttachThreadInput(me, other, False)
            if _user32.GetForegroundWindow() == hwnd:
                return True
            # Alt tap: Windows then allows SetForegroundWindow
            down = INPUT(type=INPUT_KEYBOARD)
            down.ki = KEYBDINPUT(0x12, 0, 0, 0, 0)
            up = INPUT(type=INPUT_KEYBOARD)
            up.ki = KEYBDINPUT(0x12, 0, KEYEVENTF_KEYUP, 0, 0)
            arr = (INPUT * 2)(down, up)
            _user32.SendInput(2, arr, ctypes.sizeof(INPUT))
            _user32.SetForegroundWindow(hwnd)
            return _user32.GetForegroundWindow() == hwnd

    class WindowsEnv(GameEnv):
        def __init__(self, settings: Settings, hwnd=None) -> None:
            self.settings = settings
            self._tls = threading.local()
            self._fixed = hwnd                 # one Roblox window of several (multi-window)
            self._hwnd = hwnd
            self._hwnd_checked = 0.0
            if _winmm is not None:
                try:
                    _winmm.timeBeginPeriod(1)  # 1 ms sleep resolution
                except Exception:
                    pass

        # ---- window -------------------------------------------------------
        @staticmethod
        def _title(hwnd) -> str:
            n = _user32.GetWindowTextLengthW(hwnd)
            if n <= 0:
                return ""
            buf = ctypes.create_unicode_buffer(n + 1)
            _user32.GetWindowTextW(hwnd, buf, n + 1)
            return buf.value

        def _game_hwnd(self):
            if self._fixed is not None:
                return self._fixed
            now = time.perf_counter()
            if self._hwnd and now - self._hwnd_checked < 1.0:
                return self._hwnd
            self._hwnd_checked = now
            title = self.settings.window_title or "Roblox"
            fg = _user32.GetForegroundWindow()
            if fg and self._title(fg).strip() == title:
                self._hwnd = fg
            else:
                self._hwnd = _user32.FindWindowW(None, title) or None
            return self._hwnd

        def game_region(self):
            hwnd = self._game_hwnd()
            if hwnd and _user32.IsWindowVisible(hwnd) and not _user32.IsIconic(hwnd):
                rc = wintypes.RECT()
                if _user32.GetClientRect(hwnd, ctypes.byref(rc)):
                    pt = wintypes.POINT(0, 0)
                    _user32.ClientToScreen(hwnd, ctypes.byref(pt))
                    w, h = rc.right - rc.left, rc.bottom - rc.top
                    if w >= 200 and h >= 150:
                        return (pt.x, pt.y, w, h)
            sct = self._mss()
            mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            return (mon["left"], mon["top"], mon["width"], mon["height"])

        def game_window_found(self) -> bool:
            return bool(self._game_hwnd())

        def is_game_focused(self) -> bool:
            fg = _user32.GetForegroundWindow()
            if self._fixed is not None:
                return bool(fg) and fg == self._fixed
            return bool(fg) and self._title(fg).strip() == (self.settings.window_title or "Roblox")

        def ensure_focus(self) -> None:
            """Multi-window: make this window the active one before pressing."""
            if self._fixed is None or _user32.GetForegroundWindow() == self._fixed:
                return
            force_foreground(self._fixed)
            self._focus_since = time.perf_counter()
            self._had_focus = True
            time.sleep(max(0.0, self.settings.focus_settle_ms / 1000.0))

        def focus_age(self) -> float:
            """Seconds since this window became the active one (0 = not active).
            Right after a switch Roblox can handle a key press later than usual."""
            if self._fixed is None:
                return 1e9
            now = time.perf_counter()
            if _user32.GetForegroundWindow() != self._fixed:
                self._had_focus = False
                return 0.0
            if not getattr(self, "_had_focus", False):
                self._had_focus = True
                self._focus_since = now
            return now - getattr(self, "_focus_since", now - 1e9)

        def focus_game(self) -> bool:
            hwnd = self._game_hwnd()
            if not hwnd:
                return False
            try:
                if _user32.IsIconic(hwnd):
                    _user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                return bool(_user32.SetForegroundWindow(hwnd))
            except Exception:
                return False

        # ---- screen -------------------------------------------------------
        def _mss(self):
            # mss handles must be used from the thread that created them
            sct = getattr(self._tls, "sct", None)
            if sct is None:
                import mss  # imported lazily so DPI awareness is set first
                sct = mss.mss()
                self._tls.sct = sct
            return sct

        def grab(self, region):
            left, top, width, height = region
            shot = self._mss().grab({"left": int(left), "top": int(top),
                                     "width": int(width), "height": int(height)})
            bgra = np.frombuffer(shot.bgra, dtype=np.uint8).reshape(shot.height, shot.width, 4)
            return bgra[..., 2::-1]  # BGRA -> RGB view

        # ---- input --------------------------------------------------------
        @staticmethod
        def _send(*inputs) -> None:
            arr = (INPUT * len(inputs))(*inputs)
            _user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))

        def press_key(self, key: str, hold_s: float) -> None:
            self.ensure_focus()
            vk = vk_from_name(key) or 0x45  # default 'E'
            scan = _user32.MapVirtualKeyW(vk, 0)  # MAPVK_VK_TO_VSC
            down = INPUT(type=INPUT_KEYBOARD)
            down.ki = KEYBDINPUT(0, scan, KEYEVENTF_SCANCODE, 0, 0)
            up = INPUT(type=INPUT_KEYBOARD)
            up.ki = KEYBDINPUT(0, scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0, 0)
            self._send(down)
            time.sleep(max(0.0, hold_s))
            self._send(up)

        def click(self, hold_s: float) -> None:
            self.ensure_focus()
            down = INPUT(type=INPUT_MOUSE)
            down.mi = MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, 0)
            up = INPUT(type=INPUT_MOUSE)
            up.mi = MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, 0)
            self._send(down)
            time.sleep(max(0.0, hold_s))
            self._send(up)

        def send_input(self, key: str, down: bool) -> None:
            if down:
                self.ensure_focus()
            inp = INPUT(type=INPUT_MOUSE if key == "click" else INPUT_KEYBOARD)
            if key == "click":
                inp.mi = MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTDOWN if down else MOUSEEVENTF_LEFTUP, 0, 0)
            else:
                vk = vk_from_name(key) or 0x45  # default 'E'
                scan = _user32.MapVirtualKeyW(vk, 0)  # MAPVK_VK_TO_VSC
                flags = KEYEVENTF_SCANCODE | (0 if down else KEYEVENTF_KEYUP)
                inp.ki = KEYBDINPUT(0, scan, flags, 0, 0)
            self._send(inp)

        def sleep_precise(self, s: float) -> None:
            """Sleep `s` seconds to well under a millisecond (OS sleeps overshoot
            by 0.5-2 ms): sleep most of it, spin the rest."""
            end = time.perf_counter() + max(0.0, s)
            if s > 0.002:
                time.sleep(s - 0.0015)
            while time.perf_counter() < end:
                pass

        def key_down(self, name: str) -> bool:
            vk = vk_from_name(name)
            return bool(vk) and bool(_user32.GetAsyncKeyState(vk) & 0x8000)

        def close(self) -> None:
            if _winmm is not None:
                try:
                    _winmm.timeEndPeriod(1)
                except Exception:
                    pass


# =============================================================================
#  The bot - a small state machine driven by what is on screen
# =============================================================================
ST_STOPPED = "Stopped"
ST_START = "Starting"
ST_CAST = "Casting"
ST_WAIT = "Waiting for a bite"
ST_REEL = "Reeling"
ST_AFTER = "Catch finished"
ST_PAUSED = "Paused"


@dataclass
class Stats:
    caught: int = 0
    lost: int = 0
    hits: int = 0
    misses: int = 0
    casts: int = 0
    bites: int = 0
    presses: int = 0
    skipped: int = 0               # unwanted fish skipped (skip_fish)
    started_at: float = 0.0
    run_time: float = 0.0


class FishingBot:
    FULL_SCAN_IDLE = 0.20      # full-window scan rate when the bar position is unknown
    FULL_SCAN_KNOWN = 0.50     # ... when we already know where the bar appears
    END_GRACE = 0.35           # bar must be gone this long before the round is over
    PROMPT_WAIT = 2.0          # wait this long for the Cast prompt before casting blind
    VERIFY_AFTER = 1.5         # check that a cast "took" after this long
    PROMPT_SETTLE = 0.35       # ignore prompt readings this soon after a key press

    def __init__(self, settings: Settings, env: GameEnv,
                 log: Optional[Callable[[str], None]] = None, name: str = "") -> None:
        self.name = name                     # "Window 2" etc. when fishing in several windows
        self.ignore_focus = False            # multi-window: the controller handles focus
        self.focus_gate: Optional[Callable[[], bool]] = None  # parallel: may I press right now?
        self.plan_at: Optional[float] = None  # parallel: when this window wants its next reel press
        self.stopped_by_miss = False
        self.s = settings
        self.env = env
        self._log_cb = log or (lambda m: print(m))
        self.running = False
        self.alive = True
        self.state = ST_STOPPED
        self.detail = ""
        self.stats = Stats()
        self.lock = threading.Lock()
        self.geom: Optional[BarGeom] = None
        self.tracker = MotionTracker(window=0.08, bounce_cut=True)
        self.ztracker = MotionTracker(window=0.15, bounce_cut=False)
        self._held: Optional[str] = None      # key currently held down
        self._release_at = 0.0
        self._fb_t: Optional[float] = None    # press waiting for its hit/miss to show
        self._fb_hist: deque = deque(maxlen=15)  # measured press -> result delays (s)
        self._fb_hist_fresh: deque = deque(maxlen=15)  # ... for presses right after a window switch
        self._fb_fresh = False
        self._lead_adj = 0.0                     # correction learned from early/late misses
        self._armed = True
        self._outcome_seen = True
        self._strip = None                    # (time, image, origin) of the last strip grab
        self._rec: deque = deque(maxlen=900)  # flight recorder: one entry per reel tick
        self._rec_imgs: deque = deque(maxlen=150)  # ... and pictures of the last game frames
        self._geom_seen: deque = deque(maxlen=9)
        self._walls_lo: deque = deque(maxlen=9)   # where the fish turns around (bar px)
        self._walls_hi: deque = deque(maxlen=9)
        self._geom_check_t = -1e9
        self.region: Optional[Tuple[int, int, int, int]] = None
        self._region_t = -1e9
        self._last_full = -1e9
        self._loop_dt = 0.01
        self._last_tick = None
        self._reset_round()
        self.prompt = PromptReading()
        self.prompt_t = -1e9
        self.prompt_hist: deque = deque(maxlen=4)  # (time, state) of recent readings
        self._noprompt_since: Optional[float] = None  # since when no Cast/Reel prompt at all is on screen
        self._equip_tries = 0
        self._equip_t = -1e9
        self._last_key_t = -1e9
        self._state_t = 0.0
        self._cast_t = 0.0
        self._cast_retries = 0
        self._verified = False
        self._timeouts = 0
        self._paused_since = None
        self.last_reading: Optional[MinigameReading] = None
        self.debug_request = False

    # ---------------------------------------------------------------- utils
    def log(self, msg: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self._log_cb(f"[{stamp}] " + (f"{self.name}: " if self.name else "") + msg)

    def _set_state(self, st: str, detail: str = "") -> None:
        if st != self.state:
            self.state = st
            self._state_t = self.env.now()
        self.detail = detail

    def _reset_round(self) -> None:
        self.round_seen_t = None
        self.round_last_visible = -1e9
        self.round_filled = 0
        self.round_total = 0
        self._totals = {}
        self.round_misses = 0
        self.round_presses = 0
        self.last_press_t = -1e9
        self.tracker = MotionTracker(window=0.08, bounce_cut=True)
        self.ztracker = MotionTracker(window=0.15, bounce_cut=False)
        self._fb_t = None
        self._armed = True
        self._outcome_seen = True
        self._rec.clear()
        self._rec_imgs.clear()
        self._last_press_info = None
        self.round_skip = False      # not a fish we want: unequip/re-equip (or miss on purpose), recast fast
        self._skip_stage = 0         # 0 = not started, 1 = unequipped, 2 = re-equipped, 3 = missing on purpose
        self._skip_t = -1e9
        self._big = {}               # title votes: True = "Something big is pulling!"
        self._decided = False

    def start(self) -> None:
        with self.lock:
            if self.running:
                return
            self.running = True
            self.stopped_by_miss = False
            self.stats.started_at = self.env.now()
            self._reset_round()
            self._timeouts = 0
            self._cast_retries = 0
            self.prompt_t = -1e9
            self.prompt_hist.clear()
            self._set_state(ST_START, "looking at the screen...")
        self.log("Started.")

    def stop(self) -> None:
        with self.lock:
            if not self.running:
                return
            self.running = False
            self.stats.run_time += self.env.now() - self.stats.started_at
            self._set_state(ST_STOPPED, "")
        self._release_key()
        self.log("Stopped.")

    def toggle(self) -> None:
        if self.running:
            self.stop()
        else:
            self.start()

    def snapshot(self) -> dict:
        with self.lock:
            st = Stats(**asdict(self.stats))
            if self.running:
                st.run_time += self.env.now() - st.started_at
            return {"state": self.state, "detail": self.detail, "stats": st,
                    "running": self.running, "lead_ms": self.current_lead() * 1000.0,
                    "lead_auto": self.lead_is_measured()}

    def lead_is_measured(self) -> bool:
        return bool(self.s.auto_lead and len(self._fb_hist) >= 1)

    def walls(self, width: int) -> Tuple[float, float]:
        """Where the fish turns around: learned from bounces, else a default
        (its centre stops about half a fish short of the bar's ends)."""
        w1 = float(width - 1)
        lo = float(np.median(self._walls_lo)) if self._walls_lo else 0.012 * w1
        hi = float(np.median(self._walls_hi)) if self._walls_hi else 0.985 * w1
        if hi - lo < 0.5 * w1:
            return 0.0, w1
        return lo, hi

    FRESH_FOCUS_S = 0.35

    def current_lead(self, fresh: bool = False) -> float:
        """Seconds between our key-down and the game checking the fish.
        `fresh`: the window only just became active (Roblox may react later)."""
        if fresh and self.s.auto_lead and self._fb_hist_fresh:
            d = sorted(self._fb_hist_fresh)
            return min(0.3, max(0.0, d[len(d) // 2] + self._lead_adj))
        if self.lead_is_measured():
            d = sorted(self._fb_hist)
            n = len(d)
            med = d[n // 2] if n % 2 else 0.5 * (d[n // 2 - 1] + d[n // 2])
            return min(0.25, max(0.0, med + self._lead_adj))
        if self.s.auto_lead and self.s.measured_lead2_ms > 0:
            return min(0.25, max(0.0, self.s.measured_lead2_ms / 1000.0 + self._lead_adj))
        return max(0.0, self.s.lead_ms / 1000.0 + self._lead_adj)

    def _press(self, why: str, reel: bool = False, key: Optional[str] = None) -> None:
        """Key down now; the key is released by a later tick (never blocks)."""
        self._release_key()
        self._last_key_t = self.env.now()
        self.stats.presses += 1
        if self.s.dry_run:
            self.log(f"(dry run) would press for: {why}")
            return
        if key is None:
            key = "click" if (reel and self.s.reel_with_click) else (self.s.key or "e")
        self.env.send_input(key, True)
        self._held = key
        self._release_at = self._last_key_t + max(0.0, self.s.key_hold_ms / 1000.0)

    def _release_key(self, now: Optional[float] = None) -> None:
        if self._held is None:
            return
        if now is not None and now < self._release_at:
            return
        key, self._held = self._held, None
        try:
            self.env.send_input(key, False)
        except Exception as exc:
            self.log(f"Could not release the key: {exc!r}")

    # ------------------------------------------------------------- sensing
    def _refresh_region(self, now: float) -> None:
        if self.region is None or now - self._region_t > 2.0:
            reg = self.env.game_region()
            if reg != self.region and reg is not None:
                if self.region is not None:
                    self.log(f"Game area changed to {reg[2]}x{reg[3]} at ({reg[0]},{reg[1]}).")
                self.geom = None  # window moved/resized: find the bar again
            self.region = reg
            self._region_t = now

    def _full_scan(self, now: float) -> Optional[MinigameReading]:
        """Grab the whole game area: (re)locate the bar and read the prompt."""
        self._last_full = now
        img = self.env.grab(self.region)
        ox, oy = self.region[0], self.region[1]
        geom = locate_bar(img, (ox, oy))
        reading = None
        if geom is not None:
            reading = read_minigame(img, geom, (ox, oy))
            if reading.visible:  # only trust a bar that reads like a real minigame
                if self.geom is None or (abs(geom.x0 - self.geom.x0) > 3 or abs(geom.y0 - self.geom.y0) > 3
                                         or abs(geom.w - self.geom.w) > 4):
                    self.log(f"Found the reel bar: {geom.w}x{geom.h}px at ({geom.x0},{geom.y0}).")
                    self._walls_lo.clear()
                    self._walls_hi.clear()
                self.geom = geom
        if reading is None or not reading.visible:
            pr = read_prompt(img, (ox, oy))
            if now - self._last_key_t >= self.PROMPT_SETTLE:
                self.prompt = pr
                self.prompt_t = now
                self.prompt_hist.append((now, pr.state))
                if pr.state is None and pr.box is None:      # no prompt box at all (not just hidden)
                    if self._noprompt_since is None:
                        self._noprompt_since = now
                else:
                    self._noprompt_since = None
                    self._equip_tries = 0
        else:
            self._noprompt_since = None
        return reading

    def _strip_scan(self) -> Optional[MinigameReading]:
        if self.geom is None:
            return None
        reg = self.geom.strip_region()
        img = self.env.grab(reg)
        self._strip = (self.env.now(), img, (reg[0], reg[1]))
        return read_minigame(img, self.geom, (reg[0], reg[1]))

    def _fresh_prompt(self, since: float, need: int = 2) -> Optional[str]:
        """Prompt state if it was read after `since`, else 'unknown' (None)."""
        since = max(since, self._last_key_t + self.PROMPT_SETTLE)
        recent = [st for (t, st) in self.prompt_hist if t >= since]
        # (normally) two readings in a row must agree before we act on them
        if len(recent) >= need and all(r == recent[-1] for r in recent[-need:]):
            return recent[-1]
        return None

    # ---------------------------------------------------------------- loop
    def run_forever(self) -> None:
        while self.alive:
            if not self.running:
                self.env.sleep(0.05)
                continue
            try:
                delay = self.tick()
            except Exception as exc:
                self.log(f"Error (continuing): {exc!r}")
                traceback.print_exc()
                delay = 0.5
            if delay > 0:
                self.env.sleep(delay)

    def tick(self) -> float:
        env, s = self.env, self.s
        now = env.now()
        self._release_key(now)

        # ---- safety: only act while the game is the active window
        if s.require_focus and not self.ignore_focus and not env.is_game_focused():
            if self._paused_since is None:
                self._paused_since = now
                self.log("Roblox is not the active window - paused (click into the game).")
            self.detail = "waiting for the Roblox window to be active"
            return 0.1
        if self._paused_since is not None:
            # don't let the time spent paused count towards timeouts
            paused = now - self._paused_since
            self._cast_t += paused
            self._state_t += paused
            self._paused_since = None
            self.prompt_t = -1e9
            self.prompt_hist.clear()
            self.log("Roblox active again - resuming.")

        self._refresh_region(now)
        if self.region is None:
            self.detail = "game window not found"
            return 0.5

        reading = self._strip_scan()
        interval = self.FULL_SCAN_IDLE if self.geom is None else self.FULL_SCAN_KNOWN
        if self.state in (ST_START, ST_AFTER) or (self.state == ST_WAIT and not self._verified):
            interval = min(interval, 0.05 if s.leviathan else 0.15)  # we want fresh prompt readings here
        if (reading is None or not reading.visible) and now - self._last_full >= interval:
            full = self._full_scan(now)
            if full is not None and full.visible:
                reading = full
        self.last_reading = reading

        if reading is not None and reading.visible:
            return self._on_minigame(now, reading)
        return self._on_no_minigame(now)

    # -------------------------------------------------------------- reeling
    def _on_minigame(self, now: float, rd: MinigameReading) -> float:
        s = self.s
        if self.state != ST_REEL and now - getattr(self, "_skip_end_t", -1e9) < 2.0:
            # the same fish is still on the line after the skip: miss it on purpose instead
            self._reset_round()
            self.round_seen_t = now
            self.round_skip, self._skip_stage, self._decided = True, 3, True
            self._skip_end_t = -1e9
            self._set_state(ST_REEL)
            self.log("The fish is still on the line after the skip - missing on purpose instead.")
        if self.state != ST_REEL:
            joined = self.state == ST_START
            self._reset_round()
            self.round_seen_t = now
            self._timeouts = 0
            if joined and (rd.filled or rd.misses):
                # started (or restarted with F6) while a minigame was already
                # running: the dots / red boxes already on screen are not ours
                self.round_filled, self.round_misses = rd.filled, rd.misses
                self.log(f"Joined a minigame in progress ({rd.filled} hit(s), {rd.misses} miss(es) already "
                         "on screen - not counted).")
            else:
                waited = now - self._cast_t if self.state == ST_WAIT else 0
                self.stats.bites += 1
                if s.leviathan:
                    self.log(f"Bite #{self.stats.bites} (Leviathan mode: missing on purpose)"
                             + (f" after {waited:.1f}s" if waited else ""))
                else:
                    self.log("Fish hooked! Reeling..." + (f" (bite after {waited:.1f}s)" if waited else ""))
        self._set_state(ST_REEL)
        self.round_last_visible = now

        # progress: a dot filled = hit, a red box = miss
        hit = rd.filled > self.round_filled
        miss = rd.misses > self.round_misses
        if hit:
            self.stats.hits += rd.filled - self.round_filled
            self.round_filled = rd.filled
            self.ztracker.reset()  # the zone shrinks / turns around after a hit
        if rd.total:
            self._totals[rd.total] = self._totals.get(rd.total, 0) + 1
            self.round_total = max(self._totals, key=self._totals.get)
        if s.skip_fish and not s.leviathan and not self._decided:
            self._decide_keep(now)
        fast = s.leviathan or self.round_skip
        if miss:
            self.stats.misses += rd.misses - self.round_misses
            self.round_misses = rd.misses
        shown_after = None
        if hit or miss:
            self._outcome_seen = True
            if self._fb_t is not None:
                # how long from our key-down until the game showed the result:
                # that is exactly the lead we have to plan with
                d = now - self._fb_t
                shown_after = d
                if 0.0 < d < 0.4:
                    if self._fb_fresh:
                        self._fb_hist_fresh.append(d)   # don't let a slow first press skew the rest
                    else:
                        self._fb_hist.append(d)
                        if self.lead_is_measured():
                            med = sorted(self._fb_hist)[len(self._fb_hist) // 2]
                            self.s.measured_lead2_ms = round(med * 1000.0, 1)
                self._fb_t = None
        elif self._fb_t is not None and now - self._fb_t > 0.5:
            self._fb_t = None

        # flight recorder (what the bot saw, for miss reports)
        ev = "hit" if hit else ("MISS" if miss else "")
        self._rec.append((now, rd.pointer, rd.zone, rd.filled, rd.misses, ev))
        if self._strip is not None and self._strip[0] >= now and (
                not self._rec_imgs or ev or rd.pointer != self._rec_imgs[-1][2]):
            # new game frame (+ the bar's x0 it was read with: the geometry can be refined later)
            self._rec_imgs.append((now, self._strip, rd.pointer, rd.zone, ev, self.geom.x0))
            while now - self._rec_imgs[0][0] > 1.2:   # a report needs < 1 s; keep memory small
                self._rec_imgs.popleft()

        if miss and fast:
            miss = False  # intended
            self._outcome_seen = True
        if miss:
            info = self._last_press_info
            # ours = a press of this bot can have caused it (not a dry run, not a
            # red box that was already there, not someone pressing by hand)
            ours = (not s.dry_run) and (self.round_presses > 0 or now - self._last_key_t < 0.6)
            where = (f"fish now at {rd.pointer:.0f}" if rd.pointer is not None else "fish not seen")
            if rd.zone is not None:
                where += f", gold now {rd.zone[0]:.0f}-{rd.zone[1]:.0f}"
            if info is not None and ours:
                self.log(f"MISS: pressed with fish at {info['p']:.0f} ({info['v']:+.0f}px/s), gold "
                         f"{info['zl']:.0f}-{info['zr']:.0f}, timing {info['lead'] * 1000:.0f}ms; "
                         f"result showed {('%.0fms' % (shown_after * 1000)) if shown_after else '?'} later, {where}.")
                verdict = miss_verdict(info, rd, list(self._rec_imgs), shown_after)
                if verdict:
                    self.log("  " + verdict)
                err = miss_timing_error(info, rd, list(self._rec_imgs))
                if err is not None and s.auto_lead:
                    step = max(-0.06, min(0.06, err)) * 0.8
                    self._lead_adj = max(-0.15, min(0.15, self._lead_adj + step))
                    self.log(f"  Timing corrected by {step * 1000:+.0f}ms "
                             f"(now {self.current_lead() * 1000:.0f}ms).")
            elif ours:
                self.log(f"MISS right after a cast / recovery key press (no reel press this round; {where}).")
            else:
                self.log(f"A miss showed up that AutoFish did not press for "
                         f"({'dry run' if s.dry_run else 'pressed by hand?'}; {where}).")
            if s.stop_on_miss and ours:
                self.stopped_by_miss = True
                self._release_key()   # never hold the key while the report is written
                snap = self._miss_snapshot(now, rd, shown_after)
                self.stop()           # before the (slow) report: the GUI shows Stopped at once
                path = None
                try:
                    path = self.save_miss_report(now, snap)
                except Exception as exc:
                    self.log(f"Could not save the miss report: {exc!r}")
                self.log("Stopped on the first miss (untick 'Stop on the first miss' to keep going)."
                         + (f" Report: {path}" if path else ""))
                return 0.05

        # refine the bar's ends while reeling (the fish can hide an end of the
        # bar on the very first look): median of several measurements
        if self._strip is not None and now - self._geom_check_t > 0.3:
            self._geom_check_t = now
            t_s, simg, sorg = self._strip
            g2 = locate_bar(np.asarray(simg), sorg)
            if g2 is not None and abs(g2.y0 - self.geom.y0) <= 2 and abs(g2.y1 - self.geom.y1) <= 2:
                self._geom_seen.append(g2)
                if len(self._geom_seen) >= 3:
                    med = BarGeom(int(np.median([g.x0 for g in self._geom_seen])),
                                  int(np.median([g.x1 for g in self._geom_seen])),
                                  self.geom.y0, self.geom.y1)
                    if abs(med.x0 - self.geom.x0) >= 2 or abs(med.x1 - self.geom.x1) >= 2:
                        self._rec.append((now, None, None, None, None,
                                          f"BAR ENDS REFINED x {self.geom.x0}-{self.geom.x1} -> {med.x0}-{med.x1} "
                                          f"(fish/gold columns above and below differ by {self.geom.x0 - med.x0:+d}px)"))
                        self.geom = med
                        self.tracker.reset()   # bar-local coordinates changed
                        self.ztracker.reset()
                        self._walls_lo.clear()
                        self._walls_hi.clear()
                        return 0.0

        if self._last_tick is not None:
            dt = now - self._last_tick
            if 0 < dt < 0.1:
                self._loop_dt = 0.8 * self._loop_dt + 0.2 * dt
        self._last_tick = now
        if rd.pointer is not None:
            n_before = len(self.tracker.samples)
            self.tracker.add(now, rd.pointer)
            if len(self.tracker.samples) != n_before or len(self.tracker.samples) == self.tracker.samples.maxlen:
                if len(self.tracker.samples) >= 5:
                    wb = bounce_wall(self.tracker.samples, rd.width)
                    if wb is not None:
                        (self._walls_lo if wb[0] == "lo" else self._walls_hi).append(wb[1])
        if rd.zone is not None:
            self.ztracker.add(now, (rd.zone[0] + rd.zone[1]) / 2.0)
        zl, zr = rd.zone if rd.zone else (0, 0)
        self.detail = (f"fish {rd.pointer if rd.pointer is not None else -1:5.0f}  "
                       f"gold {zl:4.0f}-{zr:4.0f}  dots {self.round_filled}/{self.round_total or '?'}")

        # ready for the next press?  (one press per pass through the zone)
        since = now - self.last_press_t
        if not self._armed:
            inside = (rd.pointer is not None and rd.zone is not None
                      and rd.zone[0] <= rd.pointer <= rd.zone[1])
            if (since >= s.min_press_gap_s and (self._outcome_seen or since > 0.25)
                    and (not inside or since > 0.6)):
                self._armed = True
        self.plan_at = None
        if self.round_skip and self._skip_stage < 3:
            return self._skip_step(now)
        if fast:
            return self._leviathan_press(now, rd)
        if s.skip_fish and not s.leviathan and not self._decided:
            return 0.0                  # not sure yet whether this fish is worth it: don't press
        if not self._armed or rd.pointer is None or rd.zone is None:
            return 0.0

        fish = self.tracker.last()
        walls = self.walls(rd.width)
        v = self.tracker.velocity(now, walls)
        if fish is None or v is None:
            return 0.0
        zone_t = self.ztracker.last()
        vz = self.ztracker.velocity(now) or 0.0
        t_fish, p = fish
        c0 = (zl + zr) / 2.0
        dz = (zone_t[0] - t_fish) if zone_t is not None else 0.0
        if zone_t is not None:
            c0 = zone_t[1]
        fresh = self.env.focus_age() < self.FRESH_FOCUS_S
        wait = plan_press(p, v, c0, (zr - zl) / 2.0, vz, rd.width, self.current_lead(fresh),
                          s.zone_margin_pct / 100.0, self.env.now() - t_fish, dz, walls=walls)
        if wait is not None:
            self.plan_at = self.env.now() + wait
        if wait is None or wait > min(0.04, max(1.5 * self._loop_dt, 0.004)):
            return 0.0  # not yet - look again
        if self.focus_gate is not None and not self.focus_gate():
            return 0.0  # no keyboard here right now: skip this pass, the next one comes soon
        self.plan_at = None
        if wait > 0:
            self.env.sleep_precise(wait)  # sub-frame precise timing
        self._armed = False
        self._outcome_seen = False
        self.round_presses += 1
        lead = self.current_lead(fresh)
        self._fb_fresh = fresh
        self._press(f"fish at {p:.0f} ({v:+.0f}px/s), gold {zl:.0f}-{zr:.0f}", reel=True)
        self.last_press_t = self._last_key_t
        # (a dry run presses nothing: a result showing now was someone else's press)
        self._fb_t = None if s.dry_run else self._last_key_t
        self._last_press_info = dict(t=self._last_key_t, p=p, t_fish=t_fish, v=v, zl=zl, zr=zr, c0=c0,
                                     vz=vz, dz=dz, lead=lead, wait=wait, loop_dt=self._loop_dt,
                                     tau=self._last_key_t - t_fish, walls=walls, width=rd.width)
        self._rec.append((self._last_key_t, None, None, None, None,
                          f"KEY DOWN (planned wait {wait * 1000:.1f}ms, timing {lead * 1000:.0f}ms)"))
        return 0.0  # reel as fast as the screen can be read

    def _decide_keep(self, now: float) -> None:
        """Reel this fish, or skip it?  Decided from the number of dots and the
        panel title, each read on a few frames (or after 0.5 s with what we have)."""
        s = self.s
        if self.geom is not None and sum(self._big.values()) < 5:
            try:
                big = read_title(self.env.grab(title_region(self.geom)), self.geom.x1 - self.geom.x0)
            except Exception:
                big = None
            if big is not None:
                self._big[big] = self._big.get(big, 0) + 1
        votes_t = self._totals.get(self.round_total, 0) if self.round_total else 0
        votes_b = sum(self._big.values())
        late = self.round_seen_t is not None and now - self.round_seen_t > 0.5
        if not ((votes_t >= 3 and votes_b >= 3) or late):
            return
        self._decided = True
        if self.round_filled > 0:
            return                      # already hit it: finish the job
        try:
            keep_hits = {int(x) for x in re.findall(r"\d+", s.keep_hits or "")}
        except ValueError:
            keep_hits = set()
        big = self._big.get(True, 0) > self._big.get(False, 0)
        hits_ok = (self.round_total in keep_hits) if self.round_total else False
        if hits_ok and (big or not s.keep_only_big):
            self.log(f"{self.round_total}-hit fish" + (" - Something big is pulling!" if big else "") + " - reeling it.")
            return
        self.round_skip = True
        self._skip_stage = 0
        self.stats.skipped += 1
        what = (f"{self.round_total}-hit" if self.round_total else "unreadable") + (" 'something big'" if big else "")
        self.log(f"{what} fish - skipping it (unequip/re-equip with '{s.skip_key}', recast).")

    def _skip_step(self, now: float) -> float:
        """Skip the fish: rod key (unequip), rod key again (equip); the round then
        ends and the bot recasts at once.  If the minigame doesn't go away, it
        falls back to missing on purpose."""
        s = self.s
        key = (s.skip_key or "3").strip() or "3"
        if self._skip_stage == 2:
            if now - self._skip_t > 2.5:
                self._skip_stage = 3    # unequipping didn't end it: deliberate misses instead
                self.log(f"The minigame is still up after unequipping - missing on purpose instead.")
            return 0.0
        wait = 0.0 if self._skip_stage == 0 else self._skip_t + max(0.1, s.skip_key_gap_s) - now
        if wait > 0:
            return min(wait, 0.05)
        self.plan_at = now
        if self.focus_gate is not None and not self.focus_gate():
            return 0.0                  # another window has the keyboard: the controller will switch here
        self.plan_at = None
        self._press("unequip rod" if self._skip_stage == 0 else "re-equip rod", key=key)
        self._skip_stage += 1
        self._skip_t = self._last_key_t
        self.last_press_t = self._last_key_t
        self._fb_t = None
        return 0.0

    def _leviathan_press(self, now: float, rd: MinigameReading) -> float:
        """Leviathan mode: the bite is all that matters, so end the round fast
        with deliberate misses: press whenever the fish is well away from the
        gold zone (one press per result, so every press counts as a miss)."""
        if rd.pointer is None or rd.zone is None:
            return 0.0
        since = now - self.last_press_t
        if not self._armed:
            if since >= 0.12 and (self._outcome_seen or since > 0.35):
                self._armed = True
            else:
                return 0.0
        zl, zr = rd.zone
        hw = (zr - zl) / 2.0
        safe = hw + max(0.12 * rd.width, hw)   # far outside the gold, even after our input lag
        if abs(rd.pointer - (zl + zr) / 2.0) < safe:
            return 0.0
        self.plan_at = now
        if self.focus_gate is not None and not self.focus_gate():
            return 0.0  # another window has the keyboard: the controller will switch here
        self.plan_at = None
        self._armed = False
        self._outcome_seen = False
        self.round_presses += 1
        self._press(f"leviathan miss (fish at {rd.pointer:.0f}, gold {zl:.0f}-{zr:.0f})", reel=True)
        self.last_press_t = self._last_key_t
        self._fb_t = None
        return 0.0

    # ------------------------------------------------------- not reeling
    def _on_no_minigame(self, now: float) -> float:
        s = self.s
        if self.state == ST_REEL:
            if self.round_skip and self._skip_stage == 1:
                return self._skip_step(now)   # the bar went away after unequipping: equip the rod again
            skipped = self.round_skip
            if now - self.round_last_visible < (0.15 if (s.leviathan or skipped) else self.END_GRACE):
                return 0.0
            # round over
            if self.round_total and self.round_filled >= self.round_total:
                self.stats.caught += 1
                self.log(f"Caught it! ({self.round_filled}/{self.round_total}, {self.round_misses} missed)"
                         f"  total caught: {self.stats.caught}")
            elif s.leviathan:
                self.log(f"Round ended ({self.round_misses} deliberate misses) - recasting.")
            elif skipped:
                self.log("Skipped it - recasting.")
            elif self.round_misses >= 3:
                self.stats.lost += 1
                self.log(f"The fish got away ({self.round_misses} misses).")
            else:
                if self.round_total == 0 and self.round_misses < 3:
                    self.stats.caught += 1  # progress dots unreadable: assume success
                self.log(f"Round over ({self.round_filled}/{self.round_total or '?'} hits, "
                         f"{self.round_misses} misses).")
            self._reset_round()
            self._last_tick = None
            self._set_state(ST_AFTER, "getting ready to cast")
            self._quick_recast = skipped          # a skipped fish: recast straight away
            self._skip_end_t = now if skipped else -1e9
            return 0.02

        if self.state == ST_START:
            self._set_state(ST_AFTER, "checking the prompt")
            self._state_t = now - s.recast_delay_s  # no delay on the very first cast
            return 0.0

        if self.state == ST_AFTER:
            elapsed = now - self._state_t
            quick = s.leviathan or getattr(self, "_quick_recast", False)
            delay = 0.0 if quick else s.recast_delay_s   # Leviathan / skipped fish: recast the moment we can
            if elapsed < delay:
                self.detail = f"recasting in {delay - elapsed:.1f}s"
                return 0.03
            prompt = self._fresh_prompt(self._state_t + delay - 0.2, need=1 if s.leviathan else 2)
            if prompt == PROMPT_REEL:
                self.log("Line is already in the water - waiting for a bite.")
                self._cast_t = now
                self._verified = True
                self._set_state(ST_WAIT)
                return 0.02
            if prompt != PROMPT_CAST and self._rod_missing(now):
                self._state_t = now - delay       # look for the Cast prompt again from now
                return 0.05
            if prompt == PROMPT_CAST or elapsed >= delay + (0.8 if s.leviathan else self.PROMPT_WAIT):
                if prompt != PROMPT_CAST:
                    why = self.prompt.note or "no prompt"
                    self.log(f"Casting without seeing the Cast prompt ({why}).")
                self._do_cast(now)
                return 0.02
            self.detail = "looking for the Cast prompt"
            return 0.01 if s.leviathan else 0.03

        if self.state == ST_WAIT:
            waited = now - self._cast_t
            self.detail = f"waiting for a bite... {waited:.0f}s"
            if waited >= 1.0 and self._noprompt_since is not None and self._noprompt_since >= self._cast_t \
                    and self._rod_missing(now):
                self._set_state(ST_AFTER, "rod equipped - casting")   # (the cast went nowhere)
                self._state_t = now - s.recast_delay_s
                return 0.05
            if not self._verified and waited >= self.VERIFY_AFTER:
                prompt = self._fresh_prompt(self._cast_t + 0.6)
                if prompt == PROMPT_REEL:
                    self._verified = True
                elif prompt == PROMPT_CAST:
                    if self._cast_retries < 3:
                        self._cast_retries += 1
                        self.log("The cast did not go out - casting again.")
                        self._do_cast(now, retry=True)
                        return 0.02
                    self._verified = True  # give up checking; timeout will handle it
                elif waited >= self.VERIFY_AFTER + 2.0:
                    self._verified = True  # can't see the prompt; trust the cast
            elif self._verified and waited >= self.VERIFY_AFTER:
                # The line can come back in while we wait (the fish got away while
                # the game was in the background, a cast that got reeled in...):
                # three "Cast" readings in a row -> cast again instead of idling
                # until the bite timeout.
                since = max(self._cast_t + 0.6, self._last_key_t + self.PROMPT_SETTLE)
                recent = [st for (t, st) in self.prompt_hist if t >= since]
                if len(recent) >= 3 and all(st == PROMPT_CAST for st in recent[-3:]):
                    self.log("The Cast prompt is showing - the line is not out. Casting.")
                    self._do_cast(now)
                    return 0.02
            if waited >= s.bite_timeout_s:
                return self._on_bite_timeout(now)
            return 0.02

        # unknown state -> behave like a fresh start
        self._set_state(ST_AFTER)
        return 0.02

    def _rod_missing(self, now: float) -> bool:
        """No Cast/Reel prompt and no minigame for a while: the rod is probably not in
        hand (e.g. a skip's re-equip didn't register).  Press the rod key to equip it.
        Returns True if it pressed.  Gives up after 4 tries in a row (the key toggles,
        and something else may be hiding the prompt) until a prompt is seen again."""
        s = self.s
        if not s.rod_check or not (s.skip_key or "").strip() or self._noprompt_since is None:
            return False
        if now - self._noprompt_since < max(0.5, s.rod_check_s) or now - self._equip_t < 2.0:
            return False
        if self._equip_tries >= 4:
            if self._equip_tries == 4:
                self._equip_tries += 1
                self.log("Still no Cast prompt after pressing the rod key 4 times - leaving it to you "
                         "(check the rod key setting).")
            return False
        self._equip_tries += 1
        self._equip_t = now
        self._noprompt_since = now
        self.log(f"No Cast prompt and no minigame - equipping the rod ('{s.skip_key.strip()}').")
        self._press("equip rod", key=s.skip_key.strip())
        return True

    def _do_cast(self, now: float, retry: bool = False) -> None:
        self._quick_recast = False
        self._press("cast")
        self.stats.casts += 1
        self._cast_t = now
        self._verified = False
        if not retry:
            self._cast_retries = 0
            self.log("Cast.")
        self._set_state(ST_WAIT)

    def _on_bite_timeout(self, now: float) -> float:
        self._timeouts += 1
        prompt = self._fresh_prompt(now - 1.5)
        self.log(f"No bite for {self.s.bite_timeout_s:.0f}s.")
        if prompt == PROMPT_CAST:
            self.log("The line is not out - casting.")
            self._do_cast(now)
        elif prompt == PROMPT_REEL:
            self.log("Reeling in to recast.")
            self._press("reel in (timeout)")
            self._set_state(ST_AFTER, "recasting")
        else:
            # can't read the prompt (or it keeps lying) - pressing once toggles
            # between "line out" and "line in", so alternating recovers either way.
            self.log("Can't confirm the line state - pressing once to toggle it.")
            self._press("toggle (timeout)")
            self._cast_t = now
            self._verified = True
            self._set_state(ST_WAIT)
            if self._timeouts >= 4:
                self.log("Tip: make sure you're facing the water and that the mouse "
                         "cursor isn't over the Cast prompt.")
        return 0.05

    # ------------------------------------------------------------ debug
    def _miss_snapshot(self, now: float, rd: Optional[MinigameReading] = None,
                       shown_after: Optional[float] = None) -> dict:
        """Copy everything a miss report needs (start() on the GUI thread clears
        the recorder, so the report must not read the live deques)."""
        return dict(now=now, rec=list(self._rec), pics=list(self._rec_imgs),
                    info=dict(self._last_press_info or {}), geom=self.geom, region=self.region,
                    lead_now=self.current_lead(), measured=self.lead_is_measured(),
                    fb=list(self._fb_hist), loop_dt=self._loop_dt, rd=rd, shown_after=shown_after)

    def save_miss_report(self, now: float, snap: Optional[dict] = None) -> Optional[str]:
        """Write what the bot saw around the last press: frames.png with one
        row per game frame (green = gold zone edges, red = fish, cyan = where
        the fish was predicted to be when the game judges the press, yellow
        frame = the last picture before the key went down, magenta = the frame
        the miss showed up in = the frame the game judged) and timeline.txt."""
        snap = snap or self._miss_snapshot(now)
        rec, info, g, rd = snap["rec"], snap["info"], snap["geom"], snap["rd"]
        if not rec or g is None:
            return None
        t_press = info.get("t", now)
        t_from = t_press - 0.45
        stamp = time.strftime("%Y%m%d_%H%M%S")
        base = os.path.join(MISS_DIR, f"miss_{stamp}")
        folder, n = base, 1
        while True:                      # never overwrite an earlier report
            try:
                os.makedirs(folder)
                break
            except FileExistsError:
                n += 1
                folder = f"{base}_{n}"
        pics = [pc for pc in snap["pics"] if pc[0] >= t_from]
        dts = [b[0] - a[0] for a, b in zip(pics, pics[1:]) if b[0] > a[0]]
        fps = 1.0 / float(np.median(dts)) if dts else 0.0
        # where the plan expected the fish / gold centre when the game judges the press
        y_pred = c_pred = t_eval = None
        if all(k in info for k in ("p", "v", "tau", "lead", "walls", "width", "c0", "vz", "zl", "zr")):
            T = info["tau"] + info["lead"]
            t_eval = t_press + info["lead"]
            y_pred = reflect(info["p"] + info["v"] * T, *info["walls"])
            hw, w1 = (info["zr"] - info["zl"]) / 2.0, info["width"] - 1.0
            c_pred = (min(max(info["c0"] + info["vz"] * (T - info.get("dz", 0.0)), hw), w1 - hw)
                      if w1 > 2 * hw else w1 / 2.0)
        sa = snap["shown_after"]
        s = self.s
        fmt = lambda v: (f"{v:.4f}" if isinstance(v, float) else  # noqa: E731
                         ("(" + ", ".join(f"{u:.1f}" for u in v) + ")" if isinstance(v, tuple) else str(v)))
        lines = [f"AutoFish {APP_VERSION} miss report {stamp}",
                 f"game area {snap['region']}; bar x {g.x0}-{g.x1} y {g.y0}-{g.y1} ({g.w}x{g.h}px)",
                 (f"timing used for this press {info['lead'] * 1000:.1f}ms; the result showed "
                  f"{('%.0fms' % (sa * 1000)) if sa is not None else '?'} after key-down"
                  if "lead" in info else "no press of AutoFish's in this round"),
                 f"timing now {snap['lead_now'] * 1000:.1f}ms ({'measured' if snap['measured'] else 'from settings'}); "
                 f"measured press->result delays (ms): {[round(d * 1000) for d in snap['fb']]}",
                 f"game frames ~{fps:.0f}/s, loop interval {snap['loop_dt'] * 1000:.1f}ms; settings: zone margin "
                 f"{s.zone_margin_pct:.0f}%, start timing {s.lead_ms:.0f}ms, auto timing {s.auto_lead}, "
                 f"min press gap {s.min_press_gap_s * 1000:.0f}ms, key hold {s.key_hold_ms:.0f}ms",
                 "last press: " + ", ".join(f"{k}={fmt(v)}" for k, v in info.items()),
                 ]
        if y_pred is not None:
            lines.append(f"plan: game judges at key-down + {info['lead'] * 1000:.0f}ms -> fish {y_pred:.1f}, "
                         f"gold centre {c_pred:.1f}")
            if rd is not None and rd.pointer is not None and rd.zone is not None:
                c_res = (rd.zone[0] + rd.zone[1]) / 2.0
                lines.append(f"judged frame: fish {rd.pointer:.1f}, gold centre {c_res:.1f} -> prediction error "
                             f"fish {rd.pointer - y_pred:+.1f}px, gold centre {c_res - c_pred:+.1f}px")
        verdict = miss_verdict(info, rd, snap["pics"], sa) if info else ""
        if verdict:
            lines.append("diagnosis: " + verdict)
        lines += ["", "(fish / gold in bar pixels, fish_v in px/s from the previous game frame)",
                  "t_ms(rel. to key down)  frame  fish  fish_v  gold_l gold_r  dots misses  event"]
        pic_index = {pc[0]: i for i, pc in enumerate(pics)}
        pic_v = {}
        for a, b in zip(pics, pics[1:]):
            if a[2] is not None and b[2] is not None and b[0] > a[0] and (len(a) < 6 or a[5] == b[5]):
                pic_v[b[0]] = (b[2] - a[2]) / (b[0] - a[0])
        rows = [r for r in rec if r[0] >= t_from]
        if t_eval is not None:
            k = next((i for i, r in enumerate(rows) if r[0] >= t_eval), len(rows))
            rows.insert(k, (t_eval, None, None, None, None,
                            f"(planned judgement: fish {y_pred:.1f}, gold centre {c_pred:.1f})"))
        prev = None
        for (t, ptr, zone, filled, misses, ev) in rows:
            new_frame = ptr is not None and t in pic_index   # (event rows can share a time stamp)
            idx = str(pic_index[t]) if new_frame else ""
            key = (ptr, zone, filled, misses)
            if not ev and not idx and key == prev:
                continue  # nothing new on screen
            prev = key
            z = f"{zone[0]:6.1f} {zone[1]:6.1f}" if zone else "     -      -"
            pp = f"{ptr:6.1f}" if ptr is not None else "     -"
            vv = f"{pic_v[t]:+7.0f}" if new_frame and t in pic_v else "       "
            lines.append(f"{(t - t_press) * 1000:9.1f}  {idx:>5}  {pp} {vv} {z}  {'' if filled is None else filled:>4} "
                         f"{'' if misses is None else misses:>6}  {ev}")
        with open(os.path.join(folder, "timeline.txt"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        if pics:
            before = max((i for i, p in enumerate(pics) if p[0] <= t_press), default=-1)
            left0 = min(pc[1][2][0] for pc in pics)
            rows_img = []
            for i, pc in enumerate(pics):
                t, simg, ptr, zone, ev = pc[:5]
                gx0 = pc[5] if len(pc) > 5 else g.x0      # the bar's x0 when this frame was read
                im = np.array(simg[1], dtype=np.uint8, copy=True)
                ox = gx0 - simg[2][0]
                hh, ww = im.shape[:2]
                k = max(2, hh // 8)

                def tick(x, ys, col):
                    xi = ox + int(round(x))
                    if 0 <= xi < ww:
                        im[ys, xi] = col
                if zone:
                    tick(zone[0], slice(0, k), (0, 255, 0))
                    tick(zone[1], slice(0, k), (0, 255, 0))
                if ptr is not None:
                    tick(ptr, slice(hh - k, hh), (255, 0, 0))
                if ev == "MISS" and y_pred is not None:
                    tick(y_pred, slice(hh - 2 * k, hh - k), (0, 255, 255))
                col = (255, 255, 0) if i == before else ((255, 0, 255) if ev == "MISS" else None)
                if col:
                    im[:2, :] = col
                    im[-2:, :] = col
                    im[:, :2] = col
                    im[:, -2:] = col
                # line rows up by screen position (the strip can move when the bar is re-measured)
                rows_img.append((simg[2][0] - left0, im))
                rows_img.append((simg[2][0] - left0, np.full((2, ww, 3), 40, np.uint8)))
            wmax = max(dx + r.shape[1] for dx, r in rows_img)
            write_png(os.path.join(folder, "frames.png"),
                      np.vstack([np.pad(r, ((0, 0), (dx, wmax - dx - r.shape[1]), (0, 0))) for dx, r in rows_img]))
        return folder

    def debug_snapshot(self) -> str:
        """Save an annotated screenshot of what the bot sees. Returns the path."""
        self._refresh_region(self.env.now())
        img = np.ascontiguousarray(self.env.grab(self.region)).copy()
        ox, oy = self.region[0], self.region[1]
        geom = locate_bar(img, (ox, oy)) or self.geom
        notes = []
        H, W = img.shape[:2]

        def rect(x0, y0, x1, y1, col):
            x0, x1 = max(0, x0 - ox), min(W - 1, x1 - ox)
            y0, y1 = max(0, y0 - oy), min(H - 1, y1 - oy)
            if x1 <= x0 or y1 <= y0:
                return
            img[y0, x0:x1 + 1] = col
            img[y1, x0:x1 + 1] = col
            img[y0:y1 + 1, x0] = col
            img[y0:y1 + 1, x1] = col

        if geom is not None:
            rect(geom.x0 - 2, geom.y0 - 2, geom.x1 + 2, geom.y1 + 2, (255, 0, 255))
            rd = read_minigame(img, geom, (ox, oy))
            if rd.visible and rd.zone:
                rect(geom.x0 + int(rd.zone[0]), geom.y0 - 4, geom.x0 + int(rd.zone[1]), geom.y1 + 4, (0, 255, 0))
            if rd.pointer is not None:
                px = geom.x0 + int(rd.pointer)
                rect(px - 1, geom.y0 - 6, px + 1, geom.y1 + 6, (255, 0, 0))
            notes.append(f"bar {geom} visible={rd.visible} zone={rd.zone} pointer={rd.pointer} "
                         f"dots={rd.filled}/{rd.total} misses={rd.misses}")
        else:
            notes.append("bar not found")
        pr = read_prompt(img, (ox, oy))
        if pr.box:
            rect(pr.box[0] - 2, pr.box[1] - 2, pr.box[2] + 2, pr.box[3] + 2, (0, 255, 255))
        notes.append(f"prompt={pr.state} ratio={pr.ratio:.2f} note={pr.note}")
        notes.append(f"leviathan: announcement={find_pull_banner(img)} boss bar={find_boss_bar(img)} "
                     f"dark={dark_fraction(img):.2f}")
        os.makedirs(DEBUG_DIR, exist_ok=True)
        path = os.path.join(DEBUG_DIR, time.strftime("snapshot_%Y%m%d_%H%M%S.png"))
        write_png(path, img)
        with open(path[:-4] + ".txt", "w", encoding="utf-8") as fh:
            fh.write("\n".join(notes) + "\n")
        self.log("Snapshot saved: " + path)
        for n in notes:
            self.log("  " + n)
        return path


# =============================================================================
#  Several Roblox windows at once: one FishingBot per window, one controller
#  that reads them all and switches the active window when one needs a key.
# =============================================================================
class MultiBot:
    RESCAN_S = 3.0

    def __init__(self, settings: Settings, make_env: Callable, list_windows: Callable,
                 foreground: Callable, log: Callable[[str], None]) -> None:
        self.s = settings
        self.make_env = make_env          # hwnd -> GameEnv for that window
        self.list_windows = list_windows  # () -> [hwnd, ...] (stable order)
        self.foreground = foreground      # () -> hwnd of the active window
        self._log_cb = log
        self.lanes: List[Tuple[int, FishingBot]] = []
        self.running = False
        self.alive = True
        self.lock = threading.Lock()
        self._scan_t = -1e9
        self._paused_since: Optional[float] = None
        self._next_num = 1
        self.own_foreground: Callable[[], bool] = lambda: False  # is the AutoFish window active?
        self.lev = LeviathanWatch()
        self.alarm: Optional[dict] = None   # the latest leviathan alarm (the GUI shows it)
        self.own_rect: Optional[Tuple[int, int, int, int]] = None  # the AutoFish window on screen (the GUI sets it)
        self._alarm_seq = 0

    def log(self, msg: str) -> None:
        self._log_cb(f"[{time.strftime('%H:%M:%S')}] {msg}")

    # ---------------------------------------------------------------- windows
    def _rescan(self) -> None:
        self._scan_t = time.perf_counter()
        try:
            hwnds = list(self.list_windows())
        except Exception as exc:
            self.log(f"Could not list the Roblox windows: {exc!r}")
            return
        if not self.s.multi_window:
            fg = self.foreground()
            hwnds = [fg] if fg in hwnds else hwnds[:1]
        known = {h for h, _ in self.lanes}
        for h, b in list(self.lanes):
            if h not in hwnds:
                b.stop()
                self.lanes.remove((h, b))
                self.log(f"{b.name or 'The Roblox window'} closed - no longer fishing there.")
        for h in hwnds:
            if h not in known:
                bot = FishingBot(self.s, self.make_env(h), self._log_cb, name=f"Window {self._next_num}")
                self._next_num += 1
                bot.ignore_focus = True
                self.lanes.append((h, bot))
                if self.running:
                    bot.start()
                self.log(f"Fishing in {bot.name}.")
        if len(self.lanes) == 1:
            self.lanes[0][1].name = ""

    def focus_any(self) -> bool:
        if not self.lanes:
            self._rescan()
        if not self.lanes:
            return False
        env = self.lanes[0][1].env
        return bool(getattr(env, "focus_game", lambda: False)())

    def window_count(self) -> int:
        return len(self.lanes)

    # -------------------------------------------------------------- control
    def start(self) -> None:
        with self.lock:
            if self.running:
                return
            self.lev = LeviathanWatch()   # a new run watches for a new leviathan (no 90 s blind spot after a restart)
            self.running = True
        self._rescan()
        if not self.lanes:
            self.log(f"No window titled '{self.s.window_title}' found yet - waiting for one.")
        for _, b in self.lanes:
            b.start()

    def stop(self) -> None:
        with self.lock:
            was = self.running
            self.running = False
        for _, b in self.lanes:
            b.stop()
        if was and len(self.lanes) > 1:
            self.log("Stopped all windows.")

    def toggle(self) -> None:
        if self.running:
            self.stop()
        else:
            self.start()

    def run_forever(self) -> None:
        while self.alive:
            if not self.running:
                for _, b in list(self.lanes):
                    if b._held is not None:
                        b._release_key()   # a press that raced a stop() from another thread
                time.sleep(0.05)
                continue
            try:
                delay = self._step()
            except Exception as exc:
                self.log(f"Error (continuing): {exc!r}")
                traceback.print_exc()
                delay = 0.5
            if delay > 0:
                time.sleep(delay)

    def _step(self) -> float:
        now = time.perf_counter()
        if now - self._scan_t > self.RESCAN_S:
            self._rescan()
        bots = [b for _, b in self.lanes]
        if not bots:
            return 0.5
        # safety: only act while one of the Roblox windows is the active window
        if (self.s.require_focus and self.foreground() not in [h for h, _ in self.lanes]
                and not self.own_foreground()):
            if self._paused_since is None:
                self._paused_since = now
                for b in bots:
                    b._release_key()
                self.log("No Roblox window is active - paused (click into any Roblox window).")
            for b in bots:
                b.detail = "paused - click into a Roblox window"
            return 0.1
        if self._paused_since is not None:
            paused = now - self._paused_since
            for b in bots:
                b._cast_t += paused
                b._state_t += paused
                b.prompt_hist.clear()
            self._paused_since = None
            self.log("Resuming.")
        if any(b.stopped_by_miss for b in bots):
            self.stop()
            return 0.05
        if (self.s.parallel_minigames or self.s.leviathan) and len(self.lanes) > 1:
            return self._step_parallel(now)
        for _, b in self.lanes:
            b.focus_gate = None
        # a window that is reeling gets the whole loop (fast, precise presses)
        for h, b in self.lanes:
            if b.running and b.state == ST_REEL:
                for _, o in self.lanes:
                    if o is not b:
                        o._release_key(now)
                if not self.s.dry_run:
                    b.env.ensure_focus()
                return b.tick()
        delay = 0.03
        for h, b in self.lanes:
            if not b.running:
                continue
            d = b.tick()
            if b.state == ST_REEL:
                if not self.s.dry_run:
                    b.env.ensure_focus()
                return 0.0
            delay = min(delay, max(0.0, d))
        return delay

    def _step_parallel(self, now: float) -> float:
        """Every window's minigame at once.  Only the active window receives
        key presses, so: look at all of them, work out when each one next
        needs a press, and switch to the window whose press comes first just
        early enough for the switch to settle."""
        fg = self.foreground()
        for h, b in self.lanes:
            b.focus_gate = (lambda h=h: self.foreground() == h)
        reeling = [(h, b) for h, b in self.lanes if b.running and b.state == ST_REEL]
        switch_cost = self.s.focus_settle_ms / 1000.0 + 0.015
        lev = self.s.leviathan
        soon = (not lev) and any(b.plan_at is not None and b.plan_at - now < 0.3 and not b.round_skip
                                 for _, b in reeling)
        # Leviathan: casting is the priority - windows that need a cast go first
        order = sorted(self.lanes, key=lambda hb: 0 if hb[1].state in (ST_AFTER, ST_START) else 1) \
            if lev else self.lanes
        for h, b in order:
            if not b.running:
                continue
            if b.state != ST_REEL and soon:
                continue  # don't steal the keyboard for a cast right before a reel press
            b.tick()
        reeling = [(h, b) for h, b in self.lanes if b.running and b.state == ST_REEL]
        if not reeling or self.s.dry_run:
            return 0.0 if reeling else (0.005 if lev else 0.02)
        now = time.perf_counter()
        fg = self.foreground()
        cur = next((b for h, b in reeling if h == fg), None)
        if cur is not None and cur.plan_at is not None and cur.plan_at - now < switch_cost + 0.05:
            return 0.0  # the active window presses next: stay
        cands = [(b.plan_at, h, b) for h, b in reeling if b.plan_at is not None and not b.round_skip
                 and (self.s.leviathan or b.plan_at - now >= switch_cost * 0.9)]
        catch_soon = any(b.plan_at is not None and not b.round_skip and b.plan_at - now < 0.3 for _, b in reeling)
        if not cands and not catch_soon:
            # fish worth catching come first; a skipped fish gets its misses when no catch press is close
            cands = [(b.plan_at, h, b) for h, b in reeling if b.plan_at is not None and b.round_skip]
        if cands:
            t, h, b = min(cands, key=lambda c: c[0])
            if h != fg and (cur is None or cur.plan_at is None or t < cur.plan_at):
                b.env.ensure_focus()
        return 0.0

    # ---------------------------------------------------------------- status
    def current_lead(self) -> float:
        for _, b in self.lanes:
            if b.lead_is_measured():
                return b.current_lead()
        return self.lanes[0][1].current_lead() if self.lanes else self.s.lead_ms / 1000.0

    def snapshot(self) -> dict:
        snaps = [b.snapshot() for _, b in self.lanes]
        tot = Stats()
        for sn in snaps:
            for f in fields(Stats):
                if f.name in ("started_at",):
                    continue
                if f.name == "run_time":
                    tot.run_time = max(tot.run_time, sn["stats"].run_time)
                else:
                    setattr(tot, f.name, getattr(tot, f.name) + getattr(sn["stats"], f.name))
        if len(snaps) == 1:
            state, detail = snaps[0]["state"], snaps[0]["detail"]
        elif snaps:
            short = {ST_REEL: "reeling", ST_WAIT: "waiting", ST_AFTER: "casting", ST_CAST: "casting",
                     ST_START: "starting", ST_STOPPED: "stopped", ST_PAUSED: "paused"}
            state = f"{len(snaps)} windows" + ("  (Leviathan)" if self.s.leviathan else "")
            detail = "  ".join(f"W{i + 1}:{short.get(sn['state'], sn['state'])}" for i, sn in enumerate(snaps))
        else:
            state, detail = ("Waiting for Roblox" if self.running else ST_STOPPED), "no Roblox window found"
        return {"state": state, "detail": detail, "stats": tot, "running": self.running,
                "lead_ms": self.current_lead() * 1000.0,
                "lead_auto": any(b.lead_is_measured() for _, b in self.lanes)}

    def debug_snapshot(self) -> str:
        if not self.lanes:
            self._rescan()
        paths = [b.debug_snapshot() for _, b in self.lanes]
        return ", ".join(paths)

    # -------------------------------------------------------- leviathan alarm
    def start_watcher(self) -> None:
        threading.Thread(target=self._watch_forever, name="autofish-leviathan", daemon=True).start()

    def _watch_busy(self) -> bool:
        """A window is in the middle of a precisely timed reel: don't take CPU
        time from it (Leviathan mode misses on purpose, so it never minds)."""
        if self.s.leviathan:
            return False
        now = time.perf_counter()
        for _, b in list(self.lanes):
            p = b.plan_at   # None = no press planned right now (just pressed / still measuring)
            if b.running and b.state == ST_REEL and p is not None and p - now < 0.15:
                return True
        return False

    def _watch_forever(self) -> None:
        """Every ~0.4 s, look at the top of each Roblox window for a leviathan pull."""
        errors = 0
        while self.alive:
            if not (self.running and self.s.leviathan_alarm):
                time.sleep(0.3)
                continue
            t0 = time.perf_counter()
            try:
                for h, b in list(self.lanes):
                    while self._watch_busy() and self.running and self.alive:
                        time.sleep(0.05)
                    if not self.running:
                        break
                    region = b.env.game_region()
                    img = b.env.grab(region)
                    ignore, r = None, self.own_rect     # don't count the AutoFish window as part of the game
                    if r is not None:
                        x0, y0 = max(r[0], region[0]) - region[0], max(r[1], region[1]) - region[1]
                        x1, y1 = min(r[2], region[0] + region[2]) - region[0], min(r[3], region[1] + region[3]) - region[1]
                        if x1 > x0 and y1 > y0:
                            ignore = (x0, y0, x1, y1)
                    for kind, name in self.lev.feed(b.name or "the Roblox window", img, time.perf_counter(), ignore):
                        self.raise_alarm(kind, name)
                errors = 0
            except Exception as exc:
                errors += 1
                if errors in (1, 20):
                    self.log(f"Leviathan alarm: couldn't read a window ({exc!r}) - still trying.")
            time.sleep(max(0.05, 0.4 - (time.perf_counter() - t0)))

    def raise_alarm(self, kind: str, name: str, test: bool = False) -> None:
        when = time.strftime("%H:%M:%S")
        if kind == "pull":
            title, detail = "LEVIATHAN PULLED!", f"'...pulled into the deep by the Serpent' in {name} at {when}"
        elif kind == "dark":
            title, detail = "LEVIATHAN - YOU'RE BEING PULLED IN!", f"{name} went dark at {when}"
        elif kind == "boss":
            title, detail = "LEVIATHAN - BOSS FIGHT!", f"boss health bar in {name} at {when}"
        else:
            title, detail = "ALARM TEST", "this is what the leviathan alarm looks and sounds like"
        stop = kind in ("dark", "boss") and self.s.alarm_stops_fishing and self.running and not test
        if stop:
            detail += " - fishing stopped"
        self._alarm_seq += 1
        self.alarm = {"seq": self._alarm_seq, "kind": kind, "title": title, "detail": detail, "t": time.time()}
        if not test:
            self.log(f"!!! {title} {detail}.")
        if stop:
            self.stop()
            self.log(f"Stopped fishing (you're in the leviathan's arena). Press {self.s.toggle_hotkey} "
                     f"to silence the alarm, and again to fish once you're back at the water.")


# =============================================================================
#  Alarm sound
# =============================================================================
def make_alarm_wav(path: str) -> None:
    """A loud two-tone siren, 2 s long (played in a loop)."""
    import wave
    rate = 22050
    parts = []
    for f in (988.0, 740.0) * 4:
        n = int(rate * 0.25)
        t = np.arange(n) / rate
        fade = np.minimum(1.0, np.minimum(np.arange(n), n - 1 - np.arange(n)) / 200.0)
        parts.append(0.9 * fade * np.sign(np.sin(2 * np.pi * f * t)) * 0.6
                     + 0.4 * fade * np.sin(2 * np.pi * f * t))
    pcm = (np.clip(np.concatenate(parts), -1, 1) * 32000).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


class AlarmSound:
    """Loops leviathan_alarm.wav (made on first use; put your own .wav there to
    change it) until stop().  Falls back to beeps if the file can't be played."""

    def __init__(self) -> None:
        self.playing = False
        self.since = 0.0
        self._beeper: Optional[threading.Thread] = None

    def start(self) -> None:
        self.stop()
        self.playing, self.since = True, time.time()
        token = self._beep_token = object()   # a newer start() retires any older beeper thread
        if not IS_WINDOWS:
            return
        import winsound
        try:
            if not os.path.exists(ALARM_WAV):
                make_alarm_wav(ALARM_WAV)
            winsound.PlaySound(ALARM_WAV, winsound.SND_FILENAME | winsound.SND_ASYNC
                               | winsound.SND_LOOP | winsound.SND_NODEFAULT)
            return
        except Exception:
            pass

        def beep():
            while self.playing and self._beep_token is token:
                try:
                    winsound.Beep(988, 250)
                    winsound.Beep(740, 250)
                except Exception:
                    time.sleep(0.5)
        self._beeper = threading.Thread(target=beep, daemon=True)
        self._beeper.start()

    def stop(self) -> None:
        was = self.playing
        self.playing = False
        if was and IS_WINDOWS:
            try:
                import winsound
                winsound.PlaySound(None, 0)
            except Exception:
                pass


def flash_taskbar(hwnd: int) -> None:
    """Flash the AutoFish button on the taskbar until its window is clicked."""
    if not IS_WINDOWS or not hwnd:
        return
    try:
        class FLASHWINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("hwnd", wintypes.HWND), ("dwFlags", wintypes.DWORD),
                        ("uCount", wintypes.UINT), ("dwTimeout", wintypes.DWORD)]
        fi = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, 3 | 12, 0, 0)   # FLASHW_ALL | FLASHW_TIMERNOFG
        _user32.FlashWindowEx(ctypes.byref(fi))
    except Exception:
        pass


# =============================================================================
#  GUI
# =============================================================================
def run_gui() -> None:
    import tkinter as tk
    from tkinter import messagebox, scrolledtext, ttk

    settings = Settings.load()
    env = WindowsEnv(settings)
    log_q: "queue.Queue[str]" = queue.Queue()

    def log(msg: str) -> None:
        print(msg)
        log_q.put(msg)

    bot = MultiBot(settings, lambda h: WindowsEnv(settings, h),
                   lambda: list_game_windows(settings.window_title or "Roblox"),
                   lambda: _user32.GetForegroundWindow(), log)
    def own_fg() -> bool:
        pid = wintypes.DWORD(0)
        fgw = _user32.GetForegroundWindow()
        if not fgw:
            return False
        _user32.GetWindowThreadProcessId(fgw, ctypes.byref(pid))
        return pid.value == os.getpid()
    bot.own_foreground = own_fg
    worker = threading.Thread(target=bot.run_forever, name="autofish-bot", daemon=True)
    worker.start()
    bot.start_watcher()

    root = tk.Tk()
    root.title(f"{APP_NAME} {APP_VERSION}")
    root.resizable(False, False)
    root.attributes("-topmost", settings.always_on_top)
    BG, FG, MUTED = "#151b23", "#e6edf3", "#8b98a5"
    GREEN, RED = "#2ea043", "#d73a49"
    root.configure(bg=BG)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("TLabel", background=BG, foreground=FG)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED)
    style.configure("TCheckbutton", background=BG, foreground=FG)
    style.map("TCheckbutton", background=[("active", BG)])
    style.configure("TLabelframe", background=BG, foreground=FG)
    style.configure("TLabelframe.Label", background=BG, foreground=MUTED)
    style.configure("TFrame", background=BG)

    pad = {"padx": 10, "pady": 4}

    hotkey_lbl = settings.toggle_hotkey.upper()
    toggle_btn = tk.Button(root, text=f"START  ({hotkey_lbl})", font=("Segoe UI", 16, "bold"),
                           bg=GREEN, fg="white", activebackground=GREEN, activeforeground="white",
                           relief="flat", height=1, width=18, cursor="hand2")
    toggle_btn.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 4))

    state_var = tk.StringVar(value="Stopped")
    detail_var = tk.StringVar(value=f"Press START or {hotkey_lbl} while in Roblox.")
    ttk.Label(root, textvariable=state_var, font=("Segoe UI", 12, "bold")).grid(row=1, column=0, columnspan=2, sticky="w", **pad)
    ttk.Label(root, textvariable=detail_var, style="Muted.TLabel", font=("Consolas", 9)).grid(row=2, column=0, columnspan=2, sticky="w", padx=10)

    stats_frame = ttk.Frame(root)
    stats_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=6)
    stat_vars = {}
    for i, (key, label) in enumerate([("caught", "Caught"), ("bites", "Bites"), ("lost", "Lost"), ("hits", "Hits"),
                                      ("misses", "Misses"), ("skipped", "Skipped"), ("casts", "Casts"), ("lead", "Timing"),
                                      ("run_time", "Run time")]):
        f = ttk.Frame(stats_frame)
        f.grid(row=0, column=i, padx=6)
        v = tk.StringVar(value="0")
        stat_vars[key] = v
        ttk.Label(f, textvariable=v, font=("Segoe UI", 13, "bold")).pack()
        ttk.Label(f, text=label, style="Muted.TLabel", font=("Segoe UI", 8)).pack()

    sf = ttk.LabelFrame(root, text="Settings (changes apply instantly)")
    sf.grid(row=4, column=0, columnspan=2, sticky="ew", padx=10, pady=4)

    num_vars = {}

    def add_num(row, label, attr, lo, hi, step, tip):
        ttk.Label(sf, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=2)
        v = tk.StringVar(value=f"{getattr(settings, attr):g}")
        sp = tk.Spinbox(sf, from_=lo, to=hi, increment=step, textvariable=v, width=7,
                        bg="#0d1117", fg=FG, buttonbackground="#30363d", insertbackground=FG,
                        relief="flat", justify="right")
        sp.grid(row=row, column=1, sticky="e", padx=6, pady=2)
        ttk.Label(sf, text=tip, style="Muted.TLabel", font=("Segoe UI", 8)).grid(row=row, column=2, sticky="w", padx=4)
        num_vars[attr] = (v, lo, hi)

    add_num(0, "Timing lead (ms)", "lead_ms", 0, 250, 5, "start value; auto timing refines it")
    add_num(1, "Gold zone margin (%)", "zone_margin_pct", 0, 45, 1, "higher = only the zone centre")
    add_num(2, "Recast delay (s)", "recast_delay_s", 0.2, 10, 0.1, "pause after each catch")
    add_num(3, "Bite timeout (s)", "bite_timeout_s", 10, 600, 5, "reel in + recast if no bite")

    ttk.Label(sf, text="Game key").grid(row=4, column=0, sticky="w", padx=6, pady=2)
    key_var = tk.StringVar(value=settings.key)
    tk.Entry(sf, textvariable=key_var, width=8, bg="#0d1117", fg=FG, insertbackground=FG,
             relief="flat", justify="center").grid(row=4, column=1, sticky="e", padx=6)
    ttk.Label(sf, text="casts and reels (E in this game)", style="Muted.TLabel", font=("Segoe UI", 8)).grid(row=4, column=2, sticky="w", padx=4)

    bool_vars = {}

    def add_bool(row, label, attr):
        v = tk.BooleanVar(value=getattr(settings, attr))
        ttk.Checkbutton(sf, text=label, variable=v).grid(row=row, column=0, columnspan=3, sticky="w", padx=6, pady=1)
        bool_vars[attr] = v

    add_bool(5, "Auto timing - measure the game's input delay (recommended)", "auto_lead")
    add_bool(6, "Stop on the first miss (saves a miss report)", "stop_on_miss")
    add_bool(7, "Reel with left-click instead of the key", "reel_with_click")
    add_bool(8, "Only press keys while Roblox is the active window (recommended)", "require_focus")
    add_bool(9, "Dry run - detect and log only, never press anything", "dry_run")
    add_bool(10, "Keep this window on top", "always_on_top")
    add_bool(11, "Fish in EVERY Roblox window (switches between them)", "multi_window")
    add_bool(12, "Leviathan mode - only trigger the bite, then miss on purpose", "leviathan")
    add_bool(13, "Play all windows' minigames at the same time (always on in Leviathan mode)", "parallel_minigames")
    add_bool(14, "Leviathan alarm - sound + flashing when a leviathan pulls", "leviathan_alarm")
    add_bool(15, "...and stop fishing once you're pulled in (screen goes dark / boss bar)", "alarm_stops_fishing")
    add_bool(16, "Skip unwanted fish: unequip + re-equip the rod (key below), recast", "skip_fish")
    add_bool(18, "...keep only fish whose panel says 'Something big is pulling!'", "keep_only_big")
    add_bool(19, "Re-equip the rod (rod key) when no Cast prompt and no minigame show", "rod_check")
    sk = ttk.Frame(sf)
    sk.grid(row=17, column=0, columnspan=3, sticky="w", padx=24, pady=1)
    ttk.Label(sk, text="Keep fish needing").pack(side="left")
    keep_var = tk.StringVar(value=settings.keep_hits)
    tk.Entry(sk, textvariable=keep_var, width=6, bg="#0d1117", fg=FG, insertbackground=FG,
             relief="flat", justify="center").pack(side="left", padx=4)
    ttk.Label(sk, text="hits     rod key").pack(side="left")
    skipkey_var = tk.StringVar(value=settings.skip_key)
    tk.Entry(sk, textvariable=skipkey_var, width=4, bg="#0d1117", fg=FG, insertbackground=FG,
             relief="flat", justify="center").pack(side="left", padx=4)

    def apply_settings(*_):
        for attr, (v, lo, hi) in num_vars.items():
            try:
                val = float(v.get())
                setattr(settings, attr, min(max(val, lo), hi))
            except ValueError:
                pass
        k = key_var.get().strip()
        if k:
            settings.key = k[:12]
        settings.keep_hits = keep_var.get().strip()[:20]
        k = skipkey_var.get().strip()
        if k:
            settings.skip_key = k[:12]
        for attr, v in bool_vars.items():
            setattr(settings, attr, bool(v.get()))
        root.attributes("-topmost", settings.always_on_top)

    for v, _, _ in num_vars.values():
        v.trace_add("write", apply_settings)
    key_var.trace_add("write", apply_settings)
    keep_var.trace_add("write", apply_settings)
    skipkey_var.trace_add("write", apply_settings)
    for v in bool_vars.values():
        v.trace_add("write", apply_settings)

    btns = ttk.Frame(root)
    btns.grid(row=5, column=0, columnspan=2, sticky="ew", padx=10, pady=4)

    def save():
        apply_settings()
        settings.save()
        log("Settings saved.")

    def defaults():
        d = Settings()
        for attr, (v, _, _) in num_vars.items():
            v.set(f"{getattr(d, attr):g}")
        key_var.set(d.key)
        keep_var.set(d.keep_hits)
        skipkey_var.set(d.skip_key)
        for attr, v in bool_vars.items():
            v.set(getattr(d, attr))

    def snapshot():
        def work():
            try:
                bot.debug_snapshot()
            except Exception as exc:
                log(f"Snapshot failed: {exc!r}")
        # run in the bot's absence of a lock is fine: it only reads the screen
        threading.Thread(target=work, daemon=True).start()

    def test_alarm():
        bot.raise_alarm("test", "", test=True)

    for i, (txt, cmd) in enumerate([("Save settings", save), ("Defaults", defaults),
                                    ("Debug snapshot", snapshot), ("Test alarm", test_alarm)]):
        tk.Button(btns, text=txt, command=cmd, bg="#30363d", fg=FG, activebackground="#3d444d",
                  activeforeground=FG, relief="flat", padx=8).grid(row=0, column=i, padx=3, sticky="ew")
        btns.columnconfigure(i, weight=1)

    logbox = scrolledtext.ScrolledText(root, width=62, height=10, bg="#0d1117", fg="#c9d1d9",
                                       insertbackground=FG, relief="flat", font=("Consolas", 9))
    logbox.grid(row=6, column=0, columnspan=2, sticky="nsew", padx=10, pady=(4, 10))
    logbox.configure(state="disabled")

    # ---- leviathan alarm: a big flashing panel over the top of the window + a siren
    ALARM_A, ALARM_B = "#d7263d", "#ffb000"
    alarm_box = tk.Frame(root, bg=ALARM_A, bd=0)
    alarm_title = tk.Label(alarm_box, text="", font=("Segoe UI", 20, "bold"), bg=ALARM_A, fg="white")
    alarm_title.pack(fill="x", padx=10, pady=(12, 0))
    alarm_detail = tk.Label(alarm_box, text="", font=("Segoe UI", 10), bg=ALARM_A, fg="white", wraplength=520)
    alarm_detail.pack(fill="x", padx=10, pady=(2, 6))
    alarm_btn = tk.Button(alarm_box, text=f"Silence alarm  ({hotkey_lbl})", font=("Segoe UI", 12, "bold"),
                          bg="white", fg="#7a0010", relief="flat", cursor="hand2")
    alarm_btn.pack(pady=(0, 12))
    sound = AlarmSound()
    alarm_state = {"seq": 0, "on": False, "flash": 0.0, "lit": False}

    def show_alarm(a: dict) -> None:
        alarm_state.update(seq=a["seq"], on=True, flash=0.0)
        alarm_title.configure(text=a["title"])
        alarm_detail.configure(text=a["detail"])
        alarm_box.place(x=0, y=0, relwidth=1.0)
        alarm_box.lift()
        root.deiconify()
        root.lift()
        root.attributes("-topmost", True)
        if a["kind"] != "test" or not sound.playing:
            sound.start()
        if IS_WINDOWS:
            try:
                flash_taskbar(int(root.wm_frame(), 16))
            except Exception:
                pass

    def silence_alarm() -> None:
        if alarm_state["on"]:
            alarm_state["on"] = False
            sound.stop()
            alarm_box.place_forget()
            root.attributes("-topmost", settings.always_on_top)
            log("Alarm silenced.")

    alarm_btn.configure(command=silence_alarm)

    def tick_alarm() -> None:
        a = bot.alarm
        if a is not None and a["seq"] != alarm_state["seq"]:
            show_alarm(a)
        if not alarm_state["on"]:
            return
        now = time.time()
        if now - alarm_state["flash"] >= 0.4:
            alarm_state["flash"] = now
            alarm_state["lit"] = not alarm_state["lit"]
            c = ALARM_B if alarm_state["lit"] else ALARM_A
            for wdg in (alarm_box, alarm_title, alarm_detail):
                wdg.configure(bg=c)
        if sound.playing and now - sound.since > max(5.0, settings.alarm_max_s):
            sound.stop()
            log("Alarm sound stopped after %.0f s (the panel stays until you silence it)." % settings.alarm_max_s)

    def on_toggle(from_button: bool = False):
        apply_settings()
        if bot.running:
            bot.stop()
        else:
            if from_button and settings.require_focus:
                if bot.focus_any():
                    log("Switched to the Roblox window.")
                elif not bot.window_count():
                    log(f"Couldn't find a window titled '{settings.window_title}'. "
                        "Open Roblox, then click into it.")
            bot.start()

    toggle_btn.configure(command=lambda: on_toggle(True))

    hotkey_state = {"down": False}

    def poll():
        # global hotkey (works while Roblox is focused)
        try:
            down = env.key_down(settings.toggle_hotkey)
        except Exception:
            down = False
        if down and not hotkey_state["down"]:
            if alarm_state["on"]:
                silence_alarm()          # the hotkey silences a sounding alarm first
            else:
                on_toggle(False)
        hotkey_state["down"] = down
        try:   # where the AutoFish window is (the leviathan watcher ignores that part of the screen)
            x, y = root.winfo_rootx(), root.winfo_rooty()
            bot.own_rect = None if root.state() == "iconic" else \
                (x - 10, y - 40, x + root.winfo_width() + 10, y + root.winfo_height() + 10)  # + frame / title bar
        except Exception:
            bot.own_rect = None
        tick_alarm()
        # log lines
        lines = []
        try:
            while True:
                lines.append(log_q.get_nowait())
        except queue.Empty:
            pass
        if lines:
            logbox.configure(state="normal")
            logbox.insert("end", "\n".join(lines) + "\n")
            n = int(logbox.index("end-1c").split(".")[0])
            if n > 600:
                logbox.delete("1.0", f"{n - 600}.0")
            logbox.see("end")
            logbox.configure(state="disabled")
        # status
        snap = bot.snapshot()
        running = snap["running"]
        toggle_btn.configure(text=("STOP" if running else "START") + f"  ({settings.toggle_hotkey.upper()})",
                             bg=RED if running else GREEN, activebackground=RED if running else GREEN)
        state_var.set(snap["state"] + ("  [DRY RUN]" if settings.dry_run and running else ""))
        detail_var.set(snap["detail"][:80])
        st = snap["stats"]
        for k in ("caught", "bites", "lost", "hits", "misses", "skipped", "casts"):
            stat_vars[k].set(str(getattr(st, k)))
        stat_vars["lead"].set(f"{snap['lead_ms']:.0f}ms" + ("*" if snap["lead_auto"] else ""))
        secs = int(st.run_time)
        stat_vars["run_time"].set(f"{secs // 3600}:{secs // 60 % 60:02d}:{secs % 60:02d}")
        root.after(30, poll)

    def on_close():
        sound.stop()
        bot.stop()
        bot.alive = False
        apply_settings()
        settings.save()
        env.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    log(f"{APP_NAME} {APP_VERSION} ready. Stand at the water with your rod out, then press "
        f"START (or {hotkey_lbl} in game). {hotkey_lbl} again stops it.")
    if not IS_WINDOWS:
        messagebox.showwarning(APP_NAME, "AutoFish only works on Windows.")
    root.after(50, poll)
    root.mainloop()


def main() -> None:
    if not IS_WINDOWS:
        print("AutoFish runs on Windows only (it needs to read the screen and press keys in Roblox).")
        sys.exit(1)
    set_dpi_awareness()
    try:
        import mss  # noqa: F401
    except ImportError:
        print("Missing package 'mss'. Run:  python -m pip install --user mss numpy")
        sys.exit(1)
    run_gui()


if __name__ == "__main__":
    main()
