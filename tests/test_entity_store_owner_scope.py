"""Entity store CRUD + owner isolation (Phase 1).

Runs in an isolated subprocess so the real store + SQLAlchemy models are
exercised against an in-memory SQLite, immune to the shared session's
``core.database`` stubbing. Skips when app deps aren't installed.
"""

import os
import subprocess
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SCRIPT = r"""
import sys
try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.database import Base
    import core.proactive_models  # noqa: F401  (register tables)
    import src.entity_store as es
except ModuleNotFoundError as ex:
    print("SKIP", ex); sys.exit(0)

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(bind=engine)
es.SessionLocal = sessionmaker(bind=engine)
store = es.EntityStore()

# add entity + fact; one positive obs on Beta(1,1) -> 2/3
e = store.add_entity("alice", "Ryne", type="person")
f = store.add_fact("alice", e["id"], "Ryne is Alice's boyfriend", category="relationship")
assert f["confidence"] == 0.6667, f

# case-insensitive dedup
dup = store.add_entity("alice", "ryne")
assert dup.get("_deduped") is True and dup["id"] == e["id"]

# near-duplicate fact reinforces (raises confidence), stays one fact
f2 = store.add_fact("alice", e["id"], "Ryne is the boyfriend of Alice")
assert f2.get("_reinforced") is True and f2["confidence"] > f["confidence"]
assert len(store.get_entity("alice", e["id"])["facts"]) == 1

# owner isolation
store.add_entity("bob", "Sam")
assert [x["name"] for x in store.list_entities("alice")] == ["Ryne"]
assert [x["name"] for x in store.list_entities("bob")] == ["Sam"]
assert store.get_entity("bob", e["id"]) is None
assert store.delete_entity("bob", e["id"]) is False

# relationships require both entities to exist (and be owned)
b = store.add_entity("alice", "Alice", type="person")
r = store.add_relationship("alice", e["id"], b["id"], "partner_of")
assert r["type"] == "partner_of"
assert store.add_relationship("alice", e["id"], "nonexistent", "x") is None

# recall finds by name
assert store.recall("alice", "Ryne", k=5)[0]["name"] == "Ryne"
print("OK")
"""


def test_entity_store_crud_and_isolation():
    p = subprocess.run([sys.executable, "-c", _SCRIPT], cwd=_ROOT,
                       capture_output=True, text=True)
    if "SKIP" in p.stdout:
        pytest.skip("deps not installed: " + p.stdout.strip())
    assert p.returncode == 0, (p.stdout + p.stderr)
    assert "OK" in p.stdout, (p.stdout + p.stderr)
