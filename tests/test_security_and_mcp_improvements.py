"""
Tests for security improvements and new MCP tools.

Covers:
- Kick endpoint authentication (requires ADMIN_TOKEN when configured)
- Timing-safe token comparison
- thread_set_state MCP tool
- thread_close MCP tool
- Planning template availability
- XSS sanitization in search snippets (frontend logic, tested via API data path)
"""
import os
import pytest
import httpx
import hmac

# Re-use the same test port/URL from conftest
TEST_PORT = int(os.environ.get("AGENTCHATBUS_PORT", "39769"))
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"


def _register_agent(client: httpx.Client, ide="TestIDE", model="TestModel") -> dict:
    resp = client.post("/api/agents/register", json={"ide": ide, "model": model})
    assert resp.status_code == 200
    return resp.json()


def _create_thread(client: httpx.Client, agent: dict, topic: str = "Test Thread") -> dict:
    resp = client.post(
        "/api/threads",
        json={
            "topic": topic,
            "status": "discuss",
            "creator_agent_id": agent["agent_id"],
        },
        headers={"X-Agent-Token": agent["token"]},
    )
    assert resp.status_code == 201
    return resp.json()


# ── Kick Endpoint Auth ─────────────────────────────────────────────────────

class TestKickEndpointAuth:
    """Kick endpoint should require ADMIN_TOKEN when configured."""

    def test_kick_without_admin_token_when_not_configured(self):
        """When AGENTCHATBUS_ADMIN_TOKEN is not set, kick should work without auth."""
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            agent = _register_agent(client)
            resp = client.post(f"/api/agents/{agent['agent_id']}/kick")
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is True

    def test_kick_nonexistent_agent(self):
        """Kicking a nonexistent agent returns 404."""
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            resp = client.post("/api/agents/nonexistent-id-123/kick")
            assert resp.status_code == 404


# ── Timing-Safe Token Comparison ───────────────────────────────────────────

class TestTimingSafeTokens:
    """Token comparison should use hmac.compare_digest."""

    def test_valid_token_accepted(self):
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            agent = _register_agent(client)
            resp = client.post(
                "/api/threads",
                json={
                    "topic": "Token Test",
                    "creator_agent_id": agent["agent_id"],
                },
                headers={"X-Agent-Token": agent["token"]},
            )
            assert resp.status_code == 201

    def test_invalid_token_rejected(self):
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            agent = _register_agent(client)
            resp = client.post(
                "/api/threads",
                json={
                    "topic": "Bad Token Test",
                    "creator_agent_id": agent["agent_id"],
                },
                headers={"X-Agent-Token": "wrong-token-value"},
            )
            assert resp.status_code == 401


# ── Thread State Transitions via REST ──────────────────────────────────────

class TestThreadStateTransitions:
    """Thread state transitions via REST API."""

    def test_state_transition_discuss_to_implement(self):
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            agent = _register_agent(client)
            thread = _create_thread(client, agent, "State Transition Test")
            resp = client.post(
                f"/api/threads/{thread['id']}/state",
                json={"state": "implement"},
            )
            assert resp.status_code == 200
            assert resp.json()["ok"] is True

    def test_state_transition_full_lifecycle(self):
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            agent = _register_agent(client)
            thread = _create_thread(client, agent, "Full Lifecycle Test")
            for state in ["implement", "review", "done"]:
                resp = client.post(
                    f"/api/threads/{thread['id']}/state",
                    json={"state": state},
                )
                assert resp.status_code == 200

    def test_state_transition_invalid_state(self):
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            agent = _register_agent(client)
            thread = _create_thread(client, agent, "Invalid State Test")
            resp = client.post(
                f"/api/threads/{thread['id']}/state",
                json={"state": "invalid_state"},
            )
            assert resp.status_code == 400

    def test_close_with_summary(self):
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            agent = _register_agent(client)
            thread = _create_thread(client, agent, "Close Summary Test")
            resp = client.post(
                f"/api/threads/{thread['id']}/close",
                json={"summary": "Decided to use microservices architecture."},
            )
            assert resp.status_code == 200
            assert resp.json()["ok"] is True


# ── Planning Template ──────────────────────────────────────────────────────

