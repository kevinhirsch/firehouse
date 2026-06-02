"""Pure awareness-engine logic (Phase 2). No app deps — runs everywhere."""

from datetime import datetime, timedelta

from services.awareness import engine as e


# ---- evaluate_condition ----------------------------------------------------

def test_field_comparisons():
    snap = {"next_event_minutes": 25, "unread": 0, "summary": "Standup"}
    assert e.evaluate_condition({"field": "next_event_minutes", "op": "lte", "value": 30}, snap) == e.FIRE
    assert e.evaluate_condition({"field": "next_event_minutes", "op": "gt", "value": 30}, snap) == e.SKIP
    assert e.evaluate_condition({"field": "summary", "op": "exists"}, snap) == e.FIRE
    assert e.evaluate_condition({"field": "missing", "op": "exists"}, snap) == e.SKIP
    assert e.evaluate_condition({"field": "summary", "op": "contains", "value": "Stand"}, snap) == e.FIRE


def test_all_and_any():
    snap = {"a": 5, "b": 1}
    assert e.evaluate_condition({"all": [
        {"field": "a", "op": "gte", "value": 5},
        {"field": "b", "op": "eq", "value": 1},
    ]}, snap) == e.FIRE
    assert e.evaluate_condition({"all": [
        {"field": "a", "op": "gte", "value": 5},
        {"field": "b", "op": "eq", "value": 99},
    ]}, snap) == e.SKIP
    assert e.evaluate_condition({"any": [
        {"field": "a", "op": "eq", "value": 0},
        {"field": "b", "op": "eq", "value": 1},
    ]}, snap) == e.FIRE


def test_fuzzy_and_empty_need_llm():
    assert e.evaluate_condition(None, {}) == e.NEEDS_LLM
    assert e.evaluate_condition({}, {}) == e.NEEDS_LLM
    assert e.evaluate_condition({"fuzzy": "anything urgent?"}, {}) == e.NEEDS_LLM
    # unknown operator can't be decided by rules
    assert e.evaluate_condition({"field": "a", "op": "weird", "value": 1}, {"a": 1}) == e.NEEDS_LLM


def test_all_with_llm_branch_escalates_not_skips():
    snap = {"a": 5}
    v = e.evaluate_condition({"all": [
        {"field": "a", "op": "gte", "value": 5},  # FIRE
        {"fuzzy": "and is it important?"},          # NEEDS_LLM
    ]}, snap)
    assert v == e.NEEDS_LLM


def test_type_mismatch_is_skip_not_crash():
    # comparing a string field to a number must not raise
    assert e.evaluate_condition({"field": "s", "op": "gt", "value": 3}, {"s": "x"}) == e.SKIP
    assert e.evaluate_condition({"field": "s", "op": "lt", "value": 3}, {"s": None}) == e.SKIP


# ---- cooldown / rate-limit -------------------------------------------------

def test_cooldown():
    now = datetime(2026, 6, 2, 12, 0, 0)
    assert e.cooldown_ok(None, 3600, now) is True            # never fired
    assert e.cooldown_ok(now - timedelta(minutes=30), 0, now) is True   # no cooldown set
    assert e.cooldown_ok(now - timedelta(minutes=30), 3600, now) is False
    assert e.cooldown_ok(now - timedelta(minutes=90), 3600, now) is True


def test_rate_limit():
    assert e.rate_limit_ok(0, 0) is True       # 0 = unlimited
    assert e.rate_limit_ok(99, 0) is True
    assert e.rate_limit_ok(2, 5) is True
    assert e.rate_limit_ok(5, 5) is False
    assert e.rate_limit_ok(6, 5) is False


# ---- change detection ------------------------------------------------------

def test_digest_is_stable_and_order_independent():
    a = {"x": 1, "y": [1, 2], "z": "hi"}
    b = {"z": "hi", "y": [1, 2], "x": 1}
    assert e.snapshot_digest(a) == e.snapshot_digest(b)


def test_digest_changes_with_content():
    assert e.snapshot_digest({"x": 1}) != e.snapshot_digest({"x": 2})


def test_digest_handles_datetimes():
    # default=str keeps non-JSON values from blowing up
    d = e.snapshot_digest({"when": datetime(2026, 6, 2)})
    assert isinstance(d, str) and len(d) == 64


def test_should_resynthesize():
    assert e.should_resynthesize(None, "abc") is True
    assert e.should_resynthesize("abc", "abc") is False
    assert e.should_resynthesize("abc", "xyz") is True
