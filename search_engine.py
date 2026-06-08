#!/usr/bin/env python3
"""
MiniSearch — Self-hosted web search for AI agents.
Provides web_search + web_fetch via a clean Python API.
Zero external API keys required.
"""

import http.client
import json
import os
import re
import socket
import ssl
import sys
import threading
import time
import urllib.parse
import numpy as np
from urllib.parse import urlparse
from html import unescape

from fastembed import TextEmbedding

# ── Config ──────────────────────────────────────────────────
PRODUCT_NAME = os.environ.get("MINISEARCH_NAME", "MiniSearch")
DEFAULT_MODEL_NAME = "BAAI/bge-small-zh-v1.5"

# DNS-over-HTTPS endpoints (tried in order)
DOH_ENDPOINTS = [
    ("https://dns.google/resolve", "8.8.8.8"),
    ("https://cloudflare-dns.com/dns-query", "1.1.1.1"),
    ("https://dns.quad9.net/dns-query", "9.9.9.9"),
]

MCP_TOOLS = [
    {
        "name": "web_search",
        "description": "Search the web using Bing. Returns real-time titles, URLs, and snippets. Use for factual, up-to-date queries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query keywords"},
                "max_results": {"type": "integer", "description": "Max results (default 10)", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "web_fetch",
        "description": "Fetch and return the text content of a specific URL (article, documentation, API response). For search queries, use web_search instead. Do NOT use this to fetch search engine result pages.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch"},
                "max_length": {"type": "integer", "description": "Max chars returned (default 30000)", "default": 30000},
            },
            "required": ["url"],
        },
    },
]


