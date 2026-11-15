AUTOFISH - QUICK START
======================

Hands-free fishing for the Roblox "Hooked! / Reel it in!" minigame.
It casts, waits for a bite, presses E every time the fish is inside the
gold zone, and recasts after each catch - forever, until you stop it.

1. Keep this folder together somewhere normal (Desktop, Documents...).

2. Double-click START_AUTOFISH.bat
   (First time only: it installs two small Python packages, numpy and
   mss. Needs Python - the .bat tells you what to do if it's missing.)

3. In Roblox: stand at the water with your fishing rod equipped, so the
   "[E] Cast" prompt is showing.

4. Press START in the AutoFish window (it switches to Roblox for you),
   or press F6 while you're in Roblox.

5. F6 (or the STOP button) stops it at any time.


SEVERAL ROBLOX WINDOWS (e.g. 4 accounts)
----------------------------------------
"Fish in EVERY Roblox window" is ON by default. AutoFish finds every
window titled "Roblox" (it re-checks every few seconds), casts in each one,
watches all of them at once and switches to whichever window needs a key
press (a cast, or the reel minigame). The log names them Window 1, 2, ...
* Tile the windows so NONE of them overlap each other (and keep the
  AutoFish window off them) - it reads each window from the screen.
* By default one minigame is played at a time; if two bite together the
  second waits its turn.
* Tick "Play all windows' minigames at the same time" to play them in
  parallel instead: AutoFish watches every reel bar at once, works out
  when each window next needs a press, and switches to that window just
  before its press (Windows only sends keys to the window in front, so
  the windows take turns only at the moment of each press). If presses
  seem to go to the wrong window, raise focus_settle_ms in
  autofish_settings.json (60 -> 100).
* Click into any Roblox window to start/resume; if you click into another
  program, everything pauses.


LEVIATHAN MODE
--------------
Tick "Leviathan mode" when you only need the bite (the "!") to happen and
don't care about catching the fish. As soon as the reel bar appears,
AutoFish presses while the fish is far from the gold zone - three quick
deliberate misses end the round - and then recasts straight away.
"Stop on the first miss" is ignored in this mode. With several windows,
Leviathan mode always plays all minigames at the same time, and casting
comes first: a window whose round just ended is recast the moment its Cast
prompt shows (the Recast delay setting is skipped in this mode). The "Bites" counter
shows how many bites were triggered.


LEVIATHAN ALARM (1.7)
---------------------
While AutoFish is running it watches every Roblox window for a leviathan
pull and raises an alarm you can't miss: a loud siren (looping) plus a big
flashing red/orange panel on top of the AutoFish window, and its taskbar
button flashes. It reacts to:
  1. the announcement "... was pulled into the deep by the Serpent of the
     ..." / "Something vast took the bait." (shown in the windows of the
     players nearby - about 2 s after the pull)
  2. a window going black right after that announcement (you're being
     pulled in) - fishing STOPS here, so nothing presses E in the arena
  3. the boss health bar ("The Serpent of the Sea - Lv 250") - the
     fallback when only the pulled player's window is open (its own window
     shows a cut-scene, not the announcement), ~15 s after the pull
Press F6 (or "Silence alarm") to silence it; F6 again starts fishing once
you're back at the water. One alarm per leviathan.
* "Test alarm" plays it so you can set the volume.
* Untick "Leviathan alarm" to turn it off, or untick "...and stop fishing"
  to keep fishing through it.
* The sound stops by itself after 5 minutes (alarm_max_s in
  autofish_settings.json); the panel stays until you silence it.
* Want a different sound? Replace leviathan_alarm.wav (made on first use,
  next to the script) with any .wav file of your own.
* The alarm only watches while AutoFish is running (START / F6).


TIPS
----
* Keep the Roblox window visible - AutoFish reads the screen. It can be
  windowed or fullscreen, any resolution.
* Move the mouse cursor off the Cast prompt (it can hide the prompt's
  text). The cursor over the reel bar is fine.
* AutoFish only presses keys while Roblox is the active window. If you
  alt-tab away it pauses, and carries on when you click back in.
* Don't type in Roblox chat while it's running (it would type "e").


SETTINGS (in the AutoFish window, changes apply instantly)
--------
Auto timing           ON (recommended). AutoFish measures how long the game
                      takes to react to a key press (shown as "Timing" in
                      the stats, with a * once measured) and times every
                      press with it - this is what makes very fast fish
                      work. It works for any fish speed: each press is
                      timed to the moment the fish reaches the middle of
                      the gold zone, including when the zone is moving
                      and when the fish bounces off the end of the bar.
Timing lead (ms)      Starting value before the delay has been measured
                      (or the fixed value if Auto timing is off).
