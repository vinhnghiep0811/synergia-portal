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

    def test_document_labels_are_not_title_text(self) -> None:
        self.assertTrue(_is_non_title_text("SPM5"))
        self.assertTrue(_is_non_title_text("SPM 5"))
        self.assertTrue(_is_non_title_text("Chapter 5"))
        self.assertTrue(_is_non_title_text("WGII"))
        self.assertTrue(_is_non_title_text("WG1"))
        self.assertTrue(_is_non_title_text("Section A"))

    def test_initialed_author_line_is_not_title_text(self) -> None:
        self.assertTrue(
            _is_non_title_text(
                "Wladimir A. Benalcazar, B. Andrei Bernevig, and Taylor L. Hughes"
            )
        )
        self.assertTrue(
            _is_non_title_text(
                "Wladimir A. Benalcazar,1 B. Andrei Bernevig,2 and Taylor L. Hughes1"
            )
        )
        self.assertTrue(
            _is_non_title_text(
                "K.S. Novoselov A.K. Geim S.V. Morozov D. Jiang Y. Zhang"
            )
        )

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

    def test_select_title_ignores_initialed_author_line_below_title(self) -> None:
        lines = [
            {
                "text": "Quantized Electric Multipole Insulators",
                "top": 52.92126400094401,
                "x0": 190.99879491,
                "x1": 425.09594328196795,
                "width": 234.09714837196796,
                "avg_size": 11.960818944000039,
            },
            {
                "text": "Wladimir A. Benalcazar, B. Andrei Bernevig, and Taylor L. Hughes",
                "top": 78.82492780350003,
                "x0": 148.08563519999998,
                "x1": 463.543132471893,
                "width": 315.457497271893,
                "avg_size": 9.96728242200004,
            },
            {
                "text": "Department of Physics and Institute for Condensed Matter Theory,",
                "top": 93.526984524,
                "x0": 170.12598930000001,
                "x1": 450.0737410118976,
                "width": 279.9477517118976,
                "avg_size": 8.970614208000029,
            },
        ]

        title = _select_title_from_lines(lines, page_width=612)

        self.assertEqual(title, "Quantized Electric Multipole Insulators")

    def test_select_title_filters_out_short_acronym_lines_when_better_candidate_exists(self) -> None:
        lines = [
            {
                "text": "OA",
                "top": 198.5,
                "x0": 74.1,
                "x1": 162.9,
                "width": 88.8,
                "avg_size": 72.0,
            },
            {
                "text": "Ocean Acidification",
                "top": 231.5,
                "x0": 217.5,
                "x1": 451.2,
                "width": 233.7,
                "avg_size": 29.0,
            },
            {
                "text": "Jean-Pierre Gattuso (France), Peter G. Brewer (USA)",
                "top": 272.7,
                "x0": 217.5,
                "x1": 551.7,
                "width": 334.2,
                "avg_size": 9.5,
            },
        ]

        title = _select_title_from_lines(lines, page_width=595.0)

        self.assertEqual(title, "Ocean Acidification")


    def test_publication_header_with_month_year_typos_is_not_title_text(self) -> None:
        self.assertTrue(_is_non_title_text("PHYSICARLESEARCH FEBRUAR1Y0 1977"))
        self.assertTrue(_is_non_title_text("Science October 2004"))
        self.assertTrue(_is_non_title_text("February 1977"))

    def test_is_valid_metadata_title(self) -> None:
        from app.services.pdf_parse_service import _is_valid_metadata_title
        self.assertTrue(_is_valid_metadata_title("AN ANALYSIS OF THE VARIATION OF OCEAN FLOOR BATHYMETRY"))
        self.assertFalse(_is_valid_metadata_title("Microsoft Word - science.doc"))
        self.assertFalse(_is_valid_metadata_title("untitled"))
        self.assertFalse(_is_valid_metadata_title("S401_23b 360..363"))
        self.assertFalse(_is_valid_metadata_title("Vol. 82, No. 5"))

    def test_verify_metadata_title_on_page(self) -> None:
        from app.services.pdf_parse_service import _verify_metadata_title_on_page
        meta = "AN ANALYSIS OF THE VARIATION OF OCEAN FLOOR BATHYMETRY"
        page_text = "This page contains AN ANALYSIS OF THE VARIATION OF OCEAN FLOOR BATHYMETRY and other details."
        self.assertTrue(_verify_metadata_title_on_page(meta, page_text))
        
        # Test fuzzy matching (e.g. OCR error 'BATHYMETRY' -> 'BATHYMETR1')
        page_text_fuzzy = "This page contains AN ANALYSIS OF THE VARIATION OF OCEAN FLOOR BATHYMETR1 and other details."
        self.assertTrue(_verify_metadata_title_on_page(meta, page_text_fuzzy))


if __name__ == "__main__":
    unittest.main()
