from modules.common.state import mark_sent, should_send


def test_should_send_with_cooldown() -> None:
    state: dict = {}
    key = "signal:test"

    assert should_send(key, "2026-02-16T10:00:00+01:00", 30, state)

    mark_sent(key, "2026-02-16T10:00:00+01:00", state)
    assert not should_send(key, "2026-02-16T10:10:00+01:00", 30, state)
    assert should_send(key, "2026-02-16T10:31:00+01:00", 30, state)