Gold zone margin (%)  How much of each edge of the gold zone to avoid.
                      Higher = only presses near the middle.
Recast delay (s)      Pause after a catch before casting again.
Bite timeout (s)      If nothing bites for this long it reels in and
                      recasts.
Game key              The key that casts/reels (E in this game).
Stop on the first miss
                      ON by default: the moment a press misses, AutoFish
                      stops and saves a miss report (see below). Untick it
                      to keep fishing through misses.
Reel with left-click  Use a mouse click instead of the key while reeling.
Dry run               Watches and logs what it WOULD do without pressing
                      anything - handy to check it sees the game.

"Save settings" writes them to autofish_settings.json next to the script
(they are also saved when you close the window).


MISS REPORTS
------------
When it stops on a miss, AutoFish saves a folder in miss_reports\ with:
  frames.png    one row per game frame from just before the press until
                the miss showed: green ticks = gold zone edges, red tick =
                the fish, yellow box = the last picture before the key
                went down, magenta box = the frame where the miss showed.
  timeline.txt  the same moments as numbers (fish position, gold zone,
                speed, the timing it used, the measured delays).
Send that folder if you want the timing looked at.


IF SOMETHING ISN'T WORKING
--------------------------
* Status says "waiting for the Roblox window to be active": click into
  the Roblox window.
* It stopped by itself: it stopped on a miss ("Stop on the first miss").
  Press START / F6 to carry on; the log shows where the report is.
* It never says "Found the reel bar": make sure the minigame bar isn't
  covered by another window, and that Roblox's graphics aren't using an
  unusual colour filter.
* Press "Debug snapshot" while the reel bar or the Cast prompt is on
  screen. It saves a picture + a text file in the debug_snapshots folder
  showing exactly what AutoFish detected (magenta box = reel bar, green =
  gold zone, red = fish, cyan = Cast/Reel prompt).


Note: automating gameplay may be against the game's or Roblox's rules -
use it at your own risk.


AUCTION READER (auction_reader.py)
==================================
Reads every listing on the auction board into an Excel file.

1. In Roblox, go to the auctioneer and open the auction board (Browse tab).
2. Double-click START_AUCTION_READER.bat (first time it installs openpyxl
   too), then press START or F7. Don't touch the mouse while it scans -
   it clicks the search bar, types a, b, c ... z and scrolls each result
   list (by dragging its scroll bar, or with the mouse wheel). It only ever
   scrolls DOWN, and a search never takes longer than 4 minutes
   ("max_scan_s" in auction_settings.json).
3. Results: auction_listings.xlsx next to the script ("Open Excel file"):
     Latest scan  every listing: item, rarity colour, price, seller,
                  time left, note (e.g. an enchant), which search found it
     Items        per item: listings, cheapest, median, highest price,
                  cheapest seller, and what you'd keep selling at the
                  cheapest price (95%)
     History      every scan appended - this builds the price history
   Each listing is saved once even if several letters find it (true
   duplicates - same item, seller and price listed twice - are kept).
4. "Repeat every (min)" keeps scanning with the board left open.
   Close the Excel file before a scan finishes, or it saves a copy instead.

Search terms are editable (any words, separated by spaces). Text is read
with Windows' own OCR (English language pack - normally already installed).
Rarity: white = Limited, blue = Legendary, red = Mythic (from the Sell
tab); other colours are written as their colour until we know the names.
If a name/price is read wrong, set "save_debug_images": true in
auction_settings.json, run a scan and send me the auction_debug folder.


AUCTION BOT (auction_bot.py) - trades by itself (version 2.3)
=============================================================
1. Open the auction board (Browse tab), double-click START_AUCTION_BOT.bat,
   press START or F8. Hands off the mouse while it runs.
2. Start with "Paper trading" ticked for an hour: it makes every decision
   and records it (Trades sheet) without clicking Buy or List.

WHAT IT WATCHES (all editable in the window, ";" between items)
  Watch list   White Death; Whitedeath; White Dragon Scale; Whitescale;
               Whiteflame Ember; Divine Darkness; Darkness Within;
               Abyssal Devastator; Gem; Gold Ore; Opal
               A term matches every item whose name contains it: "White
               Death" also covers Crystal/Frostbitten White Death, Heart of
               the White Death and White Death armour.
  Never buy    Celestial Scepter; Abyssal  (a longer watch-list name wins,
               so the Abyssal Devastator IS bought, other Abyssal items not)
  High demand  White Dragon Scale; Heart of the White Death; Whiteflame
               Ember; Darkness Within  -> the normal 15% margin applies
               (other items need 30% until the bot has seen them sell daily)
  Long term    Gold Ore; Opal -> bought only at <= 75% of their usual floor,
               listed at least 25% over cost
  Any rarity   Gold Ore; Opal -> bought whatever their rarity
