import os
import sys
import types
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# 1. Ensure a fake API key is present before settings.py is imported.
#    This prevents ValidationError when ANTHROPIC_API_KEY is not in .env.
# ---------------------------------------------------------------------------
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key-000")

# ---------------------------------------------------------------------------
# 2. Stub ChromaDB at the sys.modules level before any test file imports it.
#    ChromaDB internally uses Pydantic v1 which is broken on Python 3.14.
#    All tests that touch ChromaDB mock it anyway per project conventions.
# ---------------------------------------------------------------------------
_mock_collection = MagicMock()
_mock_collection.count.return_value = 0
_mock_collection.add = MagicMock()
_mock_collection.query.return_value = {"documents": [[]]}

_mock_chroma_client = MagicMock()
_mock_chroma_client.get_or_create_collection.return_value = _mock_collection

_chromadb_mod = types.ModuleType("chromadb")
_chromadb_mod.Client = MagicMock(return_value=_mock_chroma_client)

sys.modules["chromadb"] = _chromadb_mod
sys.modules["chromadb.utils"] = types.ModuleType("chromadb.utils")
sys.modules["chromadb.utils.embedding_functions"] = types.SimpleNamespace(
    DefaultEmbeddingFunction=MagicMock(return_value=None)
)
