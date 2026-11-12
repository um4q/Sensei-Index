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
import sys
import threading
import time
import traceback
from collections import deque
from dataclasses import asdict, dataclass, fields
from typing import Callable, List, Optional, Tuple

import numpy as np

APP_NAME = "AutoFish"
APP_VERSION = "1.0"
HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(HERE, "autofish_settings.json")
DEBUG_DIR = os.path.join(HERE, "debug_snapshots")
IS_WINDOWS = sys.platform.startswith("win")


# =============================================================================
#  Settings
# =============================================================================
@dataclass
class Settings:
    # --- reel timing -------------------------------------------------------
    lead_ms: float = 30.0          # how far ahead to predict the fish (input lag)
    zone_margin_pct: float = 18.0  # ignore this % of the gold zone on each side
    press_cooldown_s: float = 0.30 # never press twice within this time while reeling
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
        top = self.y0 - 2
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
    good = []  # (y, x0, x1)
    for i, y in enumerate(rows):
        both = navy[i] | gold[i]
        for s, e in runs(both, gap=4):
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
        y0, y1 = min(ys), max(ys)
        h = y1 - y0 + 1
        x0 = int(np.median([it[1] for it in grp]))
        x1 = int(np.median([it[2] for it in grp]))
        w = x1 - x0 + 1
        if h < 4 or not (4.0 <= w / h <= 40.0):
            continue
        if len(grp) < 0.3 * h:  # too sparse to be one solid bar
            continue
        # the bar sits on the minigame panel's dark background: the rows just
        # above and below it must be dark (rules out sunsets on water, etc.)
        off = max(2, int(round(0.12 * h)))
        dark_ok = True
        for yy in (y0 - off, y1 + off):
            if 0 <= yy < H:
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
    for s, e in runs(gcols, gap=max(2, int(round(0.12 * h)))):
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
            span = int(round(0.30 * geom.w))
            left = strip[y_a:y_b, lx0:min(Ws, lx0 + span)]
            right = strip[y_a:y_b, max(0, lx1 - span + 1):lx1 + 1]
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
            m_best = 0
            for i in range(right.shape[0]):
                m_best = max(m_best, sum(1 for s, e in runs(red[i], gap=1) if e - s + 1 >= min_dot))
            out.misses = m_best
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
    for (x0, y0, x1, y1) in uniq:
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        inner = rgb[y0 + 2:y1 - 1, x0 + 2:x1 - 1]
        if inner.size == 0 or float(inner.mean()) > 90:
            continue  # not a dark box
        # the prompt has a gold-framed key icon on its left: one of its frame
        # columns is a tall gold line (rules out other dark boxes, e.g. the
        # minigame panel while it fades out)
        kr, kg, kb = channels(rgb[y0 + 1:y1, x0:x0 + max(3, int(0.27 * bw))])
        keygold = ((kr >= 100) & (kg >= 85) & (kr - kb >= 30) & (kg - kb >= 15)
                   & (np.abs(kr - kg) <= 45))
        if keygold.size == 0 or int(keygold.sum(axis=0).max()) < 0.35 * bh:
            continue
        ya = y0 + max(2, int(0.06 * bh))
        yb = y0 + int(0.55 * bh)
        xa = x0 + int(0.26 * bw)
        xb = x1 - max(2, int(0.03 * bw))
        if yb <= ya or xb <= xa:
            continue
        rr, gg, bb = channels(rgb[ya:yb, xa:xb])
        mx = np.maximum(np.maximum(rr, gg), bb)
        mn = np.minimum(np.minimum(rr, gg), bb)
        pure_white = int((mn >= 236).sum())  # cursor (white); title text is cream
        text = (rr >= 140) & (gg >= 130) & (bb >= 100) & (mx - mn <= 80) & (mn < 236)
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
    return PromptReading(note="no prompt")


# =============================================================================
#  Timing - predict where the pointer will be when our key press lands
# =============================================================================
class PointerTracker:
    def __init__(self) -> None:
        self.samples: deque = deque(maxlen=48)

    def reset(self) -> None:
        self.samples.clear()

    def add(self, t: float, x: float) -> None:
        if self.samples and t <= self.samples[-1][0]:
            return
        self.samples.append((t, x))

    def velocity(self, window: float = 0.08) -> Optional[float]:
        """Pixels/second over the most recent stretch of one-directional motion."""
        if len(self.samples) < 2:
            return None
        pts = list(self.samples)
        t_new, x_new = pts[-1]
        direction = 0
        oldest = None
        prev_x = x_new
        for t, x in reversed(pts[:-1]):
            if t_new - t > window:
                break
            step = prev_x - x  # movement from this sample to the next one
            if abs(step) >= 0.75:
                sgn = 1 if step > 0 else -1
                if direction == 0:
                    direction = sgn
                elif sgn != direction:
                    break  # bounced - ignore anything before the bounce
            oldest = (t, x)
            prev_x = x
        if oldest is None or t_new - oldest[0] < 0.006:
            # fall back to the last two samples
            t0, x0 = pts[-2]
            if t_new - t0 <= 0 or t_new - t0 > 0.25:
                return None
            return (x_new - x0) / (t_new - t0)
        return (x_new - oldest[1]) / (t_new - oldest[0])


def reflect(x: float, lo: float, hi: float) -> float:
    """Fold a predicted position back inside [lo, hi] (the pointer bounces)."""
    if hi <= lo:
        return lo
    for _ in range(4):
        if x < lo:
            x = 2 * lo - x
        elif x > hi:
            x = 2 * hi - x
        else:
            break
    return min(max(x, lo), hi)


def should_press(reading: MinigameReading, velocity: Optional[float], lead_s: float,
                 margin_frac: float, loop_dt: float) -> Tuple[bool, float]:
    """Decide whether pressing *now* will land with the pointer in the gold zone.

    Aims for the centre of the zone: press on the sample that is closest to the
    centre (or the last sample still inside the safe part of the zone).
    Returns (press?, predicted pointer position)."""
    if not reading.visible or reading.zone is None or reading.pointer is None:
        return False, -1.0
    if velocity is None:
        return False, reading.pointer  # need two samples to know where it's going
    zl, zr = reading.zone
    zw = zr - zl + 1
    c = (zl + zr) / 2.0
    v = velocity
    p_pred = reflect(reading.pointer + v * lead_s, 0.0, float(reading.width - 1))
    m = max(1.0, margin_frac * zw)
    il, ir = zl + m, zr - m
    if il > ir:
        il = ir = c
    tol = 0.5
    if not (il - tol <= p_pred <= ir + tol):
        return False, p_pred
    speed = abs(v)
    if speed < 0.05 * reading.width:  # (nearly) still: anywhere safe is fine
        return True, p_pred
    step = speed * max(loop_dt, 0.002)
    ahead = (c - p_pred) if v > 0 else (p_pred - c)  # distance left to the centre
    if ahead <= step / 2.0:
        return True, p_pred               # this is the sample nearest the centre
    nxt = p_pred + (step if v > 0 else -step)
    if not (il - tol <= nxt <= ir + tol):
        return True, p_pred               # last chance before leaving the safe area
    return False, p_pred


# =============================================================================
#  Platform layer (Windows).  The bot only talks to this interface, so it can
#  be driven by a simulator in tests.
# =============================================================================
class GameEnv:
    def now(self) -> float: return time.perf_counter()
    def sleep(self, s: float) -> None: time.sleep(max(0.0, s))
    def game_region(self) -> Optional[Tuple[int, int, int, int]]: raise NotImplementedError
    def is_game_focused(self) -> bool: raise NotImplementedError
    def focus_game(self) -> bool: return False
    def grab(self, region: Tuple[int, int, int, int]) -> np.ndarray: raise NotImplementedError
    def press_key(self, key: str, hold_s: float) -> None: raise NotImplementedError
    def click(self, hold_s: float) -> None: raise NotImplementedError
    def key_down(self, name: str) -> bool: return False
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

    class WindowsEnv(GameEnv):
        def __init__(self, settings: Settings) -> None:
            self.settings = settings
            self._tls = threading.local()
            self._hwnd = None
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
            return bool(fg) and self._title(fg).strip() == (self.settings.window_title or "Roblox")

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
            down = INPUT(type=INPUT_MOUSE)
            down.mi = MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, 0)
            up = INPUT(type=INPUT_MOUSE)
            up.mi = MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, 0)
            self._send(down)
            time.sleep(max(0.0, hold_s))
            self._send(up)

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
    presses: int = 0
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
                 log: Optional[Callable[[str], None]] = None) -> None:
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
        self.tracker = PointerTracker()
        self.region: Optional[Tuple[int, int, int, int]] = None
        self._region_t = -1e9
        self._last_full = -1e9
        self._loop_dt = 0.01
        self._last_tick = None
        self._reset_round()
        self.prompt = PromptReading()
        self.prompt_t = -1e9
        self.prompt_hist: deque = deque(maxlen=4)  # (time, state) of recent readings
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
        self._log_cb(f"[{stamp}] {msg}")

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
        self.round_misses = 0
        self.round_presses = 0
        self.last_press_t = -1e9
        self.tracker = PointerTracker()

    def start(self) -> None:
        with self.lock:
            if self.running:
                return
            self.running = True
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
                    "running": self.running}

    def _press(self, why: str, reel: bool = False) -> None:
        self._last_key_t = self.env.now()
        self.stats.presses += 1
        if self.s.dry_run:
            self.log(f"(dry run) would press for: {why}")
            return
        hold = max(0.0, self.s.key_hold_ms / 1000.0)
        if reel and self.s.reel_with_click:
            self.env.click(hold)
        else:
            self.env.press_key(self.s.key or "e", hold)

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
            if self.geom is None or (abs(geom.x0 - self.geom.x0) > 3 or abs(geom.y0 - self.geom.y0) > 3
                                     or abs(geom.w - self.geom.w) > 4):
                self.log(f"Found the reel bar: {geom.w}x{geom.h}px at ({geom.x0},{geom.y0}).")
            self.geom = geom
            reading = read_minigame(img, geom, (ox, oy))
        if reading is None or not reading.visible:
            pr = read_prompt(img, (ox, oy))
            if now - self._last_key_t >= self.PROMPT_SETTLE:
                self.prompt = pr
                self.prompt_t = now
                self.prompt_hist.append((now, pr.state))
        return reading

    def _strip_scan(self) -> Optional[MinigameReading]:
        if self.geom is None:
            return None
        reg = self.geom.strip_region()
        img = self.env.grab(reg)
        return read_minigame(img, self.geom, (reg[0], reg[1]))

    def _fresh_prompt(self, since: float) -> Optional[str]:
        """Prompt state if it was read after `since`, else 'unknown' (None)."""
        since = max(since, self._last_key_t + self.PROMPT_SETTLE)
        recent = [st for (t, st) in self.prompt_hist if t >= since]
        # two readings in a row must agree before we act on them
        if len(recent) >= 2 and recent[-1] == recent[-2]:
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

        # ---- safety: only act while the game is the active window
        if s.require_focus and not env.is_game_focused():
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
            interval = min(interval, 0.15)  # we want fresh prompt readings here
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
        if self.state != ST_REEL:
            self._reset_round()
            self.round_seen_t = now
            self._timeouts = 0
            waited = now - self._cast_t if self.state == ST_WAIT else 0
            self.log("Fish hooked! Reeling..." + (f" (bite after {waited:.1f}s)" if waited else ""))
        self._set_state(ST_REEL)
        self.round_last_visible = now

        # progress bookkeeping (for the stats only)
        if rd.filled > self.round_filled:
            self.stats.hits += rd.filled - self.round_filled
            self.round_filled = rd.filled
        if rd.total > self.round_total:
            self.round_total = rd.total
        if rd.misses > self.round_misses:
            self.stats.misses += rd.misses - self.round_misses
            self.round_misses = rd.misses

        if self._last_tick is not None:
            dt = now - self._last_tick
            if 0 < dt < 0.1:
                self._loop_dt = 0.8 * self._loop_dt + 0.2 * dt
        self._last_tick = now
        if rd.pointer is not None:
            self.tracker.add(now, rd.pointer)
        v = self.tracker.velocity()
        press, p_pred = should_press(rd, v, s.lead_ms / 1000.0, s.zone_margin_pct / 100.0, self._loop_dt)
        zl, zr = rd.zone if rd.zone else (0, 0)
        self.detail = (f"fish {rd.pointer if rd.pointer is not None else -1:5.0f}  "
                       f"gold {zl:4.0f}-{zr:4.0f}  dots {self.round_filled}/{self.round_total or '?'}")
        if press and now - self.last_press_t >= s.press_cooldown_s:
            self.last_press_t = now
            self.round_presses += 1
            self._press(f"fish at {rd.pointer:.0f}, gold {zl:.0f}-{zr:.0f}", reel=True)
            return 0.0
        return 0.0  # reel as fast as the screen can be read

    # ------------------------------------------------------- not reeling
    def _on_no_minigame(self, now: float) -> float:
        s = self.s
        if self.state == ST_REEL:
            if now - self.round_last_visible < self.END_GRACE:
                return 0.0
            # round over
            if self.round_total and self.round_filled >= self.round_total:
                self.stats.caught += 1
                self.log(f"Caught it! ({self.round_filled}/{self.round_total}, {self.round_misses} missed)"
                         f"  total caught: {self.stats.caught}")
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
            return 0.02

        if self.state == ST_START:
            self._set_state(ST_AFTER, "checking the prompt")
            self._state_t = now - s.recast_delay_s  # no delay on the very first cast
            return 0.0

        if self.state == ST_AFTER:
            elapsed = now - self._state_t
            if elapsed < s.recast_delay_s:
                self.detail = f"recasting in {s.recast_delay_s - elapsed:.1f}s"
                return 0.03
            prompt = self._fresh_prompt(self._state_t + s.recast_delay_s - 0.2)
            if prompt == PROMPT_REEL:
                self.log("Line is already in the water - waiting for a bite.")
                self._cast_t = now
                self._verified = True
                self._set_state(ST_WAIT)
                return 0.02
            if prompt == PROMPT_CAST or elapsed >= s.recast_delay_s + self.PROMPT_WAIT:
                if prompt != PROMPT_CAST:
                    why = self.prompt.note or "no prompt"
                    self.log(f"Casting without seeing the Cast prompt ({why}).")
                self._do_cast(now)
                return 0.02
            self.detail = "looking for the Cast prompt"
            return 0.03

        if self.state == ST_WAIT:
            waited = now - self._cast_t
            self.detail = f"waiting for a bite... {waited:.0f}s"
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
            if waited >= s.bite_timeout_s:
                return self._on_bite_timeout(now)
            return 0.02

        # unknown state -> behave like a fresh start
        self._set_state(ST_AFTER)
        return 0.02

    def _do_cast(self, now: float, retry: bool = False) -> None:
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
        if prompt == PROMPT_CAST and self._timeouts <= 2:
            self.log("The line is not out - casting.")
            self._do_cast(now)
        elif prompt == PROMPT_REEL and self._timeouts <= 2:
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
    def debug_snapshot(self) -> str:
        """Save an annotated screenshot of what the bot sees. Returns the path."""
        import zlib
        import struct
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
        os.makedirs(DEBUG_DIR, exist_ok=True)
        path = os.path.join(DEBUG_DIR, time.strftime("snapshot_%Y%m%d_%H%M%S.png"))
        raw = b"".join(b"\x00" + img[y].tobytes() for y in range(H))

        def chunk(tag, data):
            c = struct.pack(">I", len(data)) + tag + data
            return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
               + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
        with open(path, "wb") as fh:
            fh.write(png)
        with open(path[:-4] + ".txt", "w", encoding="utf-8") as fh:
            fh.write("\n".join(notes) + "\n")
        self.log("Snapshot saved: " + path)
        for n in notes:
            self.log("  " + n)
        return path


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

    bot = FishingBot(settings, env, log)
    worker = threading.Thread(target=bot.run_forever, name="autofish-bot", daemon=True)
    worker.start()

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
    for i, (key, label) in enumerate([("caught", "Caught"), ("lost", "Lost"), ("hits", "Hits"),
                                      ("misses", "Misses"), ("casts", "Casts"), ("run_time", "Run time")]):
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

    add_num(0, "Timing lead (ms)", "lead_ms", 0, 250, 5, "raise if presses land late")
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

    add_bool(5, "Reel with left-click instead of the key", "reel_with_click")
    add_bool(6, "Only press keys while Roblox is the active window (recommended)", "require_focus")
    add_bool(7, "Dry run - detect and log only, never press anything", "dry_run")
    add_bool(8, "Keep this window on top", "always_on_top")

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
        for attr, v in bool_vars.items():
            setattr(settings, attr, bool(v.get()))
        root.attributes("-topmost", settings.always_on_top)

    for v, _, _ in num_vars.values():
        v.trace_add("write", apply_settings)
    key_var.trace_add("write", apply_settings)
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

    for i, (txt, cmd) in enumerate([("Save settings", save), ("Defaults", defaults),
                                    ("Debug snapshot", snapshot)]):
        tk.Button(btns, text=txt, command=cmd, bg="#30363d", fg=FG, activebackground="#3d444d",
                  activeforeground=FG, relief="flat", padx=8).grid(row=0, column=i, padx=3, sticky="ew")
        btns.columnconfigure(i, weight=1)

    logbox = scrolledtext.ScrolledText(root, width=62, height=10, bg="#0d1117", fg="#c9d1d9",
                                       insertbackground=FG, relief="flat", font=("Consolas", 9))
    logbox.grid(row=6, column=0, columnspan=2, sticky="nsew", padx=10, pady=(4, 10))
    logbox.configure(state="disabled")

    def on_toggle(from_button: bool = False):
        apply_settings()
        if bot.running:
            bot.stop()
        else:
            if from_button and settings.require_focus:
                if env.focus_game():
                    log("Switched to the Roblox window.")
                elif not env.game_window_found():
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
            on_toggle(False)
        hotkey_state["down"] = down
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
        for k in ("caught", "lost", "hits", "misses", "casts"):
            stat_vars[k].set(str(getattr(st, k)))
        secs = int(st.run_time)
        stat_vars["run_time"].set(f"{secs // 3600}:{secs // 60 % 60:02d}:{secs % 60:02d}")
        root.after(30, poll)

    def on_close():
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
