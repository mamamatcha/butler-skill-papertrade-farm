---
name: papertrade-farm
description: Farm PAPER on Papertrade by holding a long and a short of equal size, closing both after a move so the losing leg mints - a fee, not a bet on the market.
version: 0.2.0
metadata: {"butler":{"moneyMoving":true,"keywords":["farm paper","paper farm","papergainz","farm papertrade","mint paper","hedged farm","delta neutral","paper token","farm the airdrop","stop my farm"],"requires":{"bins":["python3","curl","awk","bevo-read","bevo-automation"],"skills":["papertrade-xyz"]}}}
---

## When to use

Your owner wants **PAPER**, the token Papertrade mints to traders who lose: "farm
PAPER", "run the papergainz thing", "how is my farm doing", "stop my farm".

A farm holds a **long and a short of equal size on one market**. Price direction
cancels between the legs, so the pair is not a bet on BTC or ETH. The losing leg
books a loss and mints PAPER; the winning leg covers it. What actually leaves the
account is the fee on the winning close.

This skill settles the numbers and files a duty that runs the cycles. The account,
the session key, the funding and the trading all belong to **`papertrade-xyz`** -
this skill never registers a key or funds anything, and sends the owner there when
either is needed.

Not this skill: a directional long or short (that is `papertrade-xyz`), staking the
PAPER once farmed, or any market Papertrade does not list.

## Before you start

1. **Say what a cycle costs, in dollars.** A losing close books its whole move; a
   winning one keeps about 84% of its own. That gap - roughly **17% of the move** at
   the default close size - is the cost, not the whole loss and not the 2% fee.
   `references/farm.md` has the measured table and the sentence to use.

2. **Say what it is not.** It is not yield and not a trade. It buys PAPER with fees,
   and whether that is a good buy depends on what PAPER is worth - which Butler has no
   way to tell them. Say that plainly rather than implying a return.

3. **The budget is the whole safety.** `MAX_FEES_USD` is what stops an unattended
   farm. Set it out loud with the owner, and say the farm runs without asking again
   until it is spent.

4. **The account has to be ready first.** The farm needs a usable session key and
   enough free USDC for **two** legs. Both are `papertrade-xyz`'s job.

## Procedure

1. [FIXED] Read the account through `papertrade-xyz`'s helper - the farm never ships
   its own:

   ```sh
   awk '/^```python$/{f=1;next} /^```$/{f=0} f' "$HOME/skills/papertrade-xyz/references/helper.md" > /tmp/papertrade.py
   bevo-read me
   python3 /tmp/papertrade.py account --owner <OWNER>
   python3 /tmp/papertrade.py markets
   ```

   `<OWNER>` is `user.agentWalletAddress` from `bevo-read me`.

2. [ADAPT] If `sessionKey.action` is not `ready`, or `availableUsd` is under twice the
   margin they want, stop and hand them to `papertrade-xyz` for that step. Do not file
   a farm that cannot open or cannot close.

3. [ADAPT] Settle the four numbers, and never choose them: market (`BTC` or `ETH`),
   margin per leg, leverage, and the move to close at. Quote one cycle from
   `references/farm.md`'s table, then say the fee and the budget:

   ```text
   $500 a leg at 10x, closing after a 0.3% move.
   Each cycle costs about $2.60 and mints about 162 PAPER.
   It stops when the cost reaches the $50 you set - roughly 19 cycles.
   $1,000 is tied up in the pair while each cycle runs.
   ```

4. [ADAPT] Get a yes to the **cost and the budget**, not to the idea: *"Happy to spend
   $50 to mint roughly 3,100 PAPER? That is worth it only if PAPER is above about
   1.6 cents to you."* A yes to farming is not a yes to a number.

5. [FIXED] Get the helper path the duty will run, and file the duty in
   `references/farm.md` with a `timer` trigger of 60 seconds:

   ```sh
   python3 /tmp/papertrade.py duty-helper --owner <OWNER>
   bevo-automation list
   ```

   Its settings are `PAPERTRADE_HELPER` (the path that printed), `MARKET`,
   `MARGIN_USD`, `LEVERAGE`, `CLOSE_AT_MOVE_PCT`, `MAX_FEES_USD` and `MAX_CYCLES`.
   **One farm per market** - a second one on the same market opens legs the first will
   try to close.

### Checking on a farm

```sh
bevo-automation show <FARM>
bevo-automation logs <FARM>
python3 /tmp/papertrade.py account --owner <OWNER>
```

Report cycles done, fees spent against the budget, and whether a pair is open right
now. PAPER minted per closed position is `paperMinted` in the account's history.

### Stopping a farm

```sh
bevo-automation disable <FARM>
```

Disabling stops new cycles. **It does not close an open pair** - say so, and offer to
close it through `papertrade-xyz`.

## Idempotency and retries

Reads are free; re-run them rather than reporting a figure from a minute ago.

File one duty per farm. If filing errors or you are unsure, run `bevo-automation list`
and look; **do not re-run it** - a retried money command can spend twice. Two farms on one market fight each other: the second
opens legs the first tries to close, and neither owner-visible number is then right.

The duty's own cycles are not idempotent either, which is why it waits two minutes
after sending anything and never re-sends a cycle it cannot confirm.

## Failure handling

| Outcome | What to do |
| --- | --- |
| `sessionKey.action` is not `ready` | Hand them to `papertrade-xyz` to register or renew. File nothing. |
| `availableUsd` under twice the margin | Say what a pair needs and what is free. Offer a smaller margin; never fund it here. |
| Owner wants leverage that puts the close target near the wipe-out | Refuse and say why: the losing leg would be liquidated and the winner left running alone. Offer less leverage or an earlier close. |
| Owner wants to close on a very small move | Say it costs more per PAPER, not less: under 0.1% the fixed part of the haircut more than doubles the cost. 0.3% is the default for that reason. |
| A farm already runs on that market | Say so and show it. Never file a second. |
| The duty reports it stopped | Read its reason out as given. Do not re-file without going through step 3 again. |
| Owner asks what PAPER is worth | Say Butler cannot tell them, and that the farm's cost is the fee either way. |

## Limits

- **BTC and ETH only**, whatever Papertrade lists.
- **One farm per market.**
- Buys PAPER with fees. It is not yield, and nothing here values PAPER or sells it.
- Never registers a session key, funds, or withdraws - all `papertrade-xyz`.
- Disabling a farm does not close an open pair.
- Not advice. Never choose the market, the margin, the leverage or the budget.

## Say to the owner

Lead with the fee, then the budget, then what is tied up:

"A farm holds a $5,000 long and a $5,000 short on BTC at the same time, so which way
BTC goes does not matter. Each cycle costs about **$2.60** and mints about **162
PAPER**. It stops when that reaches the **$50** you set. While a cycle runs, $1,000 of
yours is in the pair. It is worth doing only if PAPER is worth more than about **1.6
cents** to you - and I have no way to tell you whether it is."

When stopping: "Your farm is off - no new cycles. There is still a pair open; want me
to close it?"
