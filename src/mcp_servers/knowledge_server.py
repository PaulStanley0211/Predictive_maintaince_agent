import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.knowledge.ingestion import setup_knowledge_base
from src.knowledge.vector_store import VectorStore

_FAILURE_MODES_PATH = Path(__file__).parent.parent / "data" / "failure_modes.json"

mcp = FastMCP("knowledge-base")

# Populated on first tool call via _get_store(); lazy so import doesn't block startup.
_store: VectorStore | None = None


def _get_store() -> VectorStore:
    """Return the shared VectorStore, initialising it on first access."""
    global _store
    if _store is None:
        _store = setup_knowledge_base()
    return _store


@mcp.tool()
def search_failures(query: str, top_k: int = 5) -> str:
    """Search the maintenance knowledge base for failure modes matching a query.

    Args:
        query: Natural-language description of the symptoms or failure pattern.
        top_k: Maximum number of results to return (default 5).
    """
    store = _get_store()
    top_k = max(1, min(top_k, 20))  # clamp to [1, 20]
    results = store.search(query, top_k=top_k)

    if not results:
        return json.dumps(
            {
                "message": "Knowledge base is empty or no matching entries found. "
                "Run setup_knowledge_base() to ingest failure mode definitions.",
                "results": [],
            }
        )

    return json.dumps({"results": results, "count": len(results)})


@mcp.tool()
def get_failure_mode(failure_mode_name: str) -> str:
    """Return the full definition for a named failure mode from the knowledge base.

    Args:
        failure_mode_name: The failure mode identifier (e.g. 'bearing_wear', 'cavitation').
    """
    with _FAILURE_MODES_PATH.open() as f:
        data = json.load(f)

    modes: dict[str, dict] = {m["name"]: m for m in data["failure_modes"]}

    if failure_mode_name not in modes:
        available = sorted(modes.keys())
        return json.dumps(
            {
                "error": f"Unknown failure mode '{failure_mode_name}'.",
                "available_modes": available,
            }
        )

    return json.dumps(modes[failure_mode_name])


if __name__ == "__main__":
    mcp.run(transport="stdio")
