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
import shutil
import socket
import ssl
import sys
import tarfile
import threading
import time
import urllib.parse
from urllib.parse import urlparse
from pathlib import Path
from html import unescape

import numpy as np
import trafilatura
from fastembed import TextEmbedding

# ── Config ──────────────────────────────────────────────────
PRODUCT_NAME = os.environ.get("MINISEARCH_NAME", "MiniSearch")
DEFAULT_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# DNS-over-HTTPS endpoints (tried in order)
DOH_ENDPOINTS = [
    ("https://dns.google/resolve", "8.8.8.8"),
    ("https://cloudflare-dns.com/dns-query", "1.1.1.1"),
    ("https://dns.quad9.net/dns-query", "9.9.9.9"),
]

MCP_TOOLS = [
    {
        "name": "web_search",
        "description": (
            "Search the web in real time using Bing. Returns ranked titles, URLs, and snippets "
            "from live search results with near-duplicate removal.\n\n"
            "WHEN TO SEARCH — prefer searching whenever:\n"
            "- The query involves facts, news, events, dates, prices, or product information\n"
            "- You are unsure about any detail (search is cheaper than hallucination)\n"
            "- The user asks about recent developments, documentation, or real-world data\n"
            "- Comparing options or verifying claims that exist outside your training data"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query keywords"},
                "max_results": {"type": "integer", "description": "Max results (default 10)", "default": 10},
                "freshness": {
                    "type": "string",
                    "description": (
                        "Bing time filter. One of: d (past day), w (past week), m (past month), y (past year). "
                        "Omit for no time filter. Use w or m for news, reviews, community discussions, "
                        "or any query where freshness matters."
                    ),
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "web_fetch",
        "description": (
            "Fetch a URL and return clean, extracted text content (boilerplate, ads, and nav removed). "
            "Use to read articles, documentation pages, or API responses in full.\n"
            "For broad queries, use web_search first, then fetch specific URLs from its results."
        ),
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

        # ── Infrastructure (init before model loading) ──
        self._api_conn = None
        self._api_conn_host = None
        self._api_conn_lock = threading.Lock()
        self._dns_cache = {}
        self._dns_cache_lock = threading.Lock()
        self._search_cooldown_until = 0
        self._search_fail_count = 0

        # ── Embedding model ──
        if embedding_mode == "local":
            if not os.environ.get("HF_ENDPOINT"):
                os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

            print(f"[{PRODUCT_NAME}] loading embedding model ({self.model_name})...",
                  file=sys.stderr, flush=True)
            self._embedding_model = self._load_local_model()
        else:
            self._embedding_model = None
            print(f"[{PRODUCT_NAME}] using API embedding: {api_endpoint} (model={api_model})",
                  file=sys.stderr, flush=True)

        print(f"[{PRODUCT_NAME}] embedding model ready",
              file=sys.stderr, flush=True)

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

        # Percent-encode any unicode in the path
        path = urllib.parse.quote(path, safe="/?=&:%")

        for _ in range(max_redirects + 1):
            ip = self.resolve_host(host)
            if use_ssl:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
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

    # ── Embedding model ──────────────────────────────────────

    GITHUB_MODELS_URL = "https://github.com/telly6/claude-proxy/releases/download/models-v1"

    def _load_local_model(self):
        """Load embedding model with layered fallback:
        1. Use local_files_only — fastembed checks all cache locations
        2. Download from GitHub Releases → extract tar.gz → use
        3. Download from HuggingFace via fastembed → use
        4. Scan cache for any loadable model as last resort
        """
        model_slug = self.model_name.split("/")[-1]
        cache_dir = self._fastembed_cache_dir()
        model_dir = cache_dir / f"fast-{model_slug}"

        # ── Layer 1: try loading from any local cache ──
        try:
            print(f"[{PRODUCT_NAME}] checking local cache for {self.model_name}...",
                  file=sys.stderr, flush=True)
            return TextEmbedding(
                model_name=self.model_name,
                local_files_only=True,
            )
        except Exception:
            print(f"[{PRODUCT_NAME}] not found in local cache",
                  file=sys.stderr, flush=True)

        # ── Layer 2: download from GitHub Releases ──
        if self._download_from_github(model_slug, model_dir):
            return TextEmbedding(
                model_name=self.model_name,
                specific_model_path=str(model_dir),
                local_files_only=True,
            )

        # ── Layer 3: download via fastembed (HF mirror) ──
        print(f"[{PRODUCT_NAME}] trying HuggingFace download...",
              file=sys.stderr, flush=True)
        try:
            return TextEmbedding(
                model_name=self.model_name,
                local_files_only=False,
            )
        except Exception as e:
            print(f"[{PRODUCT_NAME}] HF download failed: {e}",
                  file=sys.stderr, flush=True)
            return self._fallback_embedding()

    @staticmethod
    def _fastembed_cache_dir():
        """Unified cache directory matching fastembed's native location."""
        return Path(os.path.expanduser("~/.cache/huggingface/hub"))

    def _download_from_github(self, model_slug, model_dir):
        """Download model tar.gz from GitHub Releases and extract.
        Uses urllib for maximum reliability — no DNS hacks, no custom HTTP.
        Returns True on success, False on any failure."""
        import urllib.request

        targz_path = model_dir.parent / f"{model_slug}.tar.gz"
        url = f"{self.GITHUB_MODELS_URL}/{model_slug}.tar.gz"

        try:
            print(f"[{PRODUCT_NAME}] downloading from GitHub: {url}",
                  file=sys.stderr, flush=True)

            req = urllib.request.Request(url, headers={
                "User-Agent": "MiniSearch/1.0",
                "Accept": "application/octet-stream",
            })
            with urllib.request.urlopen(req, timeout=120) as resp:
                if resp.status != 200:
                    print(f"[{PRODUCT_NAME}] GitHub returned {resp.status}",
                          file=sys.stderr, flush=True)
                    return False
                body = resp.read()

            targz_path.write_bytes(body)
            print(f"[{PRODUCT_NAME}] downloaded {len(body)/1024/1024:.0f}MB, extracting...",
                  file=sys.stderr, flush=True)

            with tarfile.open(targz_path, "r:gz") as tar:
                tar.extractall(path=model_dir.parent)

            targz_path.unlink()

            if model_dir.exists() and any(model_dir.iterdir()):
                print(f"[{PRODUCT_NAME}] model extracted to {model_dir}",
                      file=sys.stderr, flush=True)
                return True
            return False
        except Exception as e:
            print(f"[{PRODUCT_NAME}] GitHub download failed: {e}",
                  file=sys.stderr, flush=True)
            if targz_path.exists():
                targz_path.unlink()
            if model_dir.exists():
                shutil.rmtree(model_dir)
            return False

    def _fallback_embedding(self):
        """Last-resort: scan cache for any loadable model."""
        from fastembed import TextEmbedding

        # Try any fast-* directory in the cache
        cache = self._fastembed_cache_dir()
        for d in sorted(cache.glob("fast-*")):
            if not d.is_dir():
                continue
            onnx_files = list(d.glob("*.onnx")) + list(d.glob("onnx/*.onnx"))
            if not onnx_files:
                continue
            print(f"[{PRODUCT_NAME}] fallback: trying {d.name}",
                  file=sys.stderr, flush=True)
            try:
                return TextEmbedding(
                    model_name=self.model_name,
                    specific_model_path=str(d),
                    local_files_only=True,
                )
            except Exception:
                continue

        # Try any model fastembed knows about that might be cached
        for m in TextEmbedding.list_supported_models():
            try:
                return TextEmbedding(
                    model_name=m["model"],
                    local_files_only=True,
                )
            except Exception:
                continue

        raise Exception(
            "No embedding model available. "
            "Download one via the MiniSearch app or run search_server.py "
            "with a working internet connection."
        )

    # ── Embedding re-rank ───────────────────────────────────

    def _cosine_similarity(self, a, b):
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))

    def _get_api_connection(self):
        """Return a cached HTTPS connection, creating one if needed."""
        parsed = urlparse(self.api_endpoint)
        host = parsed.netloc
        port = 443
        if ":" in parsed.netloc:
            host_name, port_str = parsed.netloc.rsplit(":", 1)
            host = host_name
            port = int(port_str)

        with self._api_conn_lock:
            if self._api_conn_host != host and self._api_conn:
                try:
                    self._api_conn.close()
                except Exception:
                    pass
                self._api_conn = None
                self._api_conn_host = None

            if self._api_conn is None:
                ctx = ssl.create_default_context()
                self._api_conn = http.client.HTTPSConnection(
                    host, port, timeout=30, context=ctx)
                self._api_conn_host = host

            return self._api_conn, host, port

    def _api_embed(self, texts):
        """Get embeddings from an external OpenAI-compatible API
        with connection reuse, retry, and exponential backoff."""

        body = json.dumps({
            "model": self.api_model,
            "input": texts,
        }).encode("utf-8")

        parsed = urlparse(self.api_endpoint)
        path = parsed.path or "/v1/embeddings"

        RETRY_MAX = 3
        RETRYABLE_STATUSES = {429, 500, 502, 503, 504}

        last_error = None

        for attempt in range(RETRY_MAX):
            try:
                t0 = time.time()
                conn, host, port = self._get_api_connection()

                conn.request("POST", path, body, {
                    "Host": host,
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                    "Connection": "keep-alive",
                })
                resp = conn.getresponse()
                data = json.loads(resp.read())
                elapsed_ms = int((time.time() - t0) * 1000)

                if resp.status == 200:
                    embeddings = [item["embedding"] for item in sorted(
                        data["data"], key=lambda x: x["index"])]
                    print(f"[{PRODUCT_NAME}] api embed ok {len(texts)} texts "
                          f"→ {len(embeddings)} vectors {elapsed_ms}ms",
                          file=sys.stderr, flush=True)
                    return embeddings

                # Non-retryable client errors (except 429)
                if resp.status != 200 and resp.status not in RETRYABLE_STATUSES:
                    raise Exception(
                        f"API embedding error {resp.status}: {data}")

                last_error = Exception(
                    f"API embedding error {resp.status} (attempt {attempt+1}/{RETRY_MAX}): {data}")

            except (http.client.HTTPException, ConnectionError, TimeoutError,
                    ssl.SSLError, OSError) as e:
                # Connection-level error — close and recreate next time
                last_error = e
                with self._api_conn_lock:
                    try:
                        self._api_conn.close()
                    except Exception:
                        pass
                    self._api_conn = None
                    self._api_conn_host = None
            except Exception as e:
                if "API embedding error" in str(e):
                    last_error = e
                else:
                    raise

            if attempt < RETRY_MAX - 1:
                delay = 2 ** attempt
                print(f"[{PRODUCT_NAME}] api embed retry in {delay}s: {last_error}",
                      file=sys.stderr, flush=True)
                time.sleep(delay)

        raise Exception(f"API embedding failed after {RETRY_MAX} attempts: {last_error}")

    def _embed(self, texts):
        """Get embeddings from local model or API depending on mode."""
        if self.embedding_mode == "api":
            return self._api_embed(texts)
        return list(self._embedding_model.embed(texts))

    def _semantic_dedup(self, results, doc_vecs, threshold=0.92):
        """Remove near-duplicate results by embedding similarity.
        When two results score above threshold, keeps the one with longer content."""
        if len(results) <= 1:
            return list(range(len(results))), doc_vecs

        keep = list(range(len(results)))
        keep_doc_vecs = list(doc_vecs)

        for i in range(len(results)):
            for j in range(i + 1, len(results)):
                if j not in keep or i not in keep:
                    continue
                sim = self._cosine_similarity(doc_vecs[i], doc_vecs[j])
                if sim > threshold:
                    # Keep the one with longer content
                    len_i = len(results[i].get("fulltext", "")) or len(f"{results[i].get('title','')} {results[i].get('snippet','')}")
                    len_j = len(results[j].get("fulltext", "")) or len(f"{results[j].get('title','')} {results[j].get('snippet','')}")
                    remove = i if len_i < len_j else j
                    if remove in keep:
                        keep.remove(remove)

        if len(keep) < len(results):
            print(f"[SEARCH] dedup: {len(results)} → {len(keep)} results "
                  f"(removed {len(results)-len(keep)} near-duplicates)",
                  file=sys.stderr, flush=True)

        return [results[i] for i in keep], [doc_vecs[i] for i in keep]

    def _fetch_all_content(self, all_results, max_fetch=10):
        """Fetch full page content for each result concurrently.
        Stores extracted text in result['fulltext']. Falls back to snippet
        on any fetch failure — always leaves 'fulltext' non-empty."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if not all_results:
            return

        to_fetch = all_results[:max_fetch]

        def _fetch_one(r):
            try:
                parsed = urlparse(r["url"])
                host = parsed.netloc.split(":")[0]
                port = 443
                if ":" in parsed.netloc:
                    port = int(parsed.netloc.split(":")[1])
                path = parsed.path or "/"
                if parsed.query:
                    path += "?" + parsed.query
                resp, body = self._http_get(host, path, port=port, timeout=8)
                ct = resp.headers.get("Content-Type", "")
                charset = "utf-8"
                if "charset=" in ct:
                    charset = ct.split("charset=")[-1].split(";")[0].strip()
                html = body.decode(charset, errors="replace")
                extracted = trafilatura.extract(
                    html, include_comments=False, include_tables=True,
                    include_images=False, include_links=False, output_format="txt",
                )
                if extracted and len(extracted) > 100:
                    r["fulltext"] = extracted
                else:
                    r["fulltext"] = f"{r.get('title', '')} {r.get('snippet', '')}"
            except Exception:
                r["fulltext"] = f"{r.get('title', '')} {r.get('snippet', '')}"

        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futures = [ex.submit(_fetch_one, r) for r in to_fetch]
            for fut in as_completed(futures):
                pass  # results stored in-place

        fetched = sum(1 for r in to_fetch
                      if len(r.get("fulltext", "")) > len(f"{r.get('title','')} {r.get('snippet','')}"))
        print(f"[SEARCH] fetched fulltext for {fetched}/{len(to_fetch)} pages",
              file=sys.stderr, flush=True)

    def _embedding_rerank(self, query, all_results, max_results):
        """Re-rank results by embedding cosine similarity to the query.
        Also performs semantic dedup using the same embedding batch."""
        if not all_results:
            return []

        docs = [r.get("fulltext") or f"{r.get('title', '')} {r.get('snippet', '')}" for r in all_results]
        all_texts = [query] + docs
        embeddings = self._embed(all_texts)
        query_vec = np.array(embeddings[0])
        doc_vecs = np.array(embeddings[1:])

        # Semantic dedup
        all_results, doc_vecs = self._semantic_dedup(all_results, doc_vecs)

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

    def search(self, query, max_results=10, freshness=None):
        """Search the web and return structured results."""
        return self._do_web_search(query, max_results, freshness)

    def _do_web_search(self, query, max_results=10, freshness=None):
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

        # ── Time filter ───────────────────────────────────────
        freshness_suffix = ""
        if freshness in ("d", "w", "m", "y"):
            freshness_suffix = f"&tbs=qdr:{freshness}"

        # ── Backend registry ───────────────────────────────────
        backends = []

        def _bing_path(q):
            return f"/search?q={urllib.parse.quote(q)}&count={max_results}{mkt_suffix}{freshness_suffix}"

        def _bing_page2_path(q):
            return f"/search?q={urllib.parse.quote(q)}&count={max_results}&first=11{mkt_suffix}{freshness_suffix}"

        def _bing_parse(html):
            results = []
            blocks = re.findall(r'<li[^>]*class="[^"]*b_algo[^"]*"[^>]*>(.*?)</li>', html, re.DOTALL)
            for blk in blocks[:max_results]:
                h2_m = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', blk, re.DOTALL)
                if not h2_m:
                    continue
                title = re.sub(r'<[^>]+>', '', h2_m.group(2)).strip()
                title = unescape(title)

                # Extract real URL from <cite> element — the h2 <a> link
                # points to a Bing click-tracker, not the destination page.
                url = h2_m.group(1)
                cite_m = re.search(r'<cite[^>]*>(.*?)</cite>', blk, re.DOTALL)
                if cite_m:
                    cite_text = re.sub(r'<[^>]+>', '', cite_m.group(1)).strip()
                    cite_text = unescape(cite_text).strip()
                    # Bing breadcrumb: "domain.com › path › page"
                    segments = [s.strip() for s in cite_text.split("›")]
                    base = segments[0]
                    if base.startswith("http"):
                        if len(segments) > 1:
                            path = "/".join(segments[1:])
                            url = base.rstrip("/") + "/" + path
                        else:
                            url = base
                    else:
                        url = "https://" + base

                snip_m = re.search(r'<p[^>]*class="[^"]*b_lineclamp[^"]*"[^>]*>(.*?)</p>', blk, re.DOTALL)
                snippet = ""
                if snip_m:
                    snippet = re.sub(r'<[^>]+>', '', snip_m.group(1)).strip()
                    snippet = unescape(snippet)
                    snippet = snippet.replace("&ensp;", " ").replace("&#0183;", "·")
                if title:
                    results.append({"title": title, "url": url, "snippet": snippet})

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

        has_cjk = bool(re.search(r'[一-鿿㐀-䶿]', query))
        mkt_suffix = "" if has_cjk else "&ensearch=1"
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

        # Fetch full page content before embedding re-rank
        self._fetch_all_content(all_results, max_fetch=max_results)

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

            extracted = trafilatura.extract(
                text, include_comments=False, include_tables=True,
                include_images=False, include_links=False, output_format="txt",
            )
            if extracted:
                text = extracted
            if len(text) > max_length:
                text = text[:max_length] + "\n... [truncated]"
            return {"status": resp.status, "content_type": ct, "body": text, "error": None}
        except Exception as e:
            return {"status": 0, "content_type": "", "body": "", "error": str(e)}

    def close(self):
        """Clean up resources."""
        if self._api_conn:
            try:
                self._api_conn.close()
            except Exception:
                pass
            self._api_conn = None


# ── Main (when run directly for testing) ───────────────────
if __name__ == "__main__":
    engine = SearchEngine()
    print(f"[{PRODUCT_NAME}] engine ready", file=sys.stderr)
    results = engine.search("test", max_results=3)
    print(json.dumps(results, ensure_ascii=False, indent=2))
