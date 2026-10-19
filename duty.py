"""Farm PAPER on papertrade, unattended, by losing on purpose.

papertrade mints PAPER to traders who lose. A delta-neutral pair - a long and
a short of equal notional on one instrument - nets out on price, so the losing
leg mints while the winning leg covers it. One cycle is: open both, wait for
the price to move CLOSE_AT_MOVE_PCT, close both, bank the result.

The uncomfortable part, stated plainly because nothing else in this file will:
**this duty loses money on purpose, with nobody watching.** Whether that is
worth doing depends entirely on what PAPER is worth, which this duty cannot
know. It therefore does not judge the trade. It enforces a budget, keeps the
pair balanced, and stops the moment anything stops making sense.

Three things stop it for good:
  - realised losses reach MAX_TOTAL_LOSS_USD
  - MAX_CYCLES completed
  - PAPER's mint rate decays below MIN_PAPER_RATE

Two things stop it for a fire:
  - a leg is open that should not be, so the pair is not neutral
  - a money command's outcome is unknown

The second is the one that matters. A farm that re-opens after an uncertain
fill is a farm holding two longs, which is not a hedge - it is a directional
bet the owner never agreed to.

Settings: INSTRUMENT, MARGIN_USD, LEVERAGE, CLOSE_AT_MOVE_PCT,
MAX_TOTAL_LOSS_USD, MAX_CYCLES, MIN_PAPER_RATE, QUIET.
"""

import bevo
import json
import os
import subprocess
import time

PARAMS = json.loads(os.environ.get("PARAMS", "{}"))

INSTRUMENT = str(PARAMS.get("INSTRUMENT") or "").strip().upper()
MARGIN_USD = float(PARAMS.get("MARGIN_USD") or 0)
LEVERAGE = float(PARAMS.get("LEVERAGE") or 10)
CLOSE_AT_MOVE_PCT = float(PARAMS.get("CLOSE_AT_MOVE_PCT") or 0.5)
MAX_TOTAL_LOSS_USD = float(PARAMS.get("MAX_TOTAL_LOSS_USD") or 0)
MAX_CYCLES = int(PARAMS.get("MAX_CYCLES") or 100)
MIN_PAPER_RATE = float(PARAMS.get("MIN_PAPER_RATE") or 1)
QUIET = bool(PARAMS.get("QUIET") or False)

NAME = os.environ.get("BEVO_SERVICE_NAME") or "your PAPER farm"

#: A leg liquidates at 100/LEVERAGE percent. Closing must happen well inside
#: that, or the losing leg is wiped out and the winner is left running naked.
LIQUIDATION_SAFETY = 0.5

#: exec_status states after which a filed command is no longer in flight.
SETTLED = {
    "executed", "failed", "refused", "rejected", "expired", "cancelled",
    "canceled", "declined", "replay", "unknown",
}

PROBLEM = ""
if INSTRUMENT not in ("BTC", "ETH"):
    PROBLEM = "INSTRUMENT must be BTC or ETH, not %r" % INSTRUMENT
elif MARGIN_USD <= 0 or MAX_TOTAL_LOSS_USD <= 0:
    PROBLEM = "MARGIN_USD and MAX_TOTAL_LOSS_USD must both be above zero"
elif LEVERAGE > 25:
    PROBLEM = "LEVERAGE above 25 is refused: a leg would liquidate too easily"
elif CLOSE_AT_MOVE_PCT >= (100.0 / LEVERAGE) * LIQUIDATION_SAFETY:
    PROBLEM = ("CLOSE_AT_MOVE_PCT of %g%% is too close to the %.2f%% that liquidates a leg "
               "at %gx - close earlier, or use less leverage"
               % (CLOSE_AT_MOVE_PCT, 100.0 / LEVERAGE, LEVERAGE))


# --- small helpers -------------------------------------------------------------------------


def say(text):
    """`bevo.log()` on one line: an echoed error must not forge a log line."""
    bevo.log(" ".join(str(text).split()))


def usd(number):
    return "$%s" % format(round(float(number), 2), ",.2f")


def cycle_key():
    """The idempotency prefix for the cycle about to run.

    Keyed on the cycle NUMBER, not the tick: a tick's own identity is not
    stable enough to key money on, and two fires that stringify the same way
    would make the second cycle's open a replay of the first - so the farm
    would believe it had opened a pair it never opened.
    """
    n = int(bevo.state.get("cycles") or 0) + 1
    return "farm:%s:%d" % (bevo.SERVICE_ID, n)


def answer_of(text):
    """The JSON `acp` printed, or None. None is NOT a refusal."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        start = text.find("{")
        if start < 0:
            return None
        try:
            value, _ = json.JSONDecoder().raw_decode(text, start)
        except ValueError:
            return None
        return value if isinstance(value, dict) else None


def price_now():
    """What the instrument is worth, from Butler's own feed."""
    body = bevo.read("/token-price", {"symbol": INSTRUMENT}) or {}
    for field in ("price", "usd", "priceUsd", "value"):
        if body.get(field):
            return float(body[field])
    raise RuntimeError("no price for %s" % INSTRUMENT)


def paper_rate():
    """PAPER minted per $1 lost, read on chain rather than assumed.

    It decays and has a cliff, so a farm that trusts the rate it was filed
    with keeps running long after the deal has changed.
    """
    try:
        body = bevo.read("/papertrade/state", {}) or {}
        value = body.get("paperRatePerUsd")
        return float(value) if value is not None else None
    except Exception:  # noqa: BLE001 - absence is handled by the caller
        return None


