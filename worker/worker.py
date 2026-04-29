import os
import sys
import logging
from pathlib import Path

from dotenv import load_dotenv
from redis import Redis
from rq import Worker, Queue, SimpleWorker

WORKER_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = WORKER_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BACKEND_DIR / ".env")

for path in (str(WORKER_DIR), str(BACKEND_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import app.models  # noqa: F401


# Import task modules để RQ có thể resolve function
import worker_app.tasks.pdf_parse  # noqa: F401
import worker_app.tasks.semantic_scholar  # noqa: F401
import worker_app.tasks.llm_extract  # noqa: F401
import worker_app.tasks.build_structure  # noqa: F401
import worker_app.tasks.generate_embedding  # noqa: F401
import worker_app.tasks.citation_graph  # noqa: F401

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Ví dụ:
# WORKER_QUEUES=parse_queue
# WORKER_QUEUES=structure_queue
# WORKER_QUEUES=embedding_queue
# WORKER_QUEUES=parse_queue,structure_queue
QUEUE_NAMES = os.getenv("WORKER_QUEUES") or os.getenv("RQ_PARSE_QUEUE", "parse_queue")

redis_conn = Redis.from_url(REDIS_URL)
queues = [
    Queue(name.strip(), connection=redis_conn)
    for name in QUEUE_NAMES.split(",")
    if name.strip()
]

if __name__ == "__main__":
    log_level_name = os.getenv("WORKER_LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    logging.info("Starting worker")
    logging.info("Redis URL: %s", REDIS_URL)
    logging.info("Listening queues: %s", [q.name for q in queues])

    use_simple_worker = sys.platform == "darwin" and os.getenv("RQ_USE_FORK", "0") != "1"
    worker_cls = SimpleWorker if use_simple_worker else Worker

    worker = worker_cls(queues, connection=redis_conn)
    worker.work()