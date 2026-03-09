from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from typing import Any

import uvicorn

from src.cli_rest import BusClientError, BusRestClient
from src.cli_state import ProfileState, delete_profile, load_profile, profile_path, save_profile
from src.config import HOST, PORT, RELOAD_ENABLED


STARTER_SCENARIOS: dict[str, dict[str, str | None]] = {
    "planning": {
        "template": "planning",
        "next_step": "Post an initial plan proposal, then switch to `agentchatbus wait` or `agentchatbus loop run`.",
    },
    "code-review": {
        "template": "code-review",
        "next_step": "Post the review context, then wait for findings and follow-up discussion.",
    },
    "implementation-handoff": {
        "template": None,
        "next_step": "Send the handoff task with `--handoff-target` and then wait for the assignee's response.",
    },
    "status-sync": {
        "template": None,
        "next_step": "Send a short status update, then use `wait` for the next coordination event.",
    },
}


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _command_output(args: argparse.Namespace, payload: Any) -> None:
    if getattr(args, "json", False):
        _print_json(payload)
        return
    if isinstance(payload, str):
        print(payload)
    else:
        _print_json(payload)


def _serve(args: argparse.Namespace) -> None:
    uvicorn.run(
        "src.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
        timeout_graceful_shutdown=3,
    )


def _build_serve_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run AgentChatBus HTTP/SSE server")
    parser.add_argument("--host", default=HOST, help="Bind host")
    parser.add_argument("--port", type=int, default=PORT, help="Bind port")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    return parser


def _client_for_state(state: ProfileState) -> BusRestClient:
    return BusRestClient(endpoint=state.endpoint)


def _load_state_from_args(args: argparse.Namespace) -> ProfileState:
    state = load_profile(args.profile)
    endpoint = getattr(args, "endpoint", None)
    if endpoint:
        state.endpoint = endpoint.rstrip("/")
    return state


def _require_agent(state: ProfileState) -> None:
    if not state.agent_id or not state.token:
        raise BusClientError(
            "This profile has no registered agent yet. Run `agentchatbus connect --profile "
            f"{state.profile} --thread <topic>` first."
        )


def _require_thread(state: ProfileState, thread_id: str | None = None) -> str:
    resolved = thread_id or state.thread_id
    if not resolved:
        raise BusClientError(
            "No thread is associated with this profile. Run `agentchatbus connect --thread <topic>` "
            "or pass `--thread-id` explicitly."
        )
    return resolved


def _maybe_resume_or_register(state: ProfileState, args: argparse.Namespace) -> dict[str, Any]:
    client = _client_for_state(state)
    if not getattr(args, "fresh_agent", False) and state.agent_id and state.token:
        try:
            result = client.resume_agent(agent_id=state.agent_id, token=state.token)
            state.agent_id = result["agent_id"]
            state.agent_name = result.get("name")
            return result
        except BusClientError:
            # Fall through to re-register when the saved identity is invalid.
            pass

    registered = client.register_agent(
        ide=args.ide,
        model=args.model,
        description=args.description,
        display_name=args.display_name,
        capabilities=args.capability,
    )
    state.agent_id = registered["agent_id"]
    state.token = registered["token"]
    state.agent_name = registered.get("name")
    state.display_name = args.display_name or state.display_name
    state.ide = args.ide
    state.model = args.model
    return registered


def _thread_template_for_args(args: argparse.Namespace) -> str | None:
    if getattr(args, "template", None):
        return args.template
    if getattr(args, "scenario", None):
        scenario = STARTER_SCENARIOS.get(args.scenario)
        if scenario:
            return scenario.get("template")
    return None


def _sync_and_store(state: ProfileState) -> dict[str, Any]:
    _require_agent(state)
    thread_id = _require_thread(state)
    client = _client_for_state(state)
    sync = client.sync_context(thread_id=thread_id, agent_id=state.agent_id)
    state.last_seq = int(sync.get("current_seq", state.last_seq))
    state.last_reply_token = sync.get("reply_token")
    save_profile(state)
    return sync


def _format_messages(messages: list[dict[str, Any]]) -> str:
    if not messages:
        return "No new messages."
    lines: list[str] = []
    for message in messages:
        seq = message.get("seq", "?")
        author = message.get("author_name") or message.get("author") or "unknown"
        content = message.get("content") or ""
        lines.append(f"[{seq}] {author}: {content}")
    return "\n".join(lines)


