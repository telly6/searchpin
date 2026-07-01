"""Entry point for python -m searchpin — starts the MCP stdio server.

Usage:
    python -m searchpin              # Start with defaults
    python -m searchpin --model ...  # Custom embedding model
"""

from search_server import main

if __name__ == "__main__":
    main()
