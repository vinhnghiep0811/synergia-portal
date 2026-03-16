from redis import Redis
from rq import Queue

from app.core.config import REDIS_URL, RQ_PARSE_QUEUE

redis_conn = Redis.from_url(REDIS_URL)
parse_queue = Queue(RQ_PARSE_QUEUE, connection=redis_conn)