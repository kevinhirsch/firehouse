"""Phase 0: the new proactive-feature privileges exist and are default-off."""

from core.auth import DEFAULT_PRIVILEGES, ADMIN_PRIVILEGES


def test_new_privileges_present_and_default_off():
    assert DEFAULT_PRIVILEGES.get("can_use_awareness") is False
    assert DEFAULT_PRIVILEGES.get("can_control_home") is False


def test_admins_get_the_new_privileges():
    # ADMIN_PRIVILEGES flips every boolean default to True.
    assert ADMIN_PRIVILEGES.get("can_use_awareness") is True
    assert ADMIN_PRIVILEGES.get("can_control_home") is True
