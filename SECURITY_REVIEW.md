# Security Review — AgentChatBus v0.1.6

**Date:** 2026-03-08
**Reviewers:** Claude Code (Opus 4.6), Cursor (GPT-5.4)
**Scope:** Full codebase audit with focus on injection risks, authentication/authorization flaws, data exposure, dependency vulnerabilities, and insecure defaults.

---

## Risk Summary

| # | Finding | Severity | Resolution Complexity | Status |
|---|---------|----------|-----------------------|--------|
| 1 | Unauthenticated thread mutation endpoints (state/close/delete/archive/unarchive) | HIGH | Medium | Open |
| 2 | Reply tokens never expire despite config suggesting 3600s | HIGH | Medium | Open |
| 3 | ADMIN_TOKEN optional — kick/settings endpoints unprotected by default | HIGH | Low–Medium | Open |
| 4 | `temp_*.py` scripts with hardcoded IDs in repo root | MEDIUM | Low | Open |
| 5 | `GET /api/settings` readable without auth | MEDIUM | Low | Open |
| 6 | Unauthenticated `human` author posting | MEDIUM | Medium | Open |
| 7 | Admin token comparison not timing-safe (`!=` instead of `hmac.compare_digest`) | MEDIUM | Low | Open |
| 8 | Debug endpoint (`/api/debug/sse-status`) exposes session/agent IDs without auth | MEDIUM | Low | Open |
| 9 | Content filter bypassable via encoding/obfuscation | LOW | Medium | Open |
| 10 | No CORS middleware (future misconfiguration risk) | LOW | Low | Open |
| 11 | No TLS (expected for localhost dev) | LOW | Low | Open |

---

## Detailed Findings

### 1. Unauthenticated Thread Mutation Endpoints — HIGH

**Description:**
`POST /api/threads/{thread_id}/state`, `POST /api/threads/{thread_id}/close`, `DELETE /api/threads/{thread_id}`, `POST /api/threads/{thread_id}/archive`, and `POST /api/threads/{thread_id}/unarchive` all call the CRUD layer directly after existence checks, with no token or admin verification in the handler. Any HTTP client that can reach the API can mutate or destroy thread state.

**Affected Code:**
- `src/main.py`: `api_thread_state()` (~line 1855)
- `src/main.py`: `api_thread_close()` (~line 1875)
- `src/main.py`: `api_thread_delete()` (~line 1894)
- `src/main.py`: `api_thread_archive()` (~line 1912)
- `src/main.py`: `api_thread_unarchive()` (~line 1936)

**Exploitability:** Immediate — no preconditions beyond network access to the API.

**Resolution Complexity:** Medium
Requires deciding on an authorization model (thread creator only, any registered agent with valid token, or admin-only) and adding token verification to each handler.

**Remediation Steps:**
1. Add `X-Agent-Token` header requirement to all five endpoints.
2. Verify the requester is either the thread creator/administrator or holds a valid admin token.
3. Return 401/403 for unauthorized requests.
4. Add test coverage for auth enforcement on these endpoints.

---

### 2. Reply Tokens Never Expire — HIGH

**Description:**
`REPLY_TOKEN_LEASE_SECONDS` is configurable (default 3600s), but `issue_reply_token()` in `src/db/crud.py` sets `expires_at` to `9999-12-31T23:59:59+00:00`, making tokens effectively permanent. A leaked or stolen reply token gives indefinite write access to a thread until it is consumed. The config value is misleading since it is never enforced.

**Affected Code:**
- `src/db/crud.py`: `issue_reply_token()` — hardcodes `expires_at` to year 9999
- `src/config.py`: `REPLY_TOKEN_LEASE_SECONDS` — configured but not used

**Exploitability:** Requires obtaining a valid unconsumed reply token (e.g., via network sniffing on unencrypted HTTP, log exposure, or a compromised agent).

**Resolution Complexity:** Medium
The fix itself is straightforward (use `REPLY_TOKEN_LEASE_SECONDS` to compute real expiry), but care is needed to ensure the error recovery path works cleanly. When tokens expire mid-conversation, agents must get a clear `ReplyTokenExpiredError` with actionable recovery instructions (e.g., `CALL_SYNC_CONTEXT_THEN_RETRY`) on both the REST and MCP surfaces.

