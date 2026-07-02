# Searchpin

[![PyPI version](https://img.shields.io/pypi/v/searchpin)](https://pypi.org/project/searchpin/)
[![Python](https://img.shields.io/pypi/pyversions/searchpin)](https://pypi.org/project/searchpin/)
[![License](https://img.shields.io/pypi/l/searchpin)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ghcr.io-blue)](https://github.com/telly6/searchpin/pkgs/container/searchpin)

Self-hosted web search for AI agents — zero API keys, zero cost. `pip install searchpin` and you're done.

- **Search quality rivals commercial products** — four search engines in parallel (Baidu, Sogou, Bing CN, Bing Intl), merged and re-ranked by semantic similarity. A rare capability among free MCP search tools.
- **Zero-cost agent development** — no API keys, no sign-ups, no usage limits. Pair with a local LLM and your entire development loop costs nothing. Run 24/7 agent experiments without worrying about quotas.
- **Pollution detection** — automatically flags results that are unrelated to your query, so your agent doesn't chase irrelevant content.
- **Cross-verification** — results from four independent sources let your LLM corroborate information across engines, raising the credibility of what it finds.
- **Content extraction that handles modern sites** — goes beyond basic HTML-to-text to extract SSR hydration payloads (Next.js, Nuxt), JSON-LD structured data, and microdata from pages that would otherwise return empty.
- **Token-conscious output** — results are titles, URLs, and snippets only. Your LLM decides which pages are worth fetching in full. Structured extraction data is compact and truncated, keeping token overhead under control.

## Quick Start

```bash
pip install searchpin && searchpin-setup
```

## Configuration

### Claude Desktop / Cursor / any MCP client

Add to your `mcpServers` config:

```json
{
  "mcpServers": {
    "Searchpin": {
      "command": "searchpin-server",
      "args": []
    }
  }
}
```

### VS Code

[![Install in VS Code](https://img.shields.io/badge/VS_Code-Install-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=Searchpin&config=%7B%22command%22%3A%22searchpin-server%22%2C%22args%22%3A%5B%5D%7D)
[![Install in VS Code Insiders](https://img.shields.io/badge/VS_Code_Insiders-Install-24bfa5?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=Searchpin&config=%7B%22command%22%3A%22searchpin-server%22%2C%22args%22%3A%5B%5D%7D&quality=insiders)

Or manually, add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "Searchpin": {
      "command": "searchpin-server",
      "args": []
    }
  }
}
```

### Docker

```bash
docker run -i --rm ghcr.io/telly6/searchpin:latest
```

```json
{
  "mcpServers": {
    "Searchpin": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "ghcr.io/telly6/searchpin:latest"]
    }
  }
}
```

### Python API

```python
from searchpin import SearchEngine

engine = SearchEngine()
results = engine.search("Python 3.13 new features")
page = engine.fetch("https://docs.python.org/3/whatsnew/3.13.html")
engine.close()
```



