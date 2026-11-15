# -*- coding: utf-8 -*-
"""
AuctionBot - trades on the Roblox auction board by itself.

    python auction_bot.py        (or double-click START_AUCTION_BOT.bat)

Open the auction board (Browse tab) and press START / F8.  Every cycle it:

  1. WATCH  - searches YOUR watch list (White Death, White Dragon Scale,
     Whitescale, Whiteflame Ember, Divine Darkness, Darkness Within, Abyssal
     Devastator, Gem, Gold Ore, Opal), reading every listing and tracking each
     item's FLOOR price (cheapest listing) over time.
  2. BUY    - a listing is bought only if it can be resold for a profit after
     the 5% fee at TODAY's floor (the price it would have to undercut), it is
     Legendary or better (except "any rarity" items), not on the never-buy
     list, and every money rule passes.  The price is read twice and checked
     against the coins that actually left your balance; anything odd pauses
     buying (circuit breaker).
  3. SALES  - reads My Listings: a listing missing from two good reads in a row
     has SOLD (time from listing to sale and the profit are recorded).
     Undercut listings are cancelled and relisted (never below cost + margin).
  4. SELL   - everything the bot bought is listed from the Sell tab just under
     the cheapest competitor.  Items you owned before are never touched.
  5. LEARN  - market sales, its own sales, items that didn't sell, floor
     history -> values, margins and which items to avoid.

Everything is written to auction_bot.xlsx and auction_bot_state.json.
"Paper trading" makes every decision and records it without clicking.
"""
from __future__ import annotations

import difflib
import json
import math
import os
import queue
import re
import statistics
import sys
import threading
import time
import traceback
from dataclasses import asdict, dataclass, fields
from typing import Dict, List, Optional, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import autofish as af            # noqa: E402
import auction_reader as ar      # noqa: E402

APP = "AuctionBot"
VERSION = "2.1"
STATE_PATH = os.path.join(HERE, "auction_bot_state.json")
SETTINGS_PATH = os.path.join(HERE, "auction_bot_settings.json")
FEE_KEEP = 0.95                  # the auction house keeps 5%
H = 3600.0
DAY = 24 * H

OLD_WATCH_DEFAULTS = (
    "White Dragon Scale; Whitescale; White Death; Whitedeath; Divine Darkness; Darkness Within; "
    "Abyssal Devastator; Gem",
)


@dataclass
class BotSettings(ar.ARSettings):
    settings_version: str = VERSION
    # ---- what to watch (";" between items) -------------------------------------
    # Searched every cycle and (buy_only_watched) the only things it buys.  A
    # term matches any item whose name contains it (spaces ignored), so
    # "White Death" also covers Crystal/Frostbitten White Death, Heart of the
    # White Death and White Death armour.
    watch_items: str = ("White Death; Whitedeath; White Dragon Scale; Whitescale; Whiteflame Ember; "
                        "Divine Darkness; Darkness Within; Abyssal Devastator; Gem; Gold Ore; Opal")
    # never bought.  A LONGER watch-list name wins: "Abyssal" blocks every
    # Abyssal item except the Abyssal Devastator (on the watch list).
    never_buy: str = "Celestial Scepter; Abyssal"
    # sell fast: the normal margin applies even before the bot has seen them sell
    high_demand_items: str = "White Dragon Scale; Heart of the White Death; Whiteflame Ember; Darkness Within"
    # bought only well under their usual floor, held for a better price
    long_term_items: str = "Gold Ore; Opal"
    # bought whatever their rarity (forging materials)
    any_rarity_items: str = "Gold Ore; Opal"
    min_buy_rarity: str = "Legendary"       # Uncommon<Rare<Epic<Legendary<Mythic<Divine; Limited always passes
    mutations: str = ("Plump Huge Frostbitten Golden Blazing Shadow Crystal Ancient Celestial Charged "
                      "Frenzied Voidtouched")
    buy_only_watched: bool = True
    auto_watch: bool = False                # also search the "trending" items it learns
    watch_size: int = 14
    known_values: str = "The Divine Darkness=9500000; The Darkness Within=5100000"   # item=value; ...
    min_item_value: int = 20000
    cycle_pause_s: float = 20.0
    # ---- buying -------------------------------------------------------------------
    min_profit_pct: float = 15.0            # profit after fee, % of the buy price (fast sellers)
    slow_profit_pct: float = 30.0           # ... for items not seen selling >= 1/day
    min_profit_coins: int = 10000
    steal_ratio: float = 0.40               # price <= 40% of value -> a steal
    max_buy_frac: float = 0.40              # never spend more than this share of your coins on one item
    max_stock_frac: float = 0.60            # bought items (at cost) may be at most this share of net worth
    coin_reserve: int = 50000
    daily_spend_cap: int = 3000000          # per 24 hours (rolling)
    min_value_points: int = 2               # other listings/sales needed before trusting a value
    max_hold_per_item: int = 2              # bag + listed, per item (high-demand items: +1)
    long_term_buy_ratio: float = 0.75       # long-term items: buy at <= 75% of their usual floor
    long_term_max_hold: int = 5
    max_buys_per_cycle: int = 2             # learn whether they sell before buying more
    falling_floor_pct: float = 20.0         # floor down this much in 24h -> only steals of that item
    # ---- selling ---------------------------------------------------------------------
    undercut_pct: float = 1.0
    min_list_margin_pct: float = 5.0        # never list below cost/0.95 * (1 + this)
    long_term_margin_pct: float = 25.0      # long-term items: at least this much over cost
    relist_after_min: float = 45.0
    max_active_listings: int = 12
    rare_value: int = 250000
    rare_rarities: str = "Mythic Divine Limited"
    keep_one_rare: bool = False             # (old option) keep one copy of rare items it BOUGHT
    sell_only_bought: bool = True           # only sell what the bot bought - your own items are safe
    # ---- safety ----------------------------------------------------------------------
    pause_on_drop_pct: float = 15.0         # pause buying if net worth falls this % below today's start
    paper_trading: bool = False
    bot_hotkey: str = "F8"
    excel_out: str = "auction_bot.xlsx"
    seed_excel: str = "auction_listings.xlsx"

    @classmethod
    def load(cls) -> "BotSettings":
        s = cls()
        try:
            data = json.load(open(SETTINGS_PATH, encoding="utf-8"))
        except Exception:
            return s
        for f in fields(cls):
            if f.name in data and f.name != "settings_version":
                try:
                    setattr(s, f.name, type(getattr(s, f.name))(data[f.name]))
                except (TypeError, ValueError):
                    pass
        if data.get("settings_version") != VERSION:      # saved by an older version: new defaults
            d = cls()
            if data.get("watch_items") in OLD_WATCH_DEFAULTS:
                s.watch_items = d.watch_items
            if data.get("never_buy") in ("Celestial Scepter",):
                s.never_buy = d.never_buy
            if data.get("rare_rarities") == "Mythic Limited":
                s.rare_rarities = d.rare_rarities
            s.keep_one_rare = False                      # you chose: sell everything the bot buys
            s.max_hold_per_item = min(s.max_hold_per_item, d.max_hold_per_item)
            s.max_buy_frac = min(s.max_buy_frac, d.max_buy_frac)
        return s

    def save(self) -> None:
        try:
            d = asdict(self)
            d["settings_version"] = VERSION
            json.dump(d, open(SETTINGS_PATH, "w", encoding="utf-8"), indent=2)
        except Exception:
            pass


# =============================================================================
#  Names, rarity
# =============================================================================
def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()


