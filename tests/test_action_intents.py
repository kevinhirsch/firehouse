from src.action_intents import message_needs_tools, auto_escalation_disabled_tools


# --- shell-access regression (transcript bug) -------------------------------

def test_transcript_messages_auto_escalate():
    # Both messages from the bug report match the tool-intent patterns.
    assert message_needs_tools("can you run shell?")
    assert message_needs_tools("Can you see what environment you're running in?")


def test_auto_escalation_withholds_shell_by_default():
    disabled = auto_escalation_disabled_tools(allow_bash=False)
    assert {"bash", "python", "read_file", "write_file", "builtin_browser"} <= disabled


def test_auto_escalation_respects_explicit_shell_toggle():
    # The bug: explicit Shell Access (allow_bash=true) was overridden by
    # auto-escalation, so bash never reached the agent. It must NOT be disabled.
    disabled = auto_escalation_disabled_tools(allow_bash=True)
    assert "bash" not in disabled
    assert "python" not in disabled
    assert "read_file" not in disabled and "write_file" not in disabled
    # the browser is still withheld (separate concern / no explicit toggle here)
    assert "builtin_browser" in disabled


def test_calendar_entry_request_promotes_to_agent():
    assert message_needs_tools("Can you add an entry to my calendar?")


def test_calendar_imperative_variants_promote_to_agent():
    assert message_needs_tools("add lunch with Sam to my calendar tomorrow at noon")
    assert message_needs_tools("schedule a call with Mina next Friday")
    assert message_needs_tools("put dentist appointment on my calendar")


def test_note_todo_and_reminder_actions_promote_to_agent():
    assert message_needs_tools("add milk to my todo list")
    assert message_needs_tools("take a note that the server needs checking")
    assert message_needs_tools("set a reminder to call Pat at 4pm")


def test_email_and_ui_actions_promote_to_agent():
    assert message_needs_tools("reply to that email")
    assert message_needs_tools("mark those emails as read")
    assert message_needs_tools("open my calendar")
    assert message_needs_tools("turn off web search")


def test_research_action_promotes_to_agent():
    assert message_needs_tools("research cost effective local models")
    assert message_needs_tools("can you look into GPU hosting options")


def test_explanatory_calendar_questions_stay_plain_chat():
    assert not message_needs_tools("How do I add an entry to my calendar?")
    assert not message_needs_tools("What about the built-in Firehouse calendar, is that linked to email?")
    assert not message_needs_tools("Can you explain how calendar reminders work?")
