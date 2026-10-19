# Changelog

## 0.1.0

- First release. Farms PAPER with a delta-neutral pair: a long and a short of equal
  size on one market, closed together once the move is there, repeated to a fee
  budget by a duty.
- **Builds on `papertrade-xyz`** rather than duplicating it (`requires.skills`). The
  account, session key, funding and trading all stay there; this skill extracts that
  skill's helper and never ships its own.
- Says the cost as the **fee**, not the loss. The legs cancel, so a cycle costs about
  2% of the move — break-even is near $0.0002 a PAPER, not the ~$0.01 an unhedged
  loser needs. Quoting the loss would put an owner off something they asked for.
- `MAX_FEES_USD` is the only thing that stops an unattended farm, so it is set out
  loud with the owner and the yes is to the number, not the idea.
- One farm per market: a second fights the first, opening legs it tries to close.
- Refuses a close target near the wipe-out distance — a liquidated leg leaves the
  other running alone.
