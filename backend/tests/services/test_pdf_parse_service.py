import unittest

from app.services.pdf_parse_service import (
    _is_non_title_text,
    _select_title_from_lines,
    detect_doi,
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

    def test_detect_doi_ignores_reference_section_doi(self) -> None:
        text = (
            "A Paper Without A DOI\n"
            "Abstract\n"
            "This paper has no DOI on the title page.\n\n"
            "References\n"
            "[1] Related work. DOI 10.5555/reference-only."
        )

        result = detect_doi(text)

        self.assertIsNone(result)

    def test_detect_doi_prefers_labeled_front_matter_doi(self) -> None:
        text = (
            "A Paper With DOI\n"
            "DOI: 10.1234/CORRECT.2024.001\n"
            "Abstract\n"
            "Main text.\n\n"
            "References\n"
            "[1] Related work. DOI 10.5555/reference-only."
        )

        result = detect_doi(text)

        self.assertEqual(result, "10.1234/correct.2024.001")

    def test_detect_doi_returns_none_when_text_has_no_doi(self) -> None:
        text = "This extracted text contains title, abstract, and references but no DOI marker."

        result = detect_doi(text)

        self.assertIsNone(result)


class DetectTitleTests(unittest.TestCase):
    def test_publication_date_header_is_not_title_text(self) -> None:
        self.assertTrue(_is_non_title_text("Science Oct 22 (2004)"))

    def test_article_type_label_is_not_title_text(self) -> None:
        self.assertTrue(_is_non_title_text("Review"))

    def test_select_title_ignores_publication_header_above_title(self) -> None:
        lines = [
            {
                "text": "Science Oct 22 (2004)",
                "top": 32.27106215999993,
                "x0": 435.23999,
                "x1": 524.2485157659,
                "width": 89.00852576590006,
                "avg_size": 9.960009999999954,
            },
            {
                "text": "Electric Field Effect in Atomically Thin Carbon Films",
                "top": 58.18436784000005,
                "x0": 170.87999,
                "x1": 424.2477605000001,
                "width": 253.3677705000001,
                "avg_size": 11.039989999999989,
            },
            {
                "text": "K.S. Novoselov A.K. Geim S.V. Morozov D. Jiang Y. Zhang",
                "top": 89.26414768799998,
                "x0": 46.56076020810002,
                "x1": 548.15848761,
                "width": 501.59772740189993,
                "avg_size": 11.039989999999989,
            },
        ]

        title = _select_title_from_lines(lines, page_width=595)

        self.assertEqual(
            title,
            "Electric Field Effect in Atomically Thin Carbon Films",
        )

    def test_select_title_ignores_journal_masthead_above_article_title(self) -> None:
        lines = [
            {
                "text": "smart cities",
                "top": 50.32853146299999,
                "x0": 74.47395716000001,
                "x1": 162.697885407179,
                "width": 88.22392824717899,
                "avg_size": 19.014299999999935,
            },
            {
                "text": "Review",
                "top": 102.7356385999999,
                "x0": 35.671,
                "x1": 65.010857,
                "width": 29.339857000000002,
                "avg_size": 9.962600000000066,
            },
            {
                "text": "A Review on Electric Vehicles: Technologies and Challenges",
                "top": 115.76532480000003,
                "x0": 35.301,
                "x1": 528.4530000000002,
                "width": 493.1520000000002,
                "avg_size": 17.93279999999993,
            },
            {
                "text": "Julio A. Sanguesa, Vicente Torres-Sanz, Piedad Garrido",
                "top": 150.35144560000003,
                "x0": 35.811,
                "x1": 458.4435972,
                "width": 422.6325972,
                "avg_size": 9.807340259740215,
            },
        ]

        title = _select_title_from_lines(lines, page_width=595.276)

        self.assertEqual(
            title,
            "A Review on Electric Vehicles: Technologies and Challenges",
        )


if __name__ == "__main__":
    unittest.main()
