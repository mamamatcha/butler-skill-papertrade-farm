# Changelog

## 1.0.0

- First release. Runs the delta-neutral PAPER farm unattended: opens a long and a
  short of equal notional, closes both after `CLOSE_AT_MOVE_PCT`, and repeats.
- Three hard stops, all checked before opening: budget spent, cycle count reached,
  or PAPER's mint rate decayed below the floor.
- Refuses its own settings when `CLOSE_AT_MOVE_PCT` sits too close to the
  liquidation distance, and caps leverage at 25 — a liquidated leg leaves the other
  running unhedged.
- An unknown money-command outcome stops the duty rather than retrying: re-opening
  after an uncertain fill would leave a directional position, not a hedge.
- If one leg opens and the other does not, the opened leg is unwound.