Rarity: nothing below Legendary is bought. Name colours: green Uncommon,
blue Rare, purple Epic, orange Legendary, red Mythic, gold Divine, white
Limited (always OK). Mutations (Crystal, Celestial, Frostbitten...) recolour
the name, so a mutated item counts at its base item's rarity.

STACKS: a listing with an "x42" badge on its icon is a stack of 42 - its
price is for all 42. The bot reads the badge and works in price PER UNIT
(floors, values, the Floor/unit column). A stack is bought only if the badge
reads the same twice; one it can't read is ignored. Bought stacks are
relisted as the same stack.

PRICES = TODAY'S FLOOR
Every search records each item's floor (cheapest listing), how many are
listed, and a log line when a floor moves ("FLOOR: Abyssal Devastator
floor 1,000,000 -> 800,000 (-20%)"). The window shows a live floor table;
the Excel file has "Watched items", "Floor history" and one floor chart per
item. A purchase is valued at what it can be resold for: just under the
cheapest OTHER listing (all copies counted, enchanted and mutated copies
kept apart). If an item's floor fell 20%+ in 24h, only steals are bought.

SAFETY
 - the price is read twice (and must be a clean number) before clicking,
   the row's button must say Buy, and the coins that left your balance must
   match the price; anything odd PAUSES BUYING (orange line in the window,
   "Resume buying" button). Selling keeps going.
 - no buying while your balance can't be read; max 2 buys per cycle; max
   share of coins per buy; daily cap (rolling 24h); coin reserve; bought
   items may be at most 60% of your net worth; max 2 of one item (bag +
   listed; 3 for high-demand, 5 for long-term).
 - buying also pauses if net worth falls 15% below the day's start, or if
   coins leave your balance without a purchase it recorded.
 - EVERYTHING THE BOT BUYS IS RESOLD. Items you owned before are never
   listed ("Only sell what the bot bought").
 - a listing counts as SOLD only after it is missing from My Listings twice
   in a row; a bad read of My Listings changes nothing.
 - learning: an item that expired unsold needs a bigger margin next time
   (and is not bought again after 2 expiries in a week, or while one of
   ours has sat unsold for 48h).

SCROLLING (2.2): each list is read top to bottom, never scrolling back up.
Moving item icons, a highlighted row or Buy buttons changing colour no longer
confuse it (2.1 could get stuck scrolling back and forth for minutes). If a
list can't be read to its end (it kept changing, a search hit its time
limit...), the log says so and that read is NOT used for floors, market
sales or "sold" - only a complete read counts. A cycle skips its remaining
searches after 20 minutes ("max_cycle_min"). Your floor history and settings
from 2.1 are kept.

2.3 - SAFER BOOKKEEPING (from a full code review):
 - before the FIRST 2.3 run: open auction_bot.xlsx (Inventory sheet) and check
   that every item listed there really is in your bag; delete any that aren't
   from auction_bot_state.json's "holdings" (older versions could book a
   listing that sold while the bot was off as "back in the bag").
 - My Listings: a listing is only counted missing on a complete, trusted read,
   so the last listing is no longer stuck forever after an empty read.
 - copies coming back to the bag (expired, never went up) are only sold again
   once the Sell tab shows they are really there - never your own copy. On the
   first run the bot first reads the Sell tab to learn how many of each item
   are YOURS.
 - no buying an item until its whole list was read in the last hour (a cheaper
   copy may be further down); prices that weren't read cleanly are never used
   as floors (and pause buying that item while they are up, with a log line).
 - floors: a one-scan spike or sweep no longer counts as a resale price; Gold
   Ore/Opal need 6h+ of floor history before a long-term buy.
 - coin balance: read twice the same before it is trusted; a misread "after"
   balance pauses buying instead of recording a wrong price.
 - an old "Bought ..." / "Listed ..." message still on screen no longer counts
   as a new buy or listing; "maximum items listed" counts as failed.
 - paper trading never touches the real 24h spend cap or the drawdown baseline.
 - a seller's name containing "limited" no longer makes an item "Limited".
 - enchanted listings are never bought (the Sell tab can't tell them apart).
 - the window can no longer freeze (which also stopped F8).

GRAPH: blue = coins, green = net worth (coins + bought items at today's
floor after the fee). Buying turns coins into items, so coins dip while net
worth should hold - watch the green line.
Report: auction_bot.xlsx (Balance, Watched items, Floor history, Floor
charts, Trades, Inventory, Market, Market sales). Memory:
auction_bot_state.json. Full log: auction_bot_log.txt.
