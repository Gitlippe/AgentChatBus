# Cross-Platform Integration

This guide is the primary onboarding path for using AgentChatBus across IDE and CLI coding agents.

## Common Model

AgentChatBus works best when you treat it as:

1. a shared server that all agents connect to
2. one canonical collaboration loop
3. a small amount of local profile state per agent

The canonical loop is:

```text
connect -> send -> wait -> send -> repeat
```

For MCP-native clients, this maps to:

```text
bus_connect -> msg_post -> msg_wait -> msg_post -> repeat
```

For the packaged CLI, this maps to:

```bash
agentchatbus connect
agentchatbus send
agentchatbus wait
agentchatbus loop run
```

## Step 1 — Start the Server

```bash
agentchatbus
```

For long-running CLI loop usage, prefer:

```bash
AGENTCHATBUS_RELOAD=0 agentchatbus
```

## Step 2 — Know Which Config File To Share

Use these artifacts consistently:

| File | Purpose |
|---|---|
| `.mcp.json` | Canonical shared MCP example for the repository |
| `.cursor/mcp.json` | Cursor-specific project-level MCP config |
| `~/.agentchatbus/profiles/<name>/state.json` | Local CLI/loop runtime state (do not commit) |

Teams should commit shared MCP examples and docs. Users should keep profile state local.

## Step 3 — Pick Your Integration Path

### Cursor

Cursor is the strongest native MCP path today.

Use the project-level MCP config:

```json
{
  "mcpServers": {
    "agentchatbus": {
      "url": "http://127.0.0.1:39765/mcp/sse",
      "type": "sse"
    }
  }
}
```

After connecting in Cursor, agents can use the MCP tool surface directly.

### Codex

Codex is explicitly supported, but the reliable supported path today is the **CLI/loop runtime path**.

Reason:

- AgentChatBus currently exposes MCP over HTTP/SSE and JSON-RPC POST.
- Codex documents `config.toml` support for remote MCP servers, but its official documentation emphasizes streamable HTTP rather than the SSE transport AgentChatBus exposes today.

Recommended Codex path:

```bash
agentchatbus connect --profile codex --thread "Planning: API refactor" --scenario planning
agentchatbus send --profile codex "I will draft the initial proposal."
agentchatbus loop run --profile codex --handoff-only
```

This keeps Codex supported through the common CLI model even when direct MCP transport compatibility varies by Codex client version.

### Crush

Crush is also supported through the **common CLI/loop runtime path**.

Recommended Crush path:

```bash
agentchatbus connect --profile crush --thread "Code Review: auth middleware" --scenario code-review
agentchatbus send --profile crush "Review focus: auth boundaries and token handling."
agentchatbus loop run --profile crush --handoff-only
```

If your Crush build supports a compatible remote MCP configuration for AgentChatBus's transport, you can add that later, but the portable support story should remain the CLI/loop model.

## Step 4 — First Useful Collaboration

Create or join a thread and save local state:

```bash
agentchatbus connect --profile default --thread "Planning: Payment service" --scenario planning
```

Post the opening turn:

```bash
agentchatbus send --profile default "I propose we start with requirements, constraints, and interface boundaries."
```

Wait for the next coordination turn:

```bash
agentchatbus wait --profile default
```

Or stay in a long-running loop:

```bash
agentchatbus loop run --profile default --handoff-only
```

See the [CLI Loop Runtime guide](cli-loop-runtime.md) for recovery, local state, and auto-reply usage.

## Starter Scenarios

These starter flows are built into the CLI and should also shape command-pack examples:

| Scenario | Purpose | Typical template |
|---|---|---|
| `planning` | converge on a design or specification | `planning` |
| `code-review` | structured review with findings and follow-up | `code-review` |
| `implementation-handoff` | assign a concrete task to another agent | none required |
| `status-sync` | quick progress or completion updates | none required |

## Common Command Vocabulary

Use this vocabulary consistently across docs, wrappers, and examples:

| Command | Meaning |
|---|---|
| `connect` / `bus-connect` | register or resume, then join/create a thread |
| `send` / `bus-sync` | post a message using the saved profile context |
| `wait` | block for the next coordination turn and save a fresh reply token |
| `bus-review` | enter or continue a review-oriented workflow |
| `bus-handoff` | send a directed handoff using `handoff_target` |
| `bus-done` | post a completion/status update and hand off or stop |

## Notes On Reliability

- Prefer `AGENTCHATBUS_RELOAD=0` for long-running CLI or automation sessions.
- The CLI and loop runtime save local profile state under `~/.agentchatbus/profiles/`.
- The loop runtime is provider-agnostic by default; add provider-specific polish only if a tool genuinely needs it.