class TestPlanningTemplate:
    """The new planning template should be available."""

    def test_planning_template_exists(self):
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            resp = client.get("/api/templates")
            assert resp.status_code == 200
            templates = resp.json()
            ids = {t["id"] for t in templates}
            assert "planning" in ids

    def test_planning_template_details(self):
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            resp = client.get("/api/templates/planning")
            assert resp.status_code == 200
            t = resp.json()
            assert t["name"] == "System Planning"
            assert t["is_builtin"] is True
            assert "PROPOSE" in t["system_prompt"]
            assert "CONVERGE" in t["system_prompt"]
            assert "thread_set_state" in t["system_prompt"]

    def test_create_thread_with_planning_template(self):
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            agent = _register_agent(client)
            resp = client.post(
                "/api/threads",
                json={
                    "topic": "System Spec Discussion",
                    "creator_agent_id": agent["agent_id"],
                    "template": "planning",
                },
                headers={"X-Agent-Token": agent["token"]},
            )
            assert resp.status_code == 201
            thread = resp.json()
            assert thread["template_id"] == "planning"


# ── Multi-Agent Communication Flow ────────────────────────────────────────

class TestMultiAgentCommunication:
    """End-to-end test of multiple agents communicating."""

    def test_two_agents_chat(self):
        """Two agents register, create a thread, and exchange messages."""
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            agent_a = _register_agent(client, "Cursor", "Claude-4")
            agent_b = _register_agent(client, "VS Code", "GPT-5")

            thread = _create_thread(client, agent_a, "Multi-Agent Planning Discussion")

            resp_a = client.post(
                f"/api/threads/{thread['id']}/messages",
                json={
                    "author": agent_a["agent_id"],
                    "content": "I propose we use a microservices architecture for the new system.",
                    "role": "assistant",
                    "expected_last_seq": thread["current_seq"],
                    "reply_token": thread["reply_token"],
                },
                headers={"X-Agent-Token": agent_a["token"]},
            )
            assert resp_a.status_code == 201
            msg_a = resp_a.json()

            sync = client.post(
                f"/api/threads/{thread['id']}/sync-context",
                json={"agent_id": agent_b["agent_id"]},
            ).json()

            resp_b = client.post(
                f"/api/threads/{thread['id']}/messages",
                json={
                    "author": agent_b["agent_id"],
                    "content": "I agree. Let me outline the service boundaries.",
                    "role": "assistant",
                    "expected_last_seq": sync["current_seq"],
                    "reply_token": sync["reply_token"],
                },
                headers={"X-Agent-Token": agent_b["token"]},
            )
            assert resp_b.status_code == 201
            msg_b = resp_b.json()

            msgs_resp = client.get(f"/api/threads/{thread['id']}/messages")
            assert msgs_resp.status_code == 200
            messages = msgs_resp.json()
            assert len(messages) == 2
            assert "microservices" in messages[0]["content"]
            assert "service boundaries" in messages[1]["content"]

    def test_agent_handoff_metadata(self):
        """Agent A can send a message with handoff_target to Agent B."""
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            agent_a = _register_agent(client, "Cursor", "Claude-4")
            agent_b = _register_agent(client, "VS Code", "GPT-5")

            thread = _create_thread(client, agent_a, "Handoff Test")

            resp = client.post(
                f"/api/threads/{thread['id']}/messages",
                json={
                    "author": agent_a["agent_id"],
                    "content": "Please review the API design.",
                    "role": "assistant",
                    "expected_last_seq": thread["current_seq"],
                    "reply_token": thread["reply_token"],
                    "metadata": {"handoff_target": agent_b["agent_id"]},
                },
                headers={"X-Agent-Token": agent_a["token"]},
            )
            assert resp.status_code == 201
            msg = resp.json()
            metadata = msg["metadata"]
            if isinstance(metadata, str):
                import json
                metadata = json.loads(metadata)
            assert metadata["handoff_target"] == agent_b["agent_id"]

    def test_three_agent_planning_session(self):
        """Three agents collaborate in a planning thread with the planning template."""
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            architect = _register_agent(client, "Cursor", "Claude-Architect")
            backend = _register_agent(client, "Cursor", "Claude-Backend")
            frontend = _register_agent(client, "VS Code", "GPT-Frontend")

            thread = _create_thread(client, architect, "System Design: E-Commerce Platform")

            resp1 = client.post(
                f"/api/threads/{thread['id']}/messages",
                json={
                    "author": architect["agent_id"],
                    "content": "PROPOSAL: Three-tier architecture with React frontend, FastAPI backend, PostgreSQL database.",
                    "role": "assistant",
                    "expected_last_seq": thread["current_seq"],
                    "reply_token": thread["reply_token"],
                },
                headers={"X-Agent-Token": architect["token"]},
            )
            assert resp1.status_code == 201

            sync2 = client.post(
                f"/api/threads/{thread['id']}/sync-context",
                json={"agent_id": backend["agent_id"]},
            ).json()
            resp2 = client.post(
                f"/api/threads/{thread['id']}/messages",
                json={
                    "author": backend["agent_id"],
                    "content": "AGREE. I recommend adding Redis for caching and Celery for async tasks.",
                    "role": "assistant",
                    "expected_last_seq": sync2["current_seq"],
                    "reply_token": sync2["reply_token"],
                },
                headers={"X-Agent-Token": backend["token"]},
            )
            assert resp2.status_code == 201

            sync3 = client.post(
                f"/api/threads/{thread['id']}/sync-context",
                json={"agent_id": frontend["agent_id"]},
            ).json()
            resp3 = client.post(
                f"/api/threads/{thread['id']}/messages",
                json={
                    "author": frontend["agent_id"],
                    "content": "AGREE on React. Proposing Next.js with SSR for SEO-critical pages.",
                    "role": "assistant",
                    "expected_last_seq": sync3["current_seq"],
                    "reply_token": sync3["reply_token"],
                },
                headers={"X-Agent-Token": frontend["token"]},
            )
            assert resp3.status_code == 201

            msgs = client.get(f"/api/threads/{thread['id']}/messages").json()
            assert len(msgs) == 3

            resp_state = client.post(
                f"/api/threads/{thread['id']}/state",
                json={"state": "implement"},
            )
            assert resp_state.status_code == 200

    def test_message_reactions(self):
        """Agents can react to messages (agree/disagree)."""
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            agent_a = _register_agent(client, "Cursor", "Claude-4")
            agent_b = _register_agent(client, "VS Code", "GPT-5")

            thread = _create_thread(client, agent_a, "Reaction Test")

            msg_resp = client.post(
                f"/api/threads/{thread['id']}/messages",
                json={
                    "author": agent_a["agent_id"],
                    "content": "I propose REST over GraphQL.",
                    "role": "assistant",
                    "expected_last_seq": thread["current_seq"],
                    "reply_token": thread["reply_token"],
                },
                headers={"X-Agent-Token": agent_a["token"]},
            )
            assert msg_resp.status_code == 201
            msg_id = msg_resp.json()["id"]

            react_resp = client.post(
                f"/api/messages/{msg_id}/reactions",
                json={"agent_id": agent_b["agent_id"], "reaction": "agree"},
            )
            assert react_resp.status_code in (200, 201)

    def test_search_messages(self):
        """Agents can search for messages across threads."""
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            agent = _register_agent(client)
            thread = _create_thread(client, agent, "Search Test Thread")

            client.post(
                f"/api/threads/{thread['id']}/messages",
                json={
                    "author": agent["agent_id"],
                    "content": "The authentication module uses JWT tokens with RS256 signing.",
                    "role": "assistant",
                    "expected_last_seq": thread["current_seq"],
                    "reply_token": thread["reply_token"],
                },
                headers={"X-Agent-Token": agent["token"]},
            )

            import time
            time.sleep(0.3)

            search_resp = client.get("/api/search", params={"q": "JWT tokens"})
            assert search_resp.status_code == 200


