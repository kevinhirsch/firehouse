"""Entity store CRUD + owner isolation (Phase 1).

Skips when SQLAlchemy is only stubbed (see tests/conftest.py); runs in dev/CI
where the real dependency is installed. Points the store's SessionLocal at an
in-memory SQLite so it never touches a real workspace DB.
"""

import importlib.util

import pytest

if importlib.util.find_spec("sqlalchemy") is None:
    pytest.skip("sqlalchemy not installed", allow_module_level=True)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
import core.proactive_models  # noqa: F401  (register tables)
import src.entity_store as es


@pytest.fixture()
def store(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    # Redirect the store's session factory at the in-memory engine.
    monkeypatch.setattr(es, "SessionLocal", TestSession)
    return es.EntityStore()


def test_add_and_get_entity_with_fact(store):
    e = store.add_entity("alice", "Ryne", type="person")
    f = store.add_fact("alice", e["id"], "Ryne is Alice's boyfriend", category="relationship")
    assert f["confidence"] == 0.6667  # one positive obs on Beta(1,1) -> 2/(2+1) = 0.6667

    got = store.get_entity("alice", e["id"])
    assert got["name"] == "Ryne"
    assert len(got["facts"]) == 1
    assert got["facts"][0]["text"].startswith("Ryne")


def test_dedup_entity_by_name(store):
    a = store.add_entity("alice", "Ryne")
    b = store.add_entity("alice", "ryne")  # case-insensitive dup
    assert b.get("_deduped") is True
    assert b["id"] == a["id"]


def test_fact_reinforcement_raises_confidence(store):
    e = store.add_entity("alice", "Ryne")
    f1 = store.add_fact("alice", e["id"], "Ryne is the boyfriend of Alice")
    f2 = store.add_fact("alice", e["id"], "Ryne is Alice's boyfriend")  # near-dup -> reinforce
    assert f2.get("_reinforced") is True
    assert f2["confidence"] > f1["confidence"]
    # still one fact, not two
    assert len(store.get_entity("alice", e["id"])["facts"]) == 1


def test_owner_isolation(store):
    a = store.add_entity("alice", "Ryne")
    store.add_entity("bob", "Sam")
    assert [e["name"] for e in store.list_entities("alice")] == ["Ryne"]
    assert [e["name"] for e in store.list_entities("bob")] == ["Sam"]
    # bob cannot fetch alice's entity
    assert store.get_entity("bob", a["id"]) is None
    assert store.delete_entity("bob", a["id"]) is False


def test_relationship_requires_both_entities(store):
    a = store.add_entity("alice", "Ryne")
    b = store.add_entity("alice", "Alice", type="person")
    r = store.add_relationship("alice", a["id"], b["id"], "partner_of")
    assert r["type"] == "partner_of"
    assert store.add_relationship("alice", a["id"], "nonexistent", "x") is None


def test_recall_finds_by_name(store):
    e = store.add_entity("alice", "Ryne")
    store.add_fact("alice", e["id"], "likes hiking")
    hits = store.recall("alice", "Ryne", k=5)
    assert hits and hits[0]["name"] == "Ryne"
