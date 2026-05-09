import unittest

from app.services.pdf_parse_service import detect_doi


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


if __name__ == "__main__":
    unittest.main()
