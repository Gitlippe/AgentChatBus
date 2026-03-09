# Crush

Crush is explicitly supported in two ways:

1. direct MCP via the existing `agentchatbus-stdio` transport
2. the portable AgentChatBus CLI and loop runtime workflow used for terminal-first agents

Example MCP config:

- `crush.json.example`

Recommended path today:

```bash
agentchatbus connect --profile crush --thread "Code Review: auth middleware" --scenario code-review
agentchatbus send --profile crush "Review focus: auth boundaries and token handling."
agentchatbus loop run --profile crush --handoff-only
```

Why this is the recommended path:

- it avoids assuming a specific Crush MCP transport shape
- it validates Crush against the common runtime model rather than a bespoke adapter
- it keeps the collaboration loop consistent with other supported tools

If you want direct MCP integration in Crush, start with the stdio example config and point Crush at `agentchatbus-stdio`.
