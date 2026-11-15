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
VERSION = "1.0"
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
    [Console]::Out.WriteLine("ERR " + $_.Exception.Message)
  }
  [Console]::Out.Flush()
}
'''


class WindowsOCR:
    name = "Windows OCR"

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
        path = os.path.join(self.dir, f"img{self.n % 4}.png")
        af.write_png(path, rgb)
        self.proc.stdin.write(path + "\n")
        self.proc.stdin.flush()
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
    order = {"windows": [WindowsOCR], "tesseract": [TesseractOCR]}.get(pref, [WindowsOCR, TesseractOCR])
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
        if w < minw or h < 6 or not (5.0 <= w / h <= 16.0) or fill < 0.35:
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
            seller = st.split()[1] if len(st.split()) > 1 else st
        hr = yb - ya + 1
        nm_img = crop[ya:ya + int(0.5 * hr) + 1, int(0.085 * W):int(0.66 * W)]
        colour = colour_name(nm_img)
        out.append({"item": re.sub(r"\s+", " ", nm.replace("|", " ")).strip(" _-~*+'.,;:"), "seller": seller, "time_left": left,
                    "extra": extra, "price": int(digits), "colour": colour,
                    "rarity": RARITY_BY_COLOUR.get(colour, colour), "y": ya})
    return out


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

    def click(self, x: int, y: int) -> None:
        u = af._user32
        u.SetCursorPos(int(x), int(y))
        time.sleep(0.05)
        self._mouse(af.MOUSEEVENTF_LEFTDOWN, 0)
        time.sleep(0.05)
        self._mouse(af.MOUSEEVENTF_LEFTUP, 0)

    def _mouse(self, flags: int, data: int) -> None:
        inp = af.INPUT(type=af.INPUT_MOUSE)
        inp.mi = af.MOUSEINPUT(0, 0, data & 0xFFFFFFFF, flags, 0, 0)
        arr = (af.INPUT * 1)(inp)
        af._user32.SendInput(1, arr, af.ctypes.sizeof(af.INPUT))

    def wheel(self, x: int, y: int, notches: int) -> None:
        af._user32.SetCursorPos(int(x), int(y))
        time.sleep(0.03)
        for _ in range(abs(notches)):
            self._mouse(0x0800, -120 if notches > 0 else 120)  # MOUSEEVENTF_WHEEL
            time.sleep(0.03)

    def key(self, name: str) -> None:
        vk = {"BACKSPACE": 0x08, "ENTER": 0x0D}.get(name.upper()) or af.vk_from_name(name)
        scan = af._user32.MapVirtualKeyW(vk, 0)
        for flags in (af.KEYEVENTF_SCANCODE, af.KEYEVENTF_SCANCODE | af.KEYEVENTF_KEYUP):
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
        return read_rows(crop, self.ocr, up)

    # ---- one full scan -----------------------------------------------------
    def _type_search(self, board: Board, term: str) -> None:
        sx, sy = board.search_point()
        self.click(sx, sy)
        time.sleep(0.15)
        for _ in range(30):
            self.key("BACKSPACE")
        for ch in term:
            self.key(ch)

    def scan(self) -> Optional[List[dict]]:
        board = self.locate()
        if board is None:
            self.log("Can't see the auction board. Open it (Browse tab) and keep it visible.")
            return None
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
            self._type_search(board, term)
            time.sleep(self.s.wait_after_typing_s)
            self.wheel(px, py, -60)          # back to the top
            time.sleep(self.s.wait_after_scroll_s)
            by_pos: Dict[int, dict] = {}     # position in the list -> row (keeps true duplicates)
            offset = 0.0                     # how far we have scrolled (list pixels)
            prev = None
            for page in range(self.s.max_pages_per_term):
                if not self.running:
                    return None
                img = self.grab(board.list_region())
                if prev is not None:
                    shift = scroll_shift(prev, img)
                    if shift is None:
                        # scrolled further than one screen: step back and take smaller steps
                        self.wheel(px, py, -notches)
                        time.sleep(self.s.wait_after_scroll_s)
                        notches = max(1, notches // 2)
                        img = self.grab(board.list_region())
                        shift = scroll_shift(prev, img)
                        if shift is None:
                            self.log("Lost track of the scroll position - some rows may be missing.")
                            shift = int(0.5 * img.shape[0])
                    if shift == 0:
                        break                # nothing moved: bottom of the list
                    offset += shift
                    # aim for ~60% of a screen per step
                    per = shift / max(1, notches)
                    notches = int(max(1, min(20, round(0.6 * img.shape[0] / max(1.0, per)))))
                rows = self.read_screen_img(img, board)
                pitch = max(8.0, 32.0 * board.s)
                for row in rows:
                    row["item"] = self.canonical(row["item"])
                    pos = int(round((offset + row["y"]) / pitch))
                    if pos not in by_pos:
                        by_pos[pos] = row
                self.found = sum(n for n, _ in overall.values()) + len(by_pos)
                prev = img
                self.wheel(px, py, notches)
                time.sleep(self.s.wait_after_scroll_s)
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
        self._type_search(board, "")
        out = []
        for n, row in overall.values():
            out.extend(dict(row) for _ in range(n))
        return out

    def read_screen_img(self, crop: np.ndarray, board: Board) -> List[dict]:
        up = 3 if board.s < 1.4 else 2
        if self.s.save_debug_images:
            os.makedirs(os.path.join(HERE, "auction_debug"), exist_ok=True)
            af.write_png(os.path.join(HERE, "auction_debug", f"list_{int(time.time() * 1000)}.png"), crop)
        return read_rows(crop, self.ocr, up)

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
def save_excel(rows: List[dict], path: str, log) -> Optional[str]:
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
            if target != path:
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
