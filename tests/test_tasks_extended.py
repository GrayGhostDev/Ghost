"""Extended tests for src/ghost/tasks.py — covers workers, scheduler, decorator."""

import time
import threading
from datetime import datetime, timezone

import pytest

from src.ghost.tasks import (
    AsyncTaskWorker,
    Task,
    TaskManager,
    TaskPriority,
    TaskQueue,
    TaskResult,
    TaskScheduler,
    TaskStatus,
    TaskWorker,
    task,
)


# ──────────────────────────────────────────────
# TaskWorker — synchronous execution
# ──────────────────────────────────────────────

class TestTaskWorker:
    def test_execute_task_success(self):
        q = TaskQueue()
        worker = TaskWorker(q, "w1")
        t = Task(id="exec1", name="add", func=lambda x, y: x + y, args=(2, 3))
        worker._execute_task(t)
        result = q.get_result("exec1")
        assert result is not None
        assert result.status == TaskStatus.COMPLETED
        assert result.result == 5
        assert result.execution_time is not None

    def test_execute_task_failure(self):
        q = TaskQueue()
        worker = TaskWorker(q, "w2")

        def explode():
            raise ValueError("boom")

        t = Task(id="fail1", name="explode", func=explode, max_retries=0)
        worker._execute_task(t)
        result = q.get_result("fail1")
        assert result.status == TaskStatus.FAILED
        assert "boom" in result.error

    def test_execute_task_with_retry(self):
        q = TaskQueue()
        worker = TaskWorker(q, "w3")

        def fail_once():
            raise RuntimeError("transient")

        t = Task(id="retry1", name="fail", func=fail_once, max_retries=2, retry_delay=0)
        worker._execute_task(t)
        result = q.get_result("retry1")
        assert result.status == TaskStatus.RETRYING
        # Retry task should be enqueued
        assert q.get_pending_count() >= 1

    def test_execute_string_func(self):
        q = TaskQueue()
        worker = TaskWorker(q, "w4")
        # Use a real importable function
        t = Task(id="strfunc1", name="time", func="time.time")
        worker._execute_task(t)
        result = q.get_result("strfunc1")
        assert result.status == TaskStatus.COMPLETED
        assert isinstance(result.result, float)

    def test_start_and_stop(self):
        q = TaskQueue()
        worker = TaskWorker(q, "w5")
        worker.start()
        assert worker.running
        time.sleep(0.1)
        worker.stop()
        assert not worker.running

    def test_worker_processes_queued_task(self):
        q = TaskQueue()
        worker = TaskWorker(q, "w6")

        t = Task(id="auto1", name="add", func=lambda: 42)
        q.enqueue(t)
        worker.start()
        time.sleep(0.5)  # let worker pick up task
        worker.stop()
        result = q.get_result("auto1")
        assert result is not None
        assert result.status == TaskStatus.COMPLETED
        assert result.result == 42


# ──────────────────────────────────────────────
# AsyncTaskWorker
# ──────────────────────────────────────────────

class TestAsyncTaskWorker:
    @pytest.mark.asyncio
    async def test_execute_async_task_success(self):
        q = TaskQueue()
        worker = AsyncTaskWorker(q, "aw1")

        async def async_add(x, y):
            return x + y

        t = Task(id="aexec1", name="async_add", func=async_add, args=(3, 4))
        await worker._execute_task(t)
        result = q.get_result("aexec1")
        assert result.status == TaskStatus.COMPLETED
        assert result.result == 7

    @pytest.mark.asyncio
    async def test_execute_async_task_failure(self):
        q = TaskQueue()
        worker = AsyncTaskWorker(q, "aw2")

        async def async_fail():
            raise RuntimeError("async boom")

        t = Task(id="afail1", name="fail", func=async_fail, max_retries=0)
        await worker._execute_task(t)
        result = q.get_result("afail1")
        assert result.status == TaskStatus.FAILED
        assert "async boom" in result.error

    @pytest.mark.asyncio
    async def test_execute_async_task_timeout(self):
        import asyncio

        q = TaskQueue()
        worker = AsyncTaskWorker(q, "aw3")

        async def slow_task():
            await asyncio.sleep(10)
            return "done"

        t = Task(id="atimeout1", name="slow", func=slow_task, timeout=1)
        await worker._execute_task(t)
        result = q.get_result("atimeout1")
        assert result.status == TaskStatus.FAILED
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_async_string_func(self):
        q = TaskQueue()
        worker = AsyncTaskWorker(q, "aw4")

        # String func that resolves to an async callable
        async def _helper():
            return 99

        import src.ghost.tasks as tasks_mod
        tasks_mod._test_async_helper = _helper  # inject temporarily

        t = Task(id="astr1", name="helper", func="src.ghost.tasks._test_async_helper")
        await worker._execute_task(t)
        result = q.get_result("astr1")
        assert result.status == TaskStatus.COMPLETED
        assert result.result == 99

        del tasks_mod._test_async_helper


