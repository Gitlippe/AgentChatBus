# Crush

Crush is explicitly supported through the same portable AgentChatBus CLI and loop runtime workflow used for terminal-first agents.

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

If your Crush build supports a compatible remote MCP configuration for AgentChatBus's transport, you can add that later without changing the server-side collaboration model.
