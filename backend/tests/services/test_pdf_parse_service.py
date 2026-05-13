import unittest
from unittest.mock import MagicMock, patch

from app.services.pdf_parse_service import (
    _is_non_title_text,
    _looks_broken,
    _looks_like_author_line,
    _select_title_from_lines,
    build_fingerprint,
    detect_title,
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

    def test_detect_doi_ignores_number_prefixed_pattern(self) -> None:
        text = "Version 110.1000/ABC should not match as DOI."

        result = detect_doi(text)

        self.assertIsNone(result)

    def test_detect_doi_accepts_complex_suffix_characters(self) -> None:
        text = "Refer to DOI 10.1234/ABC.DEF:12/XYZ for details."

        result = detect_doi(text)

        self.assertEqual(result, "10.1234/abc.def:12/xyz")


class NormalizeDoiTests(unittest.TestCase):
    def test_normalize_doi_strips_whitespace_and_trailing_punctuation(self) -> None:
        raw = "  10.1000/ABC-123_XYZ).,;:]}  "

        result = normalize_doi(raw)

        self.assertEqual(result, "10.1000/abc-123_xyz")

    def test_normalize_doi_lowercases_and_trims(self) -> None:
        raw = "\n\t10.7777/TeSt.CaSe\t"

        result = normalize_doi(raw)

        self.assertEqual(result, "10.7777/test.case")

    def test_normalize_doi_strips_nul_chars(self) -> None:
        raw = "\x0010.1000/ABC\x00"

        result = normalize_doi(raw)

        self.assertEqual(result, "10.1000/abc")

    def test_normalize_doi_keeps_internal_parentheses(self) -> None:
        raw = "10.1000/ABC(DEF)ghi"

        result = normalize_doi(raw)

        self.assertEqual(result, "10.1000/abc(def)ghi")


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

    def test_normalize_text_for_fingerprint_removes_nul_and_collapses_space(self) -> None:
        text = "A\x00B\t\tC\n\nD"

        result = normalize_text_for_fingerprint(text)

        self.assertEqual(result, "ab c d")

    def test_build_fingerprint_normalizes_title_and_text_inputs(self) -> None:
        hash_a = build_fingerprint("Graph based Reasoning!", title="A Study on LLMs")
        hash_b = build_fingerprint(" graph based   reasoning ", title="a study on llms")

        self.assertEqual(hash_a, hash_b)

    def test_build_fingerprint_raises_when_text_and_title_normalize_empty(self) -> None:
        with self.assertRaises(ValueError):
            build_fingerprint("!!!", title="@@@")


class TitleHeuristicsTests(unittest.TestCase):
    def test_looks_like_author_line_detects_multiple_names(self) -> None:
        result = _looks_like_author_line("John Doe, Jane Smith")

        self.assertTrue(result)

    def test_looks_like_author_line_rejects_affiliation_like_text(self) -> None:
        result = _looks_like_author_line("Department of Computer Science, University of X")

        self.assertFalse(result)

    def test_is_non_title_text_flags_author_lines(self) -> None:
        result = _is_non_title_text("John Doe, Jane Smith")

        self.assertTrue(result)

    def test_is_non_title_text_allows_valid_title(self) -> None:
        result = _is_non_title_text("A Neural Approach for Graph Reasoning")

        self.assertFalse(result)

    def test_looks_broken_detects_ligature_fragment_lines(self) -> None:
        lines = [{"text": "fi"}, {"text": "A normal title line"}]

        result = _looks_broken(lines)

        self.assertTrue(result)

    def test_looks_broken_detects_dense_unspaced_lines(self) -> None:
        lines = [
            {"text": "ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"},
            {"text": "MNOPQRSTUVWXYZABCDEFGHIJKLMN7890"},
            {"text": "Readable text line"},
        ]

        result = _looks_broken(lines)

        self.assertTrue(result)

    def test_select_title_from_lines_combines_adjacent_high_score_lines(self) -> None:
        lines = [
            {"text": "DOI: 10.1000/xyz", "top": 12, "x0": 80, "x1": 250, "avg_size": 11},
            {
                "text": "A Practical Graph Reasoning Framework",
                "top": 40,
                "x0": 110,
                "x1": 500,
                "avg_size": 18,
            },
            {
                "text": "for Large Language Models",
                "top": 58,
                "x0": 150,
                "x1": 460,
                "avg_size": 17.6,
            },
            {"text": "Abstract", "top": 95, "x0": 100, "x1": 220, "avg_size": 13},
        ]

        result = _select_title_from_lines(lines, page_width=600)

        self.assertEqual(result, "A Practical Graph Reasoning Framework for Large Language Models")

    def test_select_title_from_lines_penalizes_all_caps_banner(self) -> None:
        lines = [
            {
                "text": "ADVANCES IN GRAPH REASONING FOR FOUNDATION MODELS",
                "top": 0,
                "x0": 40,
                "x1": 560,
                "avg_size": 20,
            },
            {
                "text": "Advances in Graph Reasoning for Foundation Models",
                "top": 40,
                "x0": 60,
                "x1": 540,
                "avg_size": 20,
            },
        ]

        result = _select_title_from_lines(lines, page_width=600)

        self.assertEqual(result, "Advances in Graph Reasoning for Foundation Models")


class DetectTitleTests(unittest.TestCase):
    @staticmethod
    def _mock_pdf_context(page_width: float = 600) -> MagicMock:
        page = MagicMock()
        page.width = page_width
        pdf = MagicMock()
        pdf.pages = [page]
        ctx = MagicMock()
        ctx.__enter__.return_value = pdf
        ctx.__exit__.return_value = False
        return ctx

    def test_detect_title_returns_none_when_pdf_has_no_pages(self) -> None:
        pdf = MagicMock()
        pdf.pages = []
        ctx = MagicMock()
        ctx.__enter__.return_value = pdf
        ctx.__exit__.return_value = False

        with patch("app.services.pdf_parse_service.pdfplumber.open", return_value=ctx):
            result = detect_title("dummy.pdf")

        self.assertIsNone(result)

    def test_detect_title_prefers_word_lines_when_not_broken(self) -> None:
        word_lines = [{"text": "Word Title", "top": 20, "x0": 80, "x1": 420, "avg_size": 18}]
        ctx = self._mock_pdf_context()

        with (
            patch("app.services.pdf_parse_service.pdfplumber.open", return_value=ctx),
            patch("app.services.pdf_parse_service._extract_lines_from_words", return_value=word_lines),
            patch("app.services.pdf_parse_service._looks_broken", return_value=False),
            patch("app.services.pdf_parse_service._extract_lines_from_chars") as chars_mock,
            patch("app.services.pdf_parse_service._select_title_from_lines", return_value="Word Title") as select_mock,
        ):
            result = detect_title("dummy.pdf")

        self.assertEqual(result, "Word Title")
        chars_mock.assert_not_called()
        select_mock.assert_called_once_with(word_lines, 600)

    def test_detect_title_falls_back_to_chars_when_word_lines_look_broken(self) -> None:
        word_lines = [{"text": "fi", "top": 15, "x0": 40, "x1": 60, "avg_size": 10}]
        char_lines = [{"text": "Recovered Char Title", "top": 25, "x0": 90, "x1": 480, "avg_size": 18}]
        ctx = self._mock_pdf_context()

        with (
            patch("app.services.pdf_parse_service.pdfplumber.open", return_value=ctx),
            patch("app.services.pdf_parse_service._extract_lines_from_words", return_value=word_lines),
            patch("app.services.pdf_parse_service._looks_broken", return_value=True),
            patch("app.services.pdf_parse_service._extract_lines_from_chars", return_value=char_lines),
            patch("app.services.pdf_parse_service._select_title_from_lines", return_value="Recovered Char Title") as select_mock,
        ):
            result = detect_title("dummy.pdf")

        self.assertEqual(result, "Recovered Char Title")
        select_mock.assert_called_once_with(char_lines, 600)

    def test_detect_title_uses_final_word_fallback_when_char_path_fails(self) -> None:
        word_lines = [{"text": "Fallback Word Title", "top": 30, "x0": 100, "x1": 420, "avg_size": 16}]
        ctx = self._mock_pdf_context()

        with (
            patch("app.services.pdf_parse_service.pdfplumber.open", return_value=ctx),
            patch("app.services.pdf_parse_service._extract_lines_from_words", return_value=word_lines),
            patch("app.services.pdf_parse_service._looks_broken", return_value=False),
            patch("app.services.pdf_parse_service._extract_lines_from_chars", return_value=[]),
            patch(
                "app.services.pdf_parse_service._select_title_from_lines",
                side_effect=[None, "Fallback Word Title"],
            ) as select_mock,
        ):
            result = detect_title("dummy.pdf")

        self.assertEqual(result, "Fallback Word Title")
        self.assertEqual(select_mock.call_count, 2)
        select_mock.assert_any_call(word_lines, 600)


if __name__ == "__main__":
    unittest.main()