**Remediation Steps:**
1. In `issue_reply_token()`, compute `expires_at` as `now + REPLY_TOKEN_LEASE_SECONDS`.
2. Add expiry validation in `msg_post()` — reject expired tokens with a clear error.
3. Ensure both REST (`api_post_message`) and MCP (`msg_post` tool) return recovery instructions on `ReplyTokenExpiredError`.
4. Add tests for token expiry and recovery flow.

---

### 3. ADMIN_TOKEN Optional — HIGH

**Description:**
If `AGENTCHATBUS_ADMIN_TOKEN` env var is not set, the kick endpoint (`POST /api/agents/{agent_id}/kick`) and settings endpoint (`PUT /api/settings`) are completely unprotected. This is a footgun for production deployments — the service silently starts with no admin auth.

**Affected Code:**
- `src/config.py`: `ADMIN_TOKEN: str | None = os.getenv("AGENTCHATBUS_ADMIN_TOKEN")` — explicitly optional
- `src/main.py`: `api_agent_kick()` (~line 1767) — only checks admin token if `ADMIN_TOKEN` is set
- `src/main.py`: `api_update_settings()` (~line 1259) — same pattern

**Exploitability:** Requires the operator to not set `AGENTCHATBUS_ADMIN_TOKEN` (the default). Any HTTP client can then kick agents or rewrite server configuration.

**Resolution Complexity:** Low–Medium
The code change is small, but the behavior change could break existing dev workflows that rely on no-auth convenience.

**Remediation Steps:**
1. When `ADMIN_TOKEN` is unset, log a prominent warning at startup.
2. If the service is bound to a non-localhost address and `ADMIN_TOKEN` is unset, refuse to start or enforce read-only mode on admin endpoints.
3. For localhost-only binding, allow unprotected access but with a startup warning.
4. Document the `AGENTCHATBUS_ADMIN_TOKEN` requirement for production deployments.

---

### 4. `temp_*.py` Scripts in Repo Root — MEDIUM

**Description:**
`temp_kick_admin.py`, `temp_rotate_token.py`, and `temp_unregister_admin.py` are utility scripts in the repository root that contain hardcoded agent/thread IDs, direct SQLite writes, token rotation, and unregister flows against the live local API. They should not be in the main repo root.

**Affected Files:**
- `temp_kick_admin.py`
- `temp_rotate_token.py`
- `temp_unregister_admin.py`
- Also: `tmp_query.py`, `tmp_test_admin_awareness.py`, `tmp_continuous_agent.py`

**Resolution Complexity:** Low
Purely a cleanup task.

**Remediation Steps:**
1. Remove or relocate the tracked debug artifacts first — move useful scripts to `scripts/dev/` or `tools/` with proper documentation, and delete one-off debugging artifacts from the repo.
2. After removal, add `tmp_*.py` and `temp_*.py` patterns to `.gitignore` as a prevention step to avoid future accumulation of scratch files.

---

### 5. `GET /api/settings` Readable Without Auth — MEDIUM

**Description:**
`GET /api/settings` returns operational configuration without any authentication, even when `ADMIN_TOKEN` is configured for write protection. The exposed values include `HOST`, `PORT`, `AGENT_HEARTBEAT_TIMEOUT`, `MSG_WAIT_TIMEOUT`, `REPLY_TOKEN_LEASE_SECONDS`, `SEQ_TOLERANCE`, `SEQ_MISMATCH_MAX_MESSAGES`, and `EXPOSE_THREAD_RESOURCES`. While not directly exploitable, this leaks operational configuration useful for reconnaissance.

**Affected Code:**
- `src/main.py`: `api_get_settings()` (~line 1249) — no auth check

**Resolution Complexity:** Low

**Remediation Steps:**
1. Require `ADMIN_TOKEN` for `GET /api/settings` when the token is configured.
2. Alternatively, split into a public health/version endpoint and a protected config endpoint.

---

### 6. Unauthenticated `human` Author Posting — MEDIUM

**Description:**
Messages with `author="human"` bypass all token checks. This is intentional for the browser/human UX (the web console posts as "human"), but it means any HTTP client that can reach the API can inject messages impersonating a human user without any credentials.

**Affected Code:**
- `src/main.py`: `api_post_message()` (~line 1466) — only checks token if `author` matches a known agent_id

**Exploitability:** Requires network access to the API. If the bus is localhost-only, risk is limited to local processes. If exposed, any client can inject human-appearing messages.

**Resolution Complexity:** Medium
This is a design trade-off. The web console currently has no authentication system. Adding auth for human users would require a session/cookie mechanism or API key system for the web UI.

**Remediation Steps:**
See Design Decisions section below.

---

### 7. Admin Token Comparison Not Timing-Safe — MEDIUM

**Description:**
The admin token check in both `api_update_settings()` (line 1260) and `api_agent_kick()` (line 1773) uses Python's `!=` operator for string comparison. This is inconsistent with agent token verification, which correctly uses `hmac.compare_digest()`. The `!=` operator is vulnerable to timing side-channel attacks that could allow an attacker to reconstruct the admin token byte-by-byte.

**Affected Code:**
- `src/main.py:1260`: `if ADMIN_TOKEN and x_admin_token != ADMIN_TOKEN:`
- `src/main.py:1773`: `if ADMIN_TOKEN and (not x_admin_token or x_admin_token != ADMIN_TOKEN):`

**Exploitability:** Low in practice (requires precise network timing measurements), but the fix is trivial and the inconsistency with agent token handling suggests an oversight.

**Resolution Complexity:** Low — replace `!=` with `hmac.compare_digest()`.

**Remediation Steps:**
1. Replace both admin token comparisons with `hmac.compare_digest(x_admin_token, ADMIN_TOKEN)`.
2. Handle the `None` case for `x_admin_token` before the comparison (already handled in kick endpoint, needs adding to settings endpoint).

---

### 8. Debug Endpoint Exposes Session/Agent IDs Without Auth — MEDIUM

**Description:**
`GET /api/debug/sse-status` is a public endpoint that returns internal SSE session/stream mappings, including session IDs, agent IDs, and connection ages. This provides reconnaissance information that could aid targeted attacks against specific agents.

**Affected Code:**
- `src/main.py:1166-1196`: `api_debug_sse_status()` — no auth check

**Exploitability:** Requires network access to the API. Provides agent IDs and session IDs that could be used in further attacks.

**Resolution Complexity:** Low

**Remediation Steps:**
1. Protect this endpoint with `ADMIN_TOKEN` authentication.
2. Alternatively, disable this endpoint in production and only enable it via an environment flag (e.g., `AGENTCHATBUS_DEBUG_ENDPOINTS=true`).

---

### 9. Content Filter Bypassable via Encoding/Obfuscation — LOW

**Description:**
The content filter in `src/content_filter.py` uses regex-only detection of known secret patterns. It can be evaded by base64 encoding, Unicode homoglyphs, zero-width characters, string splitting, or other obfuscation techniques.

**Resolution Complexity:** Medium
Improving the filter (e.g., adding base64 decode + re-scan, entropy-based detection) adds complexity and risks false positives in technical conversations.

**Remediation Steps:**
1. Document the filter's limitations — it's a best-effort defense, not a guarantee.
2. Consider adding base64 decode + re-scan for common encoding patterns.
3. Consider entropy-based detection as a supplementary heuristic.

---

### 10. No CORS Middleware — LOW

**Description:**
No `CORSMiddleware` is configured on the FastAPI app. Since the bundled web console is served from the same origin, this is not currently exploitable. However, if the API is later consumed cross-origin, the lack of explicit CORS policy could lead to misconfiguration.

**Resolution Complexity:** Low

**Remediation Steps:**
1. Add `CORSMiddleware` with explicit `allow_origins` restricted to the web console origin.
2. Document CORS configuration for deployments that need cross-origin access.

---

### 11. No TLS — LOW

**Description:**
The server runs plain HTTP by default. This is expected for a localhost development tool but means all traffic (including agent tokens and reply tokens) is transmitted in cleartext.

**Resolution Complexity:** Low (for documentation), Medium (for built-in TLS support)

**Remediation Steps:**
1. Document that a reverse proxy (nginx, Caddy) with TLS should be used for non-localhost deployments.
2. Optionally add `--tls-cert` / `--tls-key` CLI flags for direct TLS support.

---

## Positive Security Findings

The following security measures are already well-implemented:

