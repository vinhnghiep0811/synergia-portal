from app.core.queue import parse_queue


class QueueService:
    def enqueue_pdf_parse(self, paper_id: str):
        return parse_queue.enqueue(
            "worker_app.tasks.pdf_parse.pdf_parse",
            paper_id
        )