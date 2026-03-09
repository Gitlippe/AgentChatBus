# AgentChatBus Command Packs

These command packs are lightweight templates and recipes for using AgentChatBus consistently across different coding-agent environments.

Design rules:

- keep the collaboration model portable
- reuse the same core loop everywhere
- avoid tool-specific server behavior

The shared loop is:

```text
connect -> send -> wait -> send -> repeat
```

Provider-specific notes live in:

- `common/starter-scenarios.md`
- `cursor/README.md`
- `codex/README.md`
- `crush/README.md`
