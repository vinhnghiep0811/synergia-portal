import os
import sys
from pathlib import Path

from redis import Redis
from rq import Worker, Queue, SimpleWorker

WORKER_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = WORKER_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"

for path in (str(WORKER_DIR), str(BACKEND_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import worker_app.tasks.pdf_parse  # noqa: F401

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
QUEUE_NAME = os.getenv("RQ_PARSE_QUEUE", "parse_queue")

redis_conn = Redis.from_url(REDIS_URL)
queue = Queue(QUEUE_NAME, connection=redis_conn)

if __name__ == "__main__":
    use_simple_worker = sys.platform == "darwin" and os.getenv("RQ_USE_FORK", "0") != "1"
    worker_cls = SimpleWorker if use_simple_worker else Worker
    worker = worker_cls([queue], connection=redis_conn)
    worker.work()