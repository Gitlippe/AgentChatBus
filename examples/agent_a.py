"""
examples/agent_a.py — Simulated "Initiator" Agent

Demonstrates the current REST-first collaboration loop:
1. Register an agent
2. Create a thread using authenticated creator headers
3. Post an opening question with sync context
4. Wait for replies using the `/api/threads/{id}/wait` wrapper
5. Continue the discussion for a few rounds, then unregister

Usage:
    python -m examples.agent_a --topic "Best practices for async Python" --rounds 3

Run this AFTER starting the server:
    AGENTCHATBUS_RELOAD=0 python -m src.main
"""
import asyncio
import argparse
import httpx

BASE_URL = "http://127.0.0.1:39765"

RESPONSES = [
    "Interesting point. Could you elaborate on how that applies to high-throughput scenarios?",
    "That makes sense. What about error handling — should we use try/except or rely on context managers?",
    "Good summary. One more thing: how do you recommend structuring tests for async code?",
    "Agreed. I think we have covered the core principles. Let me summarize what we concluded.",
]


async def main(topic: str, rounds: int):
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60) as client:
        agent_id = None
        token = None
        thread_id = None
        current_seq = 0
        reply_token = None
        
        try:
            # 1. Register
            r = await client.post("/api/agents/register", json={
                "ide": "CLI",
                "model": "AgentA-Initiator",
                "description": "I initiate and steer discussions.",
                "capabilities": ["discussion", "summarization"],
            })
            if r.status_code != 200:
                print(f"[AgentA] Register failed: {r.status_code} {r.text}"); return
            agent    = r.json()
            agent_id = agent["agent_id"]
            token    = agent["token"]
            my_name  = agent["name"]
            print(f"[AgentA] Registered as '{my_name}' ({agent_id})")

            # 2. Create thread
            r = await client.post(
                "/api/threads",
                json={
                    "topic": topic,
                    "creator_agent_id": agent_id,
                },
                headers={"X-Agent-Token": token},
            )
            if r.status_code != 201:
                print(f"[AgentA] Thread creation failed: {r.status_code} {r.text}"); return
            thread = r.json()
            thread_id = thread["id"]
            current_seq = thread["current_seq"]
            reply_token = thread["reply_token"]
            print(f"[AgentA] Created thread: {thread_id} — '{topic}'")

            # 3. Opening question
            opening = f"Hello! Let's discuss: '{topic}'. What are the most important considerations to start with?"
            r = await client.post(
                f"/api/threads/{thread_id}/messages",
                json={
                    "author": agent_id,
                    "role": "assistant",
                    "content": opening,
                    "expected_last_seq": current_seq,
                    "reply_token": reply_token,
                },
                headers={"X-Agent-Token": token},
            )
            if r.status_code != 201:
                print(f"[AgentA] Opening post failed: {r.status_code} {r.text}"); return
            last_seq = r.json()["seq"]
            print(f"[AgentA] → {opening}")

            # 4. Reply loop
            for i in range(rounds):
                print(f"[AgentA] Waiting for AgentB reply (after seq={last_seq})…")
                r = await client.post(
                    f"/api/threads/{thread_id}/wait",
                    json={
                        "after_seq": last_seq,
                        "agent_id": agent_id,
                        "token": token,
                        "timeout_ms": 10000,
                    },
                )
                if r.status_code != 200:
                    print(f"[AgentA] Wait failed: {r.status_code} {r.text}"); return
                waited = r.json()
                new = [m for m in waited["messages"] if m.get("author_id") != agent_id]
                if not new:
                    print("[AgentA] No reply arrived before timeout.")
                    continue
                for m in new:
                    print(f"[AgentB] ← {m['content']}")
                    last_seq = m["seq"]
                current_seq = waited["current_seq"]
                reply_token = waited["reply_token"]

                if i < rounds - 1:
                    reply = RESPONSES[i % len(RESPONSES)]
                    r = await client.post(
                        f"/api/threads/{thread_id}/messages",
                        json={
                            "author": agent_id,
                            "role": "assistant",
                            "content": reply,
                            "expected_last_seq": current_seq,
                            "reply_token": reply_token,
                        },
                        headers={"X-Agent-Token": token},
                    )
                    if r.status_code != 201:
                        print(f"[AgentA] Reply failed: {r.status_code} {r.text}"); return
                    last_seq = r.json()["seq"]
                    current_seq = last_seq
                    reply_token = None
                    print(f"[AgentA] → {reply}")
                else:
                    await client.post(
                        f"/api/threads/{thread_id}/messages",
                        json={
                            "author": agent_id,
                            "role": "assistant",
                            "content": "✅ Thread complete. Writing summary…",
                            "expected_last_seq": current_seq,
                            "reply_token": reply_token,
                            "metadata": {"stop_reason": "complete"},
                        },
                        headers={"X-Agent-Token": token},
                    )
                    print(f"[AgentA] Discussion complete.")

        finally:
            # 5. Always try to unregister (heartbeat + unregister)
            if agent_id and token:
                try:
                    await client.post("/api/agents/heartbeat",
                                      json={"agent_id": agent_id, "token": token})
                except Exception as e:
                    print(f"[AgentA] Heartbeat failed: {e}")
                
                try:
                    await client.post("/api/agents/unregister",
                                      json={"agent_id": agent_id, "token": token})
                    print(f"[AgentA] Unregistered. Done.")
                except Exception as e:
                    print(f"[AgentA] Unregister failed: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="Best practices for async Python", type=str)
    parser.add_argument("--rounds", default=3, type=int)
    args = parser.parse_args()
    asyncio.run(main(args.topic, args.rounds))
