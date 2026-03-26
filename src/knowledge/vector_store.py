import chromadb


class VectorStore:
    """ChromaDB-backed vector store for maintenance knowledge retrieval."""

    def __init__(self) -> None:
        """Create an in-process ChromaDB client and open the knowledge collection."""
        self._client = chromadb.Client()
        self._collection = self._client.get_or_create_collection(
            name="maintenance_knowledge",
        )

    def add_documents(self, chunks: list[str], metadatas: list[dict] | None = None) -> None:
        """Add text chunks to the collection, generating IDs automatically."""
        if not chunks:
            return
        start = self._collection.count()
        ids = [f"doc_{start + i}" for i in range(len(chunks))]
        self._collection.add(
            documents=chunks,
            metadatas=metadatas or [{} for _ in chunks],
            ids=ids,
        )

    def search(self, query: str, top_k: int = 5) -> list[str]:
        """Return the top_k most relevant text chunks for a query string."""
        count = self._collection.count()
        if count == 0:
            return []
        results = self._collection.query(
            query_texts=[query],
            n_results=min(top_k, count),
        )
        return results["documents"][0]
