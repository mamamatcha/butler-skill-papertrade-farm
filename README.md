# butler-skill-papertrade-farm

The `papertrade-farm` skill for [Butler](https://github.com/Virtual-Protocol/butler-skills).
For the humans maintaining this repo — never published to a butler. Only `SKILL.md`
and `references/**/*.md` reach one.

## What it does

Farms **PAPER**, the token Papertrade mints to traders who lose, by holding a long and
a short of equal size on one market and closing both after a set move. Price direction
cancels between the legs; the losing one mints.

## Why it is separate from `papertrade-xyz`

It declares `requires.skills: ["papertrade-xyz"]`, so the hub installs that skill
first and this one extracts **its** helper:

```sh
awk '/^```python$/{f=1;next} /^```$/{f=0} f' "$HOME/skills/papertrade-xyz/references/helper.md" > /tmp/papertrade.py
```

Nothing is duplicated — the account, session key, funding, registration and the
open/close calls all stay in `papertrade-xyz`. Same precedent as `butler-grabfood`
building on `butler-app-checkout`.

Keeping it separate also means farming ships on its own cadence, carries its own
risk conversation, and gets its own 12,000-character budget rather than squeezing
`papertrade-xyz`'s, which sits at 11,980 of its limit.

## The thing to get right

**A hedged cycle does not cost the loss.** The legs offset, so what leaves the account
is the 2% taken on the winning close:

```text
margin 500/leg, 10x, closed after a 0.5% move

  winning leg   +$25.00   less 2% of the gain      -$0.50
  losing leg    -$25.00   mints 2,500 PAPER
  ----------------------------------------------------------
  net cash      -$0.50    the legs cancel; the fee is what is real
```

Break-even is therefore about **$0.0002 a PAPER**, not the ~$0.01 an *unhedged* loser
needs. Saying "this loses $25 a cycle" is simply false of a hedged pair.

## What can actually go wrong

**One leg open without the other.** Everything else is ordinary. So the duty in
`references/farm.md` opens only from flat, unwinds a half-opened pair rather than
leaving it, stops rather than retrying when it cannot tell what landed, and refuses
settings where the close target is more than half the wipe-out distance.

**Leverage is speed, not yield** — a leg cannot lose more than its margin, so the
PAPER a cycle mints is capped by the margin whatever the leverage. Higher leverage
only brings the wipe-out closer to the move being waited for.

## Validating a change

```sh
curl -sSLO https://virtual-protocol.github.io/butler-skills/tools/validate.py
python3 validate.py --standalone .
```

`--all` additionally checks that `papertrade-xyz` is listed, since a skill cannot be
listed ahead of one it requires.

## Releasing

Bump `version` in `SKILL.md`, add the `CHANGELOG.md` entry, merge to `main`. Listing
is maintainer-only and needs two reviews for a money-moving skill — and
`papertrade-xyz` must be listed first.
