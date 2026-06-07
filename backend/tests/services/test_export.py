import os
import sys
import types
import unittest
from unittest.mock import MagicMock
from uuid import uuid4
from types import SimpleNamespace

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

# Mock jose module
jose_module = types.ModuleType("jose")
jose_module.jwt = MagicMock()
jose_module.JWTError = Exception

jose_exceptions = types.ModuleType("jose.exceptions")
jose_exceptions.ExpiredSignatureError = Exception
jose_exceptions.JWTError = Exception
jose_exceptions.JWTClaimsError = Exception

jose_module.exceptions = jose_exceptions
sys.modules["jose"] = jose_module
sys.modules["jose.exceptions"] = jose_exceptions

from app.api.admin.canonical_documents import export_canonical_documents_metadata

class ExportCanonicalDocumentsMetadataTests(unittest.TestCase):
    def test_export_metadata_format(self):
        db = MagicMock()
        
        # Mock ExtractionRun
        run = SimpleNamespace(
            status="completed",
            problem_statement={"value": "Sample problem", "evidence": []},
            main_method={"value": "Sample method", "evidence": []},
            contributions=[{"value": "Contrib 1", "evidence": []}],
            limitations=[{"value": "Limit 1", "evidence": []}],
            evaluation_setup={"value": "Eval 1", "evidence": []}
        )

        # Mock CanonicalDocument
        doc1 = SimpleNamespace(
            id=uuid4(),
            canonical_key="doc-key-1",
            title="Sample Paper Title",
            title_candidate="Parsed Title",
            abstract="Sample Abstract",
            publication_year=2026,
            venue="ACL",
            authors_json=[{"name": "Author One", "author_id": "auth1"}, {"name": "Author Two"}],
            doi="10.1234/5678",
            latest_extraction_run=run,
            papers=[SimpleNamespace(original_filename="paper1.pdf")]
        )

        doc2 = SimpleNamespace(
            id=uuid4(),
            canonical_key="doc-key-2",
            title=None,
            title_candidate="Parsed Title Two",
            abstract=None,
            publication_year=None,
            venue=None,
            authors_json=None,
            doi=None,
            latest_extraction_run=None,
            papers=[]
        )

        db.query.return_value.options.return_value.all.return_value = [doc1, doc2]

        result = export_canonical_documents_metadata(db=db, current_user=MagicMock())

        self.assertEqual(len(result), 2)
        
        # Test doc1 fields
        self.assertEqual(result[0]["canonical_key"], "doc-key-1")
        self.assertEqual(result[0]["title"], "Sample Paper Title")
        self.assertEqual(result[0]["abstract"], "Sample Abstract")
        self.assertEqual(result[0]["year"], 2026)
        self.assertEqual(result[0]["venue"], "ACL")
        self.assertEqual(result[0]["authors"], ["Author One", "Author Two"])
        self.assertEqual(result[0]["doi"], "10.1234/5678")
        self.assertEqual(result[0]["original_filename"], "paper1.pdf")
        self.assertEqual(result[0]["problem"]["value"], "Sample problem")
        self.assertEqual(result[0]["method"]["value"], "Sample method")
        self.assertEqual(result[0]["contributions"][0]["value"], "Contrib 1")

        # Test doc2 fallbacks
        self.assertEqual(result[1]["title"], "Parsed Title Two")
        self.assertIsNone(result[1]["abstract"])
        self.assertIsNone(result[1]["original_filename"])
        self.assertIsNone(result[1]["problem"])

if __name__ == "__main__":
    unittest.main()
