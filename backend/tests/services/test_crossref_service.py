import unittest

from app.services.crossref_service import CrossrefService


class CrossrefServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = CrossrefService()

    def test_normalize_work_extracts_core_metadata(self) -> None:
        item = {
            "DOI": "https://doi.org/10.5555/ABC.DEF",
            "title": ["Attention Is All You Need"],
            "author": [
                {"given": "Ashish", "family": "Vaswani"},
                {"name": "Noam Shazeer"},
            ],
            "published-print": {"date-parts": [[2017, 12, 1]]},
            "container-title": ["Advances in Neural Information Processing Systems"],
            "abstract": "<jats:p>We propose a new simple network architecture.</jats:p>",
        }

        normalized = self.service.normalize_work(item)

        self.assertEqual(normalized["doi"], "10.5555/abc.def")
        self.assertEqual(normalized["title"], "Attention Is All You Need")
        self.assertEqual(normalized["authors"], ["Ashish Vaswani", "Noam Shazeer"])
        self.assertEqual(normalized["year"], 2017)
        self.assertEqual(
            normalized["venue"],
            "Advances in Neural Information Processing Systems",
        )
        self.assertEqual(
            normalized["abstract"],
            "We propose a new simple network architecture.",
        )

    def test_verify_metadata_marks_matching_fields_as_verified(self) -> None:
        item = {
            "DOI": "10.5555/abc",
            "title": ["Attention Is All You Need"],
            "author": [
                {"given": "Ashish", "family": "Vaswani"},
                {"given": "Noam", "family": "Shazeer"},
            ],
            "issued": {"date-parts": [[2017]]},
            "container-title": ["NeurIPS"],
            "abstract": "A transformer model for sequence transduction.",
        }
        self.service._get_by_doi = lambda _doi: (item, False, None)

        result = self.service.verify_metadata(
            {
                "source": "semantic_scholar",
                "doi": "10.5555/ABC",
                "title": "Attention is All You Need",
                "authors": ["Ashish Vaswani", "Noam Shazeer"],
                "year": 2017,
                "venue": "NeurIPS",
                "abstract": "A transformer model for sequence transduction.",
            }
        )

        self.assertEqual(result["status"], "verified")
        self.assertGreaterEqual(result["confidence"], 0.9)
        self.assertEqual(result["fields"]["doi"]["status"], "match")
        self.assertEqual(result["fields"]["title"]["status"], "match")
        self.assertEqual(result["fields"]["authors"]["status"], "match")
        self.assertEqual(result["fields"]["year"]["status"], "match")
        self.assertEqual(result["fields"]["venue"]["status"], "match")
        self.assertEqual(result["fields"]["abstract"]["status"], "match")

    def test_authors_match_with_initials_and_diacritics(self) -> None:
        result = self.service._compare_authors(
            ["Alessandro Raganato", "J. Tiedemann"],
            ["Alessandro Raganato", "Jörg Tiedemann"],
        )

        self.assertEqual(result["status"], "match")
        self.assertGreaterEqual(result["score"], 0.8)
        self.assertTrue(result["first_author_matches"])

    def test_venue_matches_abbreviation_inside_long_proceedings_title(self) -> None:
        result = self.service._compare_venue(
            "BlackboxNLP@EMNLP",
            (
                "Proceedings of the 2018 EMNLP Workshop BlackboxNLP: "
                "Analyzing and Interpreting Neural Networks for NLP"
            ),
        )

        self.assertEqual(result["status"], "match")
        self.assertGreaterEqual(result["score"], 0.8)
        self.assertIn("blackbox", result["shared_tokens"])
        self.assertIn("emnlp", result["shared_tokens"])

    def test_verify_metadata_handles_common_author_and_venue_abbreviations(self) -> None:
        item = {
            "DOI": "10.18653/v1/w18-5401",
            "title": ["An Analysis of Encoder Representations in Transformer-Based Machine Translation"],
            "author": [
                {"given": "Alessandro", "family": "Raganato"},
                {"given": "Jörg", "family": "Tiedemann"},
            ],
            "issued": {"date-parts": [[2018]]},
            "container-title": [
                (
                    "Proceedings of the 2018 EMNLP Workshop BlackboxNLP: "
                    "Analyzing and Interpreting Neural Networks for NLP"
                )
            ],
        }
        self.service._get_by_doi = lambda _doi: (item, False, None)

        result = self.service.verify_metadata(
            {
                "source": "semantic_scholar",
                "doi": "10.18653/v1/w18-5401",
                "title": "An Analysis of Encoder Representations in Transformer-Based Machine Translation",
                "authors": ["Alessandro Raganato", "J. Tiedemann"],
                "year": 2018,
                "venue": "BlackboxNLP@EMNLP",
            }
        )

        self.assertIn(result["status"], {"verified", "partial"})
        self.assertNotIn("authors", result["conflicts"])
        self.assertNotIn("venue", result["conflicts"])
        self.assertEqual(result["fields"]["authors"]["status"], "match")
        self.assertEqual(result["fields"]["venue"]["status"], "match")

    def test_verify_metadata_marks_conflicting_crossref_candidate(self) -> None:
        item = {
            "DOI": "10.5555/resnet",
            "title": ["Deep Residual Learning for Image Recognition"],
            "author": [
                {"given": "Kaiming", "family": "He"},
                {"given": "Xiangyu", "family": "Zhang"},
            ],
            "issued": {"date-parts": [[2016]]},
            "container-title": ["CVPR"],
        }
        self.service._get_by_doi = lambda _doi: (item, False, None)

        result = self.service.verify_metadata(
            {
                "source": "semantic_scholar",
                "doi": "10.5555/attention",
                "title": "Attention Is All You Need",
                "authors": ["Ashish Vaswani", "Noam Shazeer"],
                "year": 2017,
                "venue": "NeurIPS",
            }
        )

        self.assertEqual(result["status"], "conflict")
        self.assertIn("doi", result["conflicts"])
        self.assertIn("title", result["conflicts"])
        self.assertIn("authors", result["conflicts"])


if __name__ == "__main__":
    unittest.main()
