import os

from redis import Redis
from rq import Worker


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
RQ_PARSE_QUEUE = os.getenv("RQ_PARSE_QUEUE", "parse_queue")


def main() -> None:
    redis_conn = Redis.from_url(REDIS_URL)
    worker = Worker([RQ_PARSE_QUEUE], connection=redis_conn)
    worker.work()


if __name__ == "__main__":
    main()