"""
Background Task Processing Module

Provides task queue and background job processing capabilities with support for
scheduled tasks, retries, and multiple backends including native async and Celery.
"""

import asyncio
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Callable, List, Union, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import threading
import schedule
import queue
from functools import wraps
import json
from .config import get_config
from .logging import get_logger, LoggerMixin
from .database import get_db_manager


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class TaskResult:
    """Result of a task execution."""
    task_id: str
    status: TaskStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time: Optional[float] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """Background task definition."""
    id: str
    name: str
    func: Union[Callable, str]  # Function or function path
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    max_retries: int = 3
    retry_delay: int = 60  # seconds
    timeout: Optional[int] = None  # seconds
    scheduled_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def serialize(self) -> Dict[str, Any]:
        """Serialize task for storage."""
        return {
            'id': self.id,
            'name': self.name,
            'func': self.func if isinstance(self.func, str) else f"{self.func.__module__}.{self.func.__name__}",
            'args': self.args,
            'kwargs': self.kwargs,
            'priority': self.priority.value,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'timeout': self.timeout,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'created_at': self.created_at.isoformat(),
            'metadata': self.metadata
        }
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> 'Task':
        """Deserialize task from storage."""
        return cls(
            id=data['id'],
            name=data['name'],
            func=data['func'],
            args=tuple(data.get('args', [])),
            kwargs=data.get('kwargs', {}),
            priority=TaskPriority(data.get('priority', TaskPriority.NORMAL.value)),
            max_retries=data.get('max_retries', 3),
            retry_delay=data.get('retry_delay', 60),
            timeout=data.get('timeout'),
            scheduled_at=datetime.fromisoformat(data['scheduled_at']) if data.get('scheduled_at') else None,
            created_at=datetime.fromisoformat(data['created_at']),
            metadata=data.get('metadata', {})
        )


class TaskQueue(LoggerMixin):
    """In-memory task queue."""
    
    def __init__(self, max_size: int = 1000):
        """Initialize task queue.
        
        Args:
            max_size: Maximum queue size
        """
        self.queue = queue.PriorityQueue(maxsize=max_size)
        self.tasks: Dict[str, Task] = {}
        self.results: Dict[str, TaskResult] = {}
        self._lock = threading.Lock()
    
    def enqueue(self, task: Task) -> str:
        """Add task to queue.
        
        Args:
            task: Task to enqueue
            
        Returns:
            Task ID
        """
        with self._lock:
            # Priority queue item: (priority_value, timestamp, task_id)
            priority_value = -task.priority.value  # Negative for higher priority first
            timestamp = time.time()
            self.queue.put((priority_value, timestamp, task.id))
            self.tasks[task.id] = task
            self.logger.info(f"Task {task.id} ({task.name}) enqueued")
        return task.id
    
    def dequeue(self, timeout: Optional[float] = None) -> Optional[Task]:
        """Get next task from queue.
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            Next task or None
        """
        try:
            _, _, task_id = self.queue.get(timeout=timeout)
            with self._lock:
                task = self.tasks.get(task_id)
                if task:
                    del self.tasks[task_id]
                return task
        except queue.Empty:
            return None
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task or None
        """
        return self.tasks.get(task_id)
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task.
        
        Args:
            task_id: Task ID
            
        Returns:
            True if cancelled
        """
        with self._lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                self.results[task_id] = TaskResult(
                    task_id=task_id,
                    status=TaskStatus.CANCELLED
                )
                self.logger.info(f"Task {task_id} cancelled")
                return True
        return False
    
    def get_result(self, task_id: str) -> Optional[TaskResult]:
        """Get task result.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task result or None
        """
        return self.results.get(task_id)
    
    def set_result(self, result: TaskResult):
        """Store task result.
        
        Args:
            result: Task result
        """
        self.results[result.task_id] = result
    
    def get_pending_count(self) -> int:
        """Get number of pending tasks."""
        return self.queue.qsize()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        status_counts = {}
        for result in self.results.values():
            status = result.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            'pending': self.get_pending_count(),
            'total_processed': len(self.results),
            'status_counts': status_counts
        }


