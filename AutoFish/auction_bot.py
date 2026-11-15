# -*- coding: utf-8 -*-
"""
AuctionBot - trades on the Roblox auction board by itself.

    python auction_bot.py        (or double-click START_AUCTION_BOT.bat)

Open the auction board (Browse tab) and press START / F8.  Every cycle it:

  1. WATCH  - searches YOUR watch list (White Dragon Scale, Whitescale, White
     Death, Divine Darkness, Darkness Within, Abyssal Devastator, Gem...),
     reading every listing.  Only those items are bought; "never buy" items
     (Celestial Scepter) are skipped.  Optional: also trending items.
  2. BUY    - any listing it can resell at a profit after the 5% fee is bought
     on the spot; a "steal" (e.g. a 9,500,000 item listed for 100,000) is
     bought immediately.  Spending is capped (per buy, per day, coin reserve).
  3. SALES  - reads My Listings: a listing that disappeared has SOLD (time
     from listing to sale and the profit are recorded).  Listings that were
     undercut are cancelled and relisted (never below the profit floor).
  4. SELL   - lists what it bought from the Sell tab, one at a time, just under
     the cheapest competitor.  RARE items: ONE of each always stays in your bag.
  5. LEARN  - every listing it ever saw is tracked; when one disappears early it
     counts as a market sale.  That gives each item a sale price, sales per
     day and time-to-sale, which drive the watchlist, buy limits and prices.

Everything is written to auction_bot.xlsx (Trades, Market, Market sales,
Watchlist, Inventory) and auction_bot_state.json (memory between runs).
"Paper trading" makes every decision and records it without clicking.
"""
from __future__ import annotations

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


HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import autofish as af            # noqa: E402
import auction_reader as ar      # noqa: E402

APP = "AuctionBot"
VERSION = "1.1"
STATE_PATH = os.path.join(HERE, "auction_bot_state.json")
SETTINGS_PATH = os.path.join(HERE, "auction_bot_settings.json")
FEE_KEEP = 0.95                  # the auction house keeps 5%
H = 3600.0


@dataclass
class BotSettings(ar.ARSettings):
    # what to watch
    # YOUR watch list: searched every cycle, and (buy_only_watched) the only
    # things it buys. Separate with ";" - a term matches any item whose name
    # contains it (spaces ignored), so "White Death" also covers
    # "Crystal White Death", "Heart of the White Death", White Death armour...
    watch_items: str = ("White Dragon Scale; Whitescale; White Death; Whitedeath; Divine Darkness; "
                        "Darkness Within; Abyssal Devastator; Gem")
    never_buy: str = "Celestial Scepter"    # never bought, whatever the price
    buy_only_watched: bool = True           # only buy items matching the watch list
    auto_watch: bool = False                # also search the "trending" items it learns
    watch_size: int = 14                    # how many trending items (auto_watch only)
    known_values: str = "The Divine Darkness=9500000; The Darkness Within=5100000"   # item=value; ...
    min_item_value: int = 20000             # ignore items worth less than this
    cycle_pause_s: float = 20.0             # rest between cycles
    # buying
    min_profit_pct: float = 15.0            # profit after fee, % of the buy price (items that sell often)
    slow_profit_pct: float = 30.0           # ... for items it hasn't seen sell >= 1/day (slow sellers)
    min_profit_coins: int = 10000
    steal_ratio: float = 0.40               # price <= 40% of value -> buy at once
    max_buy_frac: float = 0.50              # never spend more than this share of your coins on one item
    coin_reserve: int = 50000               # always keep this many coins
    daily_spend_cap: int = 3000000
    min_value_points: int = 2               # price points needed before trusting a value
    max_hold_per_item: int = 2              # don't stack up more than this of one item
    # selling
    undercut_pct: float = 1.0               # list this % under the cheapest competitor
    min_list_margin_pct: float = 5.0        # never list below cost/0.95 * (1 + this)
    relist_after_min: float = 45.0          # undercut listings older than this get relisted
    max_active_listings: int = 12
    rare_value: int = 250000                # items worth at least this are "rare"
    rare_rarities: str = "Mythic Limited"   # ... and so are these rarities
    keep_one_rare: bool = True              # leave ONE of each rare item in the bag
    sell_only_bought: bool = True           # only sell what the bot bought
    # safety
    paper_trading: bool = False             # decide + record, but never click Buy / List
    bot_hotkey: str = "F8"
    excel_out: str = "auction_bot.xlsx"
    seed_excel: str = "auction_listings.xlsx"

    @classmethod
    def load(cls) -> "BotSettings":
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
        except Exception:
            pass


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()


