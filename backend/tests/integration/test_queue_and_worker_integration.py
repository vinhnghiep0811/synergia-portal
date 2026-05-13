"""Integration tests: queue and worker orchestration."""

from tests.integration.fixtures import IntegrationEphemeralTestCase


class QueueAndWorkerIntegrationTests(IntegrationEphemeralTestCase):
    def test_enqueue_job_keeps_stage_and_payload(self) -> None:
        job = self.workflow.enqueue_stage("parse", {"paper_id": "p1"})

        self.assertEqual(job["stage"], "parse")
        self.assertEqual(job["payload"]["paper_id"], "p1")
        self.assertEqual(self.workflow.queue.size, 1)

    def test_queue_preserves_fifo_order(self) -> None:
        self.workflow.enqueue_stage("parse", {"paper_id": "p1"})
        self.workflow.enqueue_stage("docling", {"paper_id": "p1"})

        first = self.workflow.queue.pop_next()
        second = self.workflow.queue.pop_next()

        self.assertEqual(first["stage"], "parse")
        self.assertEqual(second["stage"], "docling")

    def test_upload_then_enqueue_parse_job(self) -> None:
        paper_id = self.workflow.upload_pdf("paper.pdf", b"%PDF-1.4\ncontent")
        self.workflow.enqueue_stage("parse", {"paper_id": paper_id})

        popped = self.workflow.queue.pop_next()
        self.assertEqual(popped["payload"]["paper_id"], paper_id)

    def test_pop_next_on_empty_queue_returns_none(self) -> None:
        self.assertIsNone(self.workflow.queue.pop_next())
