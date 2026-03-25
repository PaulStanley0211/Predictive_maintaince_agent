import json
from pathlib import Path

import fitz  # PyMuPDF

from src.knowledge.vector_store import VectorStore

_FAILURE_MODES_PATH = Path(__file__).parent.parent / "data" / "failure_modes.json"
_DOCS_DIR = Path(__file__).parent / "docs"

_CHUNK_SIZE = 500
_CHUNK_OVERLAP = 50


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks of ~_CHUNK_SIZE characters."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + _CHUNK_SIZE
        chunks.append(text[start:end].strip())
        start += _CHUNK_SIZE - _CHUNK_OVERLAP
    return [c for c in chunks if c]


def ingest_pdf(path: str | Path, store: VectorStore) -> int:
    """Extract text from a PDF, chunk it, and add to the vector store. Returns chunk count."""
    doc = fitz.open(str(path))
    full_text = "\n".join(page.get_text() for page in doc)
    doc.close()
    chunks = _chunk_text(full_text)
    source = Path(path).name
    metadatas = [{"source": source, "type": "manual"} for _ in chunks]
    store.add_documents(chunks, metadatas)
    return len(chunks)


def ingest_failure_modes(store: VectorStore) -> int:
    """Convert failure_modes.json entries into text descriptions and add to the vector store."""
    with _FAILURE_MODES_PATH.open() as f:
        data = json.load(f)

    chunks: list[str] = []
    metadatas: list[dict] = []

    for mode in data["failure_modes"]:
        text = (
            f"Failure mode: {mode['name']}\n"
            f"Description: {mode['description']}\n"
            f"Affected sensors: {', '.join(mode['affected_sensors'])}\n"
            f"Typical progression: {mode['typical_progression']}\n"
            f"Recommended action: {mode['recommended_action']}\n"
            f"Urgency: {mode['default_urgency']}\n"
            f"Typical downtime: {mode['typical_downtime_hours']} hours\n"
            f"Cost of inaction: €{mode['cost_of_inaction_per_day_eur']}/day"
        )
        chunks.append(text)
        metadatas.append({"source": "failure_modes.json", "failure_mode": mode["name"]})

    store.add_documents(chunks, metadatas)
    return len(chunks)


def setup_knowledge_base(store: VectorStore | None = None) -> VectorStore:
    """Populate the vector store with failure modes and any PDFs in the docs directory."""
    if store is None:
        store = VectorStore()

    ingest_failure_modes(store)

    for pdf_path in _DOCS_DIR.glob("*.pdf"):
        ingest_pdf(pdf_path, store)

    return store
