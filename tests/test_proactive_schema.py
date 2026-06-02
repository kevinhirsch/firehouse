"""Phase 0: proactive-feature tables create cleanly and are owner-scopable.

Runs in an isolated subprocess (fresh interpreter) so the *real* SQLAlchemy
declarative models are built — the shared pytest session has sibling tests that
stub ``core.database`` in ``sys.modules``, which would corrupt ``Base`` here.
Skips when SQLAlchemy / app deps aren't installed.
"""

import os
import subprocess
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SCRIPT = r"""
import sys, uuid
try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.database import Base
    import core.proactive_models as pm
except ModuleNotFoundError as ex:
    print("SKIP", ex); sys.exit(0)

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(bind=engine)
s = sessionmaker(bind=engine)()

e = pm.Entity(id=str(uuid.uuid4()), owner="alice", type="person", name="Ryne")
s.add(e); s.flush()
s.add(pm.EntityFact(id=str(uuid.uuid4()), owner="alice", entity_id=e.id,
                    text="Ryne is Alice's boyfriend", category="relationship"))
s.commit()

f = s.query(pm.EntityFact).one()
assert f.alpha == 1.0 and f.beta == 1.0 and f.confidence == 0.5 and f.uses == 0

# owner isolation
s.add(pm.Entity(id=str(uuid.uuid4()), owner="bob", type="person", name="Sam"))
s.commit()
assert [r.name for r in s.query(pm.Entity).filter(pm.Entity.owner == "alice").all()] == ["Ryne"]
assert [r.name for r in s.query(pm.Entity).filter(pm.Entity.owner == "bob").all()] == ["Sam"]

# awareness trigger defaults
s.add(pm.AwarenessTrigger(id=str(uuid.uuid4()), owner="alice", name="Pre-event nudge"))
s.commit()
t = s.query(pm.AwarenessTrigger).one()
assert t.channel == "ntfy" and t.enabled is True and t.risk_tier == "low" and t.cooldown_seconds == 0
print("OK")
"""


def test_schema_and_owner_scope():
    p = subprocess.run([sys.executable, "-c", _SCRIPT], cwd=_ROOT,
                       capture_output=True, text=True)
    if "SKIP" in p.stdout:
        pytest.skip("deps not installed: " + p.stdout.strip())
    assert p.returncode == 0, (p.stdout + p.stderr)
    assert "OK" in p.stdout, (p.stdout + p.stderr)
