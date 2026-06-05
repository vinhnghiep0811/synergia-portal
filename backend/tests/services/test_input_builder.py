import os
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import unittest
from app.services.llm.input_builder import LLMInputBuilder

class TestLLMInputBuilder(unittest.TestCase):
    def setUp(self):
        self.builder = LLMInputBuilder()

    def test_extract_priority_tail_matches_new_headings(self):
        # Sample text representing a paper with a FUTURE TRENDS AND CHALLENGES section followed by CONCLUSION
        text = (
            "This is the introduction.\n"
            "This is the method section.\n"
            "\n9. FUTURE TRENDS AND CHALLENGES\n"
            "Cost and size are key challenges to achieving high power density.\n"
            "Lack of charging stations limits EV growth.\n"
            "\n10. CONCLUSION\n"
            "In conclusion, we have reviewed EV charging topologies.\n"
        )
        
        # Test matching "future trends and challenges" (lowercased)
        tail = self.builder._extract_priority_tail(text, fallback_chars=1000)
        self.assertTrue(tail.strip().startswith("9. FUTURE TRENDS AND CHALLENGES"))
        self.assertIn("conclusion", tail.lower())

    def test_extract_priority_tail_matches_challenges(self):
        text = (
            "Section 8: Evaluation\n"
            "\nChallenges\n"
            "One major challenge is the scale of training data.\n"
            "\nConclusion\n"
            "We conclude that our method works.\n"
        )
        tail = self.builder._extract_priority_tail(text, fallback_chars=100)
        self.assertTrue(tail.strip().startswith("Challenges"))

    def test_extract_priority_tail_matches_outlook(self):
        text = (
            "Section 8: Evaluation\n"
            "\nOutlook\n"
            "Our outlook for future research is bright.\n"
            "\nConclusion\n"
            "We conclude.\n"
        )
        tail = self.builder._extract_priority_tail(text, fallback_chars=100)
        self.assertTrue(tail.strip().startswith("Outlook"))

if __name__ == "__main__":
    unittest.main()