def _emit_loop_event(args: argparse.Namespace, event: str, **fields: Any) -> None:
    if not getattr(args, "log_json", False):
        return
    payload = {"event": event, **fields}
    print(json.dumps(payload, sort_keys=True))


def _cmd_connect(args: argparse.Namespace) -> None:
    state = _load_state_from_args(args)
    client = _client_for_state(state)
    client.health()

    agent = _maybe_resume_or_register(state, args)

    payload: dict[str, Any] = {
        "profile": state.profile,
        "endpoint": state.endpoint,
        "agent": {
            "agent_id": state.agent_id,
            "name": state.agent_name or agent.get("name"),
        },
    }

    if args.thread:
        existing = client.find_thread_by_topic(args.thread)
        if existing is None:
            if args.no_create:
                raise BusClientError(f"Thread '{args.thread}' was not found and --no-create was set")
            created = client.create_thread(
                topic=args.thread,
                creator_agent_id=state.agent_id,
                token=state.token,
                template=_thread_template_for_args(args),
            )
            state.thread_id = created["id"]
            state.thread_name = created["topic"]
        else:
            state.thread_id = existing["id"]
            state.thread_name = existing["topic"]

        messages = client.list_messages(thread_id=state.thread_id, after_seq=0, limit=200)
        sync = _sync_and_store(state)
        payload["thread"] = {
            "thread_id": state.thread_id,
            "topic": state.thread_name,
            "template": _thread_template_for_args(args),
            "current_seq": sync["current_seq"],
        }
        payload["messages"] = messages
        if args.scenario:
            payload["scenario"] = {
                "name": args.scenario,
                "next_step": STARTER_SCENARIOS[args.scenario]["next_step"],
            }

    save_profile(state)

    if getattr(args, "json", False):
        _print_json(payload)
        return

    print(f"Profile: {state.profile}")
    print(f"Endpoint: {state.endpoint}")
    print(f"Agent: {payload['agent']['name']} ({payload['agent']['agent_id']})")
    if state.thread_id:
        print(f"Thread: {state.thread_name} ({state.thread_id})")
        print(f"Current seq: {state.last_seq}")
        if args.scenario:
            print(f"Starter flow: {args.scenario}")
            print(f"Next step: {STARTER_SCENARIOS[args.scenario]['next_step']}")
        print("Suggested commands:")
        print(f"  agentchatbus send --profile {state.profile} \"<message>\"")
        print(f"  agentchatbus wait --profile {state.profile}")
        print(f"  agentchatbus loop run --profile {state.profile}")
    else:
        print("No thread selected. Re-run with --thread <topic> to join or create a collaboration thread.")


def _cmd_resume(args: argparse.Namespace) -> None:
    state = _load_state_from_args(args)
    _require_agent(state)
    client = _client_for_state(state)
    resumed = client.resume_agent(agent_id=state.agent_id, token=state.token)
    state.agent_name = resumed.get("name", state.agent_name)
    save_profile(state)
    _command_output(
        args,
        {
            "profile": state.profile,
            "agent_id": state.agent_id,
            "name": state.agent_name,
            "is_online": resumed.get("is_online"),
            "endpoint": state.endpoint,
        },
    )


def _cmd_status(args: argparse.Namespace) -> None:
    state = _load_state_from_args(args)
    payload: dict[str, Any] = {
        "profile": state.profile,
        "state_file": str(profile_path(state.profile)),
        "endpoint": state.endpoint,
        "agent_id": state.agent_id,
        "agent_name": state.agent_name,
        "thread_id": state.thread_id,
        "thread_name": state.thread_name,
        "last_seq": state.last_seq,
        "has_reply_token": bool(state.last_reply_token),
    }
    if state.agent_id:
        try:
            payload["remote_agent"] = _client_for_state(state).get_agent(state.agent_id)
        except BusClientError as exc:
            payload["remote_agent_error"] = str(exc)
    _command_output(args, payload)


def _cmd_health(args: argparse.Namespace) -> None:
    state = _load_state_from_args(args)
    payload = _client_for_state(state).health()
    payload["endpoint"] = state.endpoint
    _command_output(args, payload)


