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

    def test_detect_doi_returns_first_match_when_text_has_multiple_dois(self) -> None:
        text = "See 10.1000/AAA-1 first and 10.2000/BBB-2 second."

        result = detect_doi(text)

        self.assertEqual(result, "10.1000/aaa-1")

    def test_detect_doi_handles_nul_characters(self) -> None:
        text = "\x00DOI: 10.5555/ABC.123\x00"

        result = detect_doi(text)

        self.assertEqual(result, "10.5555/abc.123")


class NormalizeDoiTests(unittest.TestCase):
    def test_normalize_doi_strips_whitespace_and_trailing_punctuation(self) -> None:
        raw = "  10.1000/ABC-123_XYZ).,;:]}  "

        result = normalize_doi(raw)

        self.assertEqual(result, "10.1000/abc-123_xyz")

    def test_normalize_doi_lowercases_and_trims(self) -> None:
        raw = "\n\t10.7777/TeSt.CaSe\t"

        result = normalize_doi(raw)

        self.assertEqual(result, "10.7777/test.case")


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

    def test_normalize_text_for_fingerprint_returns_empty_for_symbols_only(self) -> None:
        result = normalize_text_for_fingerprint(" \n\t!!!@@@### ")

        self.assertEqual(result, "")

    def test_build_fingerprint_uses_title_when_text_is_empty(self) -> None:
        result = build_fingerprint("  ", title="Only Title")

        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 64)

    def test_build_fingerprint_respects_max_chars_limit(self) -> None:
        text_a = ("prefix " * 700) + "X-tail"
        text_b = ("prefix " * 700) + "Y-tail"

        hash_a = build_fingerprint(text_a, title="Paper", max_chars=4000)
        hash_b = build_fingerprint(text_b, title="Paper", max_chars=4000)

        self.assertEqual(hash_a, hash_b)


if __name__ == "__main__":
    unittest.main()