class TaskWorker(LoggerMixin):
    """Worker that processes tasks from queue."""
    
    def __init__(self, task_queue: TaskQueue, worker_id: str):
        """Initialize worker.
        
        Args:
            task_queue: Task queue to process
            worker_id: Unique worker ID
        """
        self.queue = task_queue
        self.worker_id = worker_id
        self.running = False
        self._thread = None
    
    def start(self):
        """Start worker thread."""
        if not self.running:
            self.running = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            self.logger.info(f"Worker {self.worker_id} started")
    
    def stop(self):
        """Stop worker thread."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        self.logger.info(f"Worker {self.worker_id} stopped")
    
    def _run(self):
        """Worker main loop."""
        while self.running:
            task = self.queue.dequeue(timeout=1)
            if task:
                self._execute_task(task)
    
    def _execute_task(self, task: Task):
        """Execute a single task.
        
        Args:
            task: Task to execute
        """
        result = TaskResult(
            task_id=task.id,
            status=TaskStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            metadata=task.metadata
        )
        
        try:
            self.logger.info(f"Executing task {task.id} ({task.name})")
            
            # Get function
            if isinstance(task.func, str):
                # Import function from string path
                module_path, func_name = task.func.rsplit('.', 1)
                module = __import__(module_path, fromlist=[func_name])
                func = getattr(module, func_name)
            else:
                func = task.func
            
            # Execute with timeout if specified
            if task.timeout:
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError(f"Task exceeded timeout of {task.timeout} seconds")
                
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(task.timeout)
                
                try:
                    result.result = func(*task.args, **task.kwargs)
                finally:
                    signal.alarm(0)
            else:
                result.result = func(*task.args, **task.kwargs)
            
            result.status = TaskStatus.COMPLETED
            result.completed_at = datetime.now(timezone.utc)
            result.execution_time = (result.completed_at - result.started_at).total_seconds()
            
            self.logger.info(f"Task {task.id} completed in {result.execution_time:.2f}s")
            
        except Exception as e:
            result.status = TaskStatus.FAILED
            result.error = str(e)
            result.completed_at = datetime.now(timezone.utc)
            result.execution_time = (result.completed_at - result.started_at).total_seconds()
            
            self.logger.error(f"Task {task.id} failed: {e}")
            
            # Handle retries
            if result.retry_count < task.max_retries:
                result.retry_count += 1
                result.status = TaskStatus.RETRYING
                
                # Re-queue with delay
                retry_task = Task(
                    id=f"{task.id}_retry_{result.retry_count}",
                    name=task.name,
                    func=task.func,
                    args=task.args,
                    kwargs=task.kwargs,
                    priority=task.priority,
                    max_retries=task.max_retries - result.retry_count,
                    retry_delay=task.retry_delay,
                    timeout=task.timeout,
                    scheduled_at=datetime.now(timezone.utc) + timedelta(seconds=task.retry_delay),
                    metadata={**task.metadata, 'retry_count': result.retry_count, 'original_task_id': task.id}
                )
                
                self.queue.enqueue(retry_task)
                self.logger.info(f"Task {task.id} scheduled for retry #{result.retry_count}")
        
        self.queue.set_result(result)


class AsyncTaskWorker(LoggerMixin):
    """Async worker for processing async tasks."""
    
    def __init__(self, task_queue: TaskQueue, worker_id: str):
        """Initialize async worker.
        
        Args:
            task_queue: Task queue to process
            worker_id: Unique worker ID
        """
        self.queue = task_queue
        self.worker_id = worker_id
        self.running = False
        self._task = None
    
    async def start(self):
        """Start async worker."""
        if not self.running:
            self.running = True
            self._task = asyncio.create_task(self._run())
            self.logger.info(f"Async worker {self.worker_id} started")
    
    async def stop(self):
        """Stop async worker."""
        self.running = False
        if self._task:
            await self._task
        self.logger.info(f"Async worker {self.worker_id} stopped")
    
    async def _run(self):
        """Async worker main loop."""
        while self.running:
            task = self.queue.dequeue(timeout=0.1)
            if task:
                await self._execute_task(task)
            else:
                await asyncio.sleep(0.1)
    
    async def _execute_task(self, task: Task):
        """Execute an async task.
        
        Args:
            task: Task to execute
        """
        result = TaskResult(
            task_id=task.id,
            status=TaskStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            metadata=task.metadata
        )
        
        try:
            self.logger.info(f"Executing async task {task.id} ({task.name})")
            
            # Get function
            if isinstance(task.func, str):
                module_path, func_name = task.func.rsplit('.', 1)
                module = __import__(module_path, fromlist=[func_name])
                func = getattr(module, func_name)
            else:
                func = task.func
            
            # Execute with timeout if specified
            if task.timeout:
                result.result = await asyncio.wait_for(
                    func(*task.args, **task.kwargs),
                    timeout=task.timeout
                )
            else:
                result.result = await func(*task.args, **task.kwargs)
            
            result.status = TaskStatus.COMPLETED
            result.completed_at = datetime.now(timezone.utc)
            result.execution_time = (result.completed_at - result.started_at).total_seconds()
            
            self.logger.info(f"Async task {task.id} completed in {result.execution_time:.2f}s")
            
        except asyncio.TimeoutError:
            result.status = TaskStatus.FAILED
            result.error = f"Task exceeded timeout of {task.timeout} seconds"
            result.completed_at = datetime.now(timezone.utc)
            result.execution_time = (result.completed_at - result.started_at).total_seconds()
            
            self.logger.error(f"Async task {task.id} timed out")
            
        except Exception as e:
            result.status = TaskStatus.FAILED
            result.error = str(e)
            result.completed_at = datetime.now(timezone.utc)
            result.execution_time = (result.completed_at - result.started_at).total_seconds()
            
            self.logger.error(f"Async task {task.id} failed: {e}")
        
        self.queue.set_result(result)


class TaskScheduler(LoggerMixin):
    """Scheduler for periodic and scheduled tasks."""
    
    def __init__(self, task_manager: 'TaskManager'):
        """Initialize scheduler.
        
        Args:
            task_manager: Task manager instance
        """
        self.task_manager = task_manager
        self.jobs: Dict[str, schedule.Job] = {}
        self.running = False
        self._thread = None
    
    def start(self):
        """Start scheduler thread."""
        if not self.running:
            self.running = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            self.logger.info("Task scheduler started")
    
    def stop(self):
        """Stop scheduler thread."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        self.logger.info("Task scheduler stopped")
    
    def _run(self):
        """Scheduler main loop."""
        while self.running:
            schedule.run_pending()
            time.sleep(1)
    
    def add_job(self, job_id: str, func: Callable, schedule_str: str, *args, **kwargs):
        """Add a scheduled job.
        
        Args:
            job_id: Unique job ID
            func: Function to execute
            schedule_str: Schedule string (e.g., "every 5 minutes", "daily at 10:30")
            *args: Function arguments
            **kwargs: Function keyword arguments
        """
        # Parse schedule string
        parts = schedule_str.lower().split()
        
        if parts[0] == "every":
            if len(parts) == 2:
                # "every minute", "every hour", etc.
                interval = parts[1].rstrip('s')
                job = getattr(schedule.every(), interval)
            elif len(parts) == 3 and parts[2] in ['minutes', 'hours', 'days', 'weeks']:
                # "every 5 minutes", etc.
                count = int(parts[1])
                interval = parts[2].rstrip('s')
                job = getattr(schedule.every(count), interval)
            else:
                raise ValueError(f"Invalid schedule string: {schedule_str}")
        elif parts[0] == "daily" and parts[1] == "at":
            # "daily at 10:30"
            time_str = parts[2]
            job = schedule.every().day.at(time_str)
        else:
            raise ValueError(f"Invalid schedule string: {schedule_str}")
        
        # Create task wrapper
        def task_wrapper():
            task = Task(
                id=f"{job_id}_{uuid.uuid4().hex[:8]}",
                name=f"Scheduled: {func.__name__}",
                func=func,
                args=args,
                kwargs=kwargs,
                priority=TaskPriority.NORMAL,
                metadata={'job_id': job_id, 'schedule': schedule_str}
            )
            self.task_manager.submit(task)
        
        job = job.do(task_wrapper)
        self.jobs[job_id] = job
        self.logger.info(f"Scheduled job {job_id}: {schedule_str}")
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job.
        
        Args:
            job_id: Job ID
            
        Returns:
            True if removed
        """
        if job_id in self.jobs:
            schedule.cancel_job(self.jobs[job_id])
            del self.jobs[job_id]
            self.logger.info(f"Removed scheduled job {job_id}")
            return True
        return False
    
    def get_jobs(self) -> List[Dict[str, Any]]:
        """Get list of scheduled jobs."""
        return [
            {
                'id': job_id,
                'next_run': str(job.next_run) if job.next_run else None,
                'interval': str(job.interval) if hasattr(job, 'interval') else None
            }
            for job_id, job in self.jobs.items()
        ]


class TaskManager(LoggerMixin):
    """Main task manager coordinating queue, workers, and scheduler."""
    
    def __init__(self, num_workers: int = 4, num_async_workers: int = 2,
                 max_queue_size: int = 1000):
        """Initialize task manager.
        
        Args:
            num_workers: Number of sync workers
            num_async_workers: Number of async workers
            max_queue_size: Maximum queue size
        """
        self.queue = TaskQueue(max_queue_size)
        self.workers: List[TaskWorker] = []
        self.async_workers: List[AsyncTaskWorker] = []
        self.scheduler = TaskScheduler(self)
        self.num_workers = num_workers
        self.num_async_workers = num_async_workers
        
        # Thread and process pools for advanced execution
        self.thread_pool = ThreadPoolExecutor(max_workers=num_workers)
        self.process_pool = ProcessPoolExecutor(max_workers=2)
    
    def start(self):
        """Start task manager."""
        # Start sync workers
        for i in range(self.num_workers):
            worker = TaskWorker(self.queue, f"worker_{i}")
            worker.start()
            self.workers.append(worker)
        
        # Start scheduler
        self.scheduler.start()
        
        self.logger.info(f"Task manager started with {self.num_workers} workers")
    
    async def start_async(self):
        """Start async components."""
        # Start async workers
        for i in range(self.num_async_workers):
            worker = AsyncTaskWorker(self.queue, f"async_worker_{i}")
            await worker.start()
            self.async_workers.append(worker)
        
        self.logger.info(f"Started {self.num_async_workers} async workers")
    
    def stop(self):
        """Stop task manager."""
        # Stop workers
        for worker in self.workers:
            worker.stop()
        
        # Stop scheduler
        self.scheduler.stop()
        
        # Shutdown pools
        self.thread_pool.shutdown(wait=True)
        self.process_pool.shutdown(wait=True)
        
        self.logger.info("Task manager stopped")
    
    async def stop_async(self):
        """Stop async components."""
        for worker in self.async_workers:
            await worker.stop()
    
    def submit(self, task: Union[Task, Callable], *args, **kwargs) -> str:
        """Submit a task for execution.
        
        Args:
            task: Task object or callable
            *args: Arguments if task is callable
            **kwargs: Keyword arguments if task is callable
            
        Returns:
            Task ID
        """
        if not isinstance(task, Task):
            # Create task from callable
            task = Task(
                id=str(uuid.uuid4()),
                name=task.__name__ if hasattr(task, '__name__') else str(task),
                func=task,
                args=args,
                kwargs=kwargs
            )
        
        return self.queue.enqueue(task)
    
    def schedule(self, func: Callable, schedule_str: str, job_id: Optional[str] = None,
                *args, **kwargs) -> str:
        """Schedule a periodic task.
        
        Args:
            func: Function to execute
            schedule_str: Schedule string
            job_id: Optional job ID
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Job ID
        """
        if job_id is None:
            job_id = str(uuid.uuid4())
        
        self.scheduler.add_job(job_id, func, schedule_str, *args, **kwargs)
        return job_id
    
    def cancel(self, task_id: str) -> bool:
        """Cancel a pending task.
        
        Args:
            task_id: Task ID
            
        Returns:
            True if cancelled
        """
        return self.queue.cancel_task(task_id)
    
    def get_result(self, task_id: str, wait: bool = False,
                   timeout: Optional[float] = None) -> Optional[TaskResult]:
        """Get task result.
        
        Args:
            task_id: Task ID
            wait: Wait for completion
            timeout: Wait timeout in seconds
            
        Returns:
            Task result or None
        """
        if wait:
            start_time = time.time()
            while True:
                result = self.queue.get_result(task_id)
                if result and result.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    return result
                
                if timeout and (time.time() - start_time) > timeout:
                    return None
                
                time.sleep(0.1)
        else:
            return self.queue.get_result(task_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get task manager statistics."""
        stats = self.queue.get_stats()
        stats.update({
            'workers': len(self.workers),
            'async_workers': len(self.async_workers),
            'scheduled_jobs': len(self.scheduler.jobs)
        })
        return stats


