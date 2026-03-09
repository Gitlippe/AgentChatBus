from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


def _state_root() -> Path:
    return Path(os.environ.get("AGENTCHATBUS_PROFILE_ROOT", "~/.agentchatbus/profiles")).expanduser()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_profile_name(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(name).strip())
    cleaned = cleaned.strip("-_")
    return cleaned or "default"


@dataclass
class ProfileState:
    profile: str
    endpoint: str = "http://127.0.0.1:39765"
    agent_id: str | None = None
    token: str | None = None
    agent_name: str | None = None
    display_name: str | None = None
    ide: str | None = None
    model: str | None = None
    thread_id: str | None = None
    thread_name: str | None = None
    last_seq: int = 0
    last_reply_token: str | None = None
    for_agent: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        self.profile = _sanitize_profile_name(self.profile)
        if self.updated_at is None:
            self.updated_at = _utc_now()

    def touch(self) -> None:
        self.updated_at = _utc_now()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ProfileState":
        return cls(**data)


def profiles_dir() -> Path:
    root = _state_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def profile_dir(profile: str) -> Path:
    path = profiles_dir() / _sanitize_profile_name(profile)
    path.mkdir(parents=True, exist_ok=True)
    return path


def profile_path(profile: str) -> Path:
    return profile_dir(profile) / "state.json"


def load_profile(profile: str) -> ProfileState:
    path = profile_path(profile)
    if not path.exists():
        return ProfileState(profile=_sanitize_profile_name(profile))
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Profile state at {path} is not a JSON object")
    return ProfileState.from_dict(data)


def save_profile(state: ProfileState) -> Path:
    state.touch()
    path = profile_path(state.profile)
    path.write_text(json.dumps(state.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return path


def delete_profile(profile: str) -> bool:
    path = profile_dir(profile)
    state_file = path / "state.json"
    if not state_file.exists():
        return False
    state_file.unlink()
    try:
        path.rmdir()
    except OSError:
        pass
    return True