class SearchEngine:
    """Self-contained web search engine.  DNS-over-HTTPS, Bing scraping,
    and local embedding re-rank — no external API keys needed."""

    def __init__(self, model_name=None, max_workers=3,
                 embedding_mode="local", api_endpoint=None, api_key=None,
                 api_model=None):
        self.model_name = model_name or DEFAULT_MODEL_NAME
        self.max_workers = max_workers
        self.embedding_mode = embedding_mode
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.api_model = api_model

        # ── Embedding model ──
        if embedding_mode == "local":
            print(f"[{PRODUCT_NAME}] loading embedding model ({self.model_name})...",
                  file=sys.stderr, flush=True)
            try:
                self._embedding_model = TextEmbedding(
                    model_name=self.model_name,
                    local_files_only=True,
                )
            except Exception:
                print(f"[{PRODUCT_NAME}] model not cached, downloading from HuggingFace...",
                      file=sys.stderr, flush=True)
                self._embedding_model = TextEmbedding(
                    model_name=self.model_name,
                    local_files_only=False,
                )
            print(f"[{PRODUCT_NAME}] embedding model ready",
                  file=sys.stderr, flush=True)
        else:
            self._embedding_model = None
            print(f"[{PRODUCT_NAME}] using API embedding: {api_endpoint} (model={api_model})",
                  file=sys.stderr, flush=True)

        # ── DNS cache ──
        self._dns_cache = {}
        self._dns_cache_lock = threading.Lock()

        # ── Search cooldown ──
        self._search_cooldown_until = 0
        self._search_fail_count = 0

    # ── DNS Resolution ──────────────────────────────────────

    def resolve_host(self, host):
        """Resolve hostname to IP using DoH, with cache."""
        with self._dns_cache_lock:
            if host in self._dns_cache:
                return self._dns_cache[host]

        # Try system resolver first
        try:
            addr = socket.getaddrinfo(host, 443)[0][4][0]
            with self._dns_cache_lock:
                self._dns_cache[host] = addr
            print(f"[DNS] system resolver: {host} → {addr}", file=sys.stderr, flush=True)
            return addr
        except Exception:
            pass

        # Fall back to DoH
        for doh_url, doh_ip in DOH_ENDPOINTS:
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

                parsed = urlparse(doh_url)
                doh_host = parsed.netloc

                conn = http.client.HTTPSConnection(doh_ip, timeout=2, context=ctx)
                conn.request("GET", parsed.path + f"?name={host}&type=A",
                             headers={"Host": doh_host, "Accept": "application/dns-json"})
                resp = conn.getresponse()
                if resp.status == 200:
                    data = json.loads(resp.read())
                    for ans in data.get("Answer", []):
                        if ans.get("type") == 1:  # A record
                            addr = ans["data"]
                            with self._dns_cache_lock:
                                self._dns_cache[host] = addr
                            print(f"[DNS] {host} → {addr} (via {doh_host})", file=sys.stderr, flush=True)
                            return addr
                conn.close()
            except Exception as e:
                print(f"[DNS] DoH {doh_host} failed: {e}", file=sys.stderr, flush=True)
                continue

        raise Exception(f"Cannot resolve {host} via any method")

    # ── HTTP ────────────────────────────────────────────────

    def _http_get(self, host, path="/", port=443, timeout=15,
                  follow_redirects=False, max_redirects=3,
                  cookies=None, extra_headers=None):
        """DoH-resolved HTTP/HTTPS GET."""
        import socket as _sock
        use_ssl = (port == 443)
        _jar = cookies

        for _ in range(max_redirects + 1):
            ip = self.resolve_host(host)
            if use_ssl:
                ctx = ssl.create_default_context()
                conn = http.client.HTTPSConnection(ip, port, timeout=timeout, context=ctx)
                def _custom_connect():
                    sock = _sock.create_connection((ip, port), timeout=timeout)
                    conn.sock = ctx.wrap_socket(sock, server_hostname=host)
                conn.connect = _custom_connect
            else:
                conn = http.client.HTTPConnection(ip, port, timeout=timeout)

            _headers = {
                "Host": host,
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html,application/json,*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
            if _jar:
                _headers["Cookie"] = _jar
            if extra_headers:
                _headers.update(extra_headers)

            conn.request("GET", path, headers=_headers)
            resp = conn.getresponse()

            # Collect Set-Cookie headers across redirects
            set_cookies = resp.headers.get_all("Set-Cookie") or resp.headers.get("Set-Cookie")
            if set_cookies:
                if isinstance(set_cookies, list):
                    set_cookies = ", ".join(set_cookies)
                new_parts = []
                for part in set_cookies.split(","):
                    part = part.strip()
                    kv = part.split(";")[0].strip()
                    if "=" in kv:
                        new_parts.append(kv)
                if new_parts:
                    if _jar:
                        _jar = _jar + "; " + "; ".join(new_parts)
                    else:
                        _jar = "; ".join(new_parts)

            if follow_redirects and resp.status in (301, 302, 303, 307):
                location = resp.headers.get("Location", "")
                conn.close()
                if not location:
                    return resp, b""
                parsed = urlparse(location)
                if parsed.netloc:
                    host = parsed.netloc.split(":")[0]
                    if ":" in parsed.netloc:
                        port = int(parsed.netloc.split(":")[1])
                    else:
                        port = 443 if parsed.scheme == "https" else 80
                    use_ssl = (port == 443)
                path = parsed.path or "/"
                if parsed.query:
                    path += "?" + parsed.query
                print(f"[HTTP] redirect → {host}{path}", file=sys.stderr, flush=True)
                continue

            body = resp.read()
            conn.close()
            return resp, body

        return resp, body

    # ── Embedding re-rank ───────────────────────────────────

    def _cosine_similarity(self, a, b):
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))

    def _api_embed(self, texts):
        """Get embeddings from an external OpenAI-compatible API."""
        body = json.dumps({
            "model": self.api_model,
            "input": texts,
        }).encode("utf-8")

        parsed = urlparse(self.api_endpoint)
        host = parsed.netloc.split(":")[0]
        port = 443
        if ":" in parsed.netloc:
            port = int(parsed.netloc.split(":")[1])
        path = parsed.path or "/v1/embeddings"

        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(host, port, timeout=30, context=ctx)
        conn.request("POST", path, body, {
            "Host": host,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        })
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()

        if resp.status != 200:
            raise Exception(f"API embedding error {resp.status}: {data}")

        embeddings = [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
        return embeddings

    def _embed(self, texts):
        """Get embeddings from local model or API depending on mode."""
        if self.embedding_mode == "api":
            return self._api_embed(texts)
        return list(self._embedding_model.embed(texts))

    def _embedding_rerank(self, query, all_results, max_results):
        """Re-rank results by embedding cosine similarity to the query."""
        if not all_results:
            return []

        docs = [f"{r.get('title', '')} {r.get('snippet', '')}" for r in all_results]
        all_texts = [query] + docs
        embeddings = self._embed(all_texts)
        query_vec = np.array(embeddings[0])
        doc_vecs = np.array(embeddings[1:])

        scored = []
        for i, r in enumerate(all_results):
            sim = self._cosine_similarity(query_vec, doc_vecs[i])
            scored.append((sim, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = [r for _, r in scored[:max_results]]
        print(f"[SEARCH] merged {len(all_results)} unique, returning top {len(top)} after embedding re-rank",
              file=sys.stderr, flush=True)
        return top

    # ── Web search ──────────────────────────────────────────

    def search(self, query, max_results=10):
        """Search the web and return structured results."""
        return self._do_web_search(query, max_results)

    def _do_web_search(self, query, max_results=10):
        """Web search via DoH-resolved HTTPS. Tries multiple backends in parallel."""
        if not query or not query.strip():
            return {"error": "empty query", "results": [], "query": query}

        now = time.time()
        if now < self._search_cooldown_until:
            self._search_fail_count += 1
            return {
                "error": f"search unavailable (cooldown, {self._search_fail_count} attempts blocked)",
                "results": [],
                "query": query,
            }

        # ── Backend registry ───────────────────────────────────
        backends = []

        def _bing_path(q):
            return f"/search?q={urllib.parse.quote(q)}&count={max_results}"

        def _bing_page2_path(q):
            return f"/search?q={urllib.parse.quote(q)}&count={max_results}&first=11"

        def _bing_parse(html):
            results = []
            blocks = re.findall(r'<li[^>]*class="[^"]*b_algo[^"]*"[^>]*>(.*?)</li>', html, re.DOTALL)
            for blk in blocks[:max_results]:
                h2_m = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', blk, re.DOTALL)
                if not h2_m:
                    continue
                title = re.sub(r'<[^>]+>', '', h2_m.group(2)).strip()
                title = unescape(title)
                snip_m = re.search(r'<p[^>]*class="[^"]*b_lineclamp[^"]*"[^>]*>(.*?)</p>', blk, re.DOTALL)
                snippet = ""
                if snip_m:
                    snippet = re.sub(r'<[^>]+>', '', snip_m.group(1)).strip()
                    snippet = unescape(snippet)
                    snippet = snippet.replace("&ensp;", " ").replace("&#0183;", "·")
                if title:
                    results.append({"title": title, "url": h2_m.group(1), "snippet": snippet})

            # Fallback: generic link scraper
            if not results:
                print("[SEARCH] b_algo miss, trying generic <a> fallback", file=sys.stderr, flush=True)
                skip_domains = {"bing.com", "microsoft.com", "live.com", "msn.com"}
                seen = set()
                for m in re.finditer(
                    r'<a[^>]*href="((?:https?://)?[^"]+)"[^>]*>(.*?)</a>',
                    html, re.DOTALL,
                ):
                    url = m.group(1)
                    if not url.startswith("http"):
                        continue
                    parsed_url = urlparse(url)
                    domain = parsed_url.netloc.lower()
                    if any(d in domain for d in skip_domains):
                        continue
                    url_key = url.lower().rstrip("/")
                    if url_key in seen:
                        continue
                    seen.add(url_key)
                    title = re.sub(r'<[^>]+>', '', m.group(2)).strip()
                    title = unescape(title)
                    if not title or len(title) < 4:
                        continue
                    results.append({"title": title, "url": url, "snippet": ""})
                    if len(results) >= max_results:
                        break
                if results:
                    print(f"[SEARCH] fallback found {len(results)} links", file=sys.stderr, flush=True)

            return results

        backends.append(("cn.bing.com", _bing_path, _bing_parse, False, 443))
        backends.append(("cn.bing.com", _bing_page2_path, _bing_parse, False, 443))

        # ── Parallel fetch, merge, deduplicate ──
        from concurrent.futures import ThreadPoolExecutor, as_completed
        all_results_lock = threading.Lock()
        all_results = []
        seen_urls = set()
        any_success = [False]

        def _fetch_one(host, path_fn, parse_fn, follow, port):
            path = path_fn(query)
            try:
                print(f"[SEARCH] trying {host}{path}", file=sys.stderr, flush=True)
                resp, body = self._http_get(host, path, timeout=5, follow_redirects=follow, port=port)
                html = body.decode("utf-8", errors="replace")
                return host, html, parse_fn, None
            except Exception as e:
                return host, "", None, e

        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futures = [ex.submit(_fetch_one, h, pf, ps, fw, p)
                       for h, pf, ps, fw, p in backends]
            for fut in as_completed(futures):
                host, html, parse_fn, err = fut.result()
                if err:
                    print(f"[SEARCH] {host} failed: {err}", file=sys.stderr, flush=True)
                    continue
                results = parse_fn(html)
                if results:
                    with all_results_lock:
                        any_success[0] = True
                        for r in results:
                            url_key = r["url"].lower().rstrip("/")
                            if url_key not in seen_urls:
                                seen_urls.add(url_key)
                                all_results.append(r)
                    print(f"[SEARCH] {host} returned {len(results)} results ({len(all_results)} unique total)",
                          file=sys.stderr, flush=True)
                else:
                    print(f"[SEARCH] {host} returned 0 parsed results (HTML {len(html)} bytes)",
                          file=sys.stderr, flush=True)

        if not any_success[0]:
            self._search_cooldown_until = time.time() + 60
            self._search_fail_count = 1
            print(f"[SEARCH] entering 60s cooldown (all backends failed)", file=sys.stderr, flush=True)
            return {"error": "all backends failed", "results": [], "query": query}

        self._search_cooldown_until = 0
        self._search_fail_count = 0

        top = self._embedding_rerank(query, all_results, max_results)
        return {"results": top, "query": query, "backend": "bing"}

    # ── Web fetch ───────────────────────────────────────────

    def fetch(self, url, max_length=30000):
        """Fetch and return the text content of a URL."""
        return self._do_web_fetch(url, max_length)

    def _do_web_fetch(self, url, max_length=30000):
        """Fetch a URL via DoH-resolved HTTPS."""
        parsed = urlparse(url)
        host = parsed.netloc.split(":")[0]
        port = 443
        if ":" in parsed.netloc:
            port = int(parsed.netloc.split(":")[1])
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        try:
            resp, body = self._http_get(host, path, port=port, timeout=15)
            ct = resp.headers.get("Content-Type", "")
            charset = "utf-8"
            if "charset=" in ct:
                charset = ct.split("charset=")[-1].split(";")[0].strip()
            try:
                text = body.decode(charset, errors="replace")
            except Exception:
                text = body.decode("utf-8", errors="replace")
            if len(text) > max_length:
                text = text[:max_length] + "\n... [truncated]"
            return {"status": resp.status, "content_type": ct, "body": text, "error": None}
        except Exception as e:
            return {"status": 0, "content_type": "", "body": "", "error": str(e)}

    def close(self):
        """Clean up resources (reserved for future use)."""
        pass


# ── Main (when run directly for testing) ───────────────────
if __name__ == "__main__":
    engine = SearchEngine()
    print(f"[{PRODUCT_NAME}] engine ready", file=sys.stderr)
    results = engine.search("test", max_results=3)
    print(json.dumps(results, ensure_ascii=False, indent=2))
