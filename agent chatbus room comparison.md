# AgentChatBus vs room

Sources compared:

- `AgentChatBus` repository documentation in this workspace
- [`knoxio/room`](https://github.com/knoxio/room)

## Highest-Value room Features Not Present In AgentChatBus

Ordered by likely practical value, based on the currently documented feature sets.

1. **Native terminal multi-user chat UI**: `room` ships a full-screen TUI for humans, while AgentChatBus is centered on MCP clients and a browser-based web console rather than a terminal-first collaborative interface.
2. **One-shot CLI workflow for non-MCP agents**: `room join`, `room send`, `room poll`, and `room watch` are designed as simple stateless commands for agents that cannot hold a persistent protocol session. AgentChatBus instead expects MCP/HTTP integrations and long-poll style coordination through `msg_wait`.
3. **Built-in direct messages**: `room` supports private `dm` messages to a specific user. AgentChatBus documents thread-based shared discussion plus targeted handoff metadata, but not first-class private message delivery.
4. **Slash-command chat operations inside the terminal UI**: `room` exposes `/claim`, `/set_status`, `/who`, `/dm`, and other command-style interactions directly in the chat experience. AgentChatBus exposes comparable coordination primitives as MCP tools and REST endpoints, not as an in-chat slash command UX.
5. **Terminal-admin controls for live rooms**: `room` documents `/kick`, `/reauth`, `/clear-tokens`, `/exit`, and `/clear` inside the TUI. AgentChatBus has administrative and lifecycle operations, but not the same documented live room moderation model in-chat.
6. **Autonomous wrapper focused on Claude Code-style loops**: `room-ralph` and the repo's plugin story explicitly target agent restart/poll/send loops. AgentChatBus supports multi-agent IDE integration, but does not document an equivalent built-in autonomous wrapper binary.
7. **Auto-start broker behavior**: `room` can start the broker automatically when the first client joins a room. AgentChatBus uses an explicit server process model.

## Overview Table

| Capability Area | AgentChatBus | room | Main Contrast |
|---|---|---|---|
| Primary purpose | Persistent AI communication bus for multi-agent collaboration across IDEs/frameworks | Multi-user Unix chat room for humans and agents | Same broad problem space, different center of gravity |
| Core transport | HTTP + SSE MCP server, plus JSON-RPC POST and REST | Unix domain socket broker plus NDJSON file history | AgentChatBus is protocol/server-oriented; room is local-IPC/CLI-oriented |
| Client model | MCP-compatible IDEs/agents, browser web console, REST integrations | Terminal UI, one-shot CLI commands, agent mode, wrapper tools | AgentChatBus optimizes interoperability; room optimizes terminal workflows |
| Standards alignment | Explicit MCP support, MCP Tools/Resources/Prompts, A2A-ready design | Custom CLI/wire protocol; Claude/agent integration via repo plugin and wrapper | AgentChatBus aims for standards-based ecosystem fit |
| Human interface | Built-in web console | Full-screen TUI | Browser-first vs terminal-first |
| Conversation model | Structured threads with lifecycle states | Chat rooms with message stream | Threaded workflow vs room-centric chat |
| Presence model | Agent registry, capabilities, skills, heartbeat, resume, typing | Username sessions, online status, status strings | AgentChatBus models agent identity more richly |
| Message waiting | `msg_wait` with seq cursor and sync tokens | `poll` / `watch` with cursor files | Different consistency and polling strategies |
| Directed work | `handoff_target`, `stop_reason`, templates | Commands like `/claim`; DMs; human conventions | AgentChatBus formalizes delegation in metadata |
| Search | Full-text message search | Not documented as a first-class feature | AgentChatBus includes retrieval/search tooling |
| Edit history | Message edit + version history | Not documented | AgentChatBus supports auditable edits |
| Reactions | Yes | Not documented | AgentChatBus has richer message semantics |
| Attachments/images | Yes via metadata and upload API | Not documented | AgentChatBus is more multimodal |
| Templates/prompts | Thread templates plus MCP prompts | No equivalent documented | AgentChatBus supports structured workflow bootstrapping |
| Read-only resources | MCP resources for transcripts, summaries, state, config | No equivalent documented | AgentChatBus supports agent onboarding via resources |
| Safety/governance | Content filtering, rate limiting, thread timeout, admin token | Token/session management and TUI admin commands | AgentChatBus focuses on policy/safety controls; room focuses on operator control |
| Deployment style | Explicit long-running server on localhost/LAN | Broker auto-started by first participant on Unix system | Server service vs lightweight room broker |
| Storage | SQLite database | NDJSON append-only history file plus token/cursor files | Database-backed structured state vs file-backed simplicity |

## Flash Data Report

### 1. Are They Solving The Same Problem?

**Partially yes.**

Both projects are trying to make **multi-agent or human-plus-agent coordination persistent and operationally useful**.

They overlap on:

- persistent shared conversation history
- multiple participants
- agent coordination workflows
- resumable collaboration over time
- suitability for autonomous or semi-autonomous agent loops

But they are **not identical products**.

- **room** is a **Unix-native collaborative chat tool** whose design center is "a shared room that humans and agents can join quickly from the terminal."
- **AgentChatBus** is a **protocol-centric agent communication server** whose design center is "a standards-aligned bus that IDE agents and other clients can connect to through MCP/HTTP."

Short version:

- `room` feels like a **chat room product that agents can use**
- `AgentChatBus` feels like an **agent bus product that humans can observe/use**

### 2. Architectural Contrast

#### AgentChatBus

- Runs as a **single explicit server process**.
- Exposes **MCP over HTTP/SSE** and **JSON-RPC POST**.
- Includes a **REST API** and **built-in web console**.
- Stores structured state in **SQLite**.
- Models first-class entities such as **threads**, **agents**, **messages**, **templates**, **resources**, and **prompts**.

#### room

- Uses a **broker over a Unix domain socket**.
- Persists history to an **NDJSON chat file**.
- Uses additional local files for **tokens** and **cursors**.
- Has a **full-screen TUI** as the main human interface.
- Provides **one-shot commands** and an **agent mode** for automation.

#### Design decision delta

- AgentChatBus chooses **structured service APIs and interoperability**.
- room chooses **local simplicity, terminal ergonomics, and composable CLI primitives**.

### 3. Conversation Model Difference

#### AgentChatBus

Conversation is organized around **threads** with explicit state transitions:

- `discuss`
- `implement`
- `review`
- `done`
- `closed`
- `archived`

This makes it suitable for workflows where discussion, implementation, review, and closure are distinct phases.

#### room

Conversation is organized around **rooms** with a shared event stream:

- users join
- send chat messages
- run commands
- poll/watch for new items

This is closer to a traditional shared chat substrate, even though it supports agent workflows.

#### Design decision delta

- AgentChatBus treats collaboration as **task/thread lifecycle management**.
- room treats collaboration as **room presence plus message flow**.

### 4. Coordination Semantics

#### AgentChatBus strengths

- Explicit **agent registration**
- **heartbeat** and **resume**
- structured **capabilities** and **skills**
- `handoff_target` metadata for delegation
- `stop_reason` metadata for convergence signaling
- `bus_connect` for register + join/create in one step
- `msg_wait` with seq-based sync and reply tokens

#### room strengths

- Simple **join/send/poll/watch** mental model
- explicit **direct message** support
- command-style coordination such as `/claim`
- user-facing `/who` and `/set_status`
- easy shell composition for autonomous loops

#### Design decision delta

- AgentChatBus encodes coordination as **machine-readable protocol state**.
- room encodes coordination as **operational commands and user conventions**.

### 5. Human Experience Contrast

#### AgentChatBus

- Browser dashboard
- thread list and monitoring
- search and participation through web UI
- good fit for teams using IDE MCP clients

#### room

- TUI-first
- strong terminal-native experience
- likely lower ceremony for local, same-machine, developer-terminal collaboration

#### Design decision delta

- AgentChatBus emphasizes **observability and IDE integration**.
- room emphasizes **fast human interaction in the terminal**.

### 6. Feature Areas Where AgentChatBus Is Richer

These are major documented capabilities in AgentChatBus that are not documented for room:

1. **Standards-compliant MCP surface**
   - MCP tools
   - MCP resources
   - MCP prompts
   - SSE transport and MCP POST endpoint
2. **REST API for programmatic integration**
3. **Web console**
4. **Structured thread lifecycle**
5. **Thread templates**
6. **Full-text search across messages**
7. **Message editing with version history**
8. **Reactions**
9. **Image attachments and upload API**
10. **Agent metadata model**
    - capabilities
    - structured skills
    - display names
    - resume semantics
    - typing signals
11. **Read-only resource model**
    - transcript
    - summary
    - state snapshot
    - active agents
12. **Prompt-generation model**
13. **Content filtering**
14. **Rate limiting**
15. **Thread timeout / auto-close support**
16. **A2A-oriented design posture**

### 7. Feature Areas Where room Is Richer

These are major documented capabilities in room that are not documented for AgentChatBus:

1. **Terminal TUI for live group chat**
2. **One-shot room CLI commands**
   - `join`
   - `send`
   - `poll`
   - `watch`
3. **First-class direct/private messages**
4. **Slash commands inside the human chat interface**
5. **Live room admin commands in the TUI**
6. **Auto-start broker on first connect**
7. **Agent mode over persistent stdin/stdout**
8. **Purpose-built autonomous wrapper (`room-ralph`)**
9. **Repo-level Claude plugin story focused on room coordination**

### 8. Implementation Strategy Delta

#### State and persistence

- AgentChatBus: structured relational state in SQLite
- room: append-only NDJSON plus local token/cursor files

Implication:

- AgentChatBus is better positioned for **querying, indexing, filtering, templates, search, state transitions, and richer APIs**
- room is better positioned for **simplicity, inspectability, and shell-friendly local operations**

#### Transport and connectivity

- AgentChatBus: HTTP/SSE designed for IDEs, browsers, remote clients, and standards-based integration
- room: Unix socket designed for local Unix environments and direct process composition

Implication:

- AgentChatBus is stronger for **cross-tool ecosystem integration**
- room is stronger for **local terminal-native usage**

#### Coordination contract

- AgentChatBus: stronger **schema and workflow contract**
- room: stronger **workflow flexibility with fewer protocol assumptions**

Implication:

- AgentChatBus better fits teams that want **structured multi-agent workflows**
- room better fits teams that want a **lightweight shared coordination substrate**

### 9. Objective-Level Difference

The objectives are close, but not identical.

#### room objective

Enable humans and agents to share a durable local room with minimal ceremony, especially from Unix terminals, using chat-style interaction and simple command-line automation.

#### AgentChatBus objective

Provide a standards-friendly, observable, structured multi-agent communication layer that IDE agents and other clients can connect to consistently through MCP and HTTP.

### 10. Bottom-Line Comparison

If the question is "are these competitors?", the answer is **somewhat**.

They overlap in multi-agent coordination, but they make notably different bets:

- Choose **room** when the priority is **Unix-native chat ergonomics, terminal UI, and shell-composable coordination primitives**.
- Choose **AgentChatBus** when the priority is **MCP-native interoperability, structured workflows, web observability, and richer agent/message semantics**.

### 11. Practical Delta Summary

#### room gives AgentChatBus ideas in

- terminal-first human UX
- private messaging
- simpler non-MCP automation commands
- embedded moderation commands
- tighter Claude Code-specific runtime helpers

#### AgentChatBus gives room ideas in

- MCP-native interoperability
- searchable and queryable structured state
- thread lifecycle/workflow modeling
- richer message metadata and auditing
- web observability
- standards-oriented integration surface

## Conclusion

Both systems are clearly aimed at **persistent coordination for multiple participants, including AI agents**.

The biggest difference is not just feature count but **where the product boundary sits**:

- `room` is a **chat system with agent affordances**
- `AgentChatBus` is an **agent coordination bus with chat affordances**

That is the most important delta to keep in mind when evaluating the two repositories.

# Agent Integration Study

This section explores which existing agentic coding tools are most relevant to AgentChatBus, what integration surfaces they expose, and which integration patterns would best support **continuous multi-agent collaboration across tools and platforms**.

## Executive Takeaway

If the goal is **true continuous multi-agent collaboration** across IDEs, terminals, and hosted agents, the best answer is **not** a single mechanism.

The strongest approach is a layered stack:

1. **MCP as the canonical control plane** for interoperable tool access and shared bus semantics.
2. **Ralph-style background loops or daemons** for continuous waiting, heartbeats, and re-entry, especially in CLI-centric or unattended workflows.
3. **Slash commands / command packs** as the UX layer that makes bus actions obvious and repeatable for humans.
4. **Hooks and workflow engines** as optional automation layers for tools that support deterministic orchestration.

Short version:

- **MCP** gives AgentChatBus breadth.
- **Ralph-style loops** give AgentChatBus continuity.
- **Slash commands** give AgentChatBus usability.
- **Workflow-provider integrations** give AgentChatBus depth in selected ecosystems.

## What Continuous Multi-Agent Collaboration Actually Requires

To work well across tools, AgentChatBus needs more than "tool invocation." It needs:

- persistent agent identity
- reconnect/resume behavior
- background waiting or long-polling
- heartbeat/presence maintenance
- directed handoff support
- easy human invocation for common bus actions
- low-friction project-level configuration
- transport options that work in IDEs, CLIs, and remote/cloud agents

This is why slash commands alone are not enough, and why raw MCP alone is also not enough.

## Common Agentic Coding Solutions

### Tool landscape summary

| Tool | Form Factor | Relevant Integration Surface | What It Suggests For AgentChatBus |
|---|---|---|---|
| [Claude Code](https://code.claude.com/docs/en/hooks) | CLI / coding agent | MCP, slash commands, hooks, subagents, project commands | Excellent target for **MCP + hooks + slash-command packs + background loop helpers** |
| [Cursor](https://cursor.com/help/customization/mcp) | IDE | Project/global MCP config, cloud-agent pickup of project MCP config | Excellent target for **native MCP-first integration** |
| [Continue](https://docs.continue.dev/customize/deep-dives/mcp) | IDE + CLI surfaces | MCP in agent mode, config blocks, sharable MCP configs, agent files | Good target for **MCP + agent templates** |
| [Cline](https://docs.cline.bot/features/slash-commands/workflows/quickstart) | IDE | Workflows, slash commands, MCP tools | Good target for **workflow files + slash commands + MCP** |
| [Roo Code](https://docs.roocode.com/features/slash-commands) | IDE | Project MCP, slash commands, modes | Good target for **MCP + mode-aware commands** |
| [OpenCode](https://dev.opencode.ai/docs/agents/) | CLI / TUI | Agents, subagents, MCP, custom commands, provider/plugin system | Strong target for **deeper workflow/provider integration** |
| [GitHub Copilot coding agent](https://docs.github.com/copilot/how-tos/use-copilot-agents/coding-agent/extend-coding-agent-with-mcp) | IDE + GitHub surfaces | MCP, custom agents, repository instructions | Strong target for **MCP + repo instructions + custom agent profiles** |
| [Windsurf](https://docs.windsurf.com/windsurf/mcp) | IDE | MCP support | Good target for **standard MCP compatibility** |
| [aider](https://aider.chat/docs/usage/commands.html) | CLI | chat commands, modes, watch-file triggers | Weaker native bus surface; better target for **wrapper/daemon integration** than deep native integration |

### Observed ecosystem pattern

Across the current tool landscape, four integration surfaces show up repeatedly:

1. **MCP**
2. **Slash commands / command files**
3. **Modes / custom agents / subagents**
4. **Workflow or hook systems**

That convergence matters. It means AgentChatBus can target a small number of patterns and still integrate with many tools.

## Integration Technique Options

### Option 1: MCP-first integration

Use AgentChatBus as the canonical MCP server and optimize for MCP-native clients first.

**Already aligned with:**

- Cursor
- Continue
- Roo Code
- Windsurf
- GitHub Copilot coding agent
- Claude Code
- OpenCode

**Strengths:**

- highest cross-tool reach
- standards-friendly
- minimal per-tool customization
- preserves one shared semantic model
- best for interoperability and long-term maintainability

**Weaknesses:**

- MCP by itself does not create good human workflows
- many tools expose MCP tools, but do not provide a good default collaboration UX
- continuous listening/presence still needs a runtime pattern

**Assessment:**

This should remain the **foundation**, but not the full answer.

### Option 2: Slash-command packs

Provide project-local or user-global command packs for major tools so users can trigger common AgentChatBus workflows consistently.

Examples:

- `/bus-connect`
- `/bus-sync`
- `/bus-wait`
- `/bus-handoff`
- `/bus-review`
- `/bus-close-thread`

**Best fits:**

- Claude Code custom commands
- Cline workflows / slash commands
- Roo Code slash commands
- OpenCode commands

**Strengths:**

- high usability
- low implementation cost
- teaches users the bus workflow
- easy to version per project
- can encode team conventions

**Weaknesses:**

- commands are usually human-invoked, not continuous
- command syntax differs by tool
- they help entry and repeatability, but do not solve unattended coordination

**Assessment:**

This is a **high-value second layer**. Slash commands are not the core transport, but they are one of the best adoption tools.

### Option 3: Ralph-style background loops

Create a small companion runtime that keeps an agent continuously connected to AgentChatBus semantics:

- register/resume
- heartbeat
- `msg_wait`
- reconnect on failure
- post replies or status
- preserve thread and cursor state

This can look like:

- a CLI wrapper
- a sidecar daemon
- a small local agent runner
- a background watch loop invoked by an IDE or CLI tool

**Best fits:**

- Claude Code
- aider
- shell-scripted agents
- headless CI or long-lived coding agents
- any tool where the assistant cannot maintain a live wait loop elegantly on its own

**Strengths:**

- directly solves the "continuous collaboration" problem
- handles presence and waiting robustly
- works even when the host tool has weak native automation
- can unify behavior across CLI tools

**Weaknesses:**

- more engineering than simple commands
- needs careful UX so users trust the background behavior
- introduces local process management concerns

**Assessment:**

If the target is **true continuous collaboration**, this is the **single highest-value missing layer** after MCP itself.

### Option 4: Hooks-based automation

Use tool-native hooks to trigger AgentChatBus behavior automatically at lifecycle events.

Examples:

- on session start: `agent_resume` or `bus_connect`
- before stop: `msg_post` with `stop_reason`
- after edits/tests: send progress update
- on task completion: write summary to current thread

This is especially attractive in tools with rich lifecycle hooks, such as Claude Code.

**Strengths:**

- automates agent discipline
- reduces reliance on prompt compliance
- can keep status/presence data more accurate

**Weaknesses:**

- highly tool-specific
- harder to make portable
- can become noisy if not carefully scoped

**Assessment:**

Hooks are a **high-leverage enhancement** for specific ecosystems, especially Claude Code, but they should sit on top of a shared MCP/loop foundation.

### Option 5: Workflow-engine or provider integrations

This is the heavier modification path. The local `opencode-workflow` example in `/Volumes/git/opencode-workflow` is a strong illustration of this pattern.

Its key idea is not just "custom commands," but **deterministic orchestration**:

- workflow definitions in agent frontmatter
- tool, agent, and nested workflow steps
- `loop.for_each`, `loop.parallel`, `loop.until`
- stateless progress reconstruction from tool-call IDs
- structured output enforcement

That is materially different from a slash-command template. It is a **workflow runtime**.

**What this suggests for AgentChatBus:**

- AgentChatBus could become the shared communication substrate under a deterministic workflow system.
- Techniques such as debate, verification loops, reviewer/writer loops, fan-out/fan-in synthesis, and best-of-N selection could run against AgentChatBus threads.
- Workflow state could remain local to the host tool while bus state remains centralized in AgentChatBus.

**Strengths:**

- strongest support for advanced multi-agent patterns
- allows deterministic orchestration without relying on the model to "remember the protocol"
- ideal for complex review, delegation, and verification workflows

**Weaknesses:**

- much higher implementation cost
- ecosystem-specific unless abstracted carefully
- easy to overfit to one host tool

**Assessment:**

This is the **most powerful specialized path**, but it should be a later layer, not the first integration move.

## What Could Be Built

### A. Thin integration artifacts

These are relatively easy and likely high ROI:

- `agentchatbus` project MCP configs for major tools
- shared command packs for Claude Code, Roo Code, Cline, and OpenCode
- repo-local instruction templates explaining the `bus_connect -> msg_wait -> msg_post` loop
- example threads/templates for code review, planning, and delegation

### B. Companion runtime artifacts

These are more strategic for continuous collaboration:

- `agentchatbus-loop`: a local loop/daemon that manages register, heartbeat, wait, reconnect, and post
- `agentchatbus-bridge-aider`: wrapper that maps aider-style sessions into bus events
- `agentchatbus-watch`: simple CLI for polling/waiting outside MCP-native environments

### C. Deep ecosystem integrations

These are heavier but potentially differentiating:

- `agentchatbus-hooks` for Claude Code lifecycle automation
- `agentchatbus-workflows` for OpenCode-style deterministic orchestration
- Cline/Roo workflow packs that implement standard multi-agent review and planning patterns
- GitHub Copilot custom agent profiles that understand AgentChatBus roles and thread semantics

## Recommended Architecture For AgentChatBus Integration

### Recommendation 1: Keep MCP as the canonical protocol surface

AgentChatBus should continue to treat MCP as the primary standards-based interface for:

- thread operations
- messaging
- agent registration/presence
- prompts/resources/templates

This is what gives AgentChatBus portability across vendors and tools.

### Recommendation 2: Add a first-class continuous loop runtime

The best addition for "true multi-agent collaboration" would be a **ralph-style continuous loop** for AgentChatBus.

This should probably be a separate companion package or mode, not fused into every tool integration.

Desired behavior:

- resume existing agent identity if present
- keep heartbeats alive
- block on `msg_wait`
- route handoffs to the right local agent/tool
- reconnect automatically after tool restarts
- preserve per-thread working memory or local state as needed

This is the layer that most directly closes the gap between "can call tools" and "is continuously collaborating."

### Recommendation 3: Ship command packs for the major tool families

Command packs should be thin wrappers over the canonical bus semantics.

Examples:

- `/bus-connect <thread>`
- `/bus-review <thread>`
- `/bus-claim <task>`
- `/bus-handoff <agent>`
- `/bus-sync`
- `/bus-done`

These improve discoverability and team consistency, but should not carry unique semantics that diverge from MCP.

### Recommendation 4: Use hooks where the host tool supports them well

Claude Code is especially promising here because hooks can enforce lifecycle behavior instead of hoping the model remembers it.

High-value hook automations:

- session-start connect/resume
- pre-stop summary post
- post-edit or post-test progress updates
- automatic state transition suggestions

This is likely the best tool-specific enhancement layer after command packs.

### Recommendation 5: Treat workflow engines as an advanced adapter layer

The `opencode-workflow` pattern is important because it demonstrates how sophisticated agent techniques can run **deterministically** rather than only as prompt instructions.

For AgentChatBus, the most promising workflow-engine patterns are:

- review loop: writer -> reviewer -> fix until pass
- planning loop: propose -> critique -> converge -> summarize
- handoff loop: decompose -> assign -> wait -> synthesize
- best-of-N loop: generate several candidate plans or patches -> rank -> pick
- verification loop: attempt -> validate against criteria -> retry

These should likely be built as **optional adapters** for ecosystems that already support workflow files, providers, or task orchestration.

## Which Combination Best Serves The Goal?

### Best overall combination

For broad, durable, cross-platform success:

1. **MCP-first core**
2. **Ralph-style continuous loop runtime**
3. **Slash-command packs**
4. **Hooks for selected ecosystems**
5. **Workflow-engine adapters later**

### Why this beats the alternatives

#### Why not slash commands alone?

Because slash commands improve invocation, but they do not provide:

- persistent listening
- automatic resume
- heartbeat discipline
- unattended collaboration

They are necessary UX, not sufficient runtime.

#### Why not workflow engines alone?

Because they are powerful, but too tool-specific and too heavy to be the primary compatibility story.

They are better as an advanced layer for ecosystems that already support them well.

#### Why not raw MCP alone?

Because standards compliance does not automatically produce good collaboration ergonomics.

Raw MCP is the protocol layer, not the full user/runtime experience.

## Priority Order

If AgentChatBus wants to maximize impact, the practical order is:

1. **Strengthen the MCP-first story across tools**
2. **Build an AgentChatBus continuous loop / daemon companion**
3. **Ship per-tool command packs and project templates**
4. **Add Claude Code hooks integration**
5. **Prototype an OpenCode-style deterministic workflow adapter**

## Bottom-Line Recommendation

The best path is a **hybrid strategy**:

- keep **AgentChatBus itself** as the portable, standards-oriented communication bus
- add a **continuous runtime companion** for presence and long-lived collaboration
- add **thin UX layers** per tool through commands, templates, and hooks
- reserve **heavier workflow-provider integrations** for advanced ecosystems like OpenCode

If forced to choose only one addition beyond today's MCP support, the most valuable would be:

**a ralph-style AgentChatBus loop runtime**, because it most directly enables real continuous multi-agent coordination instead of one-off tool usage.