# ──────────────────────────────────────────────
# TaskScheduler
# ──────────────────────────────────────────────

class TestTaskScheduler:
    def test_add_job_every_minutes(self):
        mgr = TaskManager(num_workers=1, num_async_workers=1)
        scheduler = mgr.scheduler
        scheduler.add_job("j1", lambda: None, "every 5 minutes")
        assert "j1" in scheduler.jobs

    def test_add_job_every_unit(self):
        mgr = TaskManager(num_workers=1, num_async_workers=1)
        scheduler = mgr.scheduler
        scheduler.add_job("j2", lambda: None, "every hour")
        assert "j2" in scheduler.jobs

    def test_add_job_daily_at(self):
        mgr = TaskManager(num_workers=1, num_async_workers=1)
        scheduler = mgr.scheduler
        scheduler.add_job("j3", lambda: None, "daily at 10:30")
        assert "j3" in scheduler.jobs

    def test_add_job_invalid_schedule(self):
        mgr = TaskManager(num_workers=1, num_async_workers=1)
        scheduler = mgr.scheduler
        with pytest.raises(ValueError, match="Invalid schedule"):
            scheduler.add_job("j4", lambda: None, "invalid string")

    def test_add_job_invalid_every(self):
        mgr = TaskManager(num_workers=1, num_async_workers=1)
        scheduler = mgr.scheduler
        with pytest.raises(ValueError, match="Invalid schedule"):
            scheduler.add_job("j5", lambda: None, "every 5 things weekly")

    def test_remove_job(self):
        mgr = TaskManager(num_workers=1, num_async_workers=1)
        scheduler = mgr.scheduler
        scheduler.add_job("j6", lambda: None, "every 1 minutes")
        assert scheduler.remove_job("j6")
        assert "j6" not in scheduler.jobs

    def test_remove_nonexistent_job(self):
        mgr = TaskManager(num_workers=1, num_async_workers=1)
        scheduler = mgr.scheduler
        assert not scheduler.remove_job("ghost")

    def test_get_jobs(self):
        mgr = TaskManager(num_workers=1, num_async_workers=1)
        scheduler = mgr.scheduler
        scheduler.add_job("j7", lambda: None, "every 2 hours")
        jobs = scheduler.get_jobs()
        assert len(jobs) >= 1
        assert any(j["id"] == "j7" for j in jobs)

    def test_start_and_stop(self):
        mgr = TaskManager(num_workers=1, num_async_workers=1)
        scheduler = mgr.scheduler
        scheduler.start()
        assert scheduler.running
        time.sleep(0.1)
        scheduler.stop()
        assert not scheduler.running


# ──────────────────────────────────────────────
# TaskManager extended
# ──────────────────────────────────────────────

class TestTaskManagerExtended:
    def test_start_and_stop(self):
        mgr = TaskManager(num_workers=1, num_async_workers=1)
        mgr.start()
        assert len(mgr.workers) == 1
        mgr.stop()

    def test_schedule(self):
        mgr = TaskManager(num_workers=1, num_async_workers=1)
        job_id = mgr.schedule(lambda: None, "every 10 minutes")
        assert job_id is not None

    def test_schedule_with_id(self):
        mgr = TaskManager(num_workers=1, num_async_workers=1)
        job_id = mgr.schedule(lambda: None, "every 1 hours", job_id="custom-id")
        assert job_id == "custom-id"

    def test_get_result_no_wait(self):
        mgr = TaskManager(num_workers=1, num_async_workers=1)
        assert mgr.get_result("nonexistent") is None

    def test_get_result_wait_timeout(self):
        mgr = TaskManager(num_workers=1, num_async_workers=1)
        result = mgr.get_result("nonexistent", wait=True, timeout=0.2)
        assert result is None

    def test_get_stats_extended(self):
        mgr = TaskManager(num_workers=2, num_async_workers=1)
        stats = mgr.get_stats()
        assert stats["workers"] == 0  # not started yet
        assert stats["async_workers"] == 0
        assert "scheduled_jobs" in stats

    @pytest.mark.asyncio
    async def test_start_async(self):
        mgr = TaskManager(num_workers=1, num_async_workers=1)
        await mgr.start_async()
        assert len(mgr.async_workers) == 1
        await mgr.stop_async()


# ──────────────────────────────────────────────
# @task decorator
# ──────────────────────────────────────────────

class TestTaskDecorator:
    def test_task_creates_task_object(self):
        @task(name="my_task", priority=TaskPriority.HIGH)
        def my_func(x):
            return x * 2

        result = my_func(5)
        assert isinstance(result, Task)
        assert result.name == "my_task"
        assert result.priority == TaskPriority.HIGH
        assert result.args == (5,)

    def test_task_default_name(self):
        @task()
        def another_func():
            pass

        result = another_func()
        assert result.name == "another_func"

    def test_task_delay_attr(self):
        @task()
        def delayed_func():
            pass

        assert hasattr(delayed_func, "delay")
