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
Timing lead (ms)      How far ahead it predicts the fish. If you see
                      misses where the fish had just LEFT the gold zone,
                      raise it (e.g. 30 -> 50). If it presses too EARLY,
                      lower it.
Gold zone margin (%)  How much of each edge of the gold zone to avoid.
                      Higher = only presses near the middle.
Recast delay (s)      Pause after a catch before casting again.
Bite timeout (s)      If nothing bites for this long it reels in and
                      recasts.
Game key              The key that casts/reels (E in this game).
Reel with left-click  Use a mouse click instead of the key while reeling.
Dry run               Watches and logs what it WOULD do without pressing
                      anything - handy to check it sees the game.

"Save settings" writes them to autofish_settings.json next to the script
(they are also saved when you close the window).


IF SOMETHING ISN'T WORKING
--------------------------
* Status says "waiting for the Roblox window to be active": click into
  the Roblox window.
* It never says "Found the reel bar": make sure the minigame bar isn't
  covered by another window, and that Roblox's graphics aren't using an
  unusual colour filter.
* Press "Debug snapshot" while the reel bar or the Cast prompt is on
  screen. It saves a picture + a text file in the debug_snapshots folder
  showing exactly what AutoFish detected (magenta box = reel bar, green =
  gold zone, red = fish, cyan = Cast/Reel prompt).


Note: automating gameplay may be against the game's or Roblox's rules -
use it at your own risk.
