from redis import Redis
from rq import Queue

from app.core.config import REDIS_URL, RQ_PARSE_QUEUE, RQ_DOCLING_QUEUE, RQ_STRUCTURE_QUEUE, RQ_EMBEDDING_QUEUE

redis_conn = Redis.from_url(REDIS_URL)
docling_queue = Queue(RQ_DOCLING_QUEUE, connection=redis_conn, default_timeout=600,)
parse_queue = Queue(RQ_PARSE_QUEUE, connection=redis_conn)

structure_queue = Queue(RQ_STRUCTURE_QUEUE, connection=redis_conn)
embedding_queue = Queue(RQ_EMBEDDING_QUEUE, connection=redis_conn)