"""Pure decision logic for the awareness loop (Phase 2).

No DB, LLM, network, or clock-reading side effects — every input is passed in —
so this is cheap and exhaustively unit-testable. The live loop composes these:

    tick(owner):
        signals  = collect(owner)                       # IO (later increment)
        digest   = snapshot_digest(signals)
        if should_resynthesize(prev_digest, digest):
            snapshot = synthesize(signals)              # LLM (later increment)
        for trigger in enabled_triggers(owner):
            if not cooldown_ok(trigger.last_fired_at, trigger.cooldown_seconds, now):
                continue
            verdict = evaluate_condition(trigger.condition, snapshot)
            if verdict == NEEDS_LLM:
                verdict = llm_judge(trigger, snapshot)  # LLM (later increment)
            if verdict == FIRE and rate_limit_ok(sent_today, limit):
                notify(...)                              # IO (later increment)

Standard library only.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

# Trigger verdicts.
FIRE = "fire"
SKIP = "skip"
NEEDS_LLM = "needs_llm"   # rule can't decide; escalate to an LLM judgment

_COMPARATORS = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "lt": lambda a, b: a is not None and a < b,
    "lte": lambda a, b: a is not None and a <= b,
    "gt": lambda a, b: a is not None and a > b,
    "gte": lambda a, b: a is not None and a >= b,
    "contains": lambda a, b: a is not None and b in a,
}


def evaluate_condition(condition: Optional[Dict[str, Any]], snapshot: Dict[str, Any]) -> str:
    """Evaluate a trigger ``condition`` against a ``snapshot`` of signal fields.

    Condition grammar (all keys optional; unknown shapes => NEEDS_LLM so a
    fuzzy/free-text trigger falls through to the LLM judge):

      {"field": "next_event_minutes", "op": "lte", "value": 30}
      {"field": "calendar_summary", "op": "exists"}
      {"all": [<cond>, ...]}   -> FIRE iff every sub-condition fires
      {"any": [<cond>, ...]}   -> FIRE iff any sub-condition fires
      {"fuzzy": "anything I should know before my next meeting?"} -> NEEDS_LLM
      None / {} / unrecognized -> NEEDS_LLM

    Returns FIRE, SKIP, or NEEDS_LLM. If any branch needs the LLM and no branch
    has already decided to FIRE, the result is NEEDS_LLM (so the caller escalates
    rather than silently skipping).
    """
    if not condition:
        return NEEDS_LLM
    if "fuzzy" in condition:
        return NEEDS_LLM

    if "all" in condition:
        subs = [evaluate_condition(c, snapshot) for c in condition["all"]]
        if any(s == SKIP for s in subs):
            return SKIP
        if any(s == NEEDS_LLM for s in subs):
            return NEEDS_LLM
        return FIRE

    if "any" in condition:
        subs = [evaluate_condition(c, snapshot) for c in condition["any"]]
        if any(s == FIRE for s in subs):
            return FIRE
        if any(s == NEEDS_LLM for s in subs):
            return NEEDS_LLM
        return SKIP

    field = condition.get("field")
    op = condition.get("op")
    if not field or not op:
        return NEEDS_LLM

    actual = snapshot.get(field)
    if op == "exists":
        return FIRE if actual is not None else SKIP

    comparator = _COMPARATORS.get(op)
    if comparator is None:
        return NEEDS_LLM
    try:
        return FIRE if comparator(actual, condition.get("value")) else SKIP
    except TypeError:
        # mismatched types (e.g. comparing None/str to a number) => can't decide
        return SKIP


def cooldown_ok(last_fired_at: Optional[datetime], cooldown_seconds: int,
                now: datetime) -> bool:
    """True if enough time has passed since the trigger last fired."""
    if not cooldown_seconds or last_fired_at is None:
        return True
    return now >= last_fired_at + timedelta(seconds=cooldown_seconds)


def rate_limit_ok(sent_in_window: int, max_in_window: int) -> bool:
    """True if another notification is allowed. ``max_in_window<=0`` = unlimited."""
    if max_in_window <= 0:
        return True
    return sent_in_window < max_in_window


def snapshot_digest(signals: Any) -> str:
    """Stable SHA-256 of the collected signals, for change detection.

    Order-independent for dict keys (``sort_keys``); ``default=str`` keeps it
    robust to datetimes and other non-JSON values.
    """
    blob = json.dumps(signals, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def should_resynthesize(prev_digest: Optional[str], new_digest: str) -> bool:
    """Re-run (expensive) snapshot synthesis only when the inputs changed."""
    return prev_digest != new_digest
