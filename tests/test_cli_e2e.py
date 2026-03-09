import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import BASE_URL


def _run_cli(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["AGENTCHATBUS_PROFILE_ROOT"] = str(tmp_path / "profiles")
    cmd = [sys.executable, "-m", "agentchatbus.cli", *args]
    return subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)


@pytest.mark.integration
def test_cli_connect_send_wait_flow(server, tmp_path: Path):
    connect_a = _run_cli(
        tmp_path,
        "connect",
        "--endpoint",
        BASE_URL,
        "--profile",
        "plan-a",
        "--thread",
        "Planning: CLI e2e",
        "--scenario",
        "planning",
        "--json",
    )
    assert connect_a.returncode == 0, connect_a.stderr
    assert '"thread"' in connect_a.stdout

    connect_b = _run_cli(
        tmp_path,
        "connect",
        "--endpoint",
        BASE_URL,
        "--profile",
        "plan-b",
        "--thread",
        "Planning: CLI e2e",
        "--scenario",
        "planning",
        "--json",
    )
    assert connect_b.returncode == 0, connect_b.stderr

    send = _run_cli(
        tmp_path,
        "send",
        "--endpoint",
        BASE_URL,
        "--profile",
        "plan-a",
        "--json",
        "hello from cli e2e",
    )
    assert send.returncode == 0, send.stderr
    assert '"message_id"' in send.stdout

    wait = _run_cli(
        tmp_path,
        "wait",
        "--endpoint",
        BASE_URL,
        "--profile",
        "plan-b",
        "--timeout-ms",
        "1000",
        "--json",
    )
    assert wait.returncode == 0, wait.stderr
    assert "hello from cli e2e" in wait.stdout


@pytest.mark.integration
def test_cli_loop_once_and_unregister(server, tmp_path: Path):
    connect = _run_cli(
        tmp_path,
        "connect",
        "--endpoint",
        BASE_URL,
        "--profile",
        "loop-agent",
        "--thread",
        "Planning: loop e2e",
        "--scenario",
        "planning",
        "--json",
    )
    assert connect.returncode == 0, connect.stderr

    loop_once = _run_cli(
        tmp_path,
        "loop",
        "run",
        "--endpoint",
        BASE_URL,
        "--profile",
        "loop-agent",
        "--timeout-ms",
        "5",
        "--once",
        "--log-json",
    )
    assert loop_once.returncode == 0, loop_once.stderr
    assert '"event": "wait_timeout"' in loop_once.stdout

    unregister = _run_cli(
        tmp_path,
        "unregister",
        "--endpoint",
        BASE_URL,
        "--profile",
        "loop-agent",
        "--json",
    )
    assert unregister.returncode == 0, unregister.stderr
    assert '"ok": true' in unregister.stdout.lower()
