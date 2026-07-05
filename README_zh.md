[English](./README.md) | 简体中文

# Searchpin

[![PyPI version](https://img.shields.io/pypi/v/searchpin)](https://pypi.org/project/searchpin/)
[![Python](https://img.shields.io/pypi/pyversions/searchpin)](https://pypi.org/project/searchpin/)
[![License](https://img.shields.io/pypi/l/searchpin)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ghcr.io-blue)](https://github.com/telly6/searchpin/pkgs/container/searchpin)

面向 AI Agent 的自托管免费联网搜索 —— 零 API Key，零成本。2026 年，AI 开发的重心正从"能聊天"转向"能自主执行任务"——本地部署的长运行 Agent 将成为主流。当 Agent 需要 7×24 小时持续运行，每一次联网搜索都不能被 API 配额或账单打断。Searchpin 从一开始就为这个场景设计：零外部依赖、零调用限制，Agent 可以无上限地搜索、抓取、验证，开发者不用关心任何成本。

## 为什么选择 Searchpin

### 🇨🇳 专为中国网络环境优化

默认接入**百度、搜狗、Bing CN、Bing Intl** 四条搜索引擎，四路并行查询。全程国内网络直连，无需代理、无需 VPN。大部分海外同类项目依赖 Google、DuckDuckGo、Brave 等引擎，在国内基本不可用。

### 🧠 语义重排——竞品没有的核心能力

四个引擎返回的所有结果并非简单堆砌，而是通过 embedding 模型按与查询的语义相似度重新排序。你的 AI 拿到的是已经筛选过的高质量结果，不是几十条杂乱链接。在目前免费 MCP 搜索服务器中，具备此能力的**屈指可数**。

### 💰 完全零成本、零门槛

无需注册任何账号、无需申请任何 API Key、没有调用次数限制。不依赖任何商业 API，不会哪天突然收费或限制配额——整个链路都在你自己的机器上运行。

### 🔍 专为现代网页优化

内置 SSR 内容提取，能解析 Next.js、Nuxt 等前端框架渲染的页面，提取 JSON-LD 结构化数据和微数据。普通 HTML 解析面对这类页面只会拿到空白内容。

### 🛡️ 污染检测 + 交叉验证

自动识别与查询无关的结果并标记。四条独立搜索引擎的结果可交叉验证，让 LLM 参考多个来源做出更可信的判断。

### ⚡ 工程权衡，性能可控

开发时在每个环节都做了取舍，确保日常使用不拖后腿：

- **Token 经济** — 搜索结果只返回标题、URL 和摘要，结构化提取数据紧凑截断。LLM 自行判断哪些页面值得全文抓取，不浪费上下文窗口。
- **响应高效** — 四引擎异步并行查询，总耗时取决于最慢的那个，而非逐个累积。单次搜索通常 1–2 秒完成。
- **内存友好** — 嵌入模型（仅约 118MB）仅在首次使用时通过 hf-mirror.com（HuggingFace 国内镜像）下载一次，之后本地缓存复用。

## 快速开始

```bash
pip install searchpin && searchpin-setup
```

首次运行会自动通过国内镜像下载嵌入模型（仅约 118MB），仅此一次。

## 配置

### Claude Desktop / Cursor / 任何 MCP 客户端

在 `mcpServers` 配置中添加：

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

或手动在 `.vscode/mcp.json` 中添加：

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
