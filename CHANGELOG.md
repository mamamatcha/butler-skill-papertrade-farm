# Changelog

## 0.2.0

- **Corrected the economics against ~2,400 real closes.** A cycle does not cost the 2%
  fee: a losing close books its whole move while a winning one keeps a median 43%, and
  that gap is the cost. The 2% is exact but small.
- **The rate is 10.8 PAPER per $1 lost, not 100.** The protocol's own `rate` field
  reads 100; realised minting over 1,935 closes is a tenth of that. A farm sized on the
  advertised figure overstates itself ninefold.
- **Default close moved to 0.3%.** The haircut is mostly fixed per close, so small
  moves are taxed hardest: under 0.05% a winner keeps 39%, at 0.3% about 84%. Break-even
  is ~$0.016 a PAPER at the default, against ~$0.057 if churning tiny moves.
- The duty refuses a close target under 0.05%, and quotes cost and PAPER per cycle from
  the measured figures.

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
