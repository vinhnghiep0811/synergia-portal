import unittest

from app.services.pdf_parse_service import (
    build_fingerprint,
    detect_doi,
    normalize_doi,
    normalize_text_for_fingerprint,
)


class DetectDoiTests(unittest.TestCase):
    def test_detect_doi_returns_normalized_standard_doi(self) -> None:
        text = "This paper is identified by DOI 10.1038/nphys1170."

        result = detect_doi(text)

        self.assertEqual(result, "10.1038/nphys1170")

    def test_detect_doi_finds_doi_inside_noisy_text(self) -> None:
        text = (
            "Random header ### ref[12] -- downloaded copy -- "
            "visit https://doi.org/10.1000/ABC-123_XYZ), for metadata."
        )

        result = detect_doi(text)

        self.assertEqual(result, "10.1000/abc-123_xyz")

    def test_detect_doi_returns_none_when_text_has_no_doi(self) -> None:
        text = "This extracted text contains title, abstract, and references but no DOI marker."

        result = detect_doi(text)

        self.assertIsNone(result)


class NormalizeDoiTests(unittest.TestCase):
    def test_normalize_doi_strips_whitespace_and_trailing_punctuation(self) -> None:
        raw = "  10.1000/ABC-123_XYZ).,;:]}  "

        result = normalize_doi(raw)

        self.assertEqual(result, "10.1000/abc-123_xyz")


class FingerprintTests(unittest.TestCase):
    def test_normalize_text_for_fingerprint_removes_special_chars(self) -> None:
        text = "  Graph-Based,\nReasoning!\tFor   LLMs? 2026  "

        result = normalize_text_for_fingerprint(text)

        self.assertEqual(result, "graphbased reasoning for llms 2026")

    def test_build_fingerprint_returns_stable_hash_for_same_input(self) -> None:
        text = "A simple body text for hashing."
        title = "A Test Paper"

        hash_1 = build_fingerprint(text, title=title)
        hash_2 = build_fingerprint(text, title=title)

        self.assertEqual(hash_1, hash_2)

    def test_build_fingerprint_changes_when_input_changes(self) -> None:
        base_hash = build_fingerprint("This is body text.", title="Paper A")
        changed_title_hash = build_fingerprint("This is body text.", title="Paper B")
        changed_text_hash = build_fingerprint("This is another body text.", title="Paper A")

        self.assertNotEqual(base_hash, changed_title_hash)
        self.assertNotEqual(base_hash, changed_text_hash)

    def test_build_fingerprint_raises_for_empty_content(self) -> None:
        with self.assertRaises(ValueError):
            build_fingerprint("   \n\t!!!", title=None)


if __name__ == "__main__":
    unittest.main()