def compact(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def split_terms(text: str) -> List[str]:
    return [t.strip() for t in re.split(r"[;,\n]+", text or "") if t.strip()]


def matches_any(item: str, terms: List[str]) -> bool:
    c = compact(item)
    return any(compact(t) and compact(t) in c for t in terms)


def hours_left(text: str) -> Optional[float]:
    m = re.search(r"(\d{1,3})\s*([hmd])", text or "", re.I)
    if not m:
        return None
    v, u = int(m.group(1)), m.group(2).lower()
    return v / 60.0 if u == "m" else (v * 24.0 if u == "d" else float(v))


# =============================================================================
#  Market memory
# =============================================================================
class Market:
    """Remembers every listing seen, infers sales, values items."""

    def __init__(self, data: Optional[dict] = None) -> None:
        d = data or {}
        self.obs: Dict[str, dict] = d.get("obs", {})          # listing key -> observation
        self.sales: List[dict] = d.get("sales", [])           # inferred market sales
        self.names: Dict[str, str] = d.get("names", {})       # normalised -> display name
        self.rarity: Dict[str, str] = d.get("rarity", {})
        self.seed: Dict[str, dict] = d.get("seed", {})        # from the reader's Excel

    def to_json(self) -> dict:
        cutoff = time.time() - 7 * 24 * H
        return {"obs": self.obs, "sales": [s for s in self.sales if s["gone_at"] > cutoff],
                "names": self.names, "rarity": self.rarity, "seed": self.seed}

    @staticmethod
    def key(item: str, seller: str, price: int) -> str:
        return f"{norm(item)}|{norm(seller)}|{int(price)}"

    def see(self, rows: List[dict], now: float, mine: set, my_name: str = "") -> None:
        """`mine`: {(item, price)} of our own listings; `my_name`: our seller name."""
        for r in rows:
            k = self.key(r["item"], r["seller"], r["price"])
            own = (norm(r["item"]), int(r["price"])) in mine or (my_name and norm(r["seller"]) == my_name)
            n = norm(r["item"])
            self.names.setdefault(n, r["item"])
            if r.get("rarity"):
                self.rarity[n] = r["rarity"]
            o = self.obs.get(k)
            hl = hours_left(r.get("time_left", ""))
            if o is None:
                listed = now - (24.0 - hl) * H if hl is not None and hl <= 24 else now
                self.obs[k] = {"item": n, "seller": norm(r["seller"]), "price": int(r["price"]),
                               "first": now, "last": now, "seen": 1, "hl": hl, "listed": listed,
                               "mine": bool(own)}
            else:
                o["last"], o["seen"] = now, o["seen"] + 1
                o["mine"] = o["mine"] or bool(own)
                if hl is not None:
                    o["hl"] = hl

    def sweep_gone(self, term: str, scan_start: float, now: float, log) -> int:
        """Listings matching `term` that were there before but not in this
        complete scan have gone: sold (or withdrawn) - count them as sales."""
        t = norm(term)
        gone = 0
        for k, o in list(self.obs.items()):
            if t and t not in o["item"]:
                continue
            if o["last"] >= scan_start:
                continue
            del self.obs[k]
            if o["mine"] or o["seen"] < 2:
                continue                  # ours (tracked separately) / maybe a misread
            hl_then = (o["hl"] or 24) - (o["last"] - o["first"]) / H
            if hl_then < 0.5:
                continue                  # it simply expired
            self.sales.append({"item": o["item"], "price": o["price"], "seller": o["seller"],
                               "listed": o["listed"], "gone_at": now,
                               "hours": round((now - o["listed"]) / H, 2)})
            gone += 1
        return gone

    def current(self, item_n: str, now: float, exclude_mine: bool = True) -> List[int]:
        return sorted(o["price"] for o in self.obs.values()
                      if o["item"] == item_n and now - o["last"] < 3 * H and not (exclude_mine and o["mine"]))

    def recent_sales(self, item_n: str, now: float, days: float = 3.0) -> List[dict]:
        return [s for s in self.sales if s["item"] == item_n and now - s["gone_at"] < days * 24 * H]

    def value(self, item_n: str, now: float, exclude_price: Optional[int] = None) -> Tuple[Optional[float], int]:
        """(estimated resale value, number of price points behind it).
        Sold prices first; otherwise the low end of what's listed now (a
        conservative value - the price you'd have to beat to sell)."""
        sold = [s["price"] for s in self.recent_sales(item_n, now)]
        cur = self.current(item_n, now)
        if exclude_price is not None and exclude_price in cur:
            cur = list(cur)
            cur.remove(exclude_price)
        if len(sold) >= 2:
            v = statistics.median(sold)
            if cur:
                v = min(v, statistics.median(cur[:3]) if len(cur) >= 3 else max(cur[0], 0.8 * v))
            return float(v), len(sold) + len(cur)
        pts = list(cur)
        sd = self.seed.get(item_n)
        if len(pts) < 2 and sd:
            pts += [sd["cheapest"], sd["median"]] if sd.get("listings", 1) >= 2 else [sd["cheapest"]]
        if not pts:
            return None, 0
        pts.sort()
        low = pts[:3]
        return float(statistics.median(low)), len(pts)

    def sales_per_day(self, item_n: str, now: float) -> float:
        s = self.recent_sales(item_n, now, 3.0)
        if not s:
            return 0.0
        span = max(6 * H, now - min(x["gone_at"] for x in s))
        return len(s) / (span / (24 * H))

    def hours_to_sale(self, item_n: str, now: float) -> Optional[float]:
        s = self.recent_sales(item_n, now, 7.0)
        return round(statistics.median([x["hours"] for x in s]), 2) if s else None


# =============================================================================
#  The bot
# =============================================================================
class AuctionBot(ar.AuctionReader):
    TAB_X = {"browse": -152, "sell": -94, "listings": -34}

    def __init__(self, s: BotSettings, log) -> None:
        super().__init__(s, log)
        self.s: BotSettings = s
        st = {}
        try:
            st = json.load(open(STATE_PATH, encoding="utf-8"))
        except Exception:
            pass
        self.market = Market(st.get("market"))
        self.trades: List[dict] = st.get("trades", [])
        self.holdings: Dict[str, List[dict]] = st.get("holdings", {})   # bought, in the bag: item -> [{cost, at}]
        self.listings: List[dict] = st.get("listings", [])              # our active listings
        self.spend_day: Dict[str, int] = st.get("spend_day", {})
        self.balance: List[list] = st.get("balance", [])                 # [time, coins] history
        self.my_name: str = st.get("my_name", "")
        self.coins: Optional[int] = None
        self.cycle = 0
        self.pending: Optional[dict] = None
        self.stats = {"bought": 0, "sold": 0, "profit": 0}
        self.recount()
        if not self.market.seed:
            self.load_seed()
        self.load_known_values()

    def load_known_values(self) -> None:
        """Values you typed in (for rare items the bot may not have seen yet)."""
        for part in re.split(r"[;\n]+", self.s.known_values or ""):
            if "=" not in part:
                continue
            name, val = part.rsplit("=", 1)
            try:
                v = int(re.sub(r"\D", "", val))
            except ValueError:
                continue
            n = norm(name)
            if n and v > 0:
                self.market.names.setdefault(n, name.strip())
                old = self.market.seed.get(n, {})
                self.market.seed[n] = {"listings": old.get("listings", 0), "cheapest": v, "median": float(v),
                                       "highest": v, "known": True}

    # ---- persistence ---------------------------------------------------------
    def save_state(self) -> None:
        data = {"market": self.market.to_json(), "trades": self.trades[-3000:], "holdings": self.holdings,
                "listings": self.listings, "spend_day": self.spend_day,
                "balance": self.balance[-20000:], "my_name": self.my_name}
        try:
            tmp = STATE_PATH + ".tmp"
            json.dump(data, open(tmp, "w", encoding="utf-8"))
            os.replace(tmp, STATE_PATH)
        except Exception as exc:
            self.log(f"Could not save the bot's memory: {exc!r}")

    def load_seed(self) -> None:
        """Start from the AuctionReader's last full scan (prices, demand)."""
        path = self.s.seed_excel if os.path.isabs(self.s.seed_excel) else os.path.join(HERE, self.s.seed_excel)
        try:
            from openpyxl import load_workbook
            wb = load_workbook(path, read_only=True)
            for row in wb["Items"].iter_rows(min_row=2, values_only=True):
                if row and row[0] and row[3]:
                    n = norm(str(row[0]))
                    self.market.names.setdefault(n, str(row[0]))
                    self.market.rarity.setdefault(n, str(row[1] or ""))
                    self.market.seed[n] = {"listings": int(row[2] or 0), "cheapest": int(row[3]),
                                           "median": float(row[4] or row[3]), "highest": int(row[5] or row[3])}
                    self.vocab.setdefault(str(row[0]), 5)
            self.log(f"Started from {len(self.market.seed)} items in {os.path.basename(path)}.")
        except Exception as exc:
            self.log(f"No reader scan to start from ({exc.__class__.__name__}) - learning from scratch.")

    def recount(self) -> None:
        self.stats["bought"] = sum(1 for t in self.trades if t["type"] == "buy")
        self.stats["sold"] = sum(1 for t in self.trades if t["type"] == "sold")
        self.stats["profit"] = sum(t.get("profit", 0) or 0 for t in self.trades if t["type"] == "sold")

    def trade(self, **kw) -> None:
        kw.setdefault("time", time.strftime("%Y-%m-%d %H:%M:%S"))
        kw.setdefault("paper", self.s.paper_trading)
        self.trades.append(kw)
        self.recount()

    # ---- helpers ---------------------------------------------------------------
    def is_rare(self, item_n: str, now: float) -> bool:
        rarity = (self.market.rarity.get(item_n) or "").lower()
        if rarity and rarity in self.s.rare_rarities.lower().split():
            return True
        v, _ = self.market.value(item_n, now)
        return bool(v and v >= self.s.rare_value)

    def mine_keys(self) -> set:
        """(item, price) of every listing of ours."""
        return {(norm(l["item"]), int(l["price"])) for l in self.listings}

    def spent_today(self) -> int:
        return int(self.spend_day.get(time.strftime("%Y-%m-%d"), 0))

    def ocr_text(self, region, up: int = 3) -> str:
        img = self.grab(region)
        lines = self._ocr_read(ar.prep_for_ocr(img, up))
        return " ".join(l["text"] for l in sorted(lines, key=lambda l: (l["y"], l["x"])))

    def read_coins(self, board) -> Optional[int]:
        t = self.ocr_text(board.coins_region())
        m = re.search(r"(\d[\d,.\s]{2,})", t.replace("O", "0").replace("o", "0"))
        if not m:
            return None
        v = int(re.sub(r"\D", "", m.group(1)) or 0)
        if self.coins and v and (v > 20 * self.coins or v < self.coins / 20):
            return self.coins            # a misread (digit lost / added) - ignore it
        self.coins = v
        now = time.time()
        if not self.balance or self.balance[-1][1] != v or now - self.balance[-1][0] > 600:
            self.balance.append([now, v])
        return v

    def read_message(self, board) -> str:
        x0, y0 = board.pt(0, 252)
        x1, y1 = board.pt(182, 270)
        return self.ocr_text((x0, y0, x1 - x0, y1 - y0))

    def tab(self, board, name: str) -> None:
        self.click(*board.pt(self.TAB_X[name], 36))
        time.sleep(1.0)

    def button_x(self, board) -> int:
        return board.pt(148, 0)[0]

    def type_into(self, x: int, y: int, text: str) -> None:
        self.click(x, y)
        time.sleep(0.25)
        self.clear_search()
        for ch in text:
            self.key(ch)
            time.sleep(0.03)
        time.sleep(0.2)

    # ---- decisions ---------------------------------------------------------------
    def buy_decision(self, row: dict, now: float) -> Optional[str]:
        """Why this listing should be bought, or None."""
        n = norm(row["item"])
        price = int(row["price"])
        if price <= 0 or (n, price) in self.mine_keys() or (self.my_name and norm(row["seller"]) == self.my_name):
            return None
        if matches_any(row["item"], split_terms(self.s.never_buy)):
            return None
        if self.s.buy_only_watched and not matches_any(row["item"], split_terms(self.s.watch_items)):
            return None
        value, pts = self.market.value(n, now, exclude_price=price)
        if value is None:
            return None
        if len(self.holdings.get(n, [])) >= self.s.max_hold_per_item:
            return None
        profit = FEE_KEEP * value - price
        steal = price <= self.s.steal_ratio * value and pts >= 1 and profit >= self.s.min_profit_coins
        pct = self.s.min_profit_pct if self.market.sales_per_day(n, now) >= 1.0 else self.s.slow_profit_pct
        good = (pts >= self.s.min_value_points and value >= self.s.min_item_value
                and profit >= max(self.s.min_profit_coins, pct / 100.0 * price))
        if not (steal or good):
            return None
        # money rules
        coins = self.coins or 0
        if coins and (price > self.s.max_buy_frac * coins or coins - price < self.s.coin_reserve):
            if not steal or coins - price < self.s.coin_reserve:
                return None
        if self.spent_today() + price > self.s.daily_spend_cap:
            return None
        kind = "STEAL" if steal else "deal"
        return f"{kind}: worth ~{value:,.0f} ({pts} price points), profit after fee ~{profit:,.0f}"

    def sell_price(self, item_n: str, cost: Optional[float], now: float) -> Optional[int]:
        others = self.market.current(item_n, now)
        value, _ = self.market.value(item_n, now)
        floor = 0
        if cost:
            floor = math.ceil(cost / FEE_KEEP * (1 + self.s.min_list_margin_pct / 100.0))
        elif value:
            floor = int(0.85 * value)
        if others:
            target = int(others[0] * (1 - self.s.undercut_pct / 100.0))
        elif value:
            target = int(value * 1.05)
        else:
            return None
        return max(target, floor)

    # ---- watching + buying ---------------------------------------------------------
    def watchlist(self, now: float) -> List[str]:
        out, seen = [], set()
        never = split_terms(self.s.never_buy)
        for t in split_terms(self.s.watch_items) + (self.trending(now) if self.s.auto_watch else []):
            if compact(t) not in seen and not matches_any(t, never):
                seen.add(compact(t))
                out.append(t)
        return out

    def trending(self, now: float) -> List[str]:
        """High-demand items with a good spread (only used with auto_watch)."""
        scores = []
        names = set(self.market.seed) | {o["item"] for o in self.market.obs.values()} | \
            {s["item"] for s in self.market.sales}
        for n in names:
            value, pts = self.market.value(n, now)
            if not value or value < self.s.min_item_value:
                continue
            cur = self.market.current(n, now)
            seed = self.market.seed.get(n, {})
            demand = self.market.sales_per_day(n, now) + 0.15 * max(len(cur), seed.get("listings", 0))
            spread = 0.0
            prices = cur or ([seed["cheapest"], seed["median"]] if seed else [])
            if len(prices) >= 2:
                spread = max(0.0, (statistics.median(prices) - prices[0]) / max(1.0, statistics.median(prices)))
            score = demand * (0.15 + spread) * math.log10(max(10.0, value))
            scores.append((score, n))
        scores.sort(reverse=True)
        return [self.market.names.get(n, n) for _, n in scores[: self.s.watch_size]]

    def watch_term(self, board, term: str) -> None:
        for attempt in range(4):              # repeat after each purchase (the list changed)
            now = time.time()
            start = now
            self.pending = None
            mine = self.mine_keys()

            def on_screen(img, rows):
                for r in rows:          # learn our own seller name from our listings
                    if not self.my_name and (norm(r["item"]), int(r["price"])) in mine:
                        self.my_name = norm(r["seller"])
                        self.log(f"Your seller name looks like '{r['seller']}'.")
                self.market.see(rows, time.time(), mine, self.my_name)
                for r in rows:
                    why = self.buy_decision(r, time.time())
                    if why:
                        self.pending = dict(r, why=why)
                        return True
                return False

            res = self.scan_term(board, term, on_screen)
            if res is None:
                return
            if self.pending is None:
                gone = self.market.sweep_gone(term, start, time.time(), self.log)
                if gone:
                    self.log(f"'{term}': {gone} listing(s) sold since last look.")
                return
            self.buy(board, self.pending)

    def buy(self, board, row: dict) -> None:
        item, price = row["item"], int(row["price"])
        self.log(f"BUY {item} for {price:,} from {row['seller']} - {row['why']}")
        if self.s.paper_trading:
            self.trade(type="buy", item=item, price=price, seller=row["seller"], note=row["why"])
            self.holdings.setdefault(norm(item), []).append({"cost": price, "at": time.time(), "paper": True})
            self.market.obs.pop(self.market.key(item, row["seller"], price), None)
            return
        # find the same row again on the screen right now (the list may have moved)
        crop = self.grab(board.list_region())
        lx, ly, lw, lh = board.list_region()
        target = None
        for r in self.read_screen_img(crop, board):
            if norm(r["item"]) == norm(item) and abs(int(r["price"]) - price) <= max(1, price // 100):
                target = r
                break
        if target is None:
            self.log("  ...the listing isn't on screen any more - skipped.")
            return
        before = self.read_coins(board)
        y = int(ly + target["y"] + target.get("h", 26 * board.s) / 2)
        self.click(self.button_x(board), y)
        time.sleep(1.2)
        after = self.read_coins(board)
        msg = self.read_message(board)
        ok = "bought" in msg.lower() or (before and after and before - after >= 0.98 * price)
        if not ok:
            self.log(f"  ...not bought ({msg or 'no message'}).")
            return
        paid = (before - after) if (before and after and before > after) else price
        day = time.strftime("%Y-%m-%d")
        self.spend_day[day] = self.spend_day.get(day, 0) + paid
        self.holdings.setdefault(norm(item), []).append({"cost": paid, "at": time.time()})
        self.market.obs.pop(self.market.key(item, row["seller"], price), None)
        self.trade(type="buy", item=item, price=paid, seller=row["seller"], note=row["why"])
        self.log(f"  BOUGHT {item} for {paid:,}.  Coins now {after or '?'}")
        self.save_state()

    # ---- my listings: sales + relisting ------------------------------------------------
    def check_listings(self, board) -> None:
        self.tab(board, "listings")
        rows = self.scan_term(board, None) or {}
        now = time.time()
        shown = [dict(r) for r in rows.values()]
        still = []
        for l in self.listings:
            match = next((r for r in shown if norm(r["item"]) == norm(l["item"])
                          and abs(int(r["price"]) - l["price"]) <= max(1, l["price"] // 100)), None)
            if match is not None:
                shown.remove(match)
                l["seen"] = now
                still.append(l)
                continue
            if l.get("paper"):
                still.append(l)
                continue
            hours = (now - l["listed_at"]) / H
            if hours >= 23.9:
                # expired: the item came back to the bag
                self.holdings.setdefault(norm(l["item"]), []).append({"cost": l.get("cost"), "at": now})
                self.trade(type="expired", item=l["item"], price=l["price"], hours=round(hours, 2))
                continue
            profit = int(FEE_KEEP * l["price"] - (l.get("cost") or 0)) if l.get("cost") else None
            self.trade(type="sold", item=l["item"], price=l["price"], cost=l.get("cost"),
                       profit=profit, hours=round(hours, 2),
                       listed=time.strftime("%Y-%m-%d %H:%M", time.localtime(l["listed_at"])))
            self.log(f"SOLD {l['item']} for {l['price']:,} after {hours:.1f}h"
                     + (f" - profit {profit:,}" if profit is not None else ""))
        self.listings = still
        # undercut and old enough -> cancel (the item returns to the bag, relisted below)
        for l in list(self.listings):
            if l.get("paper"):
                continue
            age_min = (now - l["listed_at"]) / 60.0
            others = self.market.current(norm(l["item"]), now)
            if age_min < self.s.relist_after_min or not others or others[0] >= l["price"]:
                continue
            new = self.sell_price(norm(l["item"]), l.get("cost"), now)
            if new is None or new >= l["price"]:
                continue
            if self.cancel(board, l):
                self.log(f"Undercut: {l['item']} at {l['price']:,} (cheapest now {others[0]:,}) - "
                         f"cancelled, will relist at {new:,}.")
        self.save_state()

    def cancel(self, board, l: dict) -> bool:
        crop = self.grab(board.list_region())
        lx, ly, lw, lh = board.list_region()
        for r in self.read_screen_img(crop, board):
            if norm(r["item"]) == norm(l["item"]) and abs(int(r["price"]) - l["price"]) <= max(1, l["price"] // 100):
                self.click(self.button_x(board), int(ly + r["y"] + r.get("h", 26 * board.s) / 2))
                time.sleep(1.0)
                self.listings.remove(l)
                self.holdings.setdefault(norm(l["item"]), []).append({"cost": l.get("cost"), "at": time.time()})
                self.trade(type="cancel", item=l["item"], price=l["price"])
                return True
        return False

    # ---- selling from the bag -------------------------------------------------------------
    def sell_inventory(self, board) -> None:
        if len(self.listings) >= self.s.max_active_listings:
            return
        self.tab(board, "sell")
        rows = list((self.scan_term(board, None, need_price=False) or {}).values())
        now = time.time()
        self.inventory_seen = [(r["item"], r.get("sub", "")) for r in rows]
        for r in rows:
            n = norm(r["item"])
            sub = r.get("sub", "")
            rar = sub.split("·")[0].strip() if "·" in sub else sub.split(" ")[0]
            if rar:
                self.market.rarity.setdefault(n, rar)
        for r in rows:
            if len(self.listings) >= self.s.max_active_listings or not self.running:
                break
            n = norm(r["item"])
            held = self.holdings.get(n, [])
            if self.s.sell_only_bought and not held:
                continue
            cost = held[0]["cost"] if held else None
            price = self.sell_price(n, cost, now)
            if price is None:
                continue
            if self.s.paper_trading:
                if held and held[0].get("paper"):
                    held.pop(0)
                    self.listings.append({"item": r["item"], "price": price, "cost": cost,
                                          "listed_at": now, "paper": True})
                    self.trade(type="list", item=r["item"], price=price, cost=cost)
                continue
            if self.list_one(board, r, price, n):
                if held:
                    held.pop(0)
                self.listings.append({"item": r["item"], "price": price, "cost": cost, "listed_at": time.time()})
                self.trade(type="list", item=r["item"], price=price, cost=cost)
                self.log(f"LISTED {r['item']} for {price:,}" + (f" (cost {cost:,})" if cost else ""))
                self.save_state()
                self.tab(board, "sell")          # the bag list changed
                return self.sell_inventory(board) if len(self.listings) < self.s.max_active_listings else None
        self.save_state()

    def list_one(self, board, r: dict, price: int, n: str) -> bool:
        """Sell... -> read how many are in the bag -> keep one if rare ->
        quantity 1, price, List item."""
        lx, ly, lw, lh = board.list_region()
        crop = self.grab(board.list_region())
        target = next((x for x in self.read_screen_img(crop, board, need_price=False)
                       if norm(x["item"]) == n), None)
        if target is None:
            return False
        self.click(self.button_x(board), int(ly + target["y"] + target.get("h", 26 * board.s) / 2))
        time.sleep(1.0)
        qx, qy = board.pt(-125, 92)
        t = self.ocr_text((qx - int(18 * board.s), qy - int(8 * board.s), int(36 * board.s), int(16 * board.s)), 4)
        m = re.search(r"\d+", t.replace("O", "0").replace("l", "1").replace("I", "1"))
        count = int(m.group(0)) if m else 1
        keep = 1 if (self.s.keep_one_rare and self.is_rare(n, time.time())) else 0
        if count - keep < 1:
            self.log(f"Keeping your last {r['item']} (rare).")
            self.click(*board.pt(99, 92))        # Back
            time.sleep(0.8)
            return False
        self.type_into(qx, qy, "1")
        px, py = board.pt(-64, 92)
        self.type_into(px, py, str(int(price)))
        self.click(*board.pt(147, 92))           # List item
        time.sleep(1.2)
        msg = self.read_message(board)
        if "listed" in msg.lower():
            return True
        self.log(f"Listing {r['item']} didn't confirm ({msg or 'no message'}).")
        return "back" not in msg.lower() and bool(msg)

    # ---- main loop ------------------------------------------------------------------------
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
        self.read_coins(board)
        now = time.time()
        terms = self.watchlist(now)
        self.log(f"Cycle {self.cycle}: coins {self.coins if self.coins is not None else '?'}, "
                 f"watching {len(terms)} searches.")
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
        self.read_coins(board)
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
        from openpyxl.styles import Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        bot.log("openpyxl missing: python -m pip install --user openpyxl")
        return None
    now = time.time()
    wb = Workbook()
    wb.remove(wb.active)
    bold, fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="7A1F2B")

    def sheet(name, heads, widths):
        ws = wb.create_sheet(name)
        ws.append(heads)
        for i, h in enumerate(heads, 1):
            c = ws.cell(row=1, column=i)
            c.font, c.fill = bold, fill
            ws.column_dimensions[get_column_letter(i)].width = widths[i - 1]
        ws.freeze_panes = "A2"
        return ws

    ws = sheet("Trades", ["Time", "Type", "Item", "Price", "Cost", "Profit", "Hours listed->sold",
                          "Seller", "Why", "Paper"], [19, 8, 32, 12, 12, 12, 12, 18, 60, 6])
    for t in bot.trades:
        ws.append([t.get("time"), t.get("type"), t.get("item"), t.get("price"), t.get("cost"),
                   t.get("profit"), t.get("hours"), t.get("seller"), t.get("note"), "yes" if t.get("paper") else ""])
    ws2 = sheet("Market", ["Item", "Rarity", "Value", "Price points", "Cheapest now", "Listed now",
                           "Sales/day", "Median hours to sell", "Market sales seen", "Rare"],
                [32, 11, 12, 8, 12, 9, 9, 12, 9, 6])
    names = set(bot.market.seed) | {o["item"] for o in bot.market.obs.values()} | {s["item"] for s in bot.market.sales}
    rows = []
    for n in names:
        v, pts = bot.market.value(n, now)
        cur = bot.market.current(n, now)
        rows.append([bot.market.names.get(n, n), bot.market.rarity.get(n, ""), round(v) if v else None, pts,
                     cur[0] if cur else None, len(cur), round(bot.market.sales_per_day(n, now), 2),
                     bot.market.hours_to_sale(n, now), len(bot.market.recent_sales(n, now, 7)),
                     "yes" if bot.is_rare(n, now) else ""])
    for r in sorted(rows, key=lambda r: -(r[6] or 0)):
        ws2.append(r)
    ws3 = sheet("Market sales", ["Seen gone", "Item", "Price", "Seller", "Hours on market"], [19, 32, 12, 18, 10])
    for s in sorted(bot.market.sales, key=lambda s: -s["gone_at"]):
        ws3.append([time.strftime("%Y-%m-%d %H:%M", time.localtime(s["gone_at"])),
                    bot.market.names.get(s["item"], s["item"]), s["price"], s["seller"], s["hours"]])
    ws4 = sheet("Watchlist", ["Search"], [34])
    for t in bot.watchlist(now):
        ws4.append([t])
    ws5 = sheet("Inventory", ["Item", "Bought (cost)", "Rare - keep one", "Listed now at"], [32, 30, 12, 20])
    for n, held in bot.holdings.items():
        if held or any(norm(l["item"]) == n for l in bot.listings):
            ws5.append([bot.market.names.get(n, n), ", ".join(f"{h.get('cost') or '?'}" for h in held),
                        "yes" if bot.is_rare(n, now) else "",
                        ", ".join(f"{l['price']:,}" for l in bot.listings if norm(l["item"]) == n)])
    for w in (ws, ws2, ws3):
        for row in w.iter_rows(min_row=2):
            for c in row:
                if isinstance(c.value, (int, float)) and c.value >= 1000:
                    c.number_format = "#,##0"
    ws6 = sheet("Balance", ["Time", "Coins"], [19, 14])
    for t_, c_ in bot.balance:
        ws6.append([time.strftime("%Y-%m-%d %H:%M", time.localtime(t_)), c_])
        ws6.cell(row=ws6.max_row, column=2).number_format = "#,##0"
    if len(bot.balance) >= 2:
        from openpyxl.chart import LineChart, Reference
        ch = LineChart()
        ch.title = "Balance (coins)"
        ch.y_axis.title = "Coins"
        ch.x_axis.title = "Time"
        ch.height, ch.width = 9, 22
        ch.legend = None
        ch.add_data(Reference(ws6, min_col=2, min_row=1, max_row=ws6.max_row), titles_from_data=True)
        ch.set_categories(Reference(ws6, min_col=1, min_row=2, max_row=ws6.max_row))
        ws6.add_chart(ch, "D2")
    wb.move_sheet("Balance", offset=-(len(wb.sheetnames) - 1))
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
    from tkinter import scrolledtext

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
    st_var, pr_var, stats_var = tk.StringVar(value="Open the auction board, then START."), tk.StringVar(), tk.StringVar()
    tk.Label(root, textvariable=st_var, bg=BG, fg=FG, font=("Segoe UI", 11, "bold")).grid(row=1, column=0, columnspan=4, sticky="w", padx=10)
    tk.Label(root, textvariable=pr_var, bg=BG, fg="#8b98a5", font=("Consolas", 9)).grid(row=2, column=0, columnspan=4, sticky="w", padx=10)
    tk.Label(root, textvariable=stats_var, bg=BG, fg=FG, font=("Consolas", 10)).grid(row=3, column=0, columnspan=4, sticky="w", padx=10, pady=4)
    vars_ = {}

    def field(r, c, label, attr, w=10):
        tk.Label(root, text=label, bg=BG, fg=FG).grid(row=r, column=c, sticky="w", padx=(10, 2))
        v = tk.StringVar(value=f"{getattr(s, attr):g}" if isinstance(getattr(s, attr), (int, float)) else getattr(s, attr))
        tk.Entry(root, textvariable=v, width=w, bg="#0d1117", fg=FG, insertbackground=FG, relief="flat").grid(
            row=r, column=c + 1, sticky="w", padx=(0, 10), pady=2)
        vars_[attr] = v

    field(4, 0, "Min profit %", "min_profit_pct")
    field(4, 2, "Steal ratio", "steal_ratio")
    field(5, 0, "Max per buy (share)", "max_buy_frac")
    field(5, 2, "Daily spend cap", "daily_spend_cap", 12)
    field(6, 0, "Coin reserve", "coin_reserve", 12)
    field(6, 2, "Max listings", "max_active_listings")
    field(7, 0, "Rare if worth >=", "rare_value", 12)
    field(7, 2, "Slow-seller profit %", "slow_profit_pct")

    def wide(r, label, attr):
        tk.Label(root, text=label, bg=BG, fg=FG).grid(row=r, column=0, sticky="w", padx=(10, 2))
        v = tk.StringVar(value=getattr(s, attr))
        tk.Entry(root, textvariable=v, width=64, bg="#0d1117", fg=FG, insertbackground=FG, relief="flat").grid(
            row=r, column=1, columnspan=3, sticky="ew", padx=(0, 10), pady=2)
        vars_[attr] = v
    wide(8, "Watch list ( ; between)", "watch_items")
    wide(9, "Never buy", "never_buy")
    paper = tk.BooleanVar(value=s.paper_trading)
    keep = tk.BooleanVar(value=s.keep_one_rare)
    only = tk.BooleanVar(value=s.sell_only_bought)
    onlyw = tk.BooleanVar(value=s.buy_only_watched)
    auto = tk.BooleanVar(value=s.auto_watch)
    for i, (txt, var) in enumerate([("Paper trading (decide + record, never click Buy/List)", paper),
                                    ("Only buy items on the watch list", onlyw),
                                    ("Also search trending items it learns (auto watch)", auto),
                                    ("Keep ONE of each rare item", keep),
                                    ("Only sell what the bot bought", only)]):
        tk.Checkbutton(root, text=txt, variable=var, bg=BG, fg=FG, selectcolor="#0d1117",
                       activebackground=BG, activeforeground=FG).grid(row=10 + i, column=0, columnspan=4, sticky="w", padx=10)

    def apply():
        for attr, v in vars_.items():
            cur = getattr(s, attr)
            try:
                setattr(s, attr, type(cur)(float(v.get())) if isinstance(cur, (int, float)) else v.get())
            except ValueError:
                pass
        s.paper_trading, s.keep_one_rare, s.sell_only_bought = paper.get(), keep.get(), only.get()
        s.buy_only_watched, s.auto_watch = onlyw.get(), auto.get()

    def toggle():
        apply()
        if bot.running:
            bot.running = False
            log("Stopping after the current step...")
        else:
            s.save()
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
        row=15, column=0, columnspan=4, sticky="ew", padx=10, pady=4)
    graph = tk.Canvas(root, width=620, height=150, bg="#0d1117", highlightthickness=0)
    graph.grid(row=16, column=0, columnspan=4, padx=10, pady=(4, 2))
    box = scrolledtext.ScrolledText(root, width=86, height=12, bg="#0d1117", fg="#c9d1d9", font=("Consolas", 9), relief="flat")
    box.grid(row=17, column=0, columnspan=4, padx=10, pady=(4, 10))
    gstate = {"n": -1}

    def draw_graph():
        pts = list(bot.balance)
        if len(pts) == gstate["n"]:
            return
        gstate["n"] = len(pts)
        graph.delete("all")
        W, Hh, L, R, T, B = 620, 150, 70, 10, 18, 22
        graph.create_text(8, 4, text="Balance", fill="#8b98a5", anchor="nw", font=("Segoe UI", 9, "bold"))
        if len(pts) < 2:
            graph.create_text(W // 2, Hh // 2, text="the balance graph appears after a few readings",
                              fill="#8b98a5", font=("Segoe UI", 9))
            return
        t0, t1 = pts[0][0], max(pts[-1][0], pts[0][0] + 1)
        lo, hi = min(p[1] for p in pts), max(p[1] for p in pts)
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
        for t, c in pts:
            line.extend(xy(t, c))
        up = pts[-1][1] >= pts[0][1]
        graph.create_line(*line, fill="#2ea043" if up else "#d73a49", width=2)
        graph.create_text(L, Hh - 4, text=time.strftime("%H:%M", time.localtime(t0)), fill="#8b98a5",
                          anchor="sw", font=("Consolas", 8))
        graph.create_text(W - R, Hh - 4, text=time.strftime("%H:%M", time.localtime(t1)), fill="#8b98a5",
                          anchor="se", font=("Consolas", 8))
        d = pts[-1][1] - pts[0][1]
        graph.create_text(W - R, 4, text=f"{pts[-1][1]:,}  ({'+' if d >= 0 else ''}{d:,})",
                          fill="#2ea043" if d >= 0 else "#d73a49", anchor="ne", font=("Consolas", 9, "bold"))
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
        stats_var.set(f"Coins {bot.coins if bot.coins is not None else '?':>10}   Bought {bot.stats['bought']:>3}   "
                      f"Sold {bot.stats['sold']:>3}   Profit {bot.stats['profit']:>10,}   "
                      f"Listed {len(bot.listings):>2}   Spent today {bot.spent_today():,}")
        draw_graph()
        root.after(200, poll)

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
    root.after(200, poll)
    root.mainloop()


if __name__ == "__main__":
    if not sys.platform.startswith("win"):
        print("Windows only.")
        sys.exit(1)
    af.set_dpi_awareness()
    run_gui()
