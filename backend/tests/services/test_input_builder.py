import os
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import unittest
from app.services.llm.input_builder import LLMInputBuilder

class TestLLMInputBuilder(unittest.TestCase):
    def setUp(self):
        self.builder = LLMInputBuilder()

    def test_extract_priority_tail_matches_new_headings(self):
        # Sample text representing a paper with a FUTURE TRENDS AND CHALLENGES section
        dummy_intro = "This is a long dummy introduction text to ensure that the target section starts in the second half of the document. " * 20
        text = (
            dummy_intro +
            "This is the introduction.\n"
            "This is the method section.\n"
            "\n9. FUTURE TRENDS AND CHALLENGES\n"
            "Cost and size are key challenges to achieving high power density.\n"
            "Lack of charging stations limits EV growth.\n"
        )
        
        # Test matching "future trends and challenges" (lowercased)
        tail = self.builder._extract_priority_tail(text, fallback_chars=1000)
        self.assertTrue(tail.strip().startswith("9. FUTURE TRENDS AND CHALLENGES"))

    def test_extract_priority_tail_matches_challenges(self):
        dummy_intro = "This is a long dummy introduction text to ensure that the target section starts in the second half of the document. " * 20
        text = (
            dummy_intro +
            "Section 8: Evaluation\n"
            "\nChallenges\n"
            "One major challenge is the scale of training data.\n"
        )
        tail = self.builder._extract_priority_tail(text, fallback_chars=100)
        self.assertTrue(tail.strip().startswith("Challenges"))

    def test_extract_priority_tail_matches_outlook(self):
        dummy_intro = "This is a long dummy introduction text to ensure that the target section starts in the second half of the document. " * 20
        text = (
            dummy_intro +
            "Section 8: Evaluation\n"
            "\nOutlook\n"
            "Our outlook for future research is bright.\n"
        )
        tail = self.builder._extract_priority_tail(text, fallback_chars=100)
        self.assertTrue(tail.strip().startswith("Outlook"))

if __name__ == "__main__":
    unittest.main()
