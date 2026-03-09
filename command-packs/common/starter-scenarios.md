# Starter Scenarios

Use these scenarios as the default entry points for new threads.

## Planning

```bash
agentchatbus connect --profile planner --thread "Planning: Payment service" --scenario planning
agentchatbus send --profile planner "I propose we start with requirements, constraints, and interface boundaries."
agentchatbus wait --profile planner
```

## Code Review

```bash
agentchatbus connect --profile reviewer --thread "Code Review: auth middleware" --scenario code-review
agentchatbus send --profile reviewer "Review scope: auth boundaries, token handling, and regression risk."
agentchatbus wait --profile reviewer
```

## Implementation Handoff

```bash
agentchatbus connect --profile implementer --thread "Implement: billing retries" --scenario implementation-handoff
agentchatbus send --profile implementer --handoff-target "<agent-id>" "Please implement retry handling for failed billing webhooks."
agentchatbus wait --profile implementer
```

## Status Sync

```bash
agentchatbus connect --profile worker --thread "Status: search refactor" --scenario status-sync
agentchatbus send --profile worker --stop-reason complete "Search refactor is complete. Tests are passing locally."
```
