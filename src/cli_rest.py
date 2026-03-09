from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class BusClientError(RuntimeError):
    pass


@dataclass
class BusRestClient:
    endpoint: str
    timeout: float = 30.0

    def __post_init__(self) -> None:
        self.endpoint = self.endpoint.rstrip("/")

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.endpoint, timeout=self.timeout)

    @staticmethod
    def _detail_text(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except Exception:
            return response.text.strip()
        if isinstance(payload, dict):
            detail = payload.get("detail", payload)
            return str(detail)
        return str(payload)

    def _expect_json(self, response: httpx.Response, expected: tuple[int, ...] = (200, 201)) -> Any:
        if response.status_code not in expected:
            raise BusClientError(
                f"{response.request.method} {response.request.url.path} failed "
                f"with {response.status_code}: {self._detail_text(response)}"
            )
        return response.json()

    def health(self) -> dict[str, Any]:
        with self._client() as client:
            return self._expect_json(client.get("/health"), expected=(200,))

    def register_agent(
        self,
        *,
        ide: str,
        model: str,
        description: str = "",
        display_name: str | None = None,
        capabilities: list[str] | None = None,
        skills: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "ide": ide,
            "model": model,
            "description": description,
        }
        if display_name:
            body["display_name"] = display_name
        if capabilities is not None:
            body["capabilities"] = capabilities
        if skills is not None:
            body["skills"] = skills
        with self._client() as client:
            return self._expect_json(client.post("/api/agents/register", json=body), expected=(200,))

    def resume_agent(self, *, agent_id: str, token: str) -> dict[str, Any]:
        with self._client() as client:
            return self._expect_json(
                client.post("/api/agents/resume", json={"agent_id": agent_id, "token": token}),
                expected=(200,),
            )

    def heartbeat(self, *, agent_id: str, token: str) -> dict[str, Any]:
        with self._client() as client:
            return self._expect_json(
                client.post("/api/agents/heartbeat", json={"agent_id": agent_id, "token": token}),
                expected=(200,),
            )

    def unregister(self, *, agent_id: str, token: str) -> dict[str, Any]:
        with self._client() as client:
            return self._expect_json(
                client.post("/api/agents/unregister", json={"agent_id": agent_id, "token": token}),
                expected=(200,),
            )

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        with self._client() as client:
            return self._expect_json(client.get(f"/api/agents/{agent_id}"), expected=(200,))

    def list_threads(self, *, status: str | None = None, include_archived: bool = False) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"include_archived": str(include_archived).lower()}
        if status:
            params["status"] = status
        with self._client() as client:
            payload = self._expect_json(client.get("/api/threads", params=params), expected=(200,))
        if isinstance(payload, dict):
            return payload.get("threads", [])
        raise BusClientError("Unexpected /api/threads response shape")

    def find_thread_by_topic(self, topic: str) -> dict[str, Any] | None:
        for thread in self.list_threads(include_archived=True):
            if thread.get("topic") == topic:
                return thread
        return None

    def create_thread(
        self,
        *,
        topic: str,
        creator_agent_id: str,
        token: str,
        template: str | None = None,
        metadata: dict[str, Any] | None = None,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "topic": topic,
            "creator_agent_id": creator_agent_id,
        }
        if template:
            body["template"] = template
        if metadata is not None:
            body["metadata"] = metadata
        if system_prompt:
            body["system_prompt"] = system_prompt
        headers = {"X-Agent-Token": token}
        with self._client() as client:
            return self._expect_json(client.post("/api/threads", json=body, headers=headers), expected=(201,))

    def sync_context(self, *, thread_id: str, agent_id: str | None = None) -> dict[str, Any]:
        body = {"agent_id": agent_id} if agent_id else {}
        with self._client() as client:
            return self._expect_json(
                client.post(f"/api/threads/{thread_id}/sync-context", json=body),
                expected=(200,),
            )

    def list_messages(
        self,
        *,
        thread_id: str,
        after_seq: int = 0,
        limit: int = 200,
        include_system_prompt: bool = False,
    ) -> list[dict[str, Any]]:
        with self._client() as client:
            return self._expect_json(
                client.get(
                    f"/api/threads/{thread_id}/messages",
                    params={
                        "after_seq": after_seq,
                        "limit": limit,
                        "include_system_prompt": str(include_system_prompt).lower(),
                    },
                ),
                expected=(200,),
            )

    def wait_messages(
        self,
        *,
        thread_id: str,
        after_seq: int,
        agent_id: str,
        token: str,
        timeout_ms: int = 300000,
        for_agent: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "after_seq": after_seq,
            "agent_id": agent_id,
            "token": token,
            "timeout_ms": timeout_ms,
        }
        if for_agent:
            body["for_agent"] = for_agent
        with self._client() as client:
            return self._expect_json(
                client.post(f"/api/threads/{thread_id}/wait", json=body),
                expected=(200,),
            )

    def post_message(
        self,
        *,
        thread_id: str,
        author: str,
        content: str,
        role: str = "assistant",
        token: str | None = None,
        metadata: dict[str, Any] | None = None,
        priority: str = "normal",
        reply_to_msg_id: str | None = None,
        expected_last_seq: int | None = None,
        reply_token: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "author": author,
            "content": content,
            "role": role,
            "priority": priority,
        }
        if metadata is not None:
            body["metadata"] = metadata
        if reply_to_msg_id:
            body["reply_to_msg_id"] = reply_to_msg_id
        if expected_last_seq is not None:
            body["expected_last_seq"] = expected_last_seq
        if reply_token:
            body["reply_token"] = reply_token
        headers = {"X-Agent-Token": token} if token else None
        with self._client() as client:
            return self._expect_json(
                client.post(f"/api/threads/{thread_id}/messages", json=body, headers=headers),
                expected=(201,),
            )
