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
   list with the mouse wheel.
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


AUCTION BOT (auction_bot.py) - trades by itself
===============================================
1. Run a full AuctionReader scan first (it uses auction_listings.xlsx as
   its starting knowledge of prices and demand).
2. Open the auction board (Browse tab), double-click START_AUCTION_BOT.bat,
   press START or F8. Hands off the mouse while it runs.

Every cycle (a few minutes) it:
 - searches your WATCH LIST (editable in the window, ";" between items):
     White Dragon Scale; Whitescale; White Death; Whitedeath;
     Divine Darkness; Darkness Within; Abyssal Devastator; Gem
   A term matches every item whose name contains it, so "White Death" also
   covers Crystal/Frostbitten White Death, Heart of the White Death and
   White Death armour; "Whitescale" is the Whitescale Helm/Plate/Greaves/
   Sabatons set; "Gem" is every Gem of ... and the Mythic Gemstone.
 - only buys items on the watch list, and NEVER buys anything on the
   "Never buy" list (Celestial Scepter, including Blazing/Charged/... ones),
 - BUYS any listing it can resell at a profit after the 5% fee (items it
   hasn't seen sell at least once a day need 30% profit, the rest 15%,
   max 2 held of one item); a STEAL
   (price <= 40% of the item's value, e.g. a Divine Darkness for 100k) is
   bought immediately,
 - reads My Listings: anything gone has SOLD - price, profit and the time
   from listing to sale are recorded; undercut listings are cancelled and
   relisted (never below cost + margin),
 - lists what it bought from the Sell tab, one at a time, just under the
   cheapest competitor. RARE items (worth >= 250k, or Mythic/Limited):
   ONE of each always stays in your bag,
 - tracks every listing it ever saw; listings that vanish early count as
   market sales -> sales/day, sale price and hours-to-sale per item, which
   drive values and prices. "Also search trending items" (off by default)
   adds the busiest items it has learned to the searches (untick "Only buy
   items on the watch list" too if you want it to buy those).

Money rules (editable in the window): min profit %, slow-seller profit %,
steal ratio, max share of your coins per buy, daily spend cap, coin
reserve, max listings.
"Paper trading" makes all decisions and records them without clicking.
"known_values" in auction_bot_settings.json lets you tell it what rare
items are worth (item=value; ...).

Your balance is read every cycle and around every trade: a live graph in
the window, and a "Balance" sheet with a chart in auction_bot.xlsx.
Report sheets: Balance, Trades, Market, Market sales, Watchlist, Inventory.
Memory between runs: auction_bot_state.json. Full log: auction_bot_log.txt.