# Task decorator for easy task creation
def task(name: Optional[str] = None, priority: TaskPriority = TaskPriority.NORMAL,
         max_retries: int = 3, timeout: Optional[int] = None):
    """Decorator to create a task from a function.
    
    Args:
        name: Task name
        priority: Task priority
        max_retries: Maximum retry attempts
        timeout: Execution timeout in seconds
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            task_obj = Task(
                id=str(uuid.uuid4()),
                name=name or func.__name__,
                func=func,
                args=args,
                kwargs=kwargs,
                priority=priority,
                max_retries=max_retries,
                timeout=timeout
            )
            return task_obj
        
        wrapper.delay = lambda *args, **kwargs: get_task_manager().submit(
            wrapper(*args, **kwargs)
        )
        
        return wrapper
    return decorator


# Singleton instance
_task_manager: Optional[TaskManager] = None


def get_task_manager(num_workers: int = 4, num_async_workers: int = 2,
                     max_queue_size: int = 1000) -> TaskManager:
    """Get or create task manager instance.
    
    Args:
        num_workers: Number of sync workers
        num_async_workers: Number of async workers
        max_queue_size: Maximum queue size
        
    Returns:
        TaskManager instance
    """
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager(num_workers, num_async_workers, max_queue_size)
        _task_manager.start()
    return _task_manager