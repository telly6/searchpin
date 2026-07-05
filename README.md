<!-- mcp-name: io.github.telly6/searchpin -->

[English](./README.md) | [简体中文](./README_zh.md)

# Searchpin

[![PyPI version](https://img.shields.io/pypi/v/searchpin)](https://pypi.org/project/searchpin/)
[![Python](https://img.shields.io/pypi/pyversions/searchpin)](https://pypi.org/project/searchpin/)
[![License](https://img.shields.io/pypi/l/searchpin)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ghcr.io-blue)](https://github.com/telly6/searchpin/pkgs/container/searchpin)

Self-hosted web search for AI agents — zero API keys, zero cost. In 2026, the center of gravity in AI development is shifting from "chatting" to "autonomous task execution" — locally deployed, long-running agents are becoming the norm. When an agent runs 24/7, every web search must not be interrupted by API quotas or billing. Searchpin was designed for this from day one: zero external dependencies, zero usage limits. Agents can search, fetch, and verify without restriction, and developers never worry about cost.

## Why Searchpin

### 🇨🇳 Optimized for Chinese Network Environments

Defaults to **Baidu, Sogou, Bing CN, and Bing Intl** — four search engines queried in parallel. Works natively within China's network, no proxy or VPN needed. Most overseas alternatives rely on Google, DuckDuckGo, or Brave, which are largely inaccessible inside China.

### 🧠 Semantic Re-ranking — a Differentiator Few Offer

Results from all four engines are not simply concatenated. They are merged and re-ranked by an embedding model based on semantic similarity to the query. What your AI receives is a curated list of high-quality results, not a pile of noisy links. Among free MCP search servers, very few offer this capability.

### 💰 Completely Free, Zero Barrier

No account registration, no API key application, no usage limits. No dependency on any commercial API — no risk of sudden paywalls or quota restrictions. The entire pipeline runs on your own machine.

### 🔍 Built for Modern Websites

Built-in SSR content extraction can parse pages rendered by Next.js, Nuxt, and similar frameworks, and extract JSON-LD structured data and microdata. Plain HTML scraping gets nothing from these sites.

### 🛡️ Pollution Detection + Cross-Verification

Automatically detects and flags results unrelated to your query. Four independent search engines provide cross-verifiable results, enabling your LLM to corroborate information across sources for more credible answers.

### ⚡ Deliberate Engineering Trade-offs

Every design decision was made with real-world usage in mind:

- **Token-conscious** — Search results return only titles, URLs, and snippets. Structured extraction data is compact and truncated. Your LLM decides which pages are worth fetching in full, without wasting context window.
- **Fast response** — Four engines queried asynchronously in parallel. Total time depends on the slowest engine, not the sum of all four. A typical search completes in 1–2 seconds.
- **Memory-friendly** — The embedding model (~118MB) is downloaded once through hf-mirror.com (HuggingFace mirror for China), then reused from local cache.

## Quick Start

```bash
pip install searchpin && searchpin-setup
```

On first run, the embedding model (~118MB) is downloaded once via hf-mirror.com (HuggingFace mirror for China). That is the only one-time setup.

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

### Python API

```python
from searchpin import SearchEngine

engine = SearchEngine()
results = engine.search("Python 3.13 新特性")
page = engine.fetch("https://docs.python.org/3/whatsnew/3.13.html")
engine.close()
```



