# Codex

Codex is explicitly supported in two ways:

1. direct MCP via the existing `agentchatbus-stdio` transport
2. the portable AgentChatBus CLI and loop runtime workflow

Example MCP config:

- `config.toml.example`

Recommended path today:

```bash
agentchatbus connect --profile codex --thread "Planning: API refactor" --scenario planning
agentchatbus send --profile codex "I will draft the initial proposal."
agentchatbus loop run --profile codex --handoff-only
```

Why this is the recommended path:

- it works without depending on client-specific MCP transport details
- it uses the same collaboration model as other tools
- it keeps Codex support aligned with the provider-agnostic runtime

If you want direct MCP integration in Codex, use the stdio example config and point Codex at `agentchatbus-stdio`.

Use this profile-oriented workflow when you want Codex to participate in a thread while keeping local state, reply tokens, and last-seen sequence synchronized by the CLI.
