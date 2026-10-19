# Farming PAPER

Papertrade mints PAPER to traders who **lose**. A farm leans on that on purpose: open a
long *and* a short of equal size on one market, let the price move, close both. Price
direction cancels out between the legs, the losing one mints, and the only money that
actually leaves is the fee on the winning close.

Not a separate venue or a separate key - the same account, the same session key, the same
helper as the rest of this skill.

## What a cycle costs, and why it is not the loss

The obvious reading is that farming costs the loss. It does not, because the pair is
held together:

```text
margin 500/leg, 10x, closed after a 0.5% move

  winning leg   +$25.00   less 2% of the gain      -$0.50
  losing leg    -$25.00   mints 2,500 PAPER
  ----------------------------------------------------------
  net cash      -$0.50    the legs cancel; the fee is what is real
```

**One cycle costs the fee, not the loss**, and mints on the whole move. Break-even is
therefore about **$0.0002 per PAPER** at these settings - the fee divided by the PAPER
minted - not the ~$0.01 that an *unhedged* loser needs.

Say that to the owner as the fee, in dollars. "It costs about 50 cents a cycle" is true
and understandable; "it loses $25" is not true of a hedged pair and will frighten them
off something they asked for.

## What makes it go wrong

**The pair stopping being a pair.** Everything that can actually hurt here is one leg
being open without the other:

- one leg opens and the other does not - a directional bet nobody agreed to
- one leg liquidates while the other runs on
- a close lands for one and not the other

So the duty below never opens unless the account is flat, unwinds a lone leg rather than
leaving it, and stops rather than retrying when it cannot tell what happened.

**Leverage is speed, not yield.** A leg cannot lose more than its own margin, so the
PAPER a cycle can mint is capped by the margin whatever the leverage. Higher leverage
only reaches a given move sooner - and brings `wipedOutAtMovePct` closer to the move the
farm is waiting for. Keep `CLOSE_AT_MOVE_PCT` well inside it: the duty refuses settings
where it is more than half.

## Filing one, from a chat

1. Run `SKILL.md` step 1, and check `sessionKey.action` is `ready`. A farm filed on a key
   that is not usable opens nothing.
2. Settle the numbers with the owner and say the fee per cycle, the budget, and that it
   runs unattended until the budget is spent.
3. Get the duty's helper path:

   ```sh
   python3 /tmp/papertrade.py duty-helper --owner <OWNER>
   ```

4. File it with a `timer` trigger (60 seconds), and its settings in `PARAMS`:
   `PAPERTRADE_HELPER`, `MARKET`, `MARGIN_USD`, `LEVERAGE`, `CLOSE_AT_MOVE_PCT`,
   `MAX_FEES_USD`, `MAX_CYCLES`.

`MAX_FEES_USD` is the whole budget and the only thing that stops an unattended farm on
its own. Set it with the owner, out loud.

## The duty

