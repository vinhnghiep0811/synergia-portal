"""Integration tests: citation graph scoring."""

from tests.integration.fixtures import IntegrationEphemeralTestCase


class CitationGraphScoringIntegrationTests(IntegrationEphemeralTestCase):
    def test_score_is_sum_of_incoming_weights(self) -> None:
        p1 = self.workflow.upload_pdf("a.pdf", b"%PDF-1.4\na")
        p2 = self.workflow.upload_pdf("b.pdf", b"%PDF-1.4\nb")
        p3 = self.workflow.upload_pdf("c.pdf", b"%PDF-1.4\nc")
        k1 = self.workflow.parse_and_map(p1, "DOI: 10.1111/a")["canonical_key"]
        k2 = self.workflow.parse_and_map(p2, "DOI: 10.1111/b")["canonical_key"]
        k3 = self.workflow.parse_and_map(p3, "DOI: 10.1111/c")["canonical_key"]

        self.workflow.add_citation(k1, k3, 0.7)
        self.workflow.add_citation(k2, k3, 0.5)

        score = self.workflow.score_citation_graph(k3)
        self.assertAlmostEqual(score, 1.2, places=6)

    def test_score_is_zero_without_incoming_edges(self) -> None:
        p = self.workflow.upload_pdf("x.pdf", b"%PDF-1.4\nx")
        key = self.workflow.parse_and_map(p, "DOI: 10.2222/x")["canonical_key"]

        score = self.workflow.score_citation_graph(key)
        self.assertEqual(score, 0.0)

    def test_multiple_edges_between_same_pair_accumulate(self) -> None:
        s = self.workflow.parse_and_map(
            self.workflow.upload_pdf("s.pdf", b"%PDF-1.4\ns"),
            "DOI: 10.3333/s",
        )["canonical_key"]
        t = self.workflow.parse_and_map(
            self.workflow.upload_pdf("t.pdf", b"%PDF-1.4\nt"),
            "DOI: 10.3333/t",
        )["canonical_key"]

        self.workflow.add_citation(s, t, 0.2)
        self.workflow.add_citation(s, t, 0.4)
        self.assertAlmostEqual(self.workflow.score_citation_graph(t), 0.6, places=6)

    def test_scoring_is_scoped_per_target(self) -> None:
        src = self.workflow.parse_and_map(
            self.workflow.upload_pdf("src.pdf", b"%PDF-1.4\nsrc"),
            "DOI: 10.4444/src",
        )["canonical_key"]
        t1 = self.workflow.parse_and_map(
            self.workflow.upload_pdf("t1.pdf", b"%PDF-1.4\nt1"),
            "DOI: 10.4444/t1",
        )["canonical_key"]
        t2 = self.workflow.parse_and_map(
            self.workflow.upload_pdf("t2.pdf", b"%PDF-1.4\nt2"),
            "DOI: 10.4444/t2",
        )["canonical_key"]

        self.workflow.add_citation(src, t1, 0.3)
        self.workflow.add_citation(src, t2, 0.9)

        self.assertAlmostEqual(self.workflow.score_citation_graph(t1), 0.3, places=6)
        self.assertAlmostEqual(self.workflow.score_citation_graph(t2), 0.9, places=6)
