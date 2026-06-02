"""Phase 0: proactive-feature tables create cleanly and are owner-scopable.

Skips when SQLAlchemy isn't really installed (the test conftest stubs it with
a MagicMock; building declarative models against the stub is meaningless), so
this runs in dev/CI where the real dependency is present.
"""

import importlib.util
import uuid

import pytest

if importlib.util.find_spec("sqlalchemy") is None:
    pytest.skip("sqlalchemy not installed", allow_module_level=True)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
import core.proactive_models as pm  # noqa: F401  (registers the tables on Base)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()


def _mk_entity(owner, name):
    return pm.Entity(id=str(uuid.uuid4()), owner=owner, type="person", name=name)


def test_entity_and_fact_roundtrip_with_defaults(db):
    e = _mk_entity("alice", "Ryne")
    db.add(e)
    db.flush()
    fact = pm.EntityFact(id=str(uuid.uuid4()), owner="alice", entity_id=e.id,
                         text="Ryne is Alice's boyfriend", category="relationship")
    db.add(fact)
    db.commit()

    got = db.query(pm.EntityFact).one()
    assert got.entity_id == e.id
    # Beta-confidence defaults present.
    assert got.alpha == 1.0 and got.beta == 1.0
    assert got.confidence == 0.5
    assert got.uses == 0


def test_owner_scoped_query_isolation(db):
    db.add_all([_mk_entity("alice", "Ryne"), _mk_entity("bob", "Sam")])
    db.commit()

    alice_rows = db.query(pm.Entity).filter(pm.Entity.owner == "alice").all()
    assert [r.name for r in alice_rows] == ["Ryne"]
    bob_rows = db.query(pm.Entity).filter(pm.Entity.owner == "bob").all()
    assert [r.name for r in bob_rows] == ["Sam"]


def test_awareness_trigger_defaults(db):
    t = pm.AwarenessTrigger(id=str(uuid.uuid4()), owner="alice", name="Pre-event nudge")
    db.add(t)
    db.commit()
    got = db.query(pm.AwarenessTrigger).one()
    assert got.channel == "ntfy"
    assert got.enabled is True
    assert got.risk_tier == "low"
    assert got.cooldown_seconds == 0
