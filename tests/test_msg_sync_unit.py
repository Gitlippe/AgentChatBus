import aiosqlite
import pytest

from src.config import SEQ_TOLERANCE
from src.db import crud
from src.db.database import init_schema


async def _make_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await init_schema(db)
    return db


async def _post_with_fresh_token(db, thread_id: str, author: str, content: str):
    sync = await crud.issue_reply_token(db, thread_id=thread_id)
    return await crud.msg_post(
        db,
        thread_id=thread_id,
        author=author,
        content=content,
        expected_last_seq=sync["current_seq"],
        reply_token=sync["reply_token"],
    )


@pytest.mark.asyncio
async def test_msg_post_requires_sync_fields():
    db = await _make_db()
    try:
        thread = await crud.thread_create(db, topic="sync-required")
        with pytest.raises(crud.MissingSyncFieldsError):
            await crud.msg_post(
                db,
                thread_id=thread.id,
                author="human",
                content="hello",
                expected_last_seq=None,
                reply_token="",
            )
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_reply_token_replay_is_rejected():
    db = await _make_db()
    try:
        thread = await crud.thread_create(db, topic="sync-replay")
        sync = await crud.issue_reply_token(db, thread_id=thread.id)

        await crud.msg_post(
            db,
            thread_id=thread.id,
            author="human",
            content="first",
            expected_last_seq=sync["current_seq"],
            reply_token=sync["reply_token"],
        )

        with pytest.raises(crud.ReplyTokenReplayError):
            await crud.msg_post(
                db,
                thread_id=thread.id,
                author="human",
                content="second",
                expected_last_seq=sync["current_seq"] + 1,
                reply_token=sync["reply_token"],
            )
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_seq_mismatch_returns_new_messages_context():
    db = await _make_db()
    try:
        thread = await crud.thread_create(db, topic="sync-seq-mismatch")
        baseline = await crud.issue_reply_token(db, thread_id=thread.id)

        # Move thread ahead beyond tolerance with valid posts.
        for i in range(SEQ_TOLERANCE + 1):
            await _post_with_fresh_token(db, thread.id, "human", f"msg-{i}")

        fresh = await crud.issue_reply_token(db, thread_id=thread.id)
        with pytest.raises(crud.SeqMismatchError) as exc_info:
            await crud.msg_post(
                db,
                thread_id=thread.id,
                author="human",
                content="stale-context-post",
                expected_last_seq=baseline["current_seq"],
                reply_token=fresh["reply_token"],
            )

        err = exc_info.value
        assert err.current_seq > err.expected_last_seq
        assert len(err.new_messages) >= SEQ_TOLERANCE
    finally:
        await db.close()