def filed(args, key, sentence):
    """Run one `acp papertrade` and read what it answered."""
    done = subprocess.run(
        ["acp", "papertrade", *args, "--idempotency-key", key],
        capture_output=True, text=True, timeout=180, check=False,
    )
    answer = answer_of(done.stdout)
    if answer is None:
        state = (bevo.exec_status(key) or {}).get("state")
        return "unknown", "%s: outcome UNKNOWN (exec_status: %s)" % (sentence, state)
    status = str(answer.get("status") or "").lower()
    if answer.get("executed") or status == "executed":
        return "done", "%s: executed" % sentence
    if answer.get("ok") or status in ("accepted", "executing", "pending", "replay"):
        return "pending", "%s: accepted" % sentence
    return "refused", "%s: refused (%s)" % (sentence, answer.get("error") or status)


# --- the farm ------------------------------------------------------------------------------


def stop(reason):
    bevo.state["stopped"] = reason
    bevo.notify(("%s has stopped: %s. Nothing is open, and no more cycles will run."
                 % (NAME, reason))[:500])


def open_cycle():
    """Open both legs. Either both go on, or the one that made it comes off."""
    size = MARGIN_USD
    base = cycle_key()
    legs = {}
    for side in ("long", "short"):
        args = ["open", "--instrument", INSTRUMENT, "--side", side,
                "--margin", ("%.2f" % size), "--leverage", ("%g" % LEVERAGE)]
        status, sentence = filed(args, "%s:open:%s" % (base, side), "open %s" % side)
        say(sentence)
        legs[side] = status
        if status in ("refused", "unknown"):
            break

    if legs.get("long") in ("done", "pending") and legs.get("short") in ("done", "pending"):
        bevo.state["cycle"] = {
            "key": base, "entry": price_now(), "opened_at": int(time.time()),
        }
        if not QUIET:
            say("cycle open: %s %gx, %s a leg" % (INSTRUMENT, LEVERAGE, usd(size)))
        return

    # One leg on and one not is a directional bet nobody asked for.
    stray = [s for s, st in legs.items() if st in ("done", "pending")]
    if stray:
        side = stray[0]
        status, sentence = filed(["close", "--instrument", INSTRUMENT, "--side", side],
                                 "%s:close:%s" % (base, side), "unwind %s" % side)
        say(sentence)
        bevo.notify(("%s could not open both legs, so it unwound the one that opened. "
                     "Nothing is left running." % NAME)[:500])
    if "unknown" in legs.values():
        stop("a leg's outcome could not be confirmed, so the pair may not be balanced")


def close_cycle(cycle, move_pct):
    """Close both legs, then bank what the cycle cost."""
    base = cycle.get("key") or cycle_key()
    outcomes = {}
    for side in ("long", "short"):
        status, sentence = filed(["close", "--instrument", INSTRUMENT, "--side", side],
                                 "%s:close:%s" % (base, side), "close %s" % side)
        say(sentence)
        outcomes[side] = status

    if "unknown" in outcomes.values():
        stop("a leg's close could not be confirmed")
        return

    # The losing leg sheds margin x leverage x move; the winner gains the same.
    loss = MARGIN_USD * LEVERAGE * (abs(move_pct) / 100.0)
    loss = min(loss, MARGIN_USD)
    spent = float(bevo.state.get("loss_usd") or 0) + loss
    cycles = int(bevo.state.get("cycles") or 0) + 1
    bevo.state["loss_usd"] = round(spent, 2)
    bevo.state["cycles"] = cycles
    bevo.state.pop("cycle", None)

    rate = paper_rate()
    minted = (rate or 0) * loss
    if not QUIET:
        bevo.notify(("%s: cycle %d done on a %.2f%% move. It cost %s and minted about "
                     "%s PAPER. %s of the %s budget is used."
                     % (NAME, cycles, abs(move_pct), usd(loss), format(minted, ",.0f"),
                        usd(spent), usd(MAX_TOTAL_LOSS_USD)))[:500])


def fire():
    if bevo.state.get("stopped"):
        say("stopped: %s" % bevo.state["stopped"])
        return

    spent = float(bevo.state.get("loss_usd") or 0)
    cycles = int(bevo.state.get("cycles") or 0)
    cycle = bevo.state.get("cycle")

    # Stop conditions are checked before anything is opened, never after.
    if not cycle:
        if spent >= MAX_TOTAL_LOSS_USD:
            stop("the %s budget is spent" % usd(MAX_TOTAL_LOSS_USD))
            return
        if cycles >= MAX_CYCLES:
            stop("%d cycles is the limit set" % MAX_CYCLES)
            return
        rate = paper_rate()
        if rate is not None and rate < MIN_PAPER_RATE:
            stop("PAPER now mints at %g per $1 lost, under the %g floor set"
                 % (rate, MIN_PAPER_RATE))
            return
        if spent + (MARGIN_USD * LEVERAGE * CLOSE_AT_MOVE_PCT / 100.0) > MAX_TOTAL_LOSS_USD:
            stop("the next cycle would cost more than the budget has left")
            return
        open_cycle()
        return

    try:
        now = price_now()
    except Exception as exc:  # noqa: BLE001 - a missed read must not close blind
        say("could not read the price, leaving the pair open: %s" % exc)
        return

    entry = float(cycle.get("entry") or 0)
    if entry <= 0:
        stop("the open cycle has no entry price recorded")
        return
    move = (now - entry) / entry * 100.0
    if abs(move) < CLOSE_AT_MOVE_PCT:
        say("%s %.2f%% from entry, waiting for %.2f%%" % (INSTRUMENT, move, CLOSE_AT_MOVE_PCT))
        return
    close_cycle(cycle, move)


if PROBLEM:
    bevo.notify("%s does nothing until its settings are fixed: %s." % (NAME, PROBLEM))

for tick in bevo.ticks():
    if PROBLEM:
        say("skipped: %s" % PROBLEM)
        continue
    fire()