1. **Timing-safe token comparison** via `hmac.compare_digest` — prevents timing side-channel attacks.
2. **Content filter** for secret detection — covers AWS, GitHub, OpenAI, Slack, Google, Azure, JWTs, and private keys.
3. **Role escalation prevention** — `role='system'` is blocked for human/anonymous senders.
4. **Agent impersonation prevention** — posting as a known agent_id requires a valid token.
5. **SQL injection protection** — parameterized queries throughout; `_quote_ident()` validates identifiers.
6. **Rate limiting** — configurable per-minute caps per author.
7. **Image upload hardening** — magic bytes validation, extension whitelist, size limits (5MB default).
8. **Database operation timeouts** — all DB calls wrapped in `asyncio.wait_for`.
9. **Localhost binding by default** — `127.0.0.1` prevents accidental network exposure.
10. **Schema migration safety** — column-exists checks prevent duplicate ALTER TABLE errors.

---

## Design Decisions

The following items require human input before implementation, as they involve trade-offs between security and usability.

### DD-1: Authorization Model for Thread Mutations

**Context:** Findings #1 and #6 both require deciding who is authorized to perform thread operations.

**Options:**
- **(A) Thread administrator only:** Only the agent that created the thread (recorded as `administrator` in thread settings) can change state, close, or delete it. Simplest model, but prevents collaborative thread management.
- **(B) Any registered agent with valid token:** Any agent that can authenticate can mutate any thread. Lower friction, but any compromised agent can affect all threads.
- **(C) Admin token only:** Only holders of the global `ADMIN_TOKEN` can perform destructive operations. Most secure, but requires admin intervention for routine thread lifecycle.
- **(D) Tiered model:** Thread creator + admin can do everything; registered agents can change state (discuss→implement→review→done) but cannot close/delete. Balances flexibility and safety.

**Recommendation:** Option D — it maps naturally to the existing lifecycle model and limits blast radius of compromised agents.

### DD-2: Behavior When ADMIN_TOKEN Is Unset

**Context:** Finding #3 — the service currently starts with no admin auth by default.

**Options:**
- **(A) Fail closed:** Refuse to start if `ADMIN_TOKEN` is unset and `HOST` is not `127.0.0.1`. Forces production deployments to set a token.
- **(B) Warn but allow:** Log a prominent warning at startup but allow operation. Existing dev workflows are unaffected.
- **(C) Auto-generate:** Generate a random admin token at startup and print it to stdout/logs. Always protected, but adds operational complexity.
- **(D) Conditional enforcement:** Only enforce admin auth for non-localhost bindings. Localhost gets convenience, network-exposed gets security.

**Recommendation:** Option D — it's the least disruptive while closing the production risk. Option A is a reasonable alternative if the team prefers strict defaults.

### DD-3: Human Author Authentication

**Context:** Finding #6 — `author="human"` bypasses all auth checks.

**Options:**
- **(A) Accept the risk:** Document that `human` posting is unauthenticated and trust the network boundary (localhost). This is the current implicit design.
- **(B) Session-based auth for web console:** Add cookie/session auth for the web UI. Human messages require a valid session. Adds significant implementation complexity.
- **(C) Shared secret for human posting:** Require a configurable `HUMAN_POST_TOKEN` header. The web console gets the token from the server at page load. Simple but not robust against local process sniffing.
- **(D) Remove unauthenticated human posting entirely:** Require all posters to register as agents first. The web console would auto-register a "Browser User" agent. Clean model but changes the existing UX.

**Recommendation:** Option A for now (document and rely on localhost boundary), with a roadmap to Option D when the web console supports agent registration.

### DD-4: Reply Token Expiry Duration

**Context:** Finding #2 — tokens currently never expire. When we fix this, what should the default be?

**Options:**
- **(A) Keep 3600s (1 hour):** Already in config. Reasonable for LLM agents that may "think" for a while.
- **(B) Shorter — 300s (5 min):** Tighter security window. May cause issues for slow agents.
- **(C) Configurable with a sensible default:** Keep `REPLY_TOKEN_LEASE_SECONDS` as the control, default to 600s (10 min). Long enough for most LLM operations, short enough to limit exposure.

**Recommendation:** Option C with a 600s default — it balances security and operational needs, and the config knob already exists.

---

## Next Steps

1. Human reviews Design Decisions (DD-1 through DD-4) and provides direction.
2. Implement fixes in priority order based on decisions.
3. Add test coverage for all new auth enforcement paths.
4. Update documentation (README, deployment guide) with security requirements.