def compact(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def split_terms(text: str) -> List[str]:
    return [t.strip() for t in re.split(r"[;,\n]+", text or "") if t.strip()]


def matches_any(item: str, terms: List[str]) -> bool:
    c = compact(item)
    return any(compact(t) and compact(t) in c for t in terms)


def blocked(item: str, never: List[str], watch: List[str]) -> bool:
    """On the never-buy list - unless a more specific watch-list name matches."""
    c = compact(item)
    for t in never:
        ct = compact(t)
        if ct and ct in c and not any(compact(w) and compact(w) in c and len(compact(w)) > len(ct)
                                      for w in watch):
            return True
    return False


def hours_left(text: str) -> Optional[float]:
    m = re.search(r"(\d{1,3})\s*([hmd])", text or "", re.I)
    if not m:
        return None
    v, u = int(m.group(1)), m.group(2).lower()
    return v / 60.0 if u == "m" else (v * 24.0 if u == "d" else float(v))


RARITY_RANK = {"common": 0, "uncommon": 1, "rare": 2, "epic": 3, "legendary": 4, "mythic": 5,
               "divine": 6, "limited": 7}
COLOUR_RARITY = {"green": "Uncommon", "blue": "Rare", "purple": "Epic", "orange": "Legendary",
                 "red": "Mythic", "gold": "Divine", "white": "Limited"}
OLD_LABEL_COLOUR = {"limited": "white", "legendary": "blue", "mythic": "red"}   # labels of v1.x scans
NEGATIVE = re.compile(r"\b(not|can'?t|cannot|fail|failed|already|sold out|unable|enough|error|max|limit)\b", re.I)


def fmt(v) -> str:
    return f"{int(round(v)):,}" if v is not None else "?"


# =============================================================================
#  Market memory
# =============================================================================
class Market:
    """Every listing seen (per item, seller, price and name colour), inferred
    market sales, floor-price history, values."""

    def __init__(self, data: Optional[dict] = None) -> None:
        d = data or {}
        obs = d.get("obs", {})
        # v1.x observations had no colour / scan counts: start the live view fresh
        self.obs: Dict[str, dict] = {k: o for k, o in obs.items() if "scans" in o}
        self.sales: List[dict] = d.get("sales", [])
        self.names: Dict[str, str] = d.get("names", {})
        self.rarity: Dict[str, str] = d.get("rarity", {})            # display only
        self.colours: Dict[str, Dict[str, int]] = d.get("colours", {})   # item -> {name colour: times}
        self.true_rarity: Dict[str, str] = d.get("true_rarity", {})  # from the Sell tab / "Limited"
        self.seed: Dict[str, dict] = d.get("seed", {})
        self.floors: Dict[str, List[list]] = d.get("floors", {})     # item -> [[time, floor, listed]]
        self.scan_id: int = d.get("scan_id", 0)
        if "colours" not in d:
            for n, c in d.get("colour", {}).items():
                self.colours[n] = {c: 3}
            for n, lab in self.rarity.items():
                c = OLD_LABEL_COLOUR.get(lab.lower(), lab.lower())
                if c in COLOUR_RARITY and n not in self.colours:
                    self.colours[n] = {c: 3}
        for s in self.sales:
            s.setdefault("colour", "")

    def to_json(self) -> dict:
        now = time.time()
        floors = {n: [p for p in f if now - p[0] < 30 * DAY][-2000:] for n, f in self.floors.items()}
        return {"obs": self.obs, "sales": [s for s in self.sales if now - s["gone_at"] < 14 * DAY],
                "names": self.names, "rarity": self.rarity, "colours": self.colours,
                "true_rarity": self.true_rarity, "seed": self.seed, "floors": floors,
                "scan_id": self.scan_id}

    @staticmethod
    def key(item: str, seller: str, price: int, colour: str = "", extra: str = "", qty: int = 1) -> str:
        return f"{norm(item)}|{norm(seller)}|{int(price)}|{colour or ''}|{norm(extra)}|{int(qty or 1)}"

    @staticmethod
    def row_key(r: dict) -> str:
        return Market.key(r["item"], r["seller"], r["price"], r.get("colour", "") if r.get("colour") != "?" else "",
                          r.get("extra", ""), r.get("qty", 1) or 1)

    def colour_of(self, n: str) -> str:
        """The usual name colour of an item (mutated copies whose prefix the
        reader lost show another colour)."""
        c = dict(self.colours.get(n) or {})
        now = time.time()
        for o in self.obs.values():               # listings up now count once per copy
            if o["item"] == n and o.get("colour") and now - o["last"] < 2 * H:
                c[o["colour"]] = c.get(o["colour"], 0) + max(1, o.get("copies", 1)) - 1
        if not c:
            return ""
        ranked = sorted(c.items(), key=lambda kv: -kv[1])
        best = ranked[0]
        if len(ranked) > 1 and ranked[1][1] == best[1]:
            return ""                             # a tie: don't guess
        return best[0] if best[1] >= 2 or len(c) == 1 else ""

    def variant_ok(self, n: str, colour: str) -> bool:
        dom = self.colour_of(n)
        return not dom or not colour or colour in ("?", "") or colour == dom

    def begin_scan(self) -> int:
        self.scan_id += 1
        return self.scan_id

    def see(self, rows: List[dict], now: float, mine: set, my_name: str = "", scan_id: int = 0) -> None:
        for r in rows:
            n = norm(r["item"])
            if not n or not r.get("qty_ok", True) or int(r["price"]) <= 0:
                continue                      # a stack whose size couldn't be read: unit price unknown
            colour = r.get("colour", "") if r.get("colour") not in (None, "?") else ""
            extra = norm(r.get("extra", ""))
            qty = max(1, int(r.get("qty", 1) or 1))
            k = self.key(r["item"], r["seller"], r["price"], colour, extra, qty)
            own = (n, int(r["price"])) in mine or (my_name and seller_is(r["seller"], my_name))
            self.names.setdefault(n, r["item"])
            if r.get("rarity"):
                self.rarity[n] = r["rarity"]
            txt = " ".join(str(r.get(x, "")) for x in ("sub", "extra"))
            if re.search(r"limited", txt, re.I):
                self.true_rarity[n] = "Limited"
            o = self.obs.get(k)
            hl = hours_left(r.get("time_left", ""))
            pos = r.get("pos")
            if o is None:
                listed = now - (24.0 - hl) * H if hl is not None and hl <= 24 else now
                o = self.obs[k] = {"item": n, "seller": norm(r["seller"]), "price": int(r["price"]), "qty": qty,
                                   "colour": colour, "extra": extra, "first": now, "last": now, "hl": hl, "listed": listed,
                                   "mine": bool(own), "scans": 0, "scan": -1, "pos": [], "copies": 1,
                                   "prev_copies": 1}
                if colour:   # count each listing once per scan towards the item's usual colour
                    self.colours.setdefault(n, {})
                    self.colours[n][colour] = self.colours[n].get(colour, 0) + 1
            if o["scan"] != scan_id:
                o["prev_copies"] = o.get("copies", 1)
                o["scan"], o["scans"], o["pos"] = scan_id, o["scans"] + 1, []
            if pos is not None and pos not in o["pos"]:
                o["pos"].append(pos)
            o["copies"] = max(1, len(o["pos"]))
            o["last"] = now
            o["mine"] = o["mine"] or bool(own)
            if hl is not None:
                o["hl"] = hl

    def end_scan(self, term: str, scan_id: int, now: float) -> int:
        """After a COMPLETE scan of `term`: listings that were there before but
        not now have gone.  Counted as a market sale only if it looks like one
        (seen in 2+ scans, not about to expire, the seller didn't simply
        re-list it at another price, at most 3 per item per scan)."""
        t = norm(term)
        here = [o for o in self.obs.values() if o["scan"] == scan_id]
        relisted = {(o["item"], o["seller"]) for o in here if o["scans"] == 1}
        per_item: Dict[str, int] = {}
        gone = 0
        for k, o in list(self.obs.items()):
            if t and t not in o["item"]:
                continue
            lost = 0
            if o["scan"] != scan_id:
                if now - o["last"] < 60:          # seen during this scan by another path
                    continue
                del self.obs[k]
                lost = o.get("copies", 1)
            elif o.get("prev_copies", 1) > o.get("copies", 1) and o["scans"] >= 2:
                lost = o["prev_copies"] - o["copies"]
                o["prev_copies"] = o["copies"]
            if not lost or o["mine"] or o["scans"] < 2 or (o["item"], o["seller"]) in relisted \
                    or bad_seller(o["seller"]) or o.get("extra"):
                continue
            hl_then = (o["hl"] if o["hl"] is not None else 24) - (now - o["last"]) / H
            if hl_then < 0.5:
                continue                          # it simply expired
            for _ in range(lost):
                if per_item.get(o["item"], 0) >= 3:
                    break
                per_item[o["item"]] = per_item.get(o["item"], 0) + 1
                self.sales.append({"item": o["item"], "price": o["price"], "qty": o.get("qty", 1),
                                   "unit": o["price"] / max(1, o.get("qty", 1)), "seller": o["seller"],
                                   "colour": o.get("colour", ""), "listed": o["listed"], "gone_at": now,
                                   "hours": round((now - o["listed"]) / H, 2)})
                gone += 1
        # forget listings nobody has seen for a long time
        for k, o in list(self.obs.items()):
            if now - o["last"] > 30 * H:
                del self.obs[k]
        return gone

    def current(self, n: str, now: float, exclude_mine: bool = True, max_age_h: float = 2.0,
                extra: str = "") -> List[float]:
        """UNIT prices listed now (price / stack size; one entry per listing),
        usual colour and the same enchant (none by default) only, cheapest first."""
        out = []
        for o in self.obs.values():
            if o["item"] != n or now - o["last"] > max_age_h * H or (exclude_mine and o["mine"]):
                continue
            if norm(o.get("extra", "")) != norm(extra):
                continue
            if not self.variant_ok(n, o.get("colour", "")):
                continue
            out += [o["price"] / max(1, o.get("qty", 1))] * max(1, o.get("copies", 1))
        return sorted(out)

    def recent_sales(self, n: str, now: float, days: float = 3.0) -> List[dict]:
        return [s for s in self.sales if s["item"] == n and now - s["gone_at"] < days * DAY
                and self.variant_ok(n, s.get("colour", ""))]

    @staticmethod
    def unit_of(sale: dict) -> float:
        return sale.get("unit", sale["price"] / max(1, sale.get("qty", 1)))

    def value(self, n: str, now: float, undercut: float = 0.01, exclude_price: Optional[float] = None,
              known: Optional[float] = None, extra: str = "") -> Tuple[Optional[float], int, str]:
        """Per UNIT.  exclude_price: the unit price of the listing being judged."""
        """(what it can be resold for, how many price points back that up, basis).
        Resale = just under TODAY's floor (the cheapest other listing): that is
        the price it has to beat.  Sold prices can only lower it."""
        live = self.current(n, now, extra=extra)
        if exclude_price is not None:
            for i, u in enumerate(live):
                if abs(u - exclude_price) <= 0.5:
                    del live[i]
                    break
        sold = sorted(self.unit_of(s) for s in self.recent_sales(n, now)) if not extra else []
        v, pts, basis = None, 0, ""
        if live:
            v, pts, basis = live[0] * (1 - undercut), len(live), "floor"
            if len(sold) >= 2:
                v = min(v, statistics.median(sold))
                pts += len(sold)
                basis = "floor+sales"
        elif len(sold) >= 2:
            v, pts, basis = statistics.median(sold) * 0.95, len(sold), "sales"
        elif known and not extra:
            v, pts, basis = float(known), 1, "your value"
        elif n in self.seed and not self.seed[n].get("known") and not extra:
            v, pts, basis = self.seed[n]["cheapest"] * 0.9, 1, "old scan"
        if v is not None and known:
            v = min(v, float(known))
        return (float(v) if v is not None else None), pts, basis

    def floor_now(self, n: str, now: float) -> Tuple[Optional[float], int]:
        """Cheapest UNIT price listed now, and how many listings."""
        live = self.current(n, now, exclude_mine=False)
        return (round(live[0], 1) if live else None), len(live)

    def record_floors(self, items: List[str], now: float) -> List[str]:
        """Remember each item's floor; returns notes about floors that moved."""
        notes = []
        for n in items:
            f, cnt = self.floor_now(n, now)
            if f is None:
                continue
            hist = self.floors.setdefault(n, [])
            last = hist[-1] if hist else None
            if last and last[1] and abs(f - last[1]) / last[1] >= 0.03:
                d = (f - last[1]) / last[1] * 100
                notes.append(f"{self.names.get(n, n)} floor {fmt(last[1])} -> {fmt(f)} ({d:+.0f}%)")
            if not last or last[1] != f or now - last[0] > 15 * 60:
                hist.append([now, f, cnt])
        return notes

    def floor_ago(self, n: str, now: float, hours: float) -> Optional[int]:
        hist = self.floors.get(n) or []
        old = [p for p in hist if p[0] <= now - hours * H]
        return old[-1][1] if old else (hist[0][1] if hist and now - hist[0][0] > 0.5 * hours * H else None)

    def usual_floor(self, n: str, now: float, days: float = 3.0) -> Optional[float]:
        """Typical floor - the LOWER of the last 24h and the last 3 days (a new,
        volatile market: never anchor to an old high)."""
        hist = [p[1] for p in self.floors.get(n) or [] if now - p[0] < days * DAY]
        day = [p[1] for p in self.floors.get(n) or [] if now - p[0] < DAY]
        if len(hist) < 3:
            return None
        u = float(statistics.median(hist))
        return min(u, float(statistics.median(day))) if len(day) >= 3 else u

    def falling(self, n: str, now: float, pct: float) -> Optional[float]:
        """How far (%) the floor has dropped from its 24h high, if more than pct."""
        hist = [p[1] for p in self.floors.get(n) or [] if now - p[0] < DAY]
        f, _ = self.floor_now(n, now)
        if not hist or f is None:
            return None
        hi = max(hist)
        d = (hi - f) / hi * 100 if hi else 0
        return d if d >= pct else None

    def sales_per_day(self, n: str, now: float) -> float:
        s = self.recent_sales(n, now, 3.0)
        if len(s) < 2:
            return 0.0
        span = max(12 * H, now - min(x["gone_at"] for x in s))
        return len(s) / (span / DAY)

    def hours_to_sale(self, n: str, now: float) -> Optional[float]:
        s = self.recent_sales(n, now, 7.0)
        return round(statistics.median([x["hours"] for x in s]), 2) if s else None


def bad_seller(seller: str) -> bool:
    """The reader sometimes takes the time-left text for the seller ('20h', 'left')."""
    return not seller or bool(re.fullmatch(r"\d+\s*[hmd]\w*|left|by|\W*", norm(seller)))


def seller_is(seller: str, my_name: str) -> bool:
    a, b = norm(seller), norm(my_name)
    if not a or not b:
        return False
    return a == b or difflib.SequenceMatcher(None, a, b).ratio() >= 0.85


# =============================================================================
#  The bot
# =============================================================================
class AuctionBot(ar.AuctionReader):
    TAB_X = {"browse": -152, "sell": -94, "listings": -34}
    TAB_BUTTON = {"browse": "buy", "sell": "sell", "listings": "cancel"}

    def __init__(self, s: BotSettings, log) -> None:
        super().__init__(s, log)
        self.s: BotSettings = s
        st = {}
        try:
            st = json.load(open(STATE_PATH, encoding="utf-8"))
        except Exception:
            pass
        self.market = Market(st.get("market"))
        if st and st.get("version") != VERSION:
            # older versions read stacks ("x42") as single items: their prices can't be trusted
            self.market.obs, self.market.floors = {}, {}
            self.market.sales = [x for x in self.market.sales if "unit" in x]
        self.trades: List[dict] = st.get("trades", [])
        self.holdings: Dict[str, List[dict]] = st.get("holdings", {})   # bought, in the bag
        self.listings: List[dict] = st.get("listings", [])              # our active listings
        self.spends: List[list] = st.get("spends", [])                  # [time, coins] per buy
        self.balance: List[list] = st.get("balance", [])                # [time, coins, net worth]
        self.my_name: str = st.get("my_name", "")
        self.day_start: Dict[str, float] = st.get("day_start", {})      # day -> net worth at start
        self.pause_reason: str = st.get("pause_reason", "")             # buying paused (circuit breaker)
        self.blocked_items: Dict[str, float] = st.get("blocked_items", {})   # item -> until (time)
        for l in self.listings:
            l.setdefault("missing", 0)
        self.coins: Optional[int] = None
        self.cycle = 0
        self.buys_this_cycle = 0
        self.pending: Optional[dict] = None
        self.stats = {"bought": 0, "sold": 0, "profit": 0}
        self.inventory_seen: List[Tuple[str, str]] = []
        self._coin_suspect: Optional[int] = None
        self._last_cycle_coins: Optional[Tuple[float, int]] = None
        self.recount()
        if not self.market.seed:
            self.load_seed()
        self.known: Dict[str, float] = {}
        self.load_known_values()

    # ---- setup / persistence ----------------------------------------------------
    def load_known_values(self) -> None:
        for part in re.split(r"[;\n]+", self.s.known_values or ""):
            if "=" not in part:
                continue
            name, val = part.rsplit("=", 1)
            digits = re.sub(r"\D", "", val)
            n = norm(name)
            if n and digits and int(digits) > 0:
                self.market.names.setdefault(n, name.strip())
                self.known[n] = float(int(digits))

    def save_state(self) -> None:
        cutoff = time.time() - 3 * DAY
        data = {"version": VERSION, "market": self.market.to_json(), "trades": self.trades[-5000:],
                "holdings": self.holdings,
                "listings": self.listings, "spends": [x for x in self.spends if x[0] > cutoff],
                "balance": self.balance[-20000:], "my_name": self.my_name, "day_start": self.day_start,
                "pause_reason": self.pause_reason, "blocked_items": self.blocked_items}
        try:
            tmp = STATE_PATH + ".tmp"
            json.dump(data, open(tmp, "w", encoding="utf-8"))
            os.replace(tmp, STATE_PATH)
        except Exception as exc:
            self.log(f"Could not save the bot's memory: {exc!r}")

    def load_seed(self) -> None:
        """Start from the AuctionReader's last full scan (only used for items
        the bot hasn't seen listed itself yet, and never alone for a buy)."""
        path = self.s.seed_excel if os.path.isabs(self.s.seed_excel) else os.path.join(HERE, self.s.seed_excel)
        try:
            from openpyxl import load_workbook
            wb = load_workbook(path, read_only=True)
            for row in wb["Items"].iter_rows(min_row=2, values_only=True):
                if row and row[0] and row[3]:
                    n = norm(str(row[0]))
                    self.market.names.setdefault(n, str(row[0]))
                    lab = str(row[1] or "").strip().lower()
                    c = OLD_LABEL_COLOUR.get(lab, lab)
                    if c in COLOUR_RARITY and n not in self.market.colours:
                        self.market.colours[n] = {c: 2}
                    self.market.seed[n] = {"listings": int(row[2] or 0), "cheapest": int(row[3]),
                                           "median": float(row[4] or row[3]), "highest": int(row[5] or row[3])}
                    self.vocab.setdefault(str(row[0]), 5)
            self.log(f"Started from {len(self.market.seed)} items in {os.path.basename(path)}.")
        except Exception as exc:
            self.log(f"No reader scan to start from ({exc.__class__.__name__}) - learning from scratch.")

    def recount(self) -> None:
        real = [t for t in self.trades if not t.get("paper")]
        self.stats["bought"] = sum(1 for t in real if t["type"] == "buy")
        self.stats["sold"] = sum(1 for t in real if t["type"] == "sold")
        self.stats["profit"] = sum(t.get("profit", 0) or 0 for t in real if t["type"] == "sold")

    def trade(self, **kw) -> None:
        kw.setdefault("time", time.strftime("%Y-%m-%d %H:%M:%S"))
        kw.setdefault("t", time.time())
        kw.setdefault("paper", self.s.paper_trading)
        self.trades.append(kw)
        self.recount()

    def drop_paper(self) -> None:
        """Paper-trading leftovers must not block or drive real trading."""
        n_h = sum(1 for v in self.holdings.values() for h in v if h.get("paper"))
        n_l = sum(1 for l in self.listings if l.get("paper"))
        if n_h or n_l:
            for k in list(self.holdings):
                self.holdings[k] = [h for h in self.holdings[k] if not h.get("paper")]
            self.listings = [l for l in self.listings if not l.get("paper")]
            self.log(f"Cleared {n_h} paper item(s) and {n_l} paper listing(s) before real trading.")

    # ---- item helpers ------------------------------------------------------------------
    def rarity_of(self, n: str) -> Optional[str]:
        """Sell-tab text if known; otherwise the usual name colour - of the BASE
        item for mutated items (a mutation recolours the name)."""
        m = self.market
        if n in m.true_rarity:
            return m.true_rarity[n]
        words = n.split()
        muts = {w.lower() for w in self.s.mutations.split()}
        if words and words[0] in muts:
            for i in range(1, len(words)):
                base = " ".join(words[i:])
                if base in m.true_rarity:
                    return m.true_rarity[base]
                if m.colour_of(base):
                    return COLOUR_RARITY.get(m.colour_of(base))
                if words[i] not in muts:
                    break
            return None
        return COLOUR_RARITY.get(m.colour_of(n))

    def is_rare(self, n: str, now: float) -> bool:
        rarity = (self.rarity_of(n) or "").lower()
        if rarity and rarity in self.s.rare_rarities.lower().split():
            return True
        v, _, _ = self.value(n, now)
        return bool(v and v >= self.s.rare_value)

    def in_list(self, n: str, attr: str) -> bool:
        return matches_any(self.market.names.get(n, n), split_terms(getattr(self.s, attr)))

    def value(self, n: str, now: float, exclude_price: Optional[int] = None, extra: str = ""):
        return self.market.value(n, now, self.s.undercut_pct / 100.0, exclude_price, self.known.get(n), extra)

    def held_count(self, n: str) -> int:
        return len([h for h in self.holdings.get(n, []) if not h.get("paper") or self.s.paper_trading]) + \
            sum(1 for l in self.listings if norm(l["item"]) == n and (not l.get("paper") or self.s.paper_trading))

    def mine_keys(self) -> set:
        return {(norm(l["item"]), int(l["price"])) for l in self.listings}

    @staticmethod
    def qty_of(x: dict) -> int:
        return max(1, int(x.get("qty", 1) or 1))

    def spent_24h(self, now: Optional[float] = None) -> int:
        now = now or time.time()
        return int(sum(c for t, c in self.spends if now - t < DAY))

    def spent_today(self) -> int:
        return self.spent_24h()

    def item_worth(self, n: str, cost: Optional[float], now: float, qty: int = 1) -> float:
        """What a held lot (qty units) would bring in after the fee at today's floor."""
        v, _, _ = self.value(n, now)
        if v:
            return FEE_KEEP * v * qty
        return float(cost or 0)

    def stock(self, now: float) -> Tuple[float, float]:
        """(cost, market worth) of everything the bot bought and still has."""
        cost = worth = 0.0
        for n, held in self.holdings.items():
            for h in held:
                if h.get("paper") and not self.s.paper_trading:
                    continue
                cost += h.get("cost") or 0
                worth += self.item_worth(n, h.get("cost"), now, self.qty_of(h))
        for l in self.listings:
            if l.get("paper") and not self.s.paper_trading:
                continue
            n = norm(l["item"])
            cost += l.get("cost") or 0
            worth += min(FEE_KEEP * l["price"],
                         self.item_worth(n, l.get("cost"), now, self.qty_of(l)) or FEE_KEEP * l["price"])
        return cost, worth

    def net_worth(self, now: float) -> Optional[float]:
        if self.coins is None:
            return None
        return self.coins + self.stock(now)[1]

    def outcome(self, n: str, now: float) -> Tuple[int, float]:
        """(expiries in the last 7 days, extra margin % it now demands) - the
        bot learning from its own results for this item."""
        recent = [t for t in self.trades if norm(t.get("item", "")) == n and not t.get("paper")
                  and now - t.get("t", 0) < 7 * DAY]
        exp = sum(1 for t in recent if t["type"] == "expired")
        sold = [t for t in recent if t["type"] == "sold" and t.get("cost")]
        extra = 10.0 * exp
        if sold:
            roi = statistics.mean((t.get("profit") or 0) / t["cost"] for t in sold)
            if roi < 0.05:
                extra += 10.0
        return exp, extra

    def item_blocked(self, n: str, now: float) -> str:
        until = self.blocked_items.get(n, 0)
        if until > now:
            return "paused for this item"
        exp, _ = self.outcome(n, now)
        if exp >= 2:
            return "didn't sell twice this week"
        for l in self.listings:
            if norm(l["item"]) == n and not l.get("paper") and now - l["listed_at"] > 48 * H:
                return "our listing hasn't sold in 48h"
        return ""

    def pause_buying(self, why: str) -> None:
        if not self.pause_reason:
            self.pause_reason = why
            self.log(f"*** BUYING PAUSED: {why}  (selling continues; press 'Resume buying' when checked)")
            self.save_state()

    # ---- screen helpers ------------------------------------------------------------------
    def ocr_text(self, region, up: int = 3) -> str:
        img = self.grab(region)
        lines = self._ocr_read(ar.prep_for_ocr(img, up))
        return " ".join(l["text"] for l in sorted(lines, key=lambda l: (l["y"], l["x"])))

    def _read_coins_once(self, board) -> Optional[int]:
        t = self.ocr_text(board.coins_region())
        if re.search(r"\d\s*[kKmMbB]\b", t) or re.search(r"\d\.\d{1,2}\b", t):
            return None                     # an abbreviated number - can't trust its digits
        t = re.sub(r"(?<=\d)[oO]|[oO](?=\d)", "0", t)
        m = re.search(r"(\d[\d,\s]{2,})", t)
        if not m:
            return None
        if m.start() > 0 and t[m.start() - 1] in "lI|!i":
            return None                     # a leading 1 read as a letter
        txt = re.sub(r"\s", "", m.group(1)).strip(",")
        if "," in txt and not re.fullmatch(r"\d{1,3}(,\d{3})+", txt):
            return None
        return int(re.sub(r"\D", "", txt) or 0)

    def read_coins(self, board, record: bool = True) -> Optional[int]:
        v = self._read_coins_once(board)
        if v is None:
            return self.coins
        if self.coins and (v > 3 * self.coins or v < self.coins / 3):
            if self._coin_suspect != v:     # a big jump must be read twice in a row
                self._coin_suspect = v
                return self.coins
        self._coin_suspect = None
        self.coins = v
        if record:
            self.note_balance()
        return v

    def read_coins_stable(self, board, timeout: float = 3.0, changed_from: Optional[int] = None) -> Optional[int]:
        """Read the balance until two readings agree (and, if asked, it changed)."""
        t_end = time.time() + timeout
        last = None
        while True:
            v = self._read_coins_once(board)
            if v is not None and v == last and (changed_from is None or v != changed_from):
                self.coins = v
                self._coin_suspect = None
                self.note_balance()
                return v
            last = v
            if time.time() > t_end:
                return v if v is not None and v == last else None
            time.sleep(0.3)

    def note_balance(self) -> None:
        now = time.time()
        nw = self.net_worth(now)
        if self.coins is None:
            return
        day = time.strftime("%Y-%m-%d")
        if nw is not None and day not in self.day_start:
            self.day_start[day] = nw
        last = self.balance[-1] if self.balance else None
        if not last or last[1] != self.coins or now - last[0] > 600:
            self.balance.append([now, self.coins, round(nw) if nw is not None else None])

    def read_message(self, board) -> str:
        x0, y0 = board.pt(0, 252)
        x1, y1 = board.pt(182, 270)
        return self.ocr_text((x0, y0, x1 - x0, y1 - y0))

    def button_x(self, board) -> int:
        return board.pt(148, 0)[0]

    def button_text(self, board, y: int) -> str:
        x = self.button_x(board)
        w, h = int(46 * board.s), int(16 * board.s)
        return self.ocr_text((x - w // 2, y - h // 2, w, h), 4).lower()

    def button_is(self, board, y: int, want: str) -> bool:
        """Is the button on this row really `want` (buy / sell / cancel)?
        Blank = can't tell (allowed); another label = wrong tab (refused)."""
        t = self.button_text(board, y)
        if not t.strip():
            return True
        others = [w for w in ("buy", "sell", "cancel") if w != want]
        if want in t:
            return True
        return not any(o in t for o in others)

    def tab(self, board, name: str) -> None:
        self.click(*board.pt(self.TAB_X[name], 36))
        time.sleep(1.0)

    def type_into(self, x: int, y: int, text: str) -> None:
        self.click(x, y)
        time.sleep(0.25)
        self.clear_search()
        for ch in text:
            self.key(ch)
            time.sleep(0.03)
        time.sleep(0.25)

    def field_digits(self, board, cx: int, cy: int, half_w: float) -> str:
        w, h = int(2 * half_w * board.s), int(16 * board.s)
        return re.sub(r"\D", "", self.ocr_text((cx - w // 2, cy - h // 2, w, h), 4).replace("O", "0").replace("o", "0"))

    def row_strip(self, img: np.ndarray, row: dict) -> np.ndarray:
        y, h = int(row["y"]), int(row.get("h", 20))
        return img[max(0, y):y + h].astype(np.int16)

    def reread_price(self, img: np.ndarray, row: dict) -> Tuple[int, bool]:
        """Read one row's price again, bigger, on its own."""
        W = img.shape[1]
        y, h = int(row["y"]), int(row.get("h", 20))
        strip = img[max(0, y):y + h, int(0.62 * W):int(0.865 * W)]
        lines = self._ocr_read(ar.prep_for_ocr(strip, 4))
        return ar.parse_price(" ".join(l["text"] for l in sorted(lines, key=lambda l: l["x"])))

    def reread_qty(self, img: np.ndarray, row: dict) -> Optional[int]:
        """Read a row's stack badge again on its own (1 = no badge)."""
        y, h = int(row["y"]), int(row.get("h", 20))
        box = ar.find_badge(img, y, y + h - 1)
        if box is None:
            return 1
        lines = self._ocr_read(ar.badge_image(img, box, 3))
        return ar.parse_qty(" ".join(l["text"] for l in sorted(lines, key=lambda l: l["x"])))

    # ---- decisions -------------------------------------------------------------------------
    def buy_decision(self, row: dict, now: float) -> Optional[str]:
        n = norm(row["item"])
        price = int(row["price"])
        if self.pause_reason or price <= 0 or not row.get("price_ok", True) or not row.get("qty_ok", True):
            return None
        qty = max(1, int(row.get("qty", 1) or 1))
        unit = price / qty
        if self.buys_this_cycle >= self.s.max_buys_per_cycle:
            return None
        if (n, price) in self.mine_keys() or (self.my_name and seller_is(row["seller"], self.my_name)):
            return None
        watch = split_terms(self.s.watch_items)
        if blocked(row["item"], split_terms(self.s.never_buy), watch):
            return None
        if self.s.buy_only_watched and not matches_any(row["item"], watch):
            return None
        if not self.market.variant_ok(n, row.get("colour", "")):
            return None                     # another colour = a mutated copy whose prefix wasn't read
        known = self.known.get(n)
        need = RARITY_RANK.get(self.s.min_buy_rarity.strip().lower(), 0)
        if need > 0 and not known and not self.in_list(n, "any_rarity_items"):
            rar = (self.rarity_of(n) or "").lower()
            if RARITY_RANK.get(rar, -1) < need:
                return None
        if self.item_blocked(n, now):
            return None
        long_term = self.in_list(n, "long_term_items")
        fast = self.in_list(n, "high_demand_items")
        cap = self.s.long_term_max_hold if long_term else self.s.max_hold_per_item + (1 if fast else 0)
        if self.held_count(n) >= cap:
            return None
        ench = norm(row.get("extra", ""))
        value, pts, basis = self.value(n, now, exclude_price=unit, extra=ench)
        if value is None:
            return None
        profit = FEE_KEEP * value * qty - price
        _, extra = self.outcome(n, now)
        drop = self.market.falling(n, now, self.s.falling_floor_pct)
        listed_ours = any(norm(l["item"]) == n for l in self.listings
                          if not l.get("paper") or self.s.paper_trading)
        if long_term:
            usual = self.market.usual_floor(n, now) or value
            if unit > self.s.long_term_buy_ratio * usual or pts < 1 or basis == "old scan" or drop:
                return None
            kind = f"LONG-TERM (usual floor ~{fmt(usual)})"
        else:
            trusted = basis in ("floor", "floor+sales", "sales") and pts >= self.s.min_value_points
            steal = (unit <= self.s.steal_ratio * value and profit >= self.s.min_profit_coins
                     and (trusted or (known and basis in ("your value", "floor"))))
            pct = (self.s.min_profit_pct if (fast or self.market.sales_per_day(n, now) >= 1.0)
                   else self.s.slow_profit_pct) + extra
            good = (trusted and value * qty >= self.s.min_item_value
                    and profit >= max(self.s.min_profit_coins, pct / 100.0 * price))
            if (drop or listed_ours) and not steal:
                return None                 # floor sliding / our own copy still unsold: steals only
            if not (steal or good):
                return None
            kind = "STEAL" if steal else "deal"
        # ---- money rules (always) ----
        if not self.s.paper_trading:
            coins = self.coins
            if not coins:
                return None                 # balance unreadable: never buy blind
            if price > self.s.max_buy_frac * coins or coins - price < self.s.coin_reserve:
                return None
            nw = self.net_worth(now) or coins
            if self.stock(now)[0] + price > self.s.max_stock_frac * nw:
                return None
        if self.spent_24h(now) + price > self.s.daily_spend_cap:
            return None
        each = f" x{qty} at {fmt(unit)} each," if qty > 1 else ""
        return (f"{kind}:{each} resale ~{fmt(value)}/unit ({basis}, {pts} pts), profit after fee ~{fmt(profit)}"
                + (f", +{extra:.0f}% margin (learned)" if extra else ""))

    def sell_price(self, n: str, cost: Optional[float], now: float, qty: int = 1) -> Optional[int]:
        """Total asking price for a lot of `qty` units (cost = what the lot cost)."""
        others = self.market.current(n, now)
        cost = (cost / qty) if cost else cost
        value, _, _ = self.value(n, now)
        exp, _ = self.outcome(n, now)
        margin = self.s.long_term_margin_pct if self.in_list(n, "long_term_items") else self.s.min_list_margin_pct
        margin = max(0.0, margin - 2.0 * exp)          # each expiry: accept a little less (never a loss)
        if cost:
            floor = math.ceil(cost / FEE_KEEP * (1 + margin / 100.0))
        elif value:
            floor = int(0.85 * value)
        else:
            floor = 0
        if others:
            target = others[0] * (1 - self.s.undercut_pct / 100.0)
        elif value:
            target = value * 1.05
        else:
            return None
        return int(math.ceil(max(target, floor) * qty))

    # ---- watching + buying -----------------------------------------------------------------
    def watchlist(self, now: float) -> List[str]:
        out, seen = [], set()
        never, watch = split_terms(self.s.never_buy), split_terms(self.s.watch_items)
        for t in watch + (self.trending(now) if self.s.auto_watch else []):
            if t.lower() not in seen and not blocked(t, never, watch):   # the game's search cares about spaces
                seen.add(t.lower())
                out.append(t)
        return out

    def trending(self, now: float) -> List[str]:
        scores = []
        names = set(self.market.seed) | {o["item"] for o in self.market.obs.values()} | \
            {s["item"] for s in self.market.sales}
        for n in names:
            value, pts, _ = self.value(n, now)
            if not value or value < self.s.min_item_value:
                continue
            cur = self.market.current(n, now)
            seed = self.market.seed.get(n, {})
            demand = self.market.sales_per_day(n, now) + 0.15 * max(len(cur), seed.get("listings", 0))
            spread = 0.0
            if len(cur) >= 2:
                spread = max(0.0, (statistics.median(cur) - cur[0]) / max(1.0, statistics.median(cur)))
            scores.append((demand * (0.15 + spread) * math.log10(max(10.0, value)), n))
        scores.sort(reverse=True)
        return [self.market.names.get(n, n) for _, n in scores[: self.s.watch_size]]

    def watched_items(self, now: float) -> List[str]:
        """Items (normalised) that match the watch list and have been seen."""
        watch = split_terms(self.s.watch_items)
        names = set(self.market.floors) | {o["item"] for o in self.market.obs.values()}
        return sorted((n for n in names if matches_any(self.market.names.get(n, n), watch)),
                      key=lambda n: -(self.market.floor_now(n, now)[0] or
                                      (self.market.floors.get(n) or [[0, 0]])[-1][1] or 0))

    def watch_term(self, board, term: str) -> None:
        for attempt in range(4):              # repeat after each purchase (the list changed)
            self.pending = None
            mine = self.mine_keys()
            sid = self.market.begin_scan()

            def on_screen(img, rows):
                self.market.see(rows, time.time(), mine, self.my_name, sid)
                for r in rows:
                    why = self.buy_decision(r, time.time())
                    if why:
                        self.pending = dict(r, why=why, strip=self.row_strip(img, r))
                        return True
                return False

            res = self.scan_term(board, term, on_screen)
            if res is None:
                return
            now = time.time()
            if self.pending is None:
                if not self.aborted and res:
                    gone = self.market.end_scan(term, sid, now)
                    if gone:
                        self.log(f"'{term}': {gone} listing(s) look sold since the last look.")
                    seen = sorted({r_["item"] and norm(r_["item"]) for r_ in res.values()} - {""})
                    for note in self.market.record_floors(seen, now):
                        self.log("FLOOR: " + note)
                return
            if self.buy(board, self.pending) != "bought":
                return                        # not bought / unsure: don't try this search again now

    def buy(self, board, row: dict) -> str:
        """Returns 'bought', 'skipped' or 'unsure'."""
        item, price, n = row["item"], int(row["price"]), norm(row["item"])
        self.log(f"BUY {item} for {price:,} from {row['seller']} - {row['why']}")
        if self.s.paper_trading:
            self.buys_this_cycle += 1
            self.trade(type="buy", item=item, price=price, seller=row["seller"], note=row["why"])
            self.holdings.setdefault(n, []).append({"cost": price, "at": time.time(), "paper": True,
                                                    "qty": self.qty_of(row)})
            self.spends.append([time.time(), price])
            self.market.obs.pop(self.market.row_key(row), None)
            return "skipped"
        img = self.grab(board.list_region())
        now_strip = self.row_strip(img, row)
        if now_strip.shape != row["strip"].shape or float(np.abs(now_strip - row["strip"]).mean()) > 8.0:
            self.log("  ...the list moved before the click - skipped.")
            return "skipped"
        p2, ok2 = self.reread_price(img, row)
        if not ok2 or p2 != price:
            self.log(f"  ...second read of the price says '{p2:,}' - not sure of the price, skipped.")
            return "skipped"
        q2 = self.reread_qty(img, row)
        if q2 != self.qty_of(row):
            self.log(f"  ...second read of the stack size says {q2}, first said {self.qty_of(row)} - skipped.")
            return "skipped"
        y = int(row["screen_y"])
        if not self.button_is(board, y, "buy"):
            self.log("  ...that row's button isn't 'Buy' (wrong tab?) - skipped.")
            return "skipped"
        before = self.read_coins_stable(board, 2.0)
        if not before:
            self.log("  ...can't read your coins - not buying.")
            return "skipped"
        if price > before:
            return "skipped"
        self.click(self.button_x(board), y)
        time.sleep(0.6)
        after = self.read_coins_stable(board, 5.0, changed_from=before)
        msg = self.read_message(board)
        drop = (before - after) if after is not None else 0
        now = time.time()
        if drop <= 0.02 * price:
            img2 = self.grab(board.list_region())
            gone = float(np.abs(self.row_strip(img2, row) - now_strip).mean()) > 8.0 \
                if self.row_strip(img2, row).shape == now_strip.shape else True
            positive = re.search(r"\b(bought|purchased)\b", msg, re.I) and not NEGATIVE.search(msg)
            if gone and positive:
                # the game said yes but the balance hasn't moved yet: count it, check later
                self.record_buy(row, price, "unconfirmed: coins didn't change yet")
                self.blocked_items[n] = now + 2 * H
                return "unsure"
            self.log(f"  ...not bought ({msg or 'no message'}).")
            return "skipped"
        if 0.97 * price <= drop <= 1.03 * price:
            self.record_buy(row, drop, "")
            self.log(f"  BOUGHT {item} for {drop:,}.  Coins now {after:,}")
            return "bought"
        if drop > 1.03 * price:
            self.record_buy(row, drop, f"OVERPAID: expected {price:,}")
            self.pause_buying(f"{item}: {drop:,} left your balance but the listing said {price:,}.")
            return "unsure"
        self.record_buy(row, price, f"coins fell by {drop:,} only")
        self.pause_buying(f"{item}: the balance changed by {drop:,}, not the {price:,} expected.")
        return "unsure"

    def record_buy(self, row: dict, paid: int, flag: str) -> None:
        item, n = row["item"], norm(row["item"])
        now = time.time()
        self.buys_this_cycle += 1
        self.spends.append([now, paid])
        q = self.qty_of(row)
        self.holdings.setdefault(n, []).append({"cost": paid, "at": now, "flag": flag, "qty": q})
        self.market.obs.pop(self.market.row_key(row), None)
        self.trade(type="buy", item=item, price=paid, qty=q, seller=row["seller"],
                   note=row["why"] + (f" [{flag}]" if flag else ""))
        if flag:
            self.log(f"  recorded {item} at {paid:,} [{flag}]")
        self.save_state()

    # ---- my listings: sales + relisting --------------------------------------------------------
    def check_listings(self, board) -> None:
        real = [l for l in self.listings if not l.get("paper")]
        if not real:
            return
        self.tab(board, "listings")
        rows = self.scan_term(board, None)
        if rows is None or self.aborted:
            return
        now = time.time()
        shown = [dict(r) for r in rows.values()]
        sellers = {norm(r["seller"]) for r in shown if r.get("seller")}
        if len(shown) >= 2 and len(sellers) == 1 and not self.my_name:
            self.my_name = sellers.pop()
            self.log(f"Your seller name looks like '{self.my_name}'.")
        matched, plan = 0, []
        for l in real:
            match = next((r for r in shown if norm(r["item"]) == norm(l["item"])
                          and abs(int(r["price"]) - l["price"]) <= max(1, l["price"] // 200)
                          and (not r.get("qty_ok", True) or self.qty_of(r) == self.qty_of(l))), None)
            if match is not None:
                shown.remove(match)
                matched += 1
            plan.append((l, match))
        if real and (not rows or matched < 0.5 * sum(1 for l in real if not l.get("unconfirmed"))) and \
                matched < len(real):
            if not rows or matched == 0 and len(real) >= 2:
                self.log("My Listings didn't read properly - nothing changed this time.")
                return
        for l, match in plan:
            if match is not None:
                l["seen"], l["missing"], l["unconfirmed"] = now, 0, False
                continue
            if l.get("unconfirmed"):
                # the listing never showed up: the item is still in the bag
                self.listings.remove(l)
                self.holdings.setdefault(norm(l["item"]), []).append({"cost": l.get("cost"), "at": now,
                                                                      "qty": self.qty_of(l)})
                self.log(f"{l['item']} at {l['price']:,} never appeared in My Listings - back to the bag.")
                continue
            l["missing"] = l.get("missing", 0) + 1
            if l["missing"] < 2:
                continue                       # missing once could be a misread: look again next cycle
            hours = (now - l["listed_at"]) / H
            self.listings.remove(l)
            if hours >= 23.9:
                self.holdings.setdefault(norm(l["item"]), []).append({"cost": l.get("cost"), "at": now,
                                                                      "qty": self.qty_of(l)})
                self.trade(type="expired", item=l["item"], price=l["price"], hours=round(hours, 2))
                self.log(f"{l['item']} at {l['price']:,} expired after {hours:.0f}h - back to the bag.")
                continue
            profit = int(FEE_KEEP * l["price"] - (l.get("cost") or 0)) if l.get("cost") else None
            self.trade(type="sold", item=l["item"], price=l["price"], qty=self.qty_of(l), cost=l.get("cost"),
                       profit=profit, hours=round(hours, 2),
                       listed=time.strftime("%Y-%m-%d %H:%M", time.localtime(l["listed_at"])))
            self.log(f"SOLD {l['item']} for {l['price']:,} after {hours:.1f}h"
                     + (f" - profit {profit:,}" if profit is not None else ""))
        # undercut and old enough -> cancel (the item comes back to the bag and is relisted lower)
        todo = []
        for l in self.listings:
            if l.get("paper") or l.get("unconfirmed"):
                continue
            age_min = (now - l["listed_at"]) / 60.0
            others = self.market.current(norm(l["item"]), now)
            mine_unit = l["price"] / self.qty_of(l)
            if age_min < self.s.relist_after_min or not others or others[0] >= mine_unit:
                continue
            new = self.sell_price(norm(l["item"]), l.get("cost"), now, self.qty_of(l))
            if new is not None and new < l["price"] * 0.995:
                todo.append((l, others[0], new))
        for l, cheapest, new in todo[:3]:
            if not self.running:
                break
            if self.cancel(board, l):
                self.log(f"Undercut: {l['item']} at {l['price']:,} (cheapest now {fmt(cheapest)}/unit) - "
                         f"cancelled, relisting at {new:,}.")
        self.save_state()

    def cancel(self, board, l: dict) -> bool:
        target = {}

        def on_screen(img, rows):
            for r in rows:
                if norm(r["item"]) == norm(l["item"]) and abs(int(r["price"]) - l["price"]) <= max(1, l["price"] // 200):
                    target.update(r, strip=self.row_strip(img, r))
                    return True
            return False

        self.scan_term(board, None, on_screen)
        if not target:
            return False
        y = int(target["screen_y"])
        if not self.button_is(board, y, "cancel"):
            self.log("  ...that row's button isn't 'Cancel' - not touching it.")
            return False
        self.click(self.button_x(board), y)
        time.sleep(1.2)
        img = self.grab(board.list_region())
        strip = self.row_strip(img, target)
        if strip.shape == target["strip"].shape and float(np.abs(strip - target["strip"]).mean()) <= 8.0:
            self.log("  ...the listing is still there - cancel didn't work.")
            return False
        self.listings.remove(l)
        self.holdings.setdefault(norm(l["item"]), []).append({"cost": l.get("cost"), "at": time.time(),
                                                              "qty": self.qty_of(l)})
        self.trade(type="cancel", item=l["item"], price=l["price"])
        return True

    # ---- selling from the bag ----------------------------------------------------------------------
    def sellable(self, n: str) -> List[dict]:
        return [h for h in self.holdings.get(n, []) if bool(h.get("paper")) == bool(self.s.paper_trading)]

    def sell_inventory(self, board) -> None:
        tried = set()
        if self.s.paper_trading:
            now = time.time()
            for n in list(self.holdings):
                for h in list(self.sellable(n)):
                    if sum(1 for l in self.listings if l.get("paper")) >= self.s.max_active_listings:
                        return
                    price = self.sell_price(n, h.get("cost"), now, self.qty_of(h))
                    if price is None:
                        continue
                    self.holdings[n].remove(h)
                    item = self.market.names.get(n, n)
                    self.listings.append({"item": item, "price": price, "cost": h.get("cost"), "qty": self.qty_of(h),
                                          "listed_at": now, "paper": True, "missing": 0})
                    self.trade(type="list", item=item, price=price, cost=h.get("cost"))
            return
        if not any(self.sellable(n) for n in self.holdings):
            return
        self.tab(board, "sell")
        for _ in range(self.s.max_active_listings):
            if len([l for l in self.listings if not l.get("paper")]) >= self.s.max_active_listings or not self.running:
                break
            pick = {}

            def on_screen(img, rows):
                for r in rows:
                    n = norm(r["item"])
                    sub = r.get("sub", "")
                    rar = sub.split("·")[0].strip() if "·" in sub else (sub.split(" ")[0] if sub else "")
                    if re.search(r"limited", sub, re.I):
                        self.market.true_rarity[n] = "Limited"
                    elif rar.lower() in RARITY_RANK:
                        self.market.true_rarity[n] = rar.title()
                for r in rows:
                    n = norm(r["item"])
                    held = self.sellable(n)
                    if n in tried or (self.s.sell_only_bought and not held):
                        continue
                    lot = self.qty_of(held[0]) if held else 1
                    price = self.sell_price(n, held[0].get("cost") if held else None, time.time(), lot)
                    if price is None:
                        tried.add(n)
                        continue
                    pick.update(r, n=n, price=price, cost=held[0].get("cost") if held else None, lot=lot)
                    return True
                return False

            rows = self.scan_term(board, None, on_screen, need_price=False)
            if rows is not None:
                self.inventory_seen = [(r["item"], r.get("sub", "")) for r in rows.values()]
            if not pick:
                break
            n, price, cost = pick["n"], pick["price"], pick["cost"]
            tried.add(n)
            res = self.list_one(board, pick, price, n, pick.get("lot", 1))
            if res in ("listed", "unsure"):
                held = self.sellable(n)
                if held:
                    held_item = held[0]
                    self.holdings[n].remove(held_item)
                self.listings.append({"item": pick["item"], "price": price, "cost": cost, "qty": pick.get("lot", 1),
                                      "listed_at": time.time(), "missing": 0, "unconfirmed": res == "unsure"})
                self.trade(type="list", item=pick["item"], price=price, cost=cost)
                self.log(f"LISTED {pick['item']}" + (f" x{pick.get('lot', 1)}" if pick.get("lot", 1) > 1 else "")
                         + f" for {price:,}" + (f" (cost {cost:,})" if cost else "")
                         + (" - will confirm in My Listings" if res == "unsure" else ""))
                self.save_state()
                time.sleep(0.5)
        self.save_state()

    def list_one(self, board, r: dict, price: int, n: str, qty: int = 1) -> str:
        """Sell... -> quantity 1 -> price -> both read back -> List item.
        Returns 'listed', 'unsure' or 'failed'."""
        y = int(r["screen_y"])
        if not self.button_is(board, y, "sell"):
            self.log("  ...that row's button isn't 'Sell' (wrong tab?) - skipped.")
            return "failed"
        self.click(self.button_x(board), y)
        time.sleep(1.0)
        qx, qy = board.pt(-125, 92)
        px, py = board.pt(-64, 92)
        if self.s.keep_one_rare and self.is_rare(n, time.time()):
            count = self.field_digits(board, qx, qy, 18)
            mine_before = int(count) - len(self.sellable(n)) if count else 0
            if count and mine_before < 1 and int(count) <= 1:
                self.log(f"Keeping your last {r['item']} (rare).")
                self.click(*board.pt(99, 92))
                time.sleep(0.8)
                return "failed"
        for attempt in range(2):
            self.type_into(qx, qy, str(int(qty)))
            self.type_into(px, py, str(int(price)))
            q_read = self.field_digits(board, qx, qy, 18)
            p_read = self.field_digits(board, px, py, 34)
            if (not q_read or q_read == str(int(qty))) and (not p_read or p_read == str(int(price))):
                break
            self.log(f"  ...the boxes read quantity '{q_read}', price '{p_read}' - retyping.")
        else:
            self.log("  ...couldn't type the quantity/price reliably - backing out.")
            self.click(*board.pt(99, 92))
            time.sleep(0.8)
            return "failed"
        self.click(*board.pt(147, 92))           # List item
        time.sleep(1.2)
        msg = self.read_message(board)
        if re.search(r"\blisted\b", msg, re.I) and not NEGATIVE.search(msg):
            return "listed"
        if NEGATIVE.search(msg or ""):
            self.log(f"Listing {r['item']} failed ({msg}).")
            self.click(*board.pt(99, 92))
            time.sleep(0.8)
            return "failed"
        self.log(f"Listing {r['item']} didn't confirm ({msg or 'no message'}) - will check My Listings.")
        return "unsure"

    # ---- safety checks -----------------------------------------------------------------------------
    def check_drawdown(self) -> None:
        now = time.time()
        nw = self.net_worth(now)
        start = self.day_start.get(time.strftime("%Y-%m-%d"))
        if nw and start and nw < start * (1 - self.s.pause_on_drop_pct / 100.0):
            self.pause_buying(f"net worth {fmt(nw)} is {100 * (1 - nw / start):.0f}% below today's start "
                              f"({fmt(start)}).")
        # coins that vanished with no recorded purchase
        if self._last_cycle_coins and self.coins is not None:
            t0, c0 = self._last_cycle_coins
            spent = sum(c for t, c in self.spends if t >= t0)
            missing = c0 - spent - self.coins
            if missing > max(50000, 0.05 * c0):
                self.pause_buying(f"{missing:,} coins left your balance without a purchase the bot recorded.")
        if self.coins is not None:
            self._last_cycle_coins = (now, self.coins)

    # ---- main loop ------------------------------------------------------------------------------------
    def run_cycle(self) -> bool:
        board = self.locate()
        if board is None:
            self.log("Waiting for the auction board - open it (Browse tab).")
            t_end = time.time() + 120
            while board is None and self.running and time.time() < t_end:
                time.sleep(1.0)
                board = self.locate()
            if board is None:
                return False
            time.sleep(1.5)
        if self.hwnd:
            af.force_foreground(self.hwnd)
            time.sleep(0.2)
        self.cycle += 1
        self.buys_this_cycle = 0
        self.read_coins_stable(board, 3.0)
        if self.coins is None and not self.s.paper_trading:
            self.log("Can't read your coin balance - no buying this cycle (selling still runs).")
        self.check_drawdown()
        now = time.time()
        terms = self.watchlist(now)
        self.log(f"Cycle {self.cycle}: coins {fmt(self.coins)}, net worth {fmt(self.net_worth(now))}, "
                 f"{len(terms)} searches" + (f"  [buying paused: {self.pause_reason}]" if self.pause_reason else ""))
        self.tab(board, "browse")
        for i, term in enumerate(terms):
            if not self.running:
                return False
            self.progress = f"cycle {self.cycle}: '{term}' ({i + 1}/{len(terms)})"
            self.watch_term(board, term)
            self.save_state()
        if not self.running:
            return False
        self.progress = f"cycle {self.cycle}: my listings"
        self.check_listings(board)
        if self.running:
            self.progress = f"cycle {self.cycle}: selling"
            self.sell_inventory(board)
        self.tab(board, "browse")
        self.read_coins_stable(board, 3.0)
        self.check_drawdown()
        write_excel(self)
        return True

    def run_forever(self) -> None:
        while self.alive:
            if not self.running:
                time.sleep(0.1)
                continue
            try:
                if self.ocr is None:
                    self.status = "Starting OCR..."
                    self.ocr = ar.make_ocr(self.s.ocr_backend)
                    self.log(f"Text reader: {self.ocr.name}.")
                self.status = "Trading" + (" (PAPER)" if self.s.paper_trading else "")
                self.run_cycle()
                end = time.time() + self.s.cycle_pause_s
                while self.running and time.time() < end:
                    self.progress = f"next cycle in {int(end - time.time())}s"
                    time.sleep(0.5)
            except Exception as exc:
                self.log(f"Error (continuing): {exc!r}")
                traceback.print_exc()
                time.sleep(3)
            finally:
                self.save_state()


# =============================================================================
#  Excel report
# =============================================================================
def write_excel(bot: AuctionBot) -> Optional[str]:
    try:
        from openpyxl import Workbook
        from openpyxl.chart import LineChart, Reference, ScatterChart, Series
        from openpyxl.styles import Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        bot.log("openpyxl missing: python -m pip install --user openpyxl")
        return None
    now = time.time()
    wb = Workbook()
    wb.remove(wb.active)
    bold, fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="7A1F2B")
    M = bot.market

    def sheet(name, heads, widths):
        ws = wb.create_sheet(name)
        ws.append(heads)
        for i, h in enumerate(heads, 1):
            c = ws.cell(row=1, column=i)
            c.font, c.fill = bold, fill
            ws.column_dimensions[get_column_letter(i)].width = widths[i - 1]
        ws.freeze_panes = "A2"
        return ws

    def numfmt(ws):
        for row in ws.iter_rows(min_row=2):
            for c in row:
                if isinstance(c.value, (int, float)) and abs(c.value) >= 1000:
                    c.number_format = "#,##0"

    # Balance (coins + net worth)
    wsb = sheet("Balance", ["Time", "Coins", "Net worth (coins + items at today's floor)"], [19, 14, 22])
    for p in bot.balance:
        wsb.append([time.strftime("%Y-%m-%d %H:%M", time.localtime(p[0])), p[1], p[2] if len(p) > 2 else None])
    numfmt(wsb)
    if len(bot.balance) >= 2:
        ch = LineChart()
        ch.title = "Coins and net worth"
        ch.height, ch.width = 10, 24
        ch.add_data(Reference(wsb, min_col=2, max_col=3, min_row=1, max_row=wsb.max_row), titles_from_data=True)
        ch.set_categories(Reference(wsb, min_col=1, min_row=2, max_row=wsb.max_row))
        wsb.add_chart(ch, "E2")
    cost, worth = bot.stock(now)
    wsb["E24"], wsb["F24"] = "Items bought, at cost", round(cost)
    wsb["E25"], wsb["F25"] = "Items bought, at today's floor", round(worth)
    wsb["E26"], wsb["F26"] = "Buying", ("PAUSED: " + bot.pause_reason) if bot.pause_reason else "on"

    # Watched items + floor history
    wsw = sheet("Watched items", ["Item", "Rarity", "Floor now (per unit)", "Listed now", "Floor 24h ago", "Change 24h %",
                                  "7-day low", "7-day high", "Resale value", "Basis", "Market sales/day",
                                  "Hours to sell", "Held/listed by bot", "Status"],
                [32, 10, 12, 9, 12, 10, 12, 12, 12, 11, 10, 9, 9, 30])
    items = bot.watched_items(now)
    for n in items:
        f, cnt = M.floor_now(n, now)
        hist = [p[1] for p in M.floors.get(n, []) if now - p[0] < 7 * DAY]
        f24 = M.floor_ago(n, now, 24)
        last = (M.floors.get(n) or [[0, None]])[-1][1]
        f_show = f if f is not None else last
        v, pts, basis = bot.value(n, now)
        wsw.append([M.names.get(n, n), bot.rarity_of(n) or M.colour_of(n), f_show, cnt, f24,
                    round((f_show - f24) / f24 * 100, 1) if f_show and f24 else None,
                    min(hist) if hist else None, max(hist) if hist else None,
                    round(v) if v else None, basis, round(M.sales_per_day(n, now), 2), M.hours_to_sale(n, now),
                    bot.held_count(n), bot.item_blocked(n, now)])
    numfmt(wsw)
    wsf = sheet("Floor history", ["Time", "Item", "Floor", "Listed"], [17, 32, 12, 8])
    for n in items:
        for t_, f_, c_ in M.floors.get(n, []):
            wsf.append([time.strftime("%Y-%m-%d %H:%M", time.localtime(t_)), M.names.get(n, n), f_, c_])
    numfmt(wsf)
    # one small chart per watched item (prices differ too much for one chart)
    wsc = wb.create_sheet("Floor charts")
    col = 1
    for k, n in enumerate([n for n in items if len(M.floors.get(n, [])) >= 2][:16]):
        hist = M.floors[n]
        wsc.cell(row=1, column=col, value=M.names.get(n, n))
        wsc.cell(row=2, column=col, value="hours ago")
        wsc.cell(row=2, column=col + 1, value="floor")
        for i, (t_, f_, _) in enumerate(hist):
            wsc.cell(row=3 + i, column=col, value=round((t_ - now) / H, 2))
            wsc.cell(row=3 + i, column=col + 1, value=f_)
        sc = ScatterChart()
        sc.title = f"{M.names.get(n, n)} - floor"
        sc.style, sc.height, sc.width = 13, 7, 12
        sc.x_axis.title, sc.y_axis.title = "hours (0 = now)", "coins"
        ser = Series(Reference(wsc, min_col=col + 1, min_row=3, max_row=2 + len(hist)),
                     Reference(wsc, min_col=col, min_row=3, max_row=2 + len(hist)), title="floor")
        sc.series.append(ser)
        sc.legend = None
        wsc.add_chart(sc, f"{get_column_letter(40 + (k % 2) * 9)}{2 + (k // 2) * 15}")
        col += 3

    ws = sheet("Trades", ["Time", "Type", "Item", "Qty", "Price", "Cost", "Profit", "Hours listed->sold",
                          "Seller", "Why / notes", "Paper"], [19, 8, 32, 5, 12, 12, 12, 12, 18, 70, 6])
    for t in bot.trades:
        ws.append([t.get("time"), t.get("type"), t.get("item"), t.get("qty", 1), t.get("price"), t.get("cost"),
                   t.get("profit"), t.get("hours"), t.get("seller"), t.get("note"), "yes" if t.get("paper") else ""])
    numfmt(ws)
    ws5 = sheet("Inventory", ["Item", "In bag (cost each)", "Listed at", "Worth now (after fee)", "Notes"],
                [32, 30, 22, 14, 40])
    for n in sorted(set(bot.holdings) | {norm(l["item"]) for l in bot.listings}):
        held = [h for h in bot.holdings.get(n, []) if not h.get("paper") or bot.s.paper_trading]
        lst = [l for l in bot.listings if norm(l["item"]) == n and (not l.get("paper") or bot.s.paper_trading)]
        if not held and not lst:
            continue
        ws5.append([M.names.get(n, n), ", ".join(fmt(h.get("cost")) + (f" (x{h['qty']})" if h.get("qty", 1) > 1 else "")
                                                for h in held),
                    ", ".join(f"{l['price']:,}" for l in lst),
                    round(bot.item_worth(n, None, now)) or None,
                    "; ".join(h.get("flag", "") for h in held if h.get("flag"))])
    numfmt(ws5)
    ws2 = sheet("Market", ["Item", "Rarity", "Resale value", "Basis", "Points", "Floor now", "Listed now",
                           "Sales/day", "Median hours to sell", "Market sales (7d)"],
                [32, 10, 12, 11, 7, 12, 9, 9, 12, 9])
    names = {o["item"] for o in M.obs.values()} | {s["item"] for s in M.sales} | set(M.floors)
    rows = []
    for n in names:
        v, pts, basis = bot.value(n, now)
        f, cnt = M.floor_now(n, now)
        rows.append([M.names.get(n, n), bot.rarity_of(n) or M.colour_of(n), round(v) if v else None, basis, pts,
                     f, cnt, round(M.sales_per_day(n, now), 2), M.hours_to_sale(n, now),
                     len(M.recent_sales(n, now, 7))])
    for r in sorted(rows, key=lambda r: -(r[2] or 0)):
        ws2.append(r)
    numfmt(ws2)
    ws3 = sheet("Market sales", ["Seen gone", "Item", "Qty", "Price", "Per unit", "Seller", "Hours on market"],
                [19, 32, 5, 12, 12, 18, 10])
    for s in sorted(M.sales, key=lambda s: -s["gone_at"]):
        ws3.append([time.strftime("%Y-%m-%d %H:%M", time.localtime(s["gone_at"])),
                    M.names.get(s["item"], s["item"]), s.get("qty", 1), s["price"], round(M.unit_of(s)),
                    s["seller"], s["hours"]])
    numfmt(ws3)
    path = bot.s.excel_out if os.path.isabs(bot.s.excel_out) else os.path.join(HERE, bot.s.excel_out)
    for target in (path, path.replace(".xlsx", f"_{time.strftime('%H%M%S')}.xlsx")):
        try:
            wb.save(target)
            bot.last_file = target
            return target
        except PermissionError:
            continue
    return None


# =============================================================================
#  GUI
# =============================================================================
def run_gui() -> None:
    import tkinter as tk
    from tkinter import scrolledtext, ttk

    s = BotSettings.load()
    q: "queue.Queue[str]" = queue.Queue()

    def log(m):
        line = f"[{time.strftime('%H:%M:%S')}] {m}"
        print(line)
        q.put(line)
        try:
            with open(os.path.join(HERE, "auction_bot_log.txt"), "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception:
            pass

    bot = AuctionBot(s, log)
    threading.Thread(target=bot.run_forever, daemon=True).start()
    env0 = af.WindowsEnv(af.Settings())
    root = tk.Tk()
    root.title(f"{APP} {VERSION}")
    root.attributes("-topmost", True)
    BG, FG = "#151b23", "#e6edf3"
    root.configure(bg=BG)
    btn = tk.Button(root, text=f"START ({s.bot_hotkey})", font=("Segoe UI", 15, "bold"), bg="#2ea043",
                    fg="white", relief="flat", width=24)
    btn.grid(row=0, column=0, columnspan=4, padx=10, pady=(10, 4), sticky="ew")
    st_var, pr_var, stats_var, pause_var = (tk.StringVar(value="Open the auction board, then START."),
                                            tk.StringVar(), tk.StringVar(), tk.StringVar())
    tk.Label(root, textvariable=st_var, bg=BG, fg=FG, font=("Segoe UI", 11, "bold")).grid(row=1, column=0, columnspan=4, sticky="w", padx=10)
    tk.Label(root, textvariable=pr_var, bg=BG, fg="#8b98a5", font=("Consolas", 9)).grid(row=2, column=0, columnspan=4, sticky="w", padx=10)
    tk.Label(root, textvariable=stats_var, bg=BG, fg=FG, font=("Consolas", 10), justify="left").grid(row=3, column=0, columnspan=4, sticky="w", padx=10, pady=4)
    pause_lbl = tk.Label(root, textvariable=pause_var, bg=BG, fg="#f0883e", font=("Segoe UI", 10, "bold"),
                         wraplength=600, justify="left")
    pause_lbl.grid(row=4, column=0, columnspan=3, sticky="w", padx=10)
    vars_ = {}

    def resume():
        bot.pause_reason = ""
        bot._last_cycle_coins = None
        bot.day_start.pop(time.strftime("%Y-%m-%d"), None)
        bot.save_state()
        log("Buying resumed.")
    tk.Button(root, text="Resume buying", command=resume, bg="#30363d", fg=FG, relief="flat").grid(
        row=4, column=3, sticky="e", padx=10)

    def field(r, c, label, attr, w=10):
        tk.Label(root, text=label, bg=BG, fg=FG).grid(row=r, column=c, sticky="w", padx=(10, 2))
        cur = getattr(s, attr)
        v = tk.StringVar(value=str(cur) if isinstance(cur, int) else (f"{cur:g}" if isinstance(cur, float) else cur))
        tk.Entry(root, textvariable=v, width=w, bg="#0d1117", fg=FG, insertbackground=FG, relief="flat").grid(
            row=r, column=c + 1, sticky="w", padx=(0, 10), pady=2)
        vars_[attr] = v

    field(5, 0, "Min profit %", "min_profit_pct")
    field(5, 2, "Slow-seller profit %", "slow_profit_pct")
    field(6, 0, "Steal ratio", "steal_ratio")
    field(6, 2, "Max per buy (share)", "max_buy_frac")
    field(7, 0, "Daily spend cap", "daily_spend_cap", 12)
    field(7, 2, "Coin reserve", "coin_reserve", 12)
    field(8, 0, "Max listings", "max_active_listings")
    field(8, 2, "Pause if net worth -%", "pause_on_drop_pct")

    def wide(r, label, attr):
        tk.Label(root, text=label, bg=BG, fg=FG).grid(row=r, column=0, sticky="w", padx=(10, 2))
        v = tk.StringVar(value=getattr(s, attr))
        tk.Entry(root, textvariable=v, width=70, bg="#0d1117", fg=FG, insertbackground=FG, relief="flat").grid(
            row=r, column=1, columnspan=3, sticky="ew", padx=(0, 10), pady=2)
        vars_[attr] = v
    wide(9, "Watch list ( ; between)", "watch_items")
    wide(10, "Never buy", "never_buy")
    wide(11, "High demand", "high_demand_items")
    wide(12, "Long term", "long_term_items")
    wide(13, "Any rarity", "any_rarity_items")
    paper = tk.BooleanVar(value=s.paper_trading)
    only = tk.BooleanVar(value=s.sell_only_bought)
    onlyw = tk.BooleanVar(value=s.buy_only_watched)
    auto = tk.BooleanVar(value=s.auto_watch)
    for i, (txt, var) in enumerate([("Paper trading (decide + record, never click Buy/List)", paper),
                                    ("Only buy items on the watch list", onlyw),
                                    ("Also search trending items it learns (auto watch)", auto),
                                    ("Only sell what the bot bought (your own items are never sold)", only)]):
        tk.Checkbutton(root, text=txt, variable=var, bg=BG, fg=FG, selectcolor="#0d1117",
                       activebackground=BG, activeforeground=FG).grid(row=14 + i, column=0, columnspan=4, sticky="w", padx=10)

    def apply():
        for attr, v in vars_.items():
            cur = getattr(s, attr)
            try:
                setattr(s, attr, type(cur)(float(v.get())) if isinstance(cur, (int, float)) else v.get())
            except ValueError:
                pass
        s.max_buy_frac = min(0.9, max(0.01, s.max_buy_frac))
        s.steal_ratio = min(0.8, max(0.05, s.steal_ratio))
        s.paper_trading, s.sell_only_bought = paper.get(), only.get()
        s.buy_only_watched, s.auto_watch = onlyw.get(), auto.get()

    def toggle():
        apply()
        if bot.running:
            bot.running = False
            log("Stopping after the current step...")
        else:
            s.save()
            if not s.paper_trading:
                bot.drop_paper()
            bot.running = True
            log("Started" + (" in PAPER mode (no real buys/listings)." if s.paper_trading else "."))

    def open_excel():
        p = bot.last_file or os.path.join(HERE, s.excel_out)
        if os.path.exists(p):
            os.startfile(p)  # type: ignore[attr-defined]
        else:
            log("No report yet - it is written after each cycle.")

    btn.configure(command=toggle)
    tk.Button(root, text="Open report (Excel)", command=open_excel, bg="#30363d", fg=FG, relief="flat").grid(
        row=18, column=0, columnspan=4, sticky="ew", padx=10, pady=4)
    graph = tk.Canvas(root, width=660, height=150, bg="#0d1117", highlightthickness=0)
    graph.grid(row=19, column=0, columnspan=4, padx=10, pady=(4, 2))
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("Floor.Treeview", background="#0d1117", fieldbackground="#0d1117", foreground="#c9d1d9",
                    rowheight=18, font=("Consolas", 9))
    style.configure("Floor.Treeview.Heading", background="#30363d", foreground=FG, font=("Segoe UI", 9, "bold"))
    cols = ("item", "floor", "chg", "listed", "value", "held")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=8, style="Floor.Treeview")
    for c_, t_, w_ in zip(cols, ("Watched item", "Floor/unit", "24h", "Listed", "Resale/unit", "Bot has"),
                          (230, 95, 60, 55, 95, 60)):
        tree.heading(c_, text=t_)
        tree.column(c_, width=w_, anchor="w" if c_ == "item" else "e")
    tree.grid(row=20, column=0, columnspan=4, padx=10, pady=(4, 2), sticky="ew")
    box = scrolledtext.ScrolledText(root, width=90, height=10, bg="#0d1117", fg="#c9d1d9", font=("Consolas", 9), relief="flat")
    box.grid(row=21, column=0, columnspan=4, padx=10, pady=(4, 10))
    gstate = {"n": -1, "t": 0.0}

    def draw_graph():
        pts = list(bot.balance)
        if len(pts) == gstate["n"]:
            return
        gstate["n"] = len(pts)
        graph.delete("all")
        W, Hh, L, R, T, B = 660, 150, 76, 10, 18, 22
        graph.create_text(8, 4, text="Coins", fill="#58a6ff", anchor="nw", font=("Segoe UI", 9, "bold"))
        graph.create_text(52, 4, text="Net worth", fill="#2ea043", anchor="nw", font=("Segoe UI", 9, "bold"))
        if len(pts) < 2:
            graph.create_text(W // 2, Hh // 2, text="the graph appears after a few readings",
                              fill="#8b98a5", font=("Segoe UI", 9))
            return
        t0, t1 = pts[0][0], max(pts[-1][0], pts[0][0] + 1)
        vals = [p[1] for p in pts] + [p[2] for p in pts if len(p) > 2 and p[2]]
        lo, hi = min(vals), max(vals)
        if hi == lo:
            hi, lo = hi + 1, lo - 1
        pad = (hi - lo) * 0.08
        lo, hi = lo - pad, hi + pad

        def xy(t, c):
            return (L + (t - t0) / (t1 - t0) * (W - L - R), T + (hi - c) / (hi - lo) * (Hh - T - B))
        for frac in (0.0, 0.5, 1.0):
            c = lo + (hi - lo) * frac
            _, y = xy(t0, c)
            graph.create_line(L, y, W - R, y, fill="#21262d")
            graph.create_text(L - 6, y, text=f"{c:,.0f}", fill="#8b98a5", anchor="e", font=("Consolas", 8))
        line = []
        for p in pts:
            line.extend(xy(p[0], p[1]))
        graph.create_line(*line, fill="#58a6ff", width=2)
        nwp = [p for p in pts if len(p) > 2 and p[2]]
        if len(nwp) >= 2:
            line = []
            for p in nwp:
                line.extend(xy(p[0], p[2]))
            graph.create_line(*line, fill="#2ea043", width=2)
        graph.create_text(L, Hh - 4, text=time.strftime("%H:%M", time.localtime(t0)), fill="#8b98a5",
                          anchor="sw", font=("Consolas", 8))
        graph.create_text(W - R, Hh - 4, text=time.strftime("%H:%M", time.localtime(t1)), fill="#8b98a5",
                          anchor="se", font=("Consolas", 8))
        ref = nwp if len(nwp) >= 2 else None
        if ref:
            d = ref[-1][2] - ref[0][2]
            graph.create_text(W - R, 4, text=f"net worth {ref[-1][2]:,}  ({'+' if d >= 0 else ''}{d:,})",
                              fill="#2ea043" if d >= 0 else "#d73a49", anchor="ne", font=("Consolas", 9, "bold"))

    def draw_floors():
        if time.time() - gstate["t"] < 2.0:
            return
        gstate["t"] = time.time()
        now = time.time()
        tree.delete(*tree.get_children())
        for n in bot.watched_items(now)[:40]:
            f, cnt = bot.market.floor_now(n, now)
            if f is None:
                hist = bot.market.floors.get(n) or []
                f = hist[-1][1] if hist else None
            f24 = bot.market.floor_ago(n, now, 24)
            chg = f"{(f - f24) / f24 * 100:+.0f}%" if f and f24 else ""
            v, _, _ = bot.value(n, now)
            tree.insert("", "end", values=(bot.market.names.get(n, n), fmt(f) if f else "-", chg, cnt,
                                           fmt(v) if v else "-", bot.held_count(n) or ""))
    hk = {"down": False}

    def poll():
        down = env0.key_down(s.bot_hotkey)
        if down and not hk["down"]:
            toggle()
        hk["down"] = down
        try:
            while True:
                box.insert("end", q.get_nowait() + "\n")
                box.see("end")
        except queue.Empty:
            pass
        btn.configure(text=("STOP" if bot.running else "START") + f" ({s.bot_hotkey})",
                      bg="#d73a49" if bot.running else "#2ea043")
        st_var.set(bot.status if bot.running else "Stopped")
        pr_var.set(bot.progress if bot.running else "")
        now = time.time()
        cost, worth = bot.stock(now)
        nw = bot.net_worth(now)
        stats_var.set(f"Coins {fmt(bot.coins):>11}   Items {fmt(worth):>10} (cost {fmt(cost)})   "
                      f"Net worth {fmt(nw):>11}\n"
                      f"Bought {bot.stats['bought']:>3}   Sold {bot.stats['sold']:>3}   "
                      f"Profit {bot.stats['profit']:>10,}   Listed {len(bot.listings):>2}   "
                      f"Spent 24h {bot.spent_24h():,}")
        pause_var.set(("BUYING PAUSED: " + bot.pause_reason) if bot.pause_reason else "")
        draw_graph()
        draw_floors()
        root.after(250, poll)

    def close():
        apply()
        s.save()
        bot.running = False
        bot.alive = False
        bot.save_state()
        try:
            write_excel(bot)
        except Exception:
            pass
        if bot.ocr:
            bot.ocr.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    log(f"{APP} {VERSION}: open the auction board (Browse tab), then START or {s.bot_hotkey}. "
        "Hands off the mouse while it runs.")
    if bot.pause_reason:
        log(f"Buying is paused from last time: {bot.pause_reason}")
    root.after(200, poll)
    root.mainloop()


if __name__ == "__main__":
    if not sys.platform.startswith("win"):
        print("Windows only.")
        sys.exit(1)
    af.set_dpi_awareness()
    run_gui()
