import httpx
import pytest

from tests.conftest import BASE_URL


@pytest.mark.integration
def test_wait_api_returns_sync_context_after_message(server):
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        waiter = client.post(
            "/api/agents/register",
            json={"ide": "CLI", "model": "Waiter"},
        ).json()
        sender = client.post(
            "/api/agents/register",
            json={"ide": "CLI", "model": "Sender"},
        ).json()

        thread = client.post(
            "/api/threads",
            json={
                "topic": "wait-api-thread",
                "creator_agent_id": waiter["agent_id"],
            },
            headers={"X-Agent-Token": waiter["token"]},
        ).json()

        send_resp = client.post(
            f"/api/threads/{thread['id']}/messages",
            json={
                "author": sender["agent_id"],
                "role": "assistant",
                "content": "hello from sender",
            },
            headers={"X-Agent-Token": sender["token"]},
        )
        assert send_resp.status_code == 201

        wait_resp = client.post(
            f"/api/threads/{thread['id']}/wait",
            json={
                "after_seq": 0,
                "agent_id": waiter["agent_id"],
                "token": waiter["token"],
                "timeout_ms": 1000,
            },
        )
        assert wait_resp.status_code == 200
        payload = wait_resp.json()

        assert payload["messages"]
        assert payload["messages"][-1]["content"] == "hello from sender"
        assert "reply_token" in payload
        assert "current_seq" in payload
