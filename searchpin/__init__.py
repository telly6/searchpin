"""
Searchpin — Self-hosted web search for AI agents.

Usage:
    from searchpin import SearchEngine

    engine = SearchEngine()
    results = engine.search("your query")
    page = engine.fetch("https://example.com/article")
    engine.close()
"""

from searchpin.config import DEFAULT_MODEL_NAME, PRODUCT_NAME
from searchpin.engine import MCP_TOOLS, SearchEngine

__version__ = "1.0.0"
__all__ = ["SearchEngine", "MCP_TOOLS", "PRODUCT_NAME", "DEFAULT_MODEL_NAME"]
