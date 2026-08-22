"""Linux production defaults for a 4-core/8-GB host behind Nginx."""
import multiprocessing
import os

bind = f"{os.getenv('SERVER_HOST', '127.0.0.1')}:{os.getenv('SERVER_PORT', '8899')}"
workers = int(os.getenv("GUNICORN_WORKERS", str(min(4, max(2, multiprocessing.cpu_count())))))
threads = int(os.getenv("GUNICORN_THREADS", "8"))
worker_class = "gthread"
worker_connections = 1000
timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
graceful_timeout = 30
keepalive = 5
max_requests = 10000
max_requests_jitter = 1000
accesslog = "-" if os.getenv("ENABLE_HTTP_ACCESS_LOG", "False").lower() == "true" else None
errorlog = "-"
preload_app = False


def post_worker_init(worker):
    # Per-process queues must run in every worker; global schedulers use systemd.
    from app import start_web_process_services
    start_web_process_services()