```python
import json
import os
import subprocess
import time

import bevo

PARAMS = json.loads(os.environ.get("PARAMS") or "{}")
INTENTS = "https://exchange.papertrade.xyz/intents"

MARKET = str(PARAMS.get("MARKET") or "BTC")
MARGIN_USD = float(PARAMS.get("MARGIN_USD") or 0)
LEVERAGE = float(PARAMS.get("LEVERAGE") or 10)
CLOSE_AT = float(PARAMS.get("CLOSE_AT_MOVE_PCT") or 0.5)
MAX_FEES_USD = float(PARAMS.get("MAX_FEES_USD") or 0)
MAX_CYCLES = int(PARAMS.get("MAX_CYCLES") or 100)

#: A leg is wiped out at 100/leverage percent. Waiting for a move anywhere near
#: that liquidates the losing leg and leaves the winner running alone, which is
#: the one thing a pair exists to prevent.
SAFETY = 0.5


def helper(*args):
    run = subprocess.run(["python3", PARAMS["PAPERTRADE_HELPER"], *args],
                         capture_output=True, text=True, timeout=120, check=False)
    if run.returncode != 0:
        bevo.log(f"papertrade {args[0]}: {run.stderr.strip()}")
        return None
    return json.loads(run.stdout)


def send(body_file):
    run = subprocess.run(["curl", "-sS", "-X", "POST", INTENTS, "-H", "Content-Type: application/json",
                          "--data", "@" + body_file, "-w", "\n%{http_code}"],
                         capture_output=True, text=True, timeout=60, check=False)
    lines = run.stdout.strip().splitlines()
    return (lines[-1] if lines else "no answer"), "\n".join(lines[:-1])


def stop(why):
    bevo.state["stopped"] = why
    bevo.done(f"Your PAPER farm has stopped: {why}.")


owner = bevo.read("/me")["user"]["agentWalletAddress"]

if MARGIN_USD <= 0 or MAX_FEES_USD <= 0:
    bevo.done("This farm needs MARGIN_USD and MAX_FEES_USD above zero before it can run.")
if CLOSE_AT >= (100.0 / LEVERAGE) * SAFETY:
    bevo.done(f"Closing at {CLOSE_AT}% is too near the {100.0 / LEVERAGE:.2f}% that wipes out a "
              f"leg at {LEVERAGE:g}x. Close earlier, or use less leverage.")

for tick in bevo.ticks():
    if bevo.state.get("stopped"):
        continue
    acct = helper("account", "--owner", owner)
    if acct is None:
        continue

    key = acct["sessionKey"]
    if key["action"] != "ready" and not bevo.state.get("told_key"):
        bevo.notify("Your Papertrade session key needs renewing. Ask me about Papertrade in a "
                    "chat to approve it; the farm is paused until then.", push="Renew Papertrade key")
        bevo.state["told_key"] = True
    if key["action"] not in ("ready", "renew"):
        continue
    bevo.state["told_key"] = False

    mine = [p for p in acct["positions"] if p["market"] == MARKET]
    fees = float(bevo.state.get("fees_usd") or 0)
    cycles = int(bevo.state.get("cycles") or 0)

    # --- nothing open: start a cycle, if it is still worth starting --------------
    if not mine:
        if fees >= MAX_FEES_USD:
            stop(f"the ${MAX_FEES_USD:,.2f} budget is spent after {cycles} cycles")
            continue
        if cycles >= MAX_CYCLES:
            stop(f"{MAX_CYCLES} cycles is the limit set")
            continue
        if acct["availableUsd"] < MARGIN_USD * 2:
            stop(f"only ${acct['availableUsd']:,.2f} is free and a pair needs "
                 f"${MARGIN_USD * 2:,.2f}")
            continue
        if time.time() - bevo.state.get("sent_at", 0) < 120:
            continue

        opened = []
        for side in ("long", "short"):
            built = helper("open", "--owner", owner, "--market", MARKET, "--side", side,
                           "--margin", f"{MARGIN_USD:.2f}", "--leverage", f"{LEVERAGE:g}")
            if built is None:
                break
            status, answer = send(built["bodyFile"])
            bevo.log(f"open {side}: {status} {answer}")
            if status != "201":
                break
            opened.append(side)
        bevo.state["sent_at"] = time.time()
        if len(opened) < 2:
            # One leg on its own is a directional bet. Say so; the next tick unwinds it.
            bevo.notify("Your PAPER farm could not open both sides, so it is unwinding and "
                        "stopping. Nothing is left running on purpose.",
                        push="PAPER farm stopped")
            bevo.state["unwind"] = True
        continue

    # --- a lone leg: unwind it, never leave it running ---------------------------
    if len(mine) == 1 or bevo.state.get("unwind"):
        built = helper("close", "--owner", owner, "--ids", ",".join(p["id"] for p in mine))
        if built is None:
            continue
        status, answer = send(built["bodyFile"])
        bevo.log(f"unwind: {status} {answer}")
        bevo.state["sent_at"] = time.time()
        if status == "201":
            stop("the pair came apart, so it closed what was left")
        continue

    # --- a pair is open: close both once the move is there -----------------------
    moved = max(abs(p.get("pnlUsdBeforeFees") or 0) for p in mine)
    target = MARGIN_USD * LEVERAGE * CLOSE_AT / 100.0
    if moved < target:
        continue
    if time.time() - bevo.state.get("sent_at", 0) < 120:
        continue

    built = helper("close", "--owner", owner, "--ids", ",".join(p["id"] for p in mine))
    if built is None:
        continue
    status, answer = send(built["bodyFile"])
    bevo.state["sent_at"] = time.time()
    bevo.log(f"close pair at {moved:,.2f}: {status} {answer}")
    if status != "201":
        continue

    # The legs cancel; what leaves is the fee on the winning close.
    cost = 0.02 * moved
    bevo.state["fees_usd"] = round(fees + cost, 4)
    bevo.state["cycles"] = cycles + 1
    bevo.notify(f"PAPER farm: cycle {cycles + 1} closed on a ${moved:,.2f} move, costing about "
                f"${cost:,.2f} in fees. ${bevo.state['fees_usd']:,.2f} of the "
                f"${MAX_FEES_USD:,.2f} budget used.")
```

Its settings: `PAPERTRADE_HELPER`, `MARKET`, `MARGIN_USD`, `LEVERAGE`,
`CLOSE_AT_MOVE_PCT`, `MAX_FEES_USD`, `MAX_CYCLES`.

## What it will not do

It never renews a key, funds the account, or withdraws - those need the owner, in a
chat, and the helper refuses them from a duty anyway. When the key lapses the farm
pauses and says so once, rather than opening half a pair it cannot close.
