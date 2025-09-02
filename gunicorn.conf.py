"""
Gunicorn configuration file for Ghost Backend Framework

This configuration is optimized for production deployment in Docker containers.
"""

import multiprocessing
import os

# Server socket
bind = f"{os.environ.get('API_HOST', '0.0.0.0')}:{os.environ.get('API_PORT', '8888')}"
backlog = 2048

# Worker processes
workers = int(os.environ.get('WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'uvicorn.workers.UvicornWorker'
worker_connections = 2000
max_requests = 10000
max_requests_jitter = 50
timeout = 120
graceful_timeout = 30
keepalive = 5

# Process naming
proc_name = 'ghost-backend'

# Logging
accesslog = '-'  # Log to stdout
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'
errorlog = '-'  # Log to stderr
loglevel = os.environ.get('LOG_LEVEL', 'info').lower()
capture_output = True
enable_stdio_inheritance = True

# Server mechanics
daemon = False
pidfile = None
user = None  # Run as current user (ghost in Docker)
group = None
tmp_upload_dir = '/app/temp'

# SSL (if needed, configure in reverse proxy instead)
keyfile = None
certfile = None

# Stats
statsd_host = os.environ.get('STATSD_HOST')
if statsd_host:
    statsd_prefix = 'ghost.backend'

def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT."""
    worker.log.info(f"Worker {worker.pid} interrupted")

def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    worker.log.warning(f"Worker {worker.pid} aborted")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    server.log.debug(f"Forking worker {worker}")

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info(f"Worker {worker.pid} spawned")

def pre_exec(server):
    """Called just before a new master process is forked."""
    server.log.info("Forking new master process")

def when_ready(server):
    """Called just after the server is started."""
    server.log.info("Ghost Backend is ready. Listening at: %s", server.address)

def worker_exit(server, worker):
    """Called just after a worker has been exited."""
    server.log.info(f"Worker {worker.pid} exited")

def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("Starting Ghost Backend Framework")
    server.log.info(f"Workers: {workers}")
    server.log.info(f"Worker class: {worker_class}")

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    server.log.info("Reloading Ghost Backend workers")

def on_exit(server):
    """Called just before exiting."""
    server.log.info("Shutting down Ghost Backend Framework")