def _cmd_unregister(args: argparse.Namespace) -> None:
    state = _load_state_from_args(args)
    _require_agent(state)
    payload = _client_for_state(state).unregister(agent_id=state.agent_id, token=state.token)
    state.last_reply_token = None
    save_profile(state)
    _command_output(
        args,
        {
            "profile": state.profile,
            "agent_id": state.agent_id,
            "endpoint": state.endpoint,
            "ok": payload.get("ok", False),
        },
    )


def _cmd_send(args: argparse.Namespace) -> None:
    state = _load_state_from_args(args)
    _require_agent(state)
    thread_id = _require_thread(state, args.thread_id)
    client = _client_for_state(state)

    if args.sync or not state.last_reply_token:
        _sync_and_store(state)

    metadata: dict[str, Any] = {}
    if args.handoff_target:
        metadata["handoff_target"] = args.handoff_target
    if args.stop_reason:
        metadata["stop_reason"] = args.stop_reason
    if not metadata:
        metadata = None

    result = client.post_message(
        thread_id=thread_id,
        author=state.agent_id,
        token=state.token,
        content=args.content,
        role=args.role,
        metadata=metadata,
        priority=args.priority,
        expected_last_seq=state.last_seq,
        reply_token=state.last_reply_token,
    )
    state.last_seq = int(result.get("seq", state.last_seq))
    state.last_reply_token = None
    save_profile(state)

    payload = {
        "profile": state.profile,
        "thread_id": thread_id,
        "seq": state.last_seq,
        "message_id": result.get("id"),
        "next_step": f"Run `agentchatbus wait --profile {state.profile}` to receive the next coordination turn.",
    }
    _command_output(args, payload)


def _cmd_wait(args: argparse.Namespace) -> None:
    state = _load_state_from_args(args)
    _require_agent(state)
    thread_id = _require_thread(state, args.thread_id)
    client = _client_for_state(state)
    target_agent = args.for_agent or state.for_agent or state.agent_id
    payload = client.wait_messages(
        thread_id=thread_id,
        after_seq=state.last_seq,
        agent_id=state.agent_id,
        token=state.token,
        timeout_ms=args.timeout_ms,
        for_agent=target_agent if args.handoff_only else args.for_agent,
    )
    state.last_seq = max(state.last_seq, int(payload.get("current_seq", state.last_seq)))
    state.last_reply_token = payload.get("reply_token")
    save_profile(state)

    if getattr(args, "json", False):
        _print_json(payload)
        return

    print(_format_messages(payload.get("messages", [])))
    if payload.get("reply_token"):
        print()
        print(f"Next reply token saved to profile '{state.profile}'.")


def _run_reply_command(command: str, payload: dict[str, Any], state: ProfileState) -> str:
    env = {
        **os.environ,
        "AGENTCHATBUS_PROFILE": state.profile,
        "AGENTCHATBUS_AGENT_ID": state.agent_id or "",
        "AGENTCHATBUS_THREAD_ID": state.thread_id or "",
    }
    proc = subprocess.run(
        shlex.split(command),
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        raise BusClientError(
            f"Reply command failed with exit code {proc.returncode}: {proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def _cmd_loop_run(args: argparse.Namespace) -> None:
    state = _load_state_from_args(args)
    _require_agent(state)
    thread_id = _require_thread(state, args.thread_id)
    client = _client_for_state(state)

    if RELOAD_ENABLED:
        print("Warning: AGENTCHATBUS_RELOAD is enabled. Long-running loop usage is more reliable with AGENTCHATBUS_RELOAD=0.")

    backoff_s = 1.0
    while True:
        try:
            _emit_loop_event(
                args,
                "wait_start",
                profile=state.profile,
                thread_id=thread_id,
                after_seq=state.last_seq,
                timeout_ms=args.timeout_ms,
            )
            payload = client.wait_messages(
                thread_id=thread_id,
                after_seq=state.last_seq,
                agent_id=state.agent_id,
                token=state.token,
                timeout_ms=args.timeout_ms,
                for_agent=state.agent_id if args.handoff_only else args.for_agent,
            )
            state.last_seq = max(state.last_seq, int(payload.get("current_seq", state.last_seq)))
            state.last_reply_token = payload.get("reply_token")
            save_profile(state)

            messages = payload.get("messages", [])
            if messages:
                _emit_loop_event(
                    args,
                    "messages_received",
                    profile=state.profile,
                    thread_id=thread_id,
                    count=len(messages),
                    current_seq=state.last_seq,
                )
                if args.json:
                    _print_json(payload)
                else:
                    print(_format_messages(messages))

                if args.reply_command:
                    reply = _run_reply_command(args.reply_command, payload, state)
                    if reply:
                        result = client.post_message(
                            thread_id=thread_id,
                            author=state.agent_id,
                            token=state.token,
                            content=reply,
                            role=args.role,
                            expected_last_seq=state.last_seq,
                            reply_token=state.last_reply_token,
                        )
                        state.last_seq = int(result.get("seq", state.last_seq))
                        state.last_reply_token = None
                        save_profile(state)
                        _emit_loop_event(
                            args,
                            "reply_posted",
                            profile=state.profile,
                            thread_id=thread_id,
                            seq=state.last_seq,
                        )
                        if not args.json:
                            print(f"[loop] posted seq {state.last_seq}")
            else:
                _emit_loop_event(
                    args,
                    "wait_timeout",
                    profile=state.profile,
                    thread_id=thread_id,
                    current_seq=state.last_seq,
                )

            if args.once:
                return

            backoff_s = 1.0
        except KeyboardInterrupt:
            if args.unregister_on_exit:
                try:
                    _emit_loop_event(args, "unregister_on_exit", profile=state.profile, thread_id=thread_id)
                    client.unregister(agent_id=state.agent_id, token=state.token)
                except BusClientError as exc:
                    print(f"Failed to unregister on exit: {exc}", file=sys.stderr)
            return
        except BusClientError as exc:
            _emit_loop_event(
                args,
                "loop_error",
                profile=state.profile,
                thread_id=thread_id,
                error=str(exc),
                retry_in_seconds=backoff_s,
            )
            print(f"[loop] {exc}", file=sys.stderr)
            time.sleep(backoff_s)
            backoff_s = min(backoff_s * 2.0, 10.0)


def _cmd_profile_clear(args: argparse.Namespace) -> None:
    deleted = delete_profile(args.profile)
    _command_output(args, {"profile": args.profile, "deleted": deleted})


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AgentChatBus CLI")
    subparsers = parser.add_subparsers(dest="command")

    serve = subparsers.add_parser("serve", help="Run the HTTP/SSE server")
    serve.add_argument("--host", default=HOST, help="Bind host")
    serve.add_argument("--port", type=int, default=PORT, help="Bind port")
    serve.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    serve.set_defaults(func=_serve)

    connect = subparsers.add_parser("connect", help="Register/resume an agent and optionally join or create a thread")
    connect.add_argument("--profile", default="default", help="Local profile name")
    connect.add_argument("--endpoint", default="http://127.0.0.1:39765", help="AgentChatBus base URL")
    connect.add_argument("--fresh-agent", action="store_true", help="Ignore saved agent identity and register a new one")
    connect.add_argument("--ide", default="CLI", help="Agent IDE/source label")
    connect.add_argument("--model", default="AgentChatBus CLI", help="Agent model label")
    connect.add_argument("--display-name", help="Human-friendly agent display name")
    connect.add_argument("--description", default="Registered via agentchatbus CLI", help="Agent description")
    connect.add_argument("--capability", action="append", default=[], help="Repeatable capability tag")
    connect.add_argument("--thread", help="Exact thread topic to join or create")
    connect.add_argument("--template", help="Template to apply when creating a new thread")
    connect.add_argument("--scenario", choices=sorted(STARTER_SCENARIOS.keys()), help="Starter scenario to guide next actions")
    connect.add_argument("--no-create", action="store_true", help="Do not create the thread if it does not already exist")
    connect.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    connect.set_defaults(func=_cmd_connect)

    resume = subparsers.add_parser("resume", help="Resume a saved agent profile")
    resume.add_argument("--profile", default="default", help="Local profile name")
    resume.add_argument("--endpoint", help="Override the saved base URL")
    resume.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    resume.set_defaults(func=_cmd_resume)

    status = subparsers.add_parser("status", help="Show local and remote status for a profile")
    status.add_argument("--profile", default="default", help="Local profile name")
    status.add_argument("--endpoint", help="Override the saved base URL")
    status.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    status.set_defaults(func=_cmd_status)

    health = subparsers.add_parser("health", help="Check server health")
    health.add_argument("--profile", default="default", help="Local profile name")
    health.add_argument("--endpoint", default="http://127.0.0.1:39765", help="AgentChatBus base URL")
    health.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    health.set_defaults(func=_cmd_health)

    unregister = subparsers.add_parser("unregister", help="Gracefully unregister the saved agent profile")
    unregister.add_argument("--profile", default="default", help="Local profile name")
    unregister.add_argument("--endpoint", help="Override the saved base URL")
    unregister.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    unregister.set_defaults(func=_cmd_unregister)

    send = subparsers.add_parser("send", help="Post a message using the saved profile")
    send.add_argument("--profile", default="default", help="Local profile name")
    send.add_argument("--endpoint", help="Override the saved base URL")
    send.add_argument("--thread-id", help="Override the saved thread id")
    send.add_argument("--role", default="assistant", help="Message role")
    send.add_argument("--priority", default="normal", help="Message priority")
    send.add_argument("--handoff-target", help="Set metadata.handoff_target")
    send.add_argument("--stop-reason", help="Set metadata.stop_reason")
    send.add_argument("--sync", action="store_true", help="Fetch a fresh sync context before posting")
    send.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    send.add_argument("content", help="Message content to post")
    send.set_defaults(func=_cmd_send)

    wait = subparsers.add_parser("wait", help="Wait for the next collaboration turn and save the reply token")
    wait.add_argument("--profile", default="default", help="Local profile name")
    wait.add_argument("--endpoint", help="Override the saved base URL")
    wait.add_argument("--thread-id", help="Override the saved thread id")
    wait.add_argument("--timeout-ms", type=int, default=300000, help="Wait timeout in milliseconds")
    wait.add_argument("--for-agent", help="Return only messages targeted at this agent id")
    wait.add_argument("--handoff-only", action="store_true", help="Filter for messages targeted at the saved agent id")
    wait.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    wait.set_defaults(func=_cmd_wait)

    loop = subparsers.add_parser("loop", help="Long-running collaboration commands")
    loop_subparsers = loop.add_subparsers(dest="loop_command")

    loop_run = loop_subparsers.add_parser("run", help="Continuously wait for new messages and optionally auto-reply")
    loop_run.add_argument("--profile", default="default", help="Local profile name")
    loop_run.add_argument("--endpoint", help="Override the saved base URL")
    loop_run.add_argument("--thread-id", help="Override the saved thread id")
    loop_run.add_argument("--timeout-ms", type=int, default=300000, help="Wait timeout in milliseconds")
    loop_run.add_argument("--for-agent", help="Return only messages targeted at this agent id")
    loop_run.add_argument("--handoff-only", action="store_true", help="Filter for messages targeted at the saved agent id")
    loop_run.add_argument("--reply-command", help="Shell command to generate a reply from the wait payload JSON on stdin")
    loop_run.add_argument("--role", default="assistant", help="Role to use when auto-posting reply-command output")
    loop_run.add_argument("--once", action="store_true", help="Process at most one wait cycle")
    loop_run.add_argument("--unregister-on-exit", action="store_true", help="Gracefully unregister when the loop exits")
    loop_run.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    loop_run.add_argument("--log-json", action="store_true", help="Emit structured loop events as JSON lines")
    loop_run.set_defaults(func=_cmd_loop_run)

    loop_clear = loop_subparsers.add_parser("clear-state", help="Delete the saved local state for a profile")
    loop_clear.add_argument("--profile", default="default", help="Local profile name")
    loop_clear.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    loop_clear.set_defaults(func=_cmd_profile_clear)

    return parser


def main() -> None:
    argv = sys.argv[1:]
    if not argv or argv[0].startswith("-"):
        args = _build_serve_parser().parse_args(argv)
        _serve(args)
        return

    parser = _build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return
    try:
        args.func(args)
    except BusClientError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
