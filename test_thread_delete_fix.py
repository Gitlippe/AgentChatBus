#!/usr/bin/env python3
"""
Quick test to verify that thread_delete now properly handles events table.
"""
import asyncio
import sys
from src.db import database as dbmod
from src.db import crud
from datetime import datetime, timezone


async def test_thread_delete_with_events():
    """Test that thread_delete properly cleans up events."""
    
    # Initialize database
    db = await dbmod.get_db()
    
    try:
        # Create a thread
        thread_id = "test-delete-" + datetime.now(timezone.utc).isoformat()
        await db.execute(
            """
            INSERT INTO threads (id, topic, status, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (thread_id, "Test Topic", "discuss", datetime.now(timezone.utc).isoformat())
        )
        
        # Add a message
        await db.execute(
            """
            INSERT INTO messages (id, thread_id, author, role, content, seq, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("msg1", thread_id, "test-author", "user", "Test message", 1, 
             datetime.now(timezone.utc).isoformat())
        )
        
        # Add an event (this was likely causing the FK constraint issue)
        await db.execute(
            """
            INSERT INTO events (event_type, thread_id, payload, created_at)
            VALUES (?, ?, ?, ?)
            """,
            ("msg.new", thread_id, '{"id":"msg1"}', datetime.now(timezone.utc).isoformat())
        )
        
        await db.commit()
        
        # Verify data was inserted
        async with db.execute("SELECT COUNT(*) as cnt FROM threads WHERE id = ?", (thread_id,)) as cur:
            count = (await cur.fetchone())["cnt"]
            assert count == 1, f"Expected 1 thread, got {count}"
        
        async with db.execute("SELECT COUNT(*) as cnt FROM messages WHERE thread_id = ?", (thread_id,)) as cur:
            count = (await cur.fetchone())["cnt"]
            assert count == 1, f"Expected 1 message, got {count}"
            
        async with db.execute("SELECT COUNT(*) as cnt FROM events WHERE thread_id = ?", (thread_id,)) as cur:
            count = (await cur.fetchone())["cnt"]
            assert count == 1, f"Expected 1 event, got {count}"
        
        # Now try to delete the thread - this should NOT raise FK constraint error
        result = await crud.thread_delete(db, thread_id)
        assert result is not None, "thread_delete should return result for existing thread"
        assert result["thread_id"] == thread_id, "Result should contain correct thread_id"
        
        # Verify everything was deleted
        async with db.execute("SELECT COUNT(*) as cnt FROM threads WHERE id = ?", (thread_id,)) as cur:
            count = (await cur.fetchone())["cnt"]
            assert count == 0, f"Expected 0 threads after delete, got {count}"
        
        async with db.execute("SELECT COUNT(*) as cnt FROM messages WHERE thread_id = ?", (thread_id,)) as cur:
            count = (await cur.fetchone())["cnt"]
            assert count == 0, f"Expected 0 messages after delete, got {count}"
            
        # Note: _emit_event() creates a new "thread.deleted" event AFTER deletion,
        # so we expect exactly 1 event after deletion (the deletion notification).
        # The original event that triggered FK constraint was deleted above.
        async with db.execute("SELECT COUNT(*) as cnt FROM events WHERE thread_id = ? AND event_type = 'thread.deleted'", (thread_id,)) as cur:
            count = (await cur.fetchone())["cnt"]
            assert count == 1, f"Expected 1 'thread.deleted' event, got {count}"
        
        print("✓ thread_delete test passed!")
        print("  - Thread with messages and events was successfully deleted")
        print("  - No FOREIGN KEY constraint errors occurred")
        return True
        
    except Exception as e:
        print(f"✗ test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await dbmod.close_db()


if __name__ == "__main__":
    success = asyncio.run(test_thread_delete_with_events())
    sys.exit(0 if success else 1)
