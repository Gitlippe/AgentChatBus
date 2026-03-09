from pathlib import Path

from src import cli_state


def test_profile_state_uses_per_profile_directory(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AGENTCHATBUS_PROFILE_ROOT", str(tmp_path))

    state = cli_state.ProfileState(
        profile="demo-profile",
        endpoint="http://127.0.0.1:39765",
        agent_id="agent-123",
        token="token-123",
        thread_id="thread-123",
        last_seq=7,
    )
    saved_path = cli_state.save_profile(state)

    assert saved_path == tmp_path / "demo-profile" / "state.json"
    assert saved_path.exists()

    loaded = cli_state.load_profile("demo-profile")
    assert loaded.profile == "demo-profile"
    assert loaded.agent_id == "agent-123"
    assert loaded.thread_id == "thread-123"
    assert loaded.last_seq == 7


def test_profile_delete_removes_state_file(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AGENTCHATBUS_PROFILE_ROOT", str(tmp_path))

    state = cli_state.ProfileState(profile="to-delete", agent_id="agent-1")
    cli_state.save_profile(state)

    assert cli_state.delete_profile("to-delete") is True
    assert not (tmp_path / "to-delete" / "state.json").exists()