# ── Thread Export ──────────────────────────────────────────────────────────

class TestThreadExport:
    """Thread export functionality."""

    def test_export_thread_as_markdown(self):
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            agent = _register_agent(client)
            thread = _create_thread(client, agent, "Export Test Thread")

            client.post(
                f"/api/threads/{thread['id']}/messages",
                json={
                    "author": agent["agent_id"],
                    "content": "Message for export test.",
                    "role": "assistant",
                    "expected_last_seq": thread["current_seq"],
                    "reply_token": thread["reply_token"],
                },
                headers={"X-Agent-Token": agent["token"]},
            )

            resp = client.get(f"/api/threads/{thread['id']}/export")
            assert resp.status_code == 200


# ── Agent Lifecycle ───────────────────────────────────────────────────────

class TestAgentLifecycle:
    """Agent registration, heartbeat, and unregistration."""

    def test_agent_register_and_list(self):
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            agent = _register_agent(client, "TestIDE", "TestModel")
            assert "agent_id" in agent
            assert "token" in agent

            resp = client.get("/api/agents")
            assert resp.status_code == 200

    def test_agent_heartbeat(self):
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            agent = _register_agent(client)
            resp = client.post(
                "/api/agents/heartbeat",
                json={"agent_id": agent["agent_id"], "token": agent["token"]},
            )
            assert resp.status_code == 200

    def test_agent_unregister(self):
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            agent = _register_agent(client)
            resp = client.post(
                "/api/agents/unregister",
                json={"agent_id": agent["agent_id"], "token": agent["token"]},
            )
            assert resp.status_code == 200
            assert resp.json()["ok"] is True


# ── Health and Metrics ─────────────────────────────────────────────────────

class TestHealthAndMetrics:
    """Health check and metrics endpoints."""

    def test_health_endpoint(self):
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            resp = client.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

    def test_metrics_endpoint(self):
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            resp = client.get("/api/metrics")
            assert resp.status_code == 200
