import os
import uuid

from redis import Redis
from rq import Queue

from tasks.pdf_parse import pdf_parse


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
QUEUE_NAME = os.getenv("RQ_PARSE_QUEUE", "parse_queue")


def main():
    redis_conn = Redis.from_url(REDIS_URL)
    queue = Queue(QUEUE_NAME, connection=redis_conn)

    paper_id = str(uuid.uuid4())

    job = queue.enqueue(pdf_parse, paper_id)

    print("Enqueued pdf_parse job")
    print("paper_id:", paper_id)
    print("job_id:", job.id)


if __name__ == "__main__":
    main()