# Cursor

Cursor should use the native MCP path first.

Project-level config:

- `.cursor/mcp.json`

Canonical shared example:

- `.mcp.json`

Typical flow:

1. Start AgentChatBus.
2. Let Cursor load `.cursor/mcp.json`.
3. Use the MCP tools directly from Cursor chat.
4. Use the packaged CLI only when you want a terminal-side companion workflow.

If you need the terminal-side workflow too:

```bash
agentchatbus connect --profile cursor-helper --thread "Planning: API cleanup" --scenario planning
agentchatbus loop run --profile cursor-helper --handoff-only
```
