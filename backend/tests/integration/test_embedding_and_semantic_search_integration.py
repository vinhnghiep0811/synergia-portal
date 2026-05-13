"""Integration tests: embedding generation and semantic search."""

import json

from tests.integration.fixtures import IntegrationEphemeralTestCase


class EmbeddingAndSemanticSearchIntegrationTests(IntegrationEphemeralTestCase):
    def test_create_embeddings_for_all_chunks(self) -> None:
        paper_id = self.workflow.upload_pdf("emb.pdf", b"%PDF-1.4\nemb")
        key = self.workflow.parse_and_map(paper_id, "DOI: 10.7878/emb")["canonical_key"]
        self.workflow.build_structure(key, "method details\n\ndataset details")

        created = self.workflow.create_embeddings(key)
        chunks = self.workflow.chunks_for(key)

        self.assertEqual(created, 2)
        self.assertTrue(all(chunk["embedding_json"] for chunk in chunks))

    def test_semantic_search_prefers_method_chunk_for_method_query(self) -> None:
        paper_id = self.workflow.upload_pdf("s.pdf", b"%PDF-1.4\ns")
        key = self.workflow.parse_and_map(paper_id, "DOI: 10.7878/search")["canonical_key"]
        self.workflow.build_structure(
            key,
            "This section explains the method and algorithm.\n\nThis section lists dataset and benchmark.",
        )
        self.workflow.create_embeddings(key)

        results = self.workflow.semantic_search("method algorithm", top_k=1)
        self.assertEqual(len(results), 1)
        self.assertIn("method", results[0]["content"].lower())

    def test_semantic_search_applies_top_k_limit(self) -> None:
        paper_id = self.workflow.upload_pdf("k.pdf", b"%PDF-1.4\nk")
        key = self.workflow.parse_and_map(paper_id, "DOI: 10.7878/topk")["canonical_key"]
        self.workflow.build_structure(key, "a\n\nb\n\nc\n\nd")
        self.workflow.create_embeddings(key)

        results = self.workflow.semantic_search("method", top_k=2)
        self.assertEqual(len(results), 2)

    def test_semantic_search_returns_empty_when_no_embeddings(self) -> None:
        results = self.workflow.semantic_search("anything", top_k=3)
        self.assertEqual(results, [])

    def test_embedding_fallback_uses_hash_for_text_without_keywords(self) -> None:
        paper_id = self.workflow.upload_pdf("hash.pdf", b"%PDF-1.4\nhash")
        key = self.workflow.parse_and_map(paper_id, "DOI: 10.7878/hash")["canonical_key"]
        self.workflow.build_structure(key, "plain text with no signals")

        self.workflow.create_embeddings(key)
        chunks = self.workflow.chunks_for(key)
        embedding = json.loads(chunks[0]["embedding_json"])

        self.assertTrue(any(value > 0 for value in embedding))

    def test_cosine_returns_zero_for_zero_vector(self) -> None:
        score = self.workflow._cosine([0.0, 0.0, 0.0], [1.0, 0.0, 0.0])

        self.assertEqual(score, 0.0)
