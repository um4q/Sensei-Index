# -*- coding: utf-8 -*-
"""
AuctionReader - reads every listing on the Roblox auction board into Excel.

    python auction_reader.py        (or double-click START_AUCTION_READER.bat)

How to use:
  1. In Roblox, walk to the auctioneer and open the auction board
     ("Open the auction board" -> Browse tab).
  2. Press START (or F7 while in Roblox).  Hands off the mouse while it runs.
  3. For every search term (a, b, c ... z by default) it types the term into
     the search bar, scrolls through all results and reads each row: item,
     seller, time left, price and rarity colour.  Every listing is saved once,
     even when several letters find it.
  4. Results go to auction_listings.xlsx next to this file:
        Latest scan  - every listing of the newest scan
        Items        - per item: listings, cheapest, median, highest price
        History      - every listing of every scan (for trends)
     With "Repeat every N minutes" it keeps scanning (board left open).

Text is read with Windows' built-in OCR (nothing to install).  If Tesseract
is installed it can be used instead.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from dataclasses import asdict, dataclass, fields
from typing import Dict, List, Optional, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import autofish as af  # noqa: E402  (screen capture, keys, PNG writer)

APP = "AuctionReader"
VERSION = "1.5"
SETTINGS_PATH = os.path.join(HERE, "auction_settings.json")


@dataclass
class ARSettings:
    search_terms: str = "a b c d e f g h i j k l m n o p q r s t u v w x y z"
    excel_path: str = "auction_listings.xlsx"
    repeat_minutes: float = 0.0     # 0 = scan once
    wait_after_typing_s: float = 1.0
    scroll_notches: int = 2         # mouse-wheel notches per step
    wait_after_scroll_s: float = 0.35
    max_pages_per_term: int = 400
    ocr_backend: str = "auto"       # auto | windows | tesseract
    toggle_hotkey: str = "F7"
    window_title: str = "Roblox"
    save_debug_images: bool = False

    @classmethod
    def load(cls) -> "ARSettings":
        s = cls()
        try:
            data = json.load(open(SETTINGS_PATH, encoding="utf-8"))
            for f in fields(cls):
                if f.name in data:
                    try:
                        setattr(s, f.name, type(getattr(s, f.name))(data[f.name]))
                    except (TypeError, ValueError):
                        pass
        except Exception:
            pass
        return s

    def save(self) -> None:
        try:
            json.dump(asdict(self), open(SETTINGS_PATH, "w", encoding="utf-8"), indent=2)
        except Exception as exc:
            print("could not save settings:", exc)


# =============================================================================
#  OCR backends -> list of lines: {"text", "x", "y", "w", "h", "words": [...]}
#  (coordinates in the image that was given)
# =============================================================================
WIN_OCR_PS = r'''
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Globalization.Language,Windows.Globalization,ContentType=WindowsRuntime]
$null = [Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics,ContentType=WindowsRuntime]
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
  $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, $type) {
  $t = $asTaskGeneric.MakeGenericMethod($type).Invoke($null, @($op))
  $t.Wait(-1) | Out-Null
  return $t.Result
}
$lang = New-Object Windows.Globalization.Language("en-US")
$engine = $null
if ([Windows.Media.Ocr.OcrEngine]::IsLanguageSupported($lang)) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang) }
if ($engine -eq $null) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
if ($engine -eq $null) { [Console]::Out.WriteLine("NOENGINE"); [Console]::Out.Flush(); exit 1 }
[Console]::Out.WriteLine("READY"); [Console]::Out.Flush()
while ($true) {
  $path = [Console]::In.ReadLine()
  if ($path -eq $null -or $path -eq "EXIT") { break }
  try {
    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($path)) ([Windows.Storage.StorageFile])
    $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bmp = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $res = Await ($engine.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult])
    $lines = New-Object System.Collections.ArrayList
    foreach ($ln in $res.Lines) {
      $words = New-Object System.Collections.ArrayList
      foreach ($w in $ln.Words) {
        $r = $w.BoundingRect
        [void]$words.Add(@{ t = $w.Text; x = [int]$r.X; y = [int]$r.Y; w = [int]$r.Width; h = [int]$r.Height })
      }
      [void]$lines.Add(@{ text = $ln.Text; words = $words })
    }
    $stream.Dispose()
    [Console]::Out.WriteLine((ConvertTo-Json -InputObject $lines -Depth 5 -Compress))
  } catch {
    [Console]::Out.WriteLine("ERR " + ($_.Exception.Message -replace "[\r\n]+", " "))
  }
  [Console]::Out.Flush()
}
'''


class WindowsOCR:
    name = "Windows OCR (PowerShell)"

    def __init__(self) -> None:
        self.dir = tempfile.mkdtemp(prefix="auctionocr_")
        script = os.path.join(self.dir, "ocr.ps1")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(WIN_OCR_PS)
        ps = shutil.which("powershell.exe") or r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        flags = 0x08000000 if sys.platform.startswith("win") else 0  # CREATE_NO_WINDOW
        self.proc = subprocess.Popen([ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True, encoding="utf-8", errors="replace", creationflags=flags)
        first = self.proc.stdout.readline().strip()
        if first != "READY":
            err = self.proc.stderr.read()[-500:] if first == "" else first
            raise RuntimeError("Windows OCR is not available: " + (err or "no OCR engine") +
                               " (Settings > Time & language > Language: add English)")
        self.n = 0

    def read(self, rgb: np.ndarray) -> List[dict]:
        self.n += 1
        if self.proc.poll() is not None:
            raise RuntimeError("OCR process stopped: " + (self.proc.stderr.read() or "")[-300:])
        h, w = rgb.shape[:2]
        if max(h, w) > 9000:                  # Windows OCR's size limit is 10000 px
            f = 9000.0 / max(h, w)
            ys = (np.arange(int(h * f)) / f).astype(int)
            xs = (np.arange(int(w * f)) / f).astype(int)
            rgb = rgb[ys][:, xs]
        path = os.path.join(self.dir, f"img{self.n % 4}.png")
        af.write_png(path, rgb)
        try:
            self.proc.stdin.write(path + "\n")
            self.proc.stdin.flush()
        except OSError:
            code = self.proc.poll()
            err = ""
            try:
                err = (self.proc.stderr.read() or "").strip().replace("\n", " ")[-400:]
            except Exception:
                pass
            raise RuntimeError(f"PowerShell OCR stopped (exit code {code}): {err or 'no message'}")
        out = self.proc.stdout.readline().strip()
        if out.startswith("ERR"):
            raise RuntimeError(out)
        try:
            data = json.loads(out.lstrip("\ufeff")) if out else []
        except ValueError:
            data = []
        if isinstance(data, dict):
            data = [data]
        lines = []
        for ln in data:
            ws = ln.get("words") or []
            if isinstance(ws, dict):
                ws = [ws]
            if not ws:
                continue
            x0 = min(w["x"] for w in ws)
            y0 = min(w["y"] for w in ws)
            x1 = max(w["x"] + w["w"] for w in ws)
            y1 = max(w["y"] + w["h"] for w in ws)
            lines.append({"text": ln.get("text", " ".join(w["t"] for w in ws)),
                          "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0, "words": ws})
        return lines

    def close(self) -> None:
        try:
            self.proc.stdin.write("EXIT\n")
            self.proc.stdin.flush()
            self.proc.wait(2)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass


class WinRTOCR:
    """Windows' own OCR called directly from Python (pip: winrt-Windows.Media.Ocr
    and friends) - no helper process, nothing to crash."""
    name = "Windows OCR"

    def __init__(self) -> None:
        import asyncio
        from winrt.windows.globalization import Language
        from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.storage.streams import DataWriter
        self._SB, self._PF, self._DW = SoftwareBitmap, BitmapPixelFormat, DataWriter
        eng = None
        try:
            lang = Language("en-US")
            if OcrEngine.is_language_supported(lang):
                eng = OcrEngine.try_create_from_language(lang)
        except Exception:
            eng = None
        if eng is None:
            eng = OcrEngine.try_create_from_user_profile_languages()
        if eng is None:
            raise RuntimeError("no OCR language installed")
        self.engine = eng
        self.loop = asyncio.new_event_loop()

    async def _recognize(self, bmp):
        return await self.engine.recognize_async(bmp)

    def read(self, rgb: np.ndarray) -> List[dict]:
        h, w = rgb.shape[:2]
        if max(h, w) > 9000:
            f = 9000.0 / max(h, w)
            rgb = rgb[(np.arange(int(h * f)) / f).astype(int)][:, (np.arange(int(w * f)) / f).astype(int)]
            h, w = rgb.shape[:2]
        rgba = np.empty((h, w, 4), np.uint8)
        rgba[..., :3] = rgb
        rgba[..., 3] = 255
        dw = self._DW()
        dw.write_bytes(rgba.tobytes())
        bmp = self._SB.create_copy_from_buffer(dw.detach_buffer(), self._PF.RGBA8, w, h)
        res = self.loop.run_until_complete(self._recognize(bmp))
        lines = []
        for ln in res.lines:
            ws = []
            for wd in ln.words:
                r = wd.bounding_rect
                ws.append({"t": wd.text, "x": int(r.x), "y": int(r.y), "w": int(r.width), "h": int(r.height)})
            if not ws:
                continue
            x0 = min(q["x"] for q in ws)
            y0 = min(q["y"] for q in ws)
            x1 = max(q["x"] + q["w"] for q in ws)
            y1 = max(q["y"] + q["h"] for q in ws)
            lines.append({"text": ln.text, "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0, "words": ws})
        return lines

    def close(self) -> None:
        try:
            self.loop.close()
        except Exception:
            pass


class TesseractOCR:
    name = "Tesseract"

    def __init__(self) -> None:
        exe = shutil.which("tesseract")
        if not exe and sys.platform.startswith("win"):
            for c in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                      r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
                if os.path.exists(c):
                    exe = c
        if not exe:
            raise RuntimeError("Tesseract not installed")
        self.exe = exe
        self.dir = tempfile.mkdtemp(prefix="auctionocr_")

    def read(self, rgb: np.ndarray) -> List[dict]:
        path = os.path.join(self.dir, "img.png")
        af.write_png(path, rgb)
        flags = 0x08000000 if sys.platform.startswith("win") else 0
        out = subprocess.run([self.exe, path, "stdout", "--psm", "6", "tsv"], capture_output=True,
                             text=True, creationflags=flags).stdout
        lines: Dict[Tuple[int, int, int], dict] = {}
        for row in out.splitlines()[1:]:
            p = row.split("\t")
            if len(p) < 12 or p[0] != "5" or not p[11].strip():
                continue
            key = (int(p[2]), int(p[3]), int(p[4]))
            w = {"t": p[11], "x": int(p[6]), "y": int(p[7]), "w": int(p[8]), "h": int(p[9])}
            lines.setdefault(key, {"words": []})["words"].append(w)
        res = []
        for ln in lines.values():
            ws = ln["words"]
            x0 = min(w["x"] for w in ws)
            y0 = min(w["y"] for w in ws)
            x1 = max(w["x"] + w["w"] for w in ws)
            y1 = max(w["y"] + w["h"] for w in ws)
            res.append({"text": " ".join(w["t"] for w in ws), "x": x0, "y": y0, "w": x1 - x0,
                        "h": y1 - y0, "words": ws})
        return res

    def close(self) -> None:
        pass


def make_ocr(pref: str):
    errors = []
    order = {"windows": [WinRTOCR, WindowsOCR], "tesseract": [TesseractOCR]}.get(
        pref, [WinRTOCR, WindowsOCR, TesseractOCR])
    for cls in order:
        try:
            return cls()
        except Exception as exc:
            errors.append(f"{cls.name}: {exc}")
    raise RuntimeError("No OCR available. " + " | ".join(errors))


# =============================================================================
#  Finding the auction board (measured at 1280x720; everything scales with
#  the width of the red "Auction House" title banner)
# =============================================================================
@dataclass
class Board:
    bx: float        # banner centre x (absolute screen px)
    by: float        # banner top y
    s: float         # scale (1.0 = banner 162 px wide)

    def pt(self, dx: float, dy: float) -> Tuple[int, int]:
        return int(round(self.bx + dx * self.s)), int(round(self.by + dy * self.s))

    def list_region(self) -> Tuple[int, int, int, int]:
        x0, y0 = self.pt(-176, 49)
        x1, y1 = self.pt(174, 249)
        return x0, y0, x1 - x0, y1 - y0

    def search_point(self) -> Tuple[int, int]:
        return self.pt(101, 36)

    def scroll_point(self) -> Tuple[int, int]:
        return self.pt(-60, 150)   # over the item names, never over a Buy button

    def coins_region(self) -> Tuple[int, int, int, int]:
        x0, y0 = self.pt(-180, 252)
        x1, y1 = self.pt(-40, 270)
        return x0, y0, x1 - x0, y1 - y0


BANNER_W = 168.0  # banner width at the 1280x720 calibration


def find_board(rgb: np.ndarray, origin=(0, 0)) -> Optional[Board]:
    """The red "Auction House" title banner: a solid crimson block about 9-10
    times as wide as it is tall (a red row border is long but thin)."""
    a = rgb.astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    # banner red/pink gradient (#E94C86 at the top .. #7A142D at the bottom);
    # blue >= green rules out the brown wood around it
    crim = (r >= 110) & (r - g >= 60) & (r - b >= 20) & (b >= g)
    H, W = crim.shape
    minw = max(60, int(0.05 * W))
    rows = np.flatnonzero(crim.sum(axis=1) >= minw)
    best = None
    for ys, ye in af.runs(np.isin(np.arange(H), rows), gap=2):
        blk = crim[ys:ye + 1]
        h = ye - ys + 1
        cols = np.flatnonzero(blk.sum(axis=0) >= max(2, 0.4 * h))
        if cols.size == 0:
            continue
        # the widest run of such columns
        cs, ce = max(af.runs(np.isin(np.arange(W), cols), gap=3), key=lambda t: t[1] - t[0])
        w = ce - cs + 1
        fill = float(blk[:, cs:ce + 1].mean())
        # (the banner is ~1/6 of the window's width at any resolution)
        if w < max(minw, 0.08 * W) or h < 6 or not (5.0 <= w / h <= 16.0) or fill < 0.35:
            continue
        # include the banner's lighter top edge rows
        top = ys
        while top - 1 >= 0 and crim[top - 1, cs:ce + 1].mean() > 0.3:
            top -= 1
        # the board's dark panel must be right below it (the minimap's red
        # place-name sign has the game world below it instead)
        sc = w / BANNER_W
        px0, px1 = int((cs + ce) / 2 - 165 * sc), int((cs + ce) / 2 + 165 * sc)
        py0, py1 = int(top + 50 * sc), int(top + 245 * sc)
        if px0 < 0 or px1 > W or py1 > H:
            continue
        panel = rgb[py0:py1, px0:px1].max(axis=2)
        if float((panel < 90).mean()) < 0.55:
            continue
        # and it must have the red X (close) button and the red "Browse" tab
        def crimson_at(dx0, dy0, dx1, dy1):
            ax0, ay0 = int((cs + ce) / 2 + dx0 * sc), int(top + dy0 * sc)
            ax1, ay1 = int((cs + ce) / 2 + dx1 * sc), int(top + dy1 * sc)
            if ax0 < 0 or ay0 < 0 or ax1 > W or ay1 > H or ax1 <= ax0 or ay1 <= ay0:
                return 0.0
            return float(crim[ay0:ay1, ax0:ax1].mean())
        if crimson_at(164, 20, 180, 34) < 0.2 or crimson_at(-172, 30, -128, 42) < 0.2:
            continue
        if best is None or w * h > best[0]:
            best = (w * h, top, cs, ce)
    if best is None:
        return None
    _, top, cs, ce = best
    return Board(bx=origin[0] + (cs + ce) / 2.0, by=origin[1] + top, s=(ce - cs + 1) / BANNER_W)


# =============================================================================
#  Parsing OCR lines of the listing area into rows
# =============================================================================
PRICE_RE = re.compile(r"(\d[\d,.\s]{2,})\s*[cC¢€]?\s*$")
BY_WORDS = r"(?:by|bv|try|wy|ty|ry|hy|ly|hv|tv|bry|bey|boy)"
SELLER_RE = re.compile(r"(?:^|[^A-Za-z])" + BY_WORDS + r"[:;,.]?\s+([A-Za-z0-9_]{2,24})", re.I)
TIME_RE = re.compile(r"(\d{1,3})\s*([hmd])\w*", re.I)

RARITY_BY_COLOUR = {"white": "Limited", "blue": "Legendary", "red": "Mythic"}


def colour_name(rgb: np.ndarray) -> str:
    """Dominant colour of an item name (= its rarity), by hue."""
    import colorsys
    if rgb.size == 0:
        return "?"
    px = rgb.reshape(-1, 3).astype(np.int16)
    br = px.max(axis=1)
    px = px[br >= max(100, np.percentile(br, 80))]
    if len(px) == 0:
        return "?"
    r, g, b = (float(v) / 255.0 for v in np.median(px, axis=0))
    h, sat, val = colorsys.rgb_to_hsv(r, g, b)
    h *= 360
    if sat < 0.16:
        return "white"
    if h < 15 or h >= 330:
        return "red"
    if h < 38:
        return "orange"
    if h < 70:
        return "gold"
    if h < 160:
        return "green"
    if h < 245:
        return "blue"
    return "purple"


def prep_for_ocr(rgb: np.ndarray, up: int) -> np.ndarray:
    """Light text on a dark board -> dark text on white, enlarged (smoothly)."""
    g = rgb.max(axis=2).astype(np.float32)
    lo, hi = np.percentile(g, 35), np.percentile(g, 99.5)
    g = np.clip((g - lo) / max(1.0, hi - lo), 0, 1)
    if up > 1:
        # bilinear enlarge (OCR reads smooth edges better than blocky ones)
        h, w = g.shape
        ys = (np.arange(h * up) + 0.5) / up - 0.5
        xs = (np.arange(w * up) + 0.5) / up - 0.5
        y0 = np.clip(np.floor(ys).astype(int), 0, h - 1)
        x0 = np.clip(np.floor(xs).astype(int), 0, w - 1)
        y1, x1 = np.clip(y0 + 1, 0, h - 1), np.clip(x0 + 1, 0, w - 1)
        fy = np.clip(ys - y0, 0, 1)[:, None]
        fx = np.clip(xs - x0, 0, 1)[None, :]
        g = (g[y0][:, x0] * (1 - fy) * (1 - fx) + g[y0][:, x1] * (1 - fy) * fx
             + g[y1][:, x0] * fy * (1 - fx) + g[y1][:, x1] * fy * fx)
    g = (255 - g * 255).astype(np.uint8)
    return np.stack([g, g, g], axis=2)


def segment_rows(crop: np.ndarray) -> List[Tuple[int, int]]:
    """Fully visible listing rows in the list image: (top, bottom) of each
    row's inside.  Rows are dark bands separated by a bright border line and
    a black gap."""
    m = crop.max(axis=2).astype(np.int16)
    W = m.shape[1]
    core = m[:, int(0.04 * W):int(0.72 * W)]
    med = np.median(core, axis=1)
    dark = (core < 26).mean(axis=1)
    inside = (med >= 22) & (med <= 70) & (dark < 0.6)
    bands = [(s_, e_) for s_, e_ in af.runs(inside, gap=1)]
    if not bands:
        return []
    hs = sorted(e_ - s_ + 1 for s_, e_ in bands)
    full = hs[len(hs) * 3 // 4]          # height of a whole row (most rows are whole)
    return [(s_, e_) for s_, e_ in bands
            if e_ - s_ + 1 >= 0.85 * full and s_ > 0 and e_ < m.shape[0] - 1]


def read_rows(crop: np.ndarray, ocr, up: int = 3) -> List[dict]:
    """Cut every whole row into a name, a seller and a price strip, stack all
    strips into one picture, read it with one OCR call, and put it together."""
    rows = segment_rows(crop)
    if not rows:
        return []
    W = crop.shape[1]
    strips, meta = [], []
    for i, (ya, yb) in enumerate(rows):
        hr = yb - ya + 1
        tx = int(0.085 * W)                       # text starts right of the item icon
        name = crop[ya:ya + int(0.5 * hr) + 1, tx:int(0.66 * W)]
        sub = crop[ya + int(0.47 * hr):yb + 1, tx:int(0.66 * W)]
        price = crop[ya:yb + 1, int(0.62 * W):int(0.865 * W)]
        for kind, img in (("name", name), ("sub", sub), ("price", price)):
            strips.append(prep_for_ocr(img, up))
            meta.append((i, kind))
    gap = 10 * up
    width = max(st.shape[1] for st in strips) + 2 * gap
    sheet, spans, y = [], [], gap
    sheet.append(np.full((gap, width, 3), 255, np.uint8))
    for st in strips:
        h, w = st.shape[:2]
        pad = np.full((h, width, 3), 255, np.uint8)
        pad[:, gap:gap + w] = st
        sheet.append(pad)
        spans.append((y, y + h))
        y += h
        sheet.append(np.full((gap, width, 3), 255, np.uint8))
        y += gap
    lines = ocr.read(np.vstack(sheet))
    texts: Dict[Tuple[int, str], List[Tuple[int, str]]] = {}
    for ln in lines:
        cy = ln["y"] + ln["h"] / 2.0
        for k, (a, b) in enumerate(spans):
            if a - gap / 2 <= cy <= b + gap / 2:
                texts.setdefault(meta[k], []).append((ln["x"], ln["text"]))
                break
    out = []
    for i, (ya, yb) in enumerate(rows):
        get = lambda kind: " ".join(t for _, t in sorted(texts.get((i, kind), []))).strip()
        nm, st, pr = get("name"), get("sub"), get("price")
        digits = re.sub(r"\D", "", re.sub(r"[cC¢€]\s*$", "", pr.replace("O", "0").replace("o", "0")))
        if not nm or not digits or int(digits) <= 0:
            continue
        st = st.replace("|", " ").strip()
        m = SELLER_RE.search(st)
        seller, left, extra = "", "", ""
        if m:
            seller = m.group(1)
            extra = st[:m.start()].strip(" ·•.-★*%>~")
            mt = TIME_RE.search(st[m.end():])
            left = (mt.group(1) + mt.group(2).lower()) if mt else ""
        else:
            words = [w for w in st.split() if re.search(r"[A-Za-z0-9]{2,}", w)]
            seller = words[1] if len(words) > 1 else (words[0] if words else "")
        hr = yb - ya + 1
        nm_img = crop[ya:ya + int(0.5 * hr) + 1, int(0.085 * W):int(0.66 * W)]
        colour = colour_name(nm_img)
        out.append({"item": re.sub(r"\s+", " ", nm.replace("|", " ")).strip(" _-~*+'.,;:"), "seller": seller, "time_left": left,
                    "extra": extra, "price": int(digits), "colour": colour,
                    "rarity": RARITY_BY_COLOUR.get(colour, colour), "y": ya})
    return out


def find_thumb_in(grab, board: "Board") -> Optional[Tuple[int, int, int, int, int]]:
    x0, y0 = board.pt(175.5, 49)       # right of the row borders (a hovered row has a bright one)
    x1, y1 = board.pt(181.5, 249)
    img = grab((x0, y0, max(3, x1 - x0), y1 - y0)).astype(np.int16)
    bright = img.max(axis=2) > 85
    cols = bright.mean(axis=0) < 0.6          # drop full-height lines (the track's border)
    if not cols.any():
        return None
    sub = bright[:, cols]
    need = max(1, int(round(1.0 * board.s)))
    rows = sub.sum(axis=1) >= need
    rs = [(a, b) for a, b in af.runs(rows, gap=1) if b - a + 1 >= max(2, int(2 * board.s))]
    if not rs:
        return None
    a, b = max(rs, key=lambda t: t[1] - t[0])
    if b - a + 1 > 0.9 * (y1 - y0):
        return None
    col_idx = np.flatnonzero(cols)
    hits = bright[a:b + 1][:, cols].sum(axis=0)
    if hits.sum() == 0:
        return None
    cx = float((col_idx * hits).sum() / hits.sum())
    return (int(round(x0 + cx)), y0 + (a + b) // 2, b - a + 1, y0, y1)


def scroll_shift(prev: np.ndarray, cur: np.ndarray) -> Optional[int]:
    """How many pixels the list moved up between two pictures of it (0 = it
    did not move).  None = no overlap found (scrolled more than a screen)."""
    a = prev.max(axis=2)[:, ::3].astype(np.float32)
    b = cur.max(axis=2)[:, ::3].astype(np.float32)
    H = a.shape[0]
    if float(np.abs(a - b).mean()) < 1.0:
        return 0
    best, best_d = None, None
    for d in range(1, int(H * 0.85)):
        diff = float(np.abs(a[d:] - b[:H - d]).mean())
        if best is None or diff < best:
            best, best_d = diff, d
    base = float(np.abs(a - b).mean())
    if best is None or best > 0.45 * base or best > 12.0:
        return None
    return best_d


# =============================================================================
#  The reader
# =============================================================================
class AuctionReader:
    def __init__(self, s: ARSettings, log) -> None:
        self.s = s
        self.log = log
        self.running = False
        self.alive = True
        self.status = "Stopped"
        self.progress = ""
        self.found = 0
        self.ocr = None
        self.last_file = ""
        self.vocab: Dict[str, int] = {}     # item names seen (spelling -> times seen)
        self.partial: Optional[List[dict]] = None   # listings read so far in the running scan

    def excel_path(self) -> str:
        return self.s.excel_path if os.path.isabs(self.s.excel_path) else os.path.join(HERE, self.s.excel_path)

    def save_partial(self) -> None:
        """Keep the Excel file up to date while scanning (and when stopped early)."""
        if self.partial:
            p = save_excel(self.partial, self.excel_path(), self.log, history=False, quiet=True)
            self.last_file = p or self.last_file

    def canonical(self, name: str) -> str:
        """Snap small OCR misspellings onto a name already seen."""
        import difflib
        if not name:
            return name
        for known in sorted(self.vocab, key=lambda k: -self.vocab[k]):
            if known.lower() == name.lower():
                self.vocab[known] += 1
                return known
        m = difflib.get_close_matches(name, list(self.vocab), n=1, cutoff=0.86)
        if m:
            self.vocab[m[0]] += 1
            return m[0]
        self.vocab[name] = 1
        return name

    def load_vocab(self, path: str) -> None:
        try:
            from openpyxl import load_workbook
            wb = load_workbook(path, read_only=True)
            if "Items" in wb.sheetnames:
                for row in wb["Items"].iter_rows(min_row=2, values_only=True):
                    if row and row[0]:
                        self.vocab.setdefault(str(row[0]), 5)
        except Exception:
            pass

    # ---- input helpers (Windows) -------------------------------------------
    def _env(self):
        return self.env

    def move(self, x: int, y: int) -> None:
        """Move the mouse like a real mouse does (Roblox ignores a cursor that
        is just teleported): absolute SendInput move, then a 1px wiggle."""
        u = af._user32
        vx, vy = u.GetSystemMetrics(76), u.GetSystemMetrics(77)      # virtual screen origin
        vw, vh = max(1, u.GetSystemMetrics(78)), max(1, u.GetSystemMetrics(79))
        nx = int(round((x - vx) * 65535 / max(1, vw - 1)))
        ny = int(round((y - vy) * 65535 / max(1, vh - 1)))
        inp = af.INPUT(type=af.INPUT_MOUSE)
        inp.mi = af.MOUSEINPUT(nx, ny, 0, 0x0001 | 0x8000 | 0x4000, 0, 0)  # MOVE|ABSOLUTE|VIRTUALDESK
        af._user32.SendInput(1, (af.INPUT * 1)(inp), af.ctypes.sizeof(af.INPUT))
        time.sleep(0.04)
        for d in (1, -1):
            inp = af.INPUT(type=af.INPUT_MOUSE)
            inp.mi = af.MOUSEINPUT(d, 0, 0, 0x0001, 0, 0)
            af._user32.SendInput(1, (af.INPUT * 1)(inp), af.ctypes.sizeof(af.INPUT))
            time.sleep(0.02)
        u.SetCursorPos(int(x), int(y))
        time.sleep(0.04)

    def move_raw(self, x: int, y: int) -> None:
        u = af._user32
        vx, vy = u.GetSystemMetrics(76), u.GetSystemMetrics(77)
        vw, vh = max(1, u.GetSystemMetrics(78)), max(1, u.GetSystemMetrics(79))
        inp = af.INPUT(type=af.INPUT_MOUSE)
        inp.mi = af.MOUSEINPUT(int(round((x - vx) * 65535 / max(1, vw - 1))),
                               int(round((y - vy) * 65535 / max(1, vh - 1))), 0, 0x0001 | 0x8000 | 0x4000, 0, 0)
        u.SendInput(1, (af.INPUT * 1)(inp), af.ctypes.sizeof(af.INPUT))

    def drag_to(self, x0: int, y0: int, x1: int, y1: int, hold: bool = False) -> None:
        """Press at (x0, y0), slide to (x1, y1) in small steps; release unless hold."""
        self.move(x0, y0)
        self._mouse(af.MOUSEEVENTF_LEFTDOWN, 0)
        time.sleep(0.08)
        n = max(2, int(abs(y1 - y0) / 6))
        for i in range(1, n + 1):
            self.move_raw(int(x0 + (x1 - x0) * i / n), int(y0 + (y1 - y0) * i / n))
            time.sleep(0.01)
        time.sleep(0.05)
        if not hold:
            self._mouse(af.MOUSEEVENTF_LEFTUP, 0)

    def click(self, x: int, y: int) -> None:
        self.move(x, y)
        self._mouse(af.MOUSEEVENTF_LEFTDOWN, 0)
        time.sleep(0.07)
        self._mouse(af.MOUSEEVENTF_LEFTUP, 0)
        time.sleep(0.05)

    def _mouse(self, flags: int, data: int) -> None:
        inp = af.INPUT(type=af.INPUT_MOUSE)
        inp.mi = af.MOUSEINPUT(0, 0, data & 0xFFFFFFFF, flags, 0, 0)
        arr = (af.INPUT * 1)(inp)
        af._user32.SendInput(1, arr, af.ctypes.sizeof(af.INPUT))

    def wheel(self, x: int, y: int, notches: int) -> None:
        cur = af.wintypes.POINT()
        af._user32.GetCursorPos(af.ctypes.byref(cur))
        if abs(cur.x - x) > 3 or abs(cur.y - y) > 3:
            self.move(x, y)
        for _ in range(abs(notches)):
            self._mouse(0x0800, -120 if notches > 0 else 120)  # MOUSEEVENTF_WHEEL
            time.sleep(0.03)

    def key(self, name: str) -> None:
        special = {"BACKSPACE": (0x08, False), "ENTER": (0x0D, False), "END": (0x23, True),
                   "HOME": (0x24, True), "DELETE": (0x2E, True)}
        vk, ext = special.get(name.upper(), (None, False))
        vk = vk or af.vk_from_name(name)
        scan = af._user32.MapVirtualKeyW(vk, 0)
        e = 0x0001 if ext else 0   # KEYEVENTF_EXTENDEDKEY: the real End/Home/Delete, not the numpad ones
        for flags in (af.KEYEVENTF_SCANCODE | e, af.KEYEVENTF_SCANCODE | af.KEYEVENTF_KEYUP | e):
            inp = af.INPUT(type=af.INPUT_KEYBOARD)
            inp.ki = af.KEYBDINPUT(0, scan, flags, 0, 0)
            arr = (af.INPUT * 1)(inp)
            af._user32.SendInput(1, arr, af.ctypes.sizeof(af.INPUT))
            time.sleep(0.012)

    # ---- screen ------------------------------------------------------------
    def grab(self, region):
        return np.ascontiguousarray(self.env.grab(region))

    def locate(self) -> Optional[Board]:
        for hwnd in af.list_game_windows(self.s.window_title or "Roblox") or [None]:
            env = af.WindowsEnv(af.Settings(), hwnd) if hwnd else af.WindowsEnv(af.Settings())
            reg = env.game_region()
            img = np.ascontiguousarray(env.grab(reg))
            b = find_board(img, (reg[0], reg[1]))
            if b is not None:
                self.env, self.hwnd = env, hwnd
                return b
        return None

    def read_screen(self, board: Board) -> List[dict]:
        crop = self.grab(board.list_region())
        up = 3 if board.s < 1.4 else 2
        if self.s.save_debug_images:
            os.makedirs(os.path.join(HERE, "auction_debug"), exist_ok=True)
            af.write_png(os.path.join(HERE, "auction_debug", f"list_{int(time.time() * 1000)}.png"), crop)
        return read_rows(crop, self, up)

    def read(self, img):
        return self._ocr_read(img)

    def _ocr_read(self, img):
        """OCR with one automatic restart if the reader process died."""
        try:
            return self.ocr.read(img)
        except Exception as exc:
            self.log(f"Text reader problem ({exc!r}) - restarting it.")
            try:
                self.ocr.close()
            except Exception:
                pass
            self.ocr = make_ocr(self.s.ocr_backend)
            return self.ocr.read(img)

    # ---- one full scan -----------------------------------------------------
    def find_thumb(self, board: Board) -> Optional[Tuple[int, int, int, int, int]]:
        """The scroll bar handle right of the Buy buttons: (x, y_mid, height,
        track_top, track_bottom) in screen px, or None (no scroll bar).
        x is the middle of the handle's own bright pixels (the bar is only a
        few pixels wide - aiming at a computed spot can miss it)."""
        return find_thumb_in(self.grab, board)

    def _search_box_img(self, board: Board) -> np.ndarray:
        x0, y0 = board.pt(50, 29)
        x1, y1 = board.pt(152, 43)
        return self.grab((x0, y0, x1 - x0, y1 - y0)).astype(np.int16)

    def _type_search(self, board: Board, term: str) -> bool:
        """Click the search bar, clear it, type `term`, move the mouse away.
        One quick check that something appeared; one retry if not."""
        sx, sy = board.search_point()
        px, py = board.scroll_point()
        for attempt in range(2):
            before = self._search_box_img(board)
            self.click(sx, sy)
            time.sleep(0.3)
            self.clear_search()
            time.sleep(0.15)
            for ch in term:
                self.key(ch)
                time.sleep(0.03)
            self.move(px, py)                # keep the mouse off the search bar
            time.sleep(0.3)
            if not term:
                return True
            after = self._search_box_img(board)
            changed = int((np.abs(after - before).max(axis=2) > 40).sum())
            if changed >= max(3, int(3 * board.s * board.s)):
                return True
            if attempt == 0:
                self.log(f"Couldn't see '{term}' appear in the search bar - typing it once more.")
        return True   # carry on anyway: the results check below shows what the list holds

    def clear_search(self) -> None:
        """Empty the search bar wherever the text cursor is: End + Backspaces,
        then Home + Deletes."""
        self.key("END")
        for _ in range(25):
            self.key("BACKSPACE")
        self.key("HOME")
        for _ in range(25):
            self.key("DELETE")

    def _wait_results(self, board: Board, before: Optional[np.ndarray], timeout: float = 8.0) -> np.ndarray:
        """The auction house takes a moment to answer a search: wait until the
        list has changed (or a while has passed) and then stopped changing."""
        t0 = time.time()
        last = None
        stable_since = None
        while True:
            img = self.grab(board.list_region()).astype(np.int16)
            now = time.time()
            if last is not None and float(np.abs(img - last).mean()) < 1.0:
                stable_since = stable_since or now
            else:
                stable_since = None
            changed = before is None or float(np.abs(img - before).mean()) > 2.0
            if stable_since and now - stable_since >= 0.4 and (changed or now - t0 > 2.5) and now - t0 > 0.6:
                return img
            if now - t0 > timeout:
                return img
            last = img
            time.sleep(0.15)

    def scan(self) -> Optional[List[dict]]:
        board = self.locate()
        if board is None:
            self.log("Waiting for the auction board - open it (Browse tab) and keep it visible.")
            t_end = time.time() + 120
            while board is None and self.running and time.time() < t_end:
                self.progress = "waiting for the auction board"
                time.sleep(1.0)
                board = self.locate()
            if board is None:
                self.log("No auction board found.")
                return None
            time.sleep(1.5)  # it has just opened: let the first page load
        if self.hwnd:
            af.force_foreground(self.hwnd)
            time.sleep(0.2)
        self.log(f"Auction board found (scale {board.s:.2f}). Reading with {self.ocr.name}.")
        terms = [t for t in re.split(r"[\s,;]+", self.s.search_terms.strip()) if t] or [""]
        stamp = time.strftime("%Y-%m-%d %H:%M")
        overall: Dict[tuple, Tuple[int, dict]] = {}   # listing key -> (how many, example row)
        px, py = board.scroll_point()
        notches = max(1, int(self.s.scroll_notches))
        for ti, term in enumerate(terms):
            if not self.running:
                return None
            self.progress = f"search '{term}' ({ti + 1}/{len(terms)})"
            before = self.grab(board.list_region()).astype(np.int16)
            if not self._type_search(board, term):
                self.log(f"Could not type '{term}' into the search bar - skipping it.")
                continue
            time.sleep(self.s.wait_after_typing_s)
            self._wait_results(board, before)
            by_pos: Dict[int, dict] = {}     # position in the list -> row (keeps true duplicates)
            pitch = max(8.0, 32.0 * board.s)
            offset = 0.0                     # how far we have scrolled (list pixels)

            def take(img):
                for row in self.read_screen_img(img, board):
                    row["item"] = self.canonical(row["item"])
                    pos = int(round((offset + row["y"]) / pitch))
                    if pos not in by_pos:
                        by_pos[pos] = row
                self.found = sum(n for n, _ in overall.values()) + len(by_pos)

            use_wheel = False
            thumb = self.find_thumb(board)
            if thumb is not None:
                # drag the scroll bar handle: much faster than the mouse wheel
                tx, ty, th, top, bottom = thumb
                self.drag_to(tx, ty, tx, top - 5)          # handle to the very top
                time.sleep(self.s.wait_after_scroll_s)
                thumb = self.find_thumb(board)
            if thumb is None:
                self.wheel(px, py, -60)                     # short list / no handle: wheel
                time.sleep(self.s.wait_after_scroll_s)
            prev = self.grab(board.list_region())
            take(prev)
            if thumb is not None:
                tx, ty, th, top, bottom = thumb
                H = prev.shape[0]
                step = max(1.0, 0.7 * th)                   # handle px per ~0.7 screen (first guess)
                y = float(ty)
                self.move(tx, ty)
                self._mouse(af.MOUSEEVENTF_LEFTDOWN, 0)
                time.sleep(0.08)
                still = 0
                try:
                    for page in range(self.s.max_pages_per_term):
                        if not self.running:
                            return None
                        y_try = min(float(bottom + 5), y + step)
                        self.move_raw(tx, int(round(y_try)))
                        time.sleep(self.s.wait_after_scroll_s)
                        img = self.grab(board.list_region())
                        shift = scroll_shift(prev, img)
                        if shift is None:                   # jumped more than a screen: go back halfway
                            step = max(1.0, step * 0.5)
                            self.move_raw(tx, int(round(y + step)))
                            time.sleep(self.s.wait_after_scroll_s)
                            img = self.grab(board.list_region())
                            shift = scroll_shift(prev, img)
                            y_try = y + step
                            if shift is None:
                                self.log("Lost track of the list position - some rows may be missing.")
                                shift = int(0.6 * H)
                        y = y_try
                        if shift == 0:
                            still += 1
                            if offset == 0 and still >= 2:
                                use_wheel = True            # the drag never moved the list
                                self.log("The scroll bar didn't respond - using the mouse wheel instead.")
                                break
                            if still >= 2 or y >= bottom:
                                break                       # bottom of the list
                            step *= 2
                            continue
                        still = 0
                        offset += shift
                        take(img)
                        prev = img
                        step = max(1.0, min(4.0 * th + 4, step * (0.7 * H) / shift))
                finally:
                    self._mouse(af.MOUSEEVENTF_LEFTUP, 0)
            if thumb is None or use_wheel:
                for page in range(self.s.max_pages_per_term):
                    if not self.running:
                        return None
                    self.wheel(px, py, notches)
                    time.sleep(self.s.wait_after_scroll_s)
                    img = self.grab(board.list_region())
                    shift = scroll_shift(prev, img)
                    if shift == 0:
                        break
                    if shift is None:
                        self.wheel(px, py, -notches)
                        time.sleep(self.s.wait_after_scroll_s)
                        notches = max(1, notches // 2)
                        continue
                    offset += shift
                    notches = int(max(1, min(20, round(0.6 * img.shape[0] / max(1.0, shift / notches)))))
                    take(img)
                    prev = img
            counts: Dict[tuple, int] = {}
            for row in by_pos.values():
                k = (row["item"].lower(), row["seller"].lower(), row["price"])
                counts[k] = counts.get(k, 0) + 1
                if k not in overall:
                    row.update(search=term, scanned=stamp)
                    overall[k] = (0, row)
            for k, n in counts.items():
                if n > overall[k][0]:
                    overall[k] = (n, overall[k][1])
            total = sum(n for n, _ in overall.values())
            self.log(f"'{term}': {len(by_pos)} listing(s) shown, {total} different listings so far.")
            self.partial = [dict(r) for n, r in overall.values() for _ in range(n)]
            self.save_partial()
        self._type_search(board, "")
        self.partial = None
        out = []
        for n, row in overall.values():
            out.extend(dict(row) for _ in range(n))
        return out

    def read_screen_img(self, crop: np.ndarray, board: Board) -> List[dict]:
        up = 3 if board.s < 1.4 else 2
        if self.s.save_debug_images:
            os.makedirs(os.path.join(HERE, "auction_debug"), exist_ok=True)
            af.write_png(os.path.join(HERE, "auction_debug", f"list_{int(time.time() * 1000)}.png"), crop)
        return read_rows(crop, self, up)

    # ---- loop --------------------------------------------------------------
    def run_forever(self) -> None:
        while self.alive:
            if not self.running:
                time.sleep(0.1)
                continue
            try:
                if self.ocr is None:
                    self.status = "Starting OCR..."
                    self.ocr = make_ocr(self.s.ocr_backend)
                    self.log(f"Text reader: {self.ocr.name}.")
                    xl = self.s.excel_path if os.path.isabs(self.s.excel_path) else os.path.join(HERE, self.s.excel_path)
                    self.load_vocab(xl)
                self.status = "Scanning"
                rows = self.scan()
                if rows is None and self.partial:
                    self.save_partial()
                    self.log(f"Stopped early: {len(self.partial)} listings saved to {self.last_file}.")
                    self.partial = None
                if rows is not None:
                    path = save_excel(rows, os.path.join(HERE, self.s.excel_path) if not os.path.isabs(
                        self.s.excel_path) else self.s.excel_path, self.log)
                    self.last_file = path or self.last_file
                    self.log(f"Scan done: {len(rows)} listings saved to {path}.")
                if self.s.repeat_minutes > 0 and self.running:
                    self.status = "Waiting for next scan"
                    end = time.time() + self.s.repeat_minutes * 60
                    while self.running and time.time() < end:
                        self.progress = f"next scan in {int(end - time.time())}s"
                        time.sleep(0.5)
                else:
                    self.running = False
                    self.status = "Done"
            except Exception as exc:
                self.log(f"Error: {exc!r}")
                traceback.print_exc()
                self.running = False
                self.status = "Error"


# =============================================================================
#  Excel
# =============================================================================
def save_excel(rows: List[dict], path: str, log, history: bool = True, quiet: bool = False) -> Optional[str]:
    try:
        from openpyxl import Workbook, load_workbook
        from openpyxl.styles import Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        log("openpyxl is missing: python -m pip install --user openpyxl")
        return None
    cols = ["scanned", "item", "rarity", "price", "seller", "time_left", "extra", "search"]
    heads = ["Scanned", "Item", "Rarity", "Price", "Seller", "Time left", "Note", "Found by search"]
    try:
        wb = load_workbook(path) if os.path.exists(path) else Workbook()
    except Exception:
        wb = Workbook()
    bold = Font(bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="7A1F2B")

    def sheet(name, headers, widths):
        if name in wb.sheetnames:
            del wb[name]
        ws = wb.create_sheet(name)
        ws.append(headers)
        for i, h in enumerate(headers, 1):
            c = ws.cell(row=1, column=i)
            c.font, c.fill = bold, fill
            ws.column_dimensions[get_column_letter(i)].width = widths[i - 1]
        ws.freeze_panes = "A2"
        return ws

    rows = sorted(rows, key=lambda r: (r["item"].lower(), r["price"]))
    ws = sheet("Latest scan", heads, [17, 34, 11, 14, 20, 10, 18, 9])
    for r in rows:
        ws.append([r.get(c, "") for c in cols])
        ws.cell(row=ws.max_row, column=4).number_format = "#,##0"
    ws.auto_filter.ref = ws.dimensions

    by_item: Dict[str, List[dict]] = {}
    for r in rows:
        by_item.setdefault(r["item"], []).append(r)
    ws2 = sheet("Items", ["Item", "Rarity", "Listings", "Cheapest", "Median", "Highest",
                          "Cheapest seller", "You keep if sold at cheapest (95%)"],
                [34, 11, 9, 13, 13, 13, 20, 18])
    for item in sorted(by_item, key=str.lower):
        ps = sorted(r["price"] for r in by_item[item])
        cheap = min(by_item[item], key=lambda r: r["price"])
        ws2.append([item, cheap["rarity"], len(ps), ps[0], statistics.median(ps), ps[-1],
                    cheap["seller"], round(ps[0] * 0.95)])
        for c in (4, 5, 6, 8):
            ws2.cell(row=ws2.max_row, column=c).number_format = "#,##0"
    ws2.auto_filter.ref = ws2.dimensions

    if "History" not in wb.sheetnames:
        wh = wb.create_sheet("History")
        wh.append(heads)
        for i in range(1, len(heads) + 1):
            c = wh.cell(row=1, column=i)
            c.font, c.fill = bold, fill
        wh.freeze_panes = "A2"
    if history:   # only finished scans go into the history (partial saves don't)
        wh = wb["History"]
        for r in rows:
            wh.append([r.get(c, "") for c in cols])
    for name in list(wb.sheetnames):
        if name not in ("Latest scan", "Items", "History"):
            del wb[name]
    wb._sheets.sort(key=lambda s: ["Latest scan", "Items", "History"].index(s.title))
    for target in (path, path.replace(".xlsx", f"_{time.strftime('%H%M%S')}.xlsx")):
        try:
            wb.save(target)
            if target != path and not quiet:
                log(f"{os.path.basename(path)} is open in Excel - saved to {os.path.basename(target)} instead.")
            return target
        except PermissionError:
            continue
    log("Could not save the Excel file.")
    return None


# =============================================================================
#  GUI
# =============================================================================
def run_gui() -> None:
    import queue
    import tkinter as tk
    from tkinter import scrolledtext

    s = ARSettings.load()
    q: "queue.Queue[str]" = queue.Queue()

    def log(m):
        line = f"[{time.strftime('%H:%M:%S')}] {m}"
        print(line)
        q.put(line)

    rd = AuctionReader(s, log)
    threading.Thread(target=rd.run_forever, daemon=True).start()
    env0 = af.WindowsEnv(af.Settings())

    root = tk.Tk()
    root.title(f"{APP} {VERSION}")
    root.attributes("-topmost", True)
    BG, FG = "#151b23", "#e6edf3"
    root.configure(bg=BG)
    btn = tk.Button(root, text=f"START ({s.toggle_hotkey})", font=("Segoe UI", 15, "bold"), bg="#2ea043",
                    fg="white", relief="flat", width=22)
    btn.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 4), sticky="ew")
    st_var, pr_var = tk.StringVar(value="Open the auction board, then press START."), tk.StringVar()
    tk.Label(root, textvariable=st_var, bg=BG, fg=FG, font=("Segoe UI", 11, "bold")).grid(
        row=1, column=0, columnspan=2, sticky="w", padx=10)
    tk.Label(root, textvariable=pr_var, bg=BG, fg="#8b98a5", font=("Consolas", 9)).grid(
        row=2, column=0, columnspan=2, sticky="w", padx=10)

    def field(r, label, var, width=40):
        tk.Label(root, text=label, bg=BG, fg=FG).grid(row=r, column=0, sticky="w", padx=10, pady=2)
        e = tk.Entry(root, textvariable=var, width=width, bg="#0d1117", fg=FG, insertbackground=FG, relief="flat")
        e.grid(row=r, column=1, sticky="ew", padx=10, pady=2)

    terms = tk.StringVar(value=s.search_terms)
    rep = tk.StringVar(value=f"{s.repeat_minutes:g}")
    field(3, "Search terms", terms)
    field(4, "Repeat every (min, 0 = once)", rep, 8)

    def apply():
        s.search_terms = terms.get()
        try:
            s.repeat_minutes = max(0.0, float(rep.get()))
        except ValueError:
            pass

    def toggle():
        apply()
        if rd.running:
            rd.running = False
            log("Stopping...")
        else:
            s.save()
            rd.running = True
            log("Started.")

    def open_excel():
        p = rd.last_file or os.path.join(HERE, s.excel_path)
        if os.path.exists(p):
            os.startfile(p)  # type: ignore[attr-defined]
        else:
            log("No Excel file yet - run a scan first.")

    btn.configure(command=toggle)
    tk.Button(root, text="Open Excel file", command=open_excel, bg="#30363d", fg=FG, relief="flat").grid(
        row=5, column=0, columnspan=2, sticky="ew", padx=10, pady=4)
    box = scrolledtext.ScrolledText(root, width=70, height=12, bg="#0d1117", fg="#c9d1d9",
                                    font=("Consolas", 9), relief="flat")
    box.grid(row=6, column=0, columnspan=2, padx=10, pady=(4, 10))
    hk = {"down": False}

    def poll():
        down = env0.key_down(s.toggle_hotkey)
        if down and not hk["down"]:
            toggle()
        hk["down"] = down
        try:
            while True:
                box.insert("end", q.get_nowait() + "\n")
                box.see("end")
        except queue.Empty:
            pass
        btn.configure(text=("STOP" if rd.running else "START") + f" ({s.toggle_hotkey})",
                      bg="#d73a49" if rd.running else "#2ea043")
        st_var.set(f"{rd.status}  -  {rd.found} listings read" if rd.running or rd.found else rd.status)
        pr_var.set(rd.progress if rd.running else "")
        root.after(100, poll)

    def close():
        apply()
        s.save()
        rd.running = False
        rd.alive = False
        if rd.ocr:
            rd.ocr.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    log(f"{APP} {VERSION}: open the auction board in Roblox (Browse tab), then press START "
        f"or {s.toggle_hotkey}. Don't touch the mouse while it scans.")
    root.after(100, poll)
    root.mainloop()


if __name__ == "__main__":
    if not sys.platform.startswith("win"):
        print("Windows only.")
        sys.exit(1)
    af.set_dpi_awareness()
    run_gui()
