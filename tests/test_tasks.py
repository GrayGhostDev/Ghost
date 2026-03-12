"""Tests for src/ghost/tasks.py"""

import pytest
from datetime import datetime, timezone

from src.ghost.tasks import (
    Task,
    TaskManager,
    TaskPriority,
    TaskQueue,
    TaskResult,
    TaskStatus,
)


# ──────────────────────────────────────────────
# Task dataclass
# ──────────────────────────────────────────────

class TestTask:
    def test_serialize_with_callable(self):
        def my_func():
            pass

        t = Task(id="t1", name="test", func=my_func)
        data = t.serialize()
        assert data["id"] == "t1"
        assert "my_func" in data["func"]
        assert data["priority"] == TaskPriority.NORMAL.value

    def test_serialize_with_string_func(self):
        t = Task(id="t2", name="test", func="mymod.myfunc")
        data = t.serialize()
        assert data["func"] == "mymod.myfunc"

    def test_deserialize(self):
        data = {
            "id": "t3",
            "name": "restored",
            "func": "mod.func",
            "args": [1, 2],
            "kwargs": {"k": "v"},
            "priority": TaskPriority.HIGH.value,
            "max_retries": 5,
            "retry_delay": 30,
            "timeout": 120,
            "scheduled_at": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {"job": "test"},
        }
        t = Task.deserialize(data)
        assert t.id == "t3"
        assert t.name == "restored"
        assert t.args == (1, 2)
        assert t.kwargs == {"k": "v"}
        assert t.priority == TaskPriority.HIGH
        assert t.max_retries == 5
        assert t.metadata["job"] == "test"

    def test_deserialize_with_scheduled_at(self):
        now = datetime.now(timezone.utc)
        data = {
            "id": "t4",
            "name": "scheduled",
            "func": "mod.func",
            "scheduled_at": now.isoformat(),
            "created_at": now.isoformat(),
        }
        t = Task.deserialize(data)
        assert t.scheduled_at is not None


# ──────────────────────────────────────────────
# TaskResult
# ──────────────────────────────────────────────

class TestTaskResult:
    def test_defaults(self):
        r = TaskResult(task_id="r1", status=TaskStatus.PENDING)
        assert r.result is None
        assert r.error is None
        assert r.retry_count == 0
        assert r.metadata == {}


# ──────────────────────────────────────────────
# TaskQueue
# ──────────────────────────────────────────────

class TestTaskQueue:
    def test_enqueue_dequeue(self):
        q = TaskQueue()
        t = Task(id="q1", name="job", func=lambda: None)
        q.enqueue(t)
        assert q.get_pending_count() == 1

        dequeued = q.dequeue(timeout=1)
        assert dequeued is not None
        assert dequeued.id == "q1"

    def test_dequeue_empty(self):
        q = TaskQueue()
        assert q.dequeue(timeout=0.1) is None

    def test_priority_ordering(self):
        q = TaskQueue()
        low = Task(id="low", name="low", func=lambda: None, priority=TaskPriority.LOW)
        high = Task(id="high", name="high", func=lambda: None, priority=TaskPriority.HIGH)
        q.enqueue(low)
        q.enqueue(high)

        first = q.dequeue(timeout=1)
        assert first.id == "high"

    def test_cancel_task(self):
        q = TaskQueue()
        t = Task(id="c1", name="cancel me", func=lambda: None)
        q.enqueue(t)
        assert q.cancel_task("c1") is True
        result = q.get_result("c1")
        assert result.status == TaskStatus.CANCELLED

    def test_cancel_nonexistent(self):
        q = TaskQueue()
        assert q.cancel_task("nope") is False

    def test_get_task(self):
        q = TaskQueue()
        t = Task(id="gt1", name="get", func=lambda: None)
        q.enqueue(t)
        assert q.get_task("gt1") is not None
        assert q.get_task("missing") is None

    def test_set_and_get_result(self):
        q = TaskQueue()
        r = TaskResult(task_id="sr1", status=TaskStatus.COMPLETED, result=42)
        q.set_result(r)
        fetched = q.get_result("sr1")
        assert fetched.result == 42

    def test_stats(self):
        q = TaskQueue()
        r = TaskResult(task_id="st1", status=TaskStatus.COMPLETED)
        q.set_result(r)
        stats = q.get_stats()
        assert stats["total_processed"] == 1
        assert "completed" in stats["status_counts"]


# ──────────────────────────────────────────────
# TaskManager
# ──────────────────────────────────────────────

class TestTaskManager:
    def test_submit_task_object(self):
        mgr = TaskManager(num_workers=1, num_async_workers=1)
        t = Task(id="tm1", name="test", func=lambda: None)
        task_id = mgr.submit(t)
        assert task_id == "tm1"

    def test_submit_callable(self):
        mgr = TaskManager(num_workers=1, num_async_workers=1)
        task_id = mgr.submit(lambda: 42)
        assert task_id is not None

    def test_cancel_via_manager(self):
        mgr = TaskManager(num_workers=1, num_async_workers=1)
        t = Task(id="cm1", name="cancel", func=lambda: None)
        mgr.submit(t)
        assert mgr.cancel("cm1") is True

    def test_get_stats(self):
        mgr = TaskManager(num_workers=1, num_async_workers=1)
        stats = mgr.get_stats()
        assert "pending" in stats
        assert "workers" in stats
