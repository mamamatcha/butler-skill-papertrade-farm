# butler-skill-papertrade-farm

The `papertrade-farm` duty template for [Butler](https://github.com/Virtual-Protocol/butler-skills).
Runs the PAPER farm unattended.

## The strategy

papertrade mints PAPER to traders who **lose**. One cycle:

1. Open a **long and a short of equal notional** on BTC or ETH — delta neutral, so
   price direction nets out.
2. Wait for the price to move `CLOSE_AT_MOVE_PCT` from entry, either way.
3. **Close both legs.** The losing leg's realised loss mints PAPER; the winning leg
   covers it.
4. Repeat until a budget is spent.

## What this duty is, honestly

**It loses money on purpose, with nobody watching.** Whether that is worth doing
depends entirely on what PAPER is worth, and this duty cannot know that. So it does
not judge the trade — it enforces a budget, keeps the pair balanced, and stops the
moment anything stops making sense.

## The arithmetic that sets the leverage cap

A leg liquidates at `100 / LEVERAGE` percent, and **a leg cannot lose more than its
own margin** — so the PAPER a cycle can mint is capped at `rate × margin` at *any*
leverage. Leverage changes how fast a cycle completes, never how much it yields.

What it does change is the failure: a liquidated leg leaves the other one running
**unhedged**, which is the one state a delta-neutral pair exists to prevent. Hence
`LEVERAGE ≤ 25`, and `CLOSE_AT_MOVE_PCT` must sit at most halfway to the liquidation
distance — the duty refuses its own settings otherwise.

## Stopping

Three things stop it **for good**, each checked before a cycle is opened, never after:

| | |
| --- | --- |
| `MAX_TOTAL_LOSS_USD` | the whole budget; realised losses accumulate against it |
| `MAX_CYCLES` | a hard count |
| `MIN_PAPER_RATE` | the mint rate decays and has a cliff — a farm filed at one rate should not keep running at a worse one |

Two things stop it **for a fire**: an unbalanced pair, and a money command whose
outcome is unknown.

That second one is the important one. **A farm that re-opens after an uncertain fill
is a farm holding two longs** — not a hedge, but a directional bet the owner never
agreed to. So an unknown outcome stops the duty rather than retrying.

Likewise, if one leg opens and the other does not, the duty **unwinds the leg that
opened** rather than leaving it running.

## What it needs that does not exist yet

- **`acp papertrade open|close`** — the money command. Validates today, so this
  template is ready the day that primitive lands.
- **`bevo.read("/papertrade/state")`** returning `paperRatePerUsd` — without it the
  `MIN_PAPER_RATE` stop cannot fire, and the farm cannot tell when the deal has got
  worse. The duty degrades safely (it treats an unreadable rate as "no opinion"), but
  that stop is the one worth having.

Prices come from the existing `bevo.read("/token-price")`.
