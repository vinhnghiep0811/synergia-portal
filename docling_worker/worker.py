import os
import logging
from redis import Redis
from rq import Worker, SimpleWorker
import app.models
from app.core.config import REDIS_URL, RQ_DOCLING_QUEUE


def main() -> None:
    # --- logging config ---
    log_level_name = os.getenv("WORKER_LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,  # 👈 QUAN TRỌNG
    )

    logging.info("Docling worker started")

    # --- worker init ---
    redis_conn = Redis.from_url(REDIS_URL)

    use_simple_worker = os.getenv("RQ_USE_FORK", "1") != "1"
    worker_cls = SimpleWorker if use_simple_worker else Worker

    worker = worker_cls([RQ_DOCLING_QUEUE], connection=redis_conn)
    worker.work()


if __name__ == "__main__":
    main()