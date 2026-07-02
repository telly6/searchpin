#!/usr/bin/env python3
"""
Searchpin — Self-hosted web search for AI agents.
Provides web_search + web_fetch via a clean Python API.
Zero external API keys required.
"""

import concurrent.futures
import gzip
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
import zlib
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
from fastembed import TextEmbedding

from searchpin.backends import build_backends
from searchpin.config import (
    DEFAULT_MODEL_NAME,
    DOH_ENDPOINTS,
    PRODUCT_NAME,
    TIMING_LOG_PATH,
)
from searchpin.quality import quality_score
from searchpin.structured_extract import process as structured_extract_process

MCP_TOOLS = [
    {
        "name": "web_search",
        "description": (
            "Search the web via multiple engines (Baidu, Sogou, Bing CN, Bing Intl). "
            "Returns ranked titles, URLs, and snippets "
            "(no full page content — use web_fetch to get the full text of any result). "
            "Results re-ranked by embedding similarity — the top results are the most relevant.\n\n"
            "Iterative search is normal: search → read → refine → search → read → synthesize. "
            "Search returns only titles + snippets. Read snippets to identify promising results, "
            "then call web_fetch to get full page content for the URLs that look most useful.\n\n"
            "BEFORE FETCHING, READ THE SNIPPETS FIRST:\n"
            "- Search results come with title + URL + snippet only (no full content). "
            "Read snippets to decide which URLs are worth fetching.\n"
            "- Fetch only the 1-3 most promising URLs — do not blindly fetch everything.\n"
            "Each unnecessary web_fetch wastes 1-3s per call.\n\n"
            "⛔ WHEN RESULTS LOOK WRONG, DO NOT GIVE UP — ITERATE IMMEDIATELY:\n"
            "If search results are all irrelevant (wrong topic, wrong domain, "
            "generic encyclopedia entries, piracy sites, brand pages, file format tools, "
            "or dictionary entries), DO NOT conclude the information is unavailable. "
            "The fix is almost always a query reformulation. The most common root cause is "
            "Bing's tokenizer splitting your query words into fragments that collide with "
            "unrelated content. Replace fragile/generic terms with INSEPARABLE identifiers — "
            "proper nouns, compound terms, subdomain names, or acronyms that the tokenizer "
            "CANNOT split. Then immediately re-search. Do not narrate the failure — just "
            "try a different formulation.\n"
            "The PRINCIPLE (not the specific domain) matters:\n"
            "  - A law query: 'GDPR enforcement tracker 2026' not 'GDPR fine'\n"
            "  - A car query: '全固态电池量产线' not 'solid state battery'\n"
            "  - A finance query: 'USDJPY exchange rate' not 'yen dollar'\n"
            "  - A programming query: 'rustc 1.87 changelog' not 'Rust release notes'\n"
            "  - FOR CHINESE: no spaces around Chinese chars! '2026年新能源汽车补贴' ✓, '新能源汽车补贴 2026' ✗\n\n"
            "SEARCH STRATEGY (patterns drawn from real-world use):\n\n"
            '1. DATE TERMS HIJACK QUERIES — Putting year numbers or month names ("2026年", '
            '"June") directly in query text often backfires: the engine weights them as the '
            "primary topic and you get calendar summaries or current-events roundups instead "
            "of your actual topic. PREFER the 'freshness' parameter to control recency — it "
            "filters by publication date without polluting the query text.\n\n"
            "2. SHORT COMMON WORDS COLLIDE — In Chinese, single characters that are also "
            "standalone dictionary headwords get tokenized independently and matched to "
            "dictionary/encyclopedia entries, regardless of surrounding context. In English, "
            "short common words that also name major products/services (credit card brands, "
            "consumer goods) cause the same problem. RECOGNISE THE PATTERN: if any word in "
            "your query could appear as a dictionary headword or a product name on its own, "
            "it WILL collide. Embed such terms inside longer inseparable compounds.\n\n"
            "3. LONG PROPER NOUNS ARE ANTI-NOISE ANCHORS — Full institutional names, "
            "drug trade names, legal case codes, product model numbers resist tokenizer "
            "fragmentation. They act as unbreakable signals that pull results toward the "
            "right topic. When a shorter query goes off-target, try a version built around a "
            "specific long-form name.\n\n"
            "4. LANGUAGE-SWITCH ESCAPES TOKENIZER TRAPS — When a Chinese query keeps "
            "hitting noise despite retries, switch "
            "the query to English. English-language media covers many China-specific "
            "topics, and the English tokenizer does not fragment CJK characters into "
            "dictionary entries.\n\n"
            "5. REPLACE THE ANCHOR — Adding another word to a noisy "
            "query rarely fixes it (the original offending token still dominates the "
            "ranking). Instead, restructure the query around a DIFFERENT anchor term "
            "entirely — a proper noun, a model number, or a multi-word technical phrase "
            "that the tokenizer cannot split.\n\n"
            "6. THE VOCABULARY BRIDGE — Chinese search engines match on LEXICOGRAPHIC "
            "(word-level), NOT semantic. The words you use MUST match how the target "
            "documents actually phrase things. This creates a critical gap:\n"
            "  - User language (descriptive): 极端天气, 气候灾害, 高温热浪\n"
            "  - Source language (operational): 暴雨橙警, 三级应急响应, 解除预警\n"
            "  These are two entirely different vocabulary systems and the engine CANNOT "
            "automatically map between them. When abstract category terms return only "
            "encyclopedia definitions and year-old retrospectives, switch to the "
            "OPERATIONAL terms that the institutions/sources themselves use — alert "
            "levels, government response codes, proper institutional names, numeric "
            'thresholds ("四十度"), or named entities ("台风蔷薇").\n'
            "  - Abstract: '2026年极端天气气候灾害' → only dictionaries & retrospectives\n"
            "  - Operational: '暴雨橙警 应急响应 中央气象台' → nmc.cn real-time alerts\n"
            "  This is not a data-coverage problem. The documents exist in the index. "
            "They just use a different vocabulary than you searched for.\n\n"
            "⚡ NUMERIC DATA CROSS-VERIFICATION:\n"
            "- When a critical number appears in one result, confirm it against "
            "at least one other source before accepting it as fact. Different "
            "aggregators can lag; conflicting values demand a third source.\n\n"
            "⛔ DO NOT STOP EARLY — PERSISTENCE IS REQUIRED:\n"
            "- When a search returns 10 irrelevant results, that does NOT mean the "
            "information doesn't exist. It means the current query formulation failed "
            "to reach it. Real-world testing shows: the same engine (baidu/bing_cn) "
            "that returned 100% calendar-dictionary noise for '2026年极端天气' returned "
            "nmc.cn real-time severe weather alerts (rerank 0.908) when reformulated as "
            "'暴雨洪涝 应急响应 中央气象台 预警'.\n"
            "- Top-10 failure is a QUERY PROBLEM, not a content-availability problem. "
            "The valid pages are likely at positions 11-30, pushed out of view by "
            "noise that matched your abstract terms. Do not conclude 'information "
            "unavailable' from a failed top 10.\n"
            "- EXHAUST AT LEAST 3-4 DISTINCT STRATEGIES before any 'not found' verdict:\n"
            "  1. Different vocabulary (descriptive → operational)\n"
            "  2. Different language (CN ↔ EN)\n"
            "  3. Different anchors (category term → proper name/number)\n"
            "  4. Site-restricted search (site:target-source.tld)\n"
            "- Never stop after 1-2 rounds just because the first attempts returned noise. "
            "The difference between 'completely unsolvable' and 'fully answered in 1 round' "
            "is often a single query reformulation — changing '极端天气' to '暴雨橙警'.\n\n"
            "CONDUCT ALL ITERATIONS SILENTLY: "
            "When you need multiple rounds of searching and fetching to gather "
            "information, run all iterations as tool calls without narrating each step "
            "in your reply. Present only the final synthesized answer to the user. "
            "Do NOT say things like 'let me search again' or 'I tried searching for X "
            "but got Y, let me try Z instead' — just do it and deliver the result."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query keywords"},
                "freshness": {
                    "type": "string",
                    "description": (
                        "Time filter. One of: d (past day), w (past week), m (past month), y (past year). "
                        "PREFER this over putting years/months in the query text — date words in "
                        "queries get weighted as the primary topic and cause noise. This parameter "
                        "filters by publication date without polluting the query. Omit for no filter."
                    ),
                },
                "topic": {
                    "type": "string",
                    "description": (
                        "Search vertical. 'general' (default, web search) or 'news' (Bing News — "
                        "prioritises recent articles from mainstream media; best for earnings, "
                        "sports scores, political events, breaking stories). "
                        "Also useful as an escape hatch: when 'general' returns Chinese dictionary "
                        "entries for a query that should have news coverage, switching to 'news' "
                        "can bypass the dictionary index entirely."
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max results to return (default 10, max 20). Controls output count only.",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 20,
                },
                "include_domains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Limit results to ONLY these domains (whitelist). "
                        "Use when you want results from specific sources "
                        "(e.g. ['docs.python.org', 'python.org'] for Python docs only). "
                        "Applied before re-ranking. Empty/omitted = no restriction. "
                        "Supplied by the LLM at runtime — no hardcoded list."
                    ),
                },
                "exclude_domains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Domains to filter OUT of results before re-ranking. "
                        "Use when a previous search returned pages from a noise domain "
                        "(e.g. a dictionary site, a brand page, a mirror). "
                        "Example: ['zidian.gushici.net', 'hancibao.com']. "
                        "Supply at runtime only — no permanent blocklist."
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
            "For broad queries, use web_search first, then fetch specific URLs from its results.\n"
            "After fetching, look for technical terms, names, or references you can use "
            "as keywords for a better follow-up search.\n\n"
            "⚠️ FAILURE IS NORMAL — DO NOT GIVE UP AFTER 1-2 FAILED FETCHES:\n"
            "- If a fetch returns empty body, 403, or obvious JS-template garbage, try the NEXT URL "
            "from the search results immediately. Each retry costs only ~0.5s.\n"
            "- Common failure causes: JS-rendered SPA shells (stock pages, forums), "
            "Chinese paywalls/captchas (wenku.baidu.com, zhihu.com), government site timeouts.\n"
            "- Rule of thumb: try at least 3 URLs from 3 different domains before concluding "
            "the content is unreachable. Skipping this wastes the search you already paid for.\n"
            "- When retrying, pick a URL from a DIFFERENT domain — same-domain failures often share "
            "the same root cause (e.g., all pages behind the same Cloudflare/WAF).\n\n"
            "RETRY SILENTLY: "
            "When a fetch fails, retry with the next URL immediately as another tool call. "
            "Do NOT narrate each failure to the user ('this one failed, trying another…'). "
            "Only mention failures in your final reply if ALL attempts were exhausted."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch"},
            },
            "required": ["url"],
        },
    },
]


class SearchEngine:
    """Self-contained web search engine.  DNS-over-HTTPS, multi-engine
    search (baidu/sogou/bing_cn/bing_intl), and local embedding re-rank
    — no external API keys needed."""

    _timing_log_path = TIMING_LOG_PATH

    @classmethod
    def _log_timing(cls, entry):
        """Write a timing entry to the timing log, if enabled.
        Set SEARCHPIN_TIMING_LOG='' to disable."""
        if not cls._timing_log_path:
            return
        try:
            with open(cls._timing_log_path, "a") as _tf:
                _tf.write(entry)
        except OSError:
            pass

    def __init__(
        self,
        model_name=None,
        max_workers=3,
        embedding_mode="local",
        api_endpoint=None,
        api_key=None,
        api_model=None,
    ):
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

        # ── Fetch strategy cache (runtime-learned, zero hardcoding) ──
        # domain → (strategy, timestamp)
        #   'ok'      — bare HTTP works, content available
        #   'blocked' — CDN/WAF block confirmed (2h TTL, auto-retry after expiry)
        self._fetch_strategy: dict[str, tuple[str, float]] = {}

        # ── Per-engine session & rate limit ──
        # Persistent cookies per host (Baidu session, Sogou session, etc.)
        self._host_cookies = {}  # host → cookie string
        self._host_cookies_lock = threading.Lock()
        # Per-engine backoff: host → earliest time next request allowed
        self._engine_backoff_until = {}
        self._engine_backoff_lock = threading.Lock()
        # Per-engine consecutive penalty count (doubled on each failure)
        self._engine_backoff_secs = {}  # host → current penalty seconds

        # ── Embedding model ──
        if embedding_mode == "local":
            if not os.environ.get("HF_ENDPOINT"):
                os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

            print(f"[{PRODUCT_NAME}] loading embedding model ({self.model_name})...", file=sys.stderr, flush=True)
            self._embedding_model = self._load_local_model()
            print(f"[{PRODUCT_NAME}] embedding model ready", file=sys.stderr, flush=True)
        else:
            self._embedding_model = None
            print(
                f"[{PRODUCT_NAME}] using API embedding: {api_endpoint} (model={api_model})", file=sys.stderr, flush=True
            )

    # ── DNS Resolution ──────────────────────────────────────

    def resolve_host(self, host, force_doh=False):
        """Resolve hostname to IP. Tries system resolver first, then DoH.
        Set force_doh=True to prefer DoH (avoids China CDN poisoning for intl hosts)."""
        _dns_start = time.time()
        with self._dns_cache_lock:
            if host in self._dns_cache:
                _dns_elapsed = time.time() - _dns_start
                if _dns_elapsed > 0.001:
                    SearchEngine._log_timing(f"[TIMING] dns {host} cache hit {_dns_elapsed * 1000:.0f}ms\n")
                return self._dns_cache[host]

        first, second = ("doh", "system") if force_doh else ("system", "doh")

        for method in (first, second):
            if method == "system":
                _sys_start = time.time()
                try:
                    addr = socket.getaddrinfo(host, 443)[0][4][0]
                    with self._dns_cache_lock:
                        self._dns_cache[host] = addr
                    _sys_elapsed = (time.time() - _sys_start) * 1000
                    print(f"[DNS] system resolver: {host} → {addr} ({_sys_elapsed:.0f}ms)", file=sys.stderr, flush=True)
                    SearchEngine._log_timing(f"[TIMING] dns system {host}={_sys_elapsed:.0f}ms\n")
                    return addr
                except Exception:
                    continue
            else:
                for doh_url, doh_ip in DOH_ENDPOINTS:
                    _doh_start = time.time()
                    try:
                        ctx = ssl.create_default_context()
                        ctx.check_hostname = False
                        ctx.verify_mode = ssl.CERT_NONE

                        parsed = urlparse(doh_url)
                        doh_host_url = parsed.netloc

                        conn = http.client.HTTPSConnection(doh_ip, timeout=3, context=ctx)
                        conn.request(
                            "GET",
                            parsed.path + f"?name={host}&type=A",
                            headers={"Host": doh_host_url, "Accept": "application/dns-json"},
                        )
                        resp = conn.getresponse()
                        if resp.status == 200:
                            data = json.loads(resp.read())
                            for ans in data.get("Answer", []):
                                if ans.get("type") == 1:
                                    addr = ans["data"]
                                    with self._dns_cache_lock:
                                        self._dns_cache[host] = addr
                                    _doh_elapsed = (time.time() - _doh_start) * 1000
                                    print(
                                        f"[DNS] {host} → {addr} (via {doh_host_url}, {_doh_elapsed:.0f}ms)",
                                        file=sys.stderr,
                                        flush=True,
                                    )
                                    SearchEngine._log_timing(f"[TIMING] dns doh {host}={_doh_elapsed:.0f}ms\n")
                                    return addr
                        conn.close()
                    except Exception as e:
                        _doh_elapsed = (time.time() - _doh_start) * 1000
                        print(
                            f"[DNS] DoH {doh_host_url} failed in {_doh_elapsed:.0f}ms: {e}", file=sys.stderr, flush=True
                        )
                        continue

        raise Exception(f"Cannot resolve {host} via any method")

    # ── HTTP ────────────────────────────────────────────────

    def _http_get(
        self,
        host,
        path="/",
        port=443,
        timeout=15,
        follow_redirects=False,
        max_redirects=3,
        cookies=None,
        extra_headers=None,
        force_doh=False,
        simple_headers=False,
        force_tls12=False,
    ):
        """DoH-resolved HTTP/HTTPS GET.

        simple_headers=True strips Sec-Fetch-*, Upgrade-Insecure-Requests,
        and DNT headers — useful for engines that flag these as bot signals
        (e.g. Sogou's antispider)."""
        import socket as _sock

        _http_start = time.time()
        use_ssl = port == 443
        _jar = cookies

        # Percent-encode any unicode in the path
        path = urllib.parse.quote(path, safe="/?=&:%")

        body = b""  # guard against redirect chain exhausting all iterations
        for _ in range(max_redirects + 1):
            _dns_before = time.time()
            ip = self.resolve_host(host, force_doh=force_doh)
            _dns_time = time.time() - _dns_before
            if use_ssl:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                if force_tls12:
                    ctx.maximum_version = ssl.TLSVersion.TLSv1_2
                conn = http.client.HTTPSConnection(ip, port, timeout=timeout, context=ctx)

                def _custom_connect():
                    sock = _sock.create_connection((ip, port), timeout=timeout)
                    conn.sock = ctx.wrap_socket(sock, server_hostname=host)

                conn.connect = _custom_connect
            else:
                conn = http.client.HTTPConnection(ip, port, timeout=timeout)

            _headers = {
                "Host": host,
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/143.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": f"https://{host}/",
            }
            if not simple_headers:
                _headers.update(
                    {
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none",
                        "Sec-Fetch-User": "?1",
                        "Upgrade-Insecure-Requests": "1",
                        "DNT": "1",
                    }
                )
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
                    return resp, b"", _jar
                parsed = urlparse(location)
                if parsed.netloc:
                    host = parsed.netloc.split(":")[0]
                    if ":" in parsed.netloc:
                        port = int(parsed.netloc.split(":")[1])
                    else:
                        port = 443 if parsed.scheme == "https" else 80
                    use_ssl = parsed.scheme == "https"
                path = parsed.path or "/"
                if parsed.query:
                    path += "?" + parsed.query
                print(f"[HTTP] redirect → {host}{path}", file=sys.stderr, flush=True)
                continue

            body = resp.read()
            # Decompress if server sent compressed response
            content_encoding = resp.headers.get("Content-Encoding", "")
            if content_encoding:
                encodings = [e.strip() for e in content_encoding.lower().split(",")]
                for enc in reversed(encodings):  # outermost last
                    if enc == "gzip":
                        body = gzip.decompress(body)
                    elif enc == "deflate":
                        body = zlib.decompress(body)
                    elif enc == "br":
                        try:
                            import brotli

                            body = brotli.decompress(body)
                        except ImportError:
                            pass  # fall through, hope it's actually uncompressed
            _http_elapsed = (time.time() - _http_start) * 1000
            SearchEngine._log_timing(
                f"[TIMING] http_get {host}{path[:60]} dns={_dns_time * 1000:.0f}ms total={_http_elapsed:.0f}ms status={resp.status}\n"
            )
            conn.close()
            return resp, body, _jar

        _http_elapsed = (time.time() - _http_start) * 1000
        SearchEngine._log_timing(
            f"[TIMING] http_get {host}{path[:60]} dns={_dns_time * 1000:.0f}ms total={_http_elapsed:.0f}ms status={resp.status}\n"
        )
        return resp, body, _jar

    # ── Embedding model ──────────────────────────────────────

    def _load_local_model(self):
        """Load embedding model with layered fallback:
        1. Use local_files_only — fastembed checks all cache locations
        2. Download from HuggingFace via fastembed → use
        3. Scan cache for any loadable model as last resort
        """
        model_slug = self.model_name.split("/")[-1]
        cache_dir = self._fastembed_cache_dir()
        model_dir = cache_dir / f"fast-{model_slug}"

        # ── Layer 1: try loading from any local cache ──
        try:
            print(f"[{PRODUCT_NAME}] checking local cache for {self.model_name}...", file=sys.stderr, flush=True)
            return TextEmbedding(
                model_name=self.model_name,
                cache_dir=str(cache_dir),
                local_files_only=True,
            )
        except Exception:
            print(f"[{PRODUCT_NAME}] not found in local cache", file=sys.stderr, flush=True)

        # ── Layer 2: download via fastembed (HF mirror) ──
        print(f"[{PRODUCT_NAME}] trying HuggingFace download...", file=sys.stderr, flush=True)
        try:
            return TextEmbedding(
                model_name=self.model_name,
                cache_dir=str(cache_dir),
                local_files_only=False,
            )
        except Exception as e:
            print(f"[{PRODUCT_NAME}] HF download failed: {e}", file=sys.stderr, flush=True)
            return self._fallback_embedding()

    @staticmethod
    def _fastembed_cache_dir():
        """Unified cache directory matching fastembed's native location."""
        return Path(os.path.expanduser("~/.cache/huggingface/hub"))

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
            print(f"[{PRODUCT_NAME}] fallback: trying {d.name}", file=sys.stderr, flush=True)
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
            "No embedding model available. Download one by running search_server.py with a working internet connection."
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
                self._api_conn = http.client.HTTPSConnection(host, port, timeout=30, context=ctx)
                self._api_conn_host = host

            return self._api_conn, host, port

    def _api_embed(self, texts):
        """Get embeddings from an external OpenAI-compatible API
        with connection reuse, retry, and exponential backoff."""

        body = json.dumps(
            {
                "model": self.api_model,
                "input": texts,
            }
        ).encode("utf-8")

        parsed = urlparse(self.api_endpoint)
        path = parsed.path or "/v1/embeddings"

        RETRY_MAX = 3
        RETRYABLE_STATUSES = {429, 500, 502, 503, 504}

        last_error = None

        for attempt in range(RETRY_MAX):
            fatal_error = None
            try:
                t0 = time.time()
                conn, host, _ = self._get_api_connection()

                conn.request(
                    "POST",
                    path,
                    body,
                    {
                        "Host": host,
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}",
                        "Connection": "keep-alive",
                    },
                )
                resp = conn.getresponse()
                data = json.loads(resp.read())
                elapsed_ms = int((time.time() - t0) * 1000)

                if resp.status == 200:
                    embeddings = [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
                    print(
                        f"[{PRODUCT_NAME}] api embed ok {len(texts)} texts → {len(embeddings)} vectors {elapsed_ms}ms",
                        file=sys.stderr,
                        flush=True,
                    )
                    return embeddings

                # Non-retryable client errors — flag for immediate raise.
                # Must not raise inside try (caught by catch-all below).
                if resp.status not in RETRYABLE_STATUSES:
                    fatal_error = Exception(f"API embedding error {resp.status}: {data}")
                else:
                    last_error = Exception(
                        f"API embedding error {resp.status} (attempt {attempt + 1}/{RETRY_MAX}): {data}"
                    )

            except (http.client.HTTPException, ConnectionError, TimeoutError, ssl.SSLError, OSError) as e:
                # Connection-level error — close and recreate next time
                last_error = e
                with self._api_conn_lock:
                    try:
                        self._api_conn.close()
                    except Exception:
                        pass
                    self._api_conn = None
                    self._api_conn_host = None

            if fatal_error:
                raise fatal_error

            if attempt < RETRY_MAX - 1:
                delay = 2**attempt
                print(f"[{PRODUCT_NAME}] api embed retry in {delay}s: {last_error}", file=sys.stderr, flush=True)
                time.sleep(delay)

        raise Exception(f"API embedding failed after {RETRY_MAX} attempts: {last_error}")

    def _embed(self, texts):
        """Get embeddings from local model or API depending on mode."""
        if self.embedding_mode == "api":
            return self._api_embed(texts)
        return list(self._embedding_model.embed(texts))

    @staticmethod
    def _extract_text(html):
        """Strip scripts, styles, and tags, then collapse whitespace.
        Returns (text, source) where source is 'html-strip' or ''."""
        # HTML text-strip — strip all tags, collapse whitespace
        text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            return text, "html-strip"

        return "", ""

    def _embedding_rerank(self, query, all_results):
        """Re-rank results by embedding cosine similarity to the query.
        Uses title + snippet as document representation (no truncation)."""
        _rerank_start = time.time()
        if not all_results:
            return []

        docs = [f"{r.get('title', '')} {r.get('snippet', '')}" for r in all_results]
        all_texts = [query] + docs
        _t_before_embed = time.time()
        embeddings = self._embed(all_texts)
        _t_embed_done = time.time()
        query_vec = np.array(embeddings[0])
        doc_vecs = np.array(embeddings[1:])

        scored = []
        for i, r in enumerate(all_results):
            sim = self._cosine_similarity(query_vec, doc_vecs[i])
            r["_rerank_score"] = float(sim)
            scored.append((sim, r))

        scored.sort(key=lambda x: x[0], reverse=True)

        top = [r for _, r in scored]

        _t_total_rerank = time.time() - _rerank_start
        print(f"[SEARCH] reranked {len(top)} results (no truncation)", file=sys.stderr, flush=True)
        SearchEngine._log_timing(
            f"[TIMING] rerank total={_t_total_rerank:.2f}s embed={_t_embed_done - _t_before_embed:.2f}s\n"
        )
        return top

    # ── Web search ──────────────────────────────────────────

    def search(self, query, max_results=10, freshness=None, topic=None, exclude_domains=None, include_domains=None):
        """Search the web and return structured results.

        Args:
            topic: 'general' (default), 'news' — uses Bing News vertical
            exclude_domains: optional list of domains to filter out,
                             applied BEFORE the embedding re-rank.
                             Supplied by the LLM at runtime; NO list
                             is maintained in code.
            include_domains: optional list of domains to restrict results to
                             (whitelist). Applied BEFORE re-rank.
        """
        return self._do_web_search(
            query,
            max_results,
            freshness,
            topic=topic,
            exclude_domains=exclude_domains,
            include_domains=include_domains,
        )

    def _do_web_search(
        self,
        query,
        max_results=10,
        freshness=None,
        topic=None,
        exclude_domains=None,
        include_domains=None,
        _retry_depth=0,
    ):
        """Web search via DoH-resolved HTTPS. Fires all 4 engines
        (baidu, sogou, bing_cn, bing_intl) in parallel, then
        de-duplicates and re-ranks the merged results.

        Engine mix designed for complementary coverage:
          baidu       – Chinese-language sites, government portals
          sogou       – WeChat public accounts, Zhihu
          cn.bing.com – Chinese market index (zh-CN Accept-Language)
          www.bing.com – International index (en-US Accept-Language)

        If one engine's tokenizer splits your query into dictionary
        entries, the others often have the real pages.

        topic='news' switches to Bing's /news/search vertical, which
        prioritises recent articles from mainstream media sources.

        exclude_domains (list[str]|None) removes results whose URL domain
        matches any entry.  include_domains (list[str]|None) keeps ONLY
        results matching the whitelist.  Both applied post-parse, pre-re-rank.
        The LLM supplies these lists at runtime — no hardcoded domain lists."""

        _t_start = time.time()
        SearchEngine._log_timing(
            f"[TIMING] _do_web_search exclude_domains={exclude_domains!r} topic={topic!r} q={str(query or '')[:50]!r}\n"
        )
        # Normalize query to string (handle int/float/None from malformed JSON-RPC)
        query = str(query or "").strip()
        # ── Guard ───────────────────────────────────────────
        if not query:
            return {"error": "empty query", "results": [], "query": query}
        now = time.time()
        if now < self._search_cooldown_until:
            self._search_fail_count += 1
            return {
                "error": f"search unavailable (cooldown, {self._search_fail_count} attempts blocked)",
                "results": [],
                "query": query,
            }

        freshness_suffix = ""
        if freshness in ("d", "w", "m", "y"):
            freshness_suffix = f"&tbs=qdr:{freshness}"

        # ── Page 1: fire all engines ────────────────────────
        all_results = []
        seen_urls = set()
        page_fetch_ms = []

        p1_backends = build_backends(query, page=0, topic=topic, freshness_suffix=freshness_suffix)
        p1_results, any_success, p1_ms = self._search_fire_one_page(p1_backends, seen_urls)
        all_results.extend(p1_results)
        page_fetch_ms.append(p1_ms)

        if not any_success:
            self._search_cooldown_until = time.time() + 30
            self._search_fail_count = 1
            print("[SEARCH] entering 30s cooldown (all backends failed)", file=sys.stderr, flush=True)
            return {"error": "all backends failed", "results": [], "query": query}

        self._search_cooldown_until = 0
        self._search_fail_count = 0

        # ── News fallback #1: empty results ─────────────────
        if topic == "news" and len(all_results) == 0:
            print("[SEARCH] topic=news returned 0 results, falling back to general", file=sys.stderr, flush=True)
            return self._do_web_search(
                query,
                max_results,
                freshness,
                topic="general",
                exclude_domains=exclude_domains,
                include_domains=include_domains,
                _retry_depth=_retry_depth + 1,
            )

        # ── Domain filtering ────────────────────────────────
        self._search_filter_domains(all_results, include_domains, exclude_domains)

        _t_after_bing = time.time()

        # ── Rerank ──────────────────────────────────────────
        ranked = self._embedding_rerank(query, all_results)
        print(f"[SEARCH] {len(all_results)} results → {len(ranked)} after re-rank", file=sys.stderr, flush=True)

        _t_after_rerank = time.time()

        _t_bing = _t_after_bing - _t_start
        _t_rerank = _t_after_rerank - _t_after_bing
        _pagination_info = f" pages={len(page_fetch_ms)}" if len(page_fetch_ms) > 1 else ""
        SearchEngine._log_timing(
            f"[TIMING] search total={_t_after_rerank - _t_start:.2f}s "
            f"fetch={_t_bing:.2f}s rerank={_t_rerank:.2f}s{_pagination_info}\n"
        )

        # ── Assemble response ───────────────────────────────
        _results_out = []
        _engine_counts = {}
        for r in ranked[:max_results]:
            eng = r.get("_source_engine", "unknown")
            _engine_counts[eng] = _engine_counts.get(eng, 0) + 1
            _results_out.append(
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("snippet", ""),
                    "content": r.get("snippet", ""),  # snippet only — LLM uses web_fetch for full text
                    "_rerank_score": r.get("_rerank_score", 0),
                    "_source_engine": eng,
                }
            )
        _t_total = time.time() - _t_start
        response = {
            "results": _results_out,
            "query": query,
            "backend": "multi",
            "_timing": {
                "total": round(_t_total, 2),
                "stages": {
                    "search": round(_t_bing, 2),
                    "rerank": round(_t_rerank, 2),
                    "pages": len(page_fetch_ms),
                    "page_ms": page_fetch_ms,
                    "num_results_merged": len(all_results),
                },
                "engine_counts": _engine_counts,
            },
        }
        return response

    # ── Search pipeline stage methods ─────────────────────────
    # Each stage extracted from _do_web_search — same logic, named interface.

    def _search_fetch_one(self, host, path, parse_fn, follow, port, accept_language, pool_tag):
        """Fetch a single engine's results. Handles backoff, cookies,
        anti-spider detection. Returns (host, html|status_tag, parse_fn|None, elapsed, tag)."""
        _pool_start = time.time()

        with self._engine_backoff_lock:
            bo_until = self._engine_backoff_until.get(host, 0)
        _now = time.time()
        if _now < bo_until:
            wait = bo_until - _now
            print(f"[SEARCH] {host}[{pool_tag}] backoff wait {wait:.1f}s", file=sys.stderr, flush=True)
            time.sleep(wait)

        with self._host_cookies_lock:
            cookies = self._host_cookies.get(host)

        # ── Sogou: acquire homepage cookies to avoid antispider ─
        # Sogou's web_hd detection requires ABTEST + IPLOC cookies
        # from the homepage before the first search request.
        if host == "www.sogou.com" and not cookies:
            try:
                _, _, _hp_jar = self._http_get(host, "/", timeout=12, force_tls12=True, simple_headers=True)
                if _hp_jar:
                    with self._host_cookies_lock:
                        self._host_cookies[host] = _hp_jar
                    cookies = _hp_jar
                    print("[SEARCH] sogou homepage cookie seeded", file=sys.stderr, flush=True)
            except Exception:
                pass

        try:
            print(f"[SEARCH] trying {host}{path}", file=sys.stderr, flush=True)
            extra = {"Accept-Language": accept_language}
            # Sogou flags Sec-Fetch-* and Upgrade-Insecure-Requests as
            # bot signals — use simple headers to avoid antispider.
            # Python's default TLS 1.3 fingerprint also triggers Sogou's
            # headless-detection (antip=web_hd) — cap at TLS 1.2.
            _simple = host == "www.sogou.com"
            _tls12 = host == "www.sogou.com"
            resp, body, jar = self._http_get(
                host,
                path,
                timeout=12,
                follow_redirects=follow,
                port=port,
                extra_headers=extra,
                cookies=cookies,
                simple_headers=_simple,
                force_tls12=_tls12,
            )

            if jar:
                with self._host_cookies_lock:
                    self._host_cookies[host] = jar

            html = body.decode("utf-8", errors="replace")
            _pool_elapsed = time.time() - _pool_start

            # ── Sogou anti-spider detection ─────────────────
            # Sogou redirects to /antispider/ when it detects bots.
            # With follow_redirects=True, the 302 is followed and we
            # get a 200 antispider page.  Detect both cases.
            if host == "www.sogou.com":
                _loc = resp.getheader("Location") or ""
                _is_antispider = (
                    # Case 1: 302 block (follow_redirects=False path)
                    (
                        resp.status == 302
                        and len(html) < 500
                        and ("antispider" in html.lower() or "antispider" in _loc.lower())
                    )
                    # Case 2: 200 antispider page (followed redirect)
                    or (resp.status == 200 and "/antispider/" in html[:500].lower() and len(html) < 5000)
                )
                if _is_antispider:
                    with self._engine_backoff_lock:
                        cur = self._engine_backoff_secs.get(host, 30)
                        # Penalty doubles each time, capped at 120s for IP cooldown
                        penalty = min(cur * 2, 120)
                        self._engine_backoff_secs[host] = penalty
                        self._engine_backoff_until[host] = time.time() + penalty
                    print(f"[SEARCH] sogou antispider → backoff {penalty}s", file=sys.stderr, flush=True)
                    return host, "antispider", None, _pool_elapsed, pool_tag
            # ── Baidu captcha detection ────────────────────
            if host == "www.baidu.com":
                loc = resp.getheader("Location") or ""
                if resp.status == 302 and ("wappass.baidu.com" in loc or "wappass.baidu.com" in html):
                    with self._engine_backoff_lock:
                        cur = self._engine_backoff_secs.get(host, 30)
                        self._engine_backoff_secs[host] = cur
                        self._engine_backoff_until[host] = time.time() + cur
                    print(f"[SEARCH] baidu captcha → backoff {cur}s", file=sys.stderr, flush=True)
                    return host, "captcha", None, _pool_elapsed, pool_tag

            return host, html, parse_fn, _pool_elapsed, pool_tag
        except Exception as e:
            _pool_elapsed = time.time() - _pool_start
            return host, str(e), None, _pool_elapsed, pool_tag

    def _search_fire_one_page(self, backends, seen_urls):
        """Fire one page batch across all engines in parallel.
        Returns (page_results, any_success, batch_ms)."""
        _batch_start = time.time()
        pool_lock = threading.Lock()
        page_results = []
        page_any_success = [False]

        with concurrent.futures.ThreadPoolExecutor(max_workers=max(self.max_workers, 6)) as ex:
            futures = [
                ex.submit(self._search_fetch_one, h, p, ps, fw, pt, al, ptg) for h, p, ps, fw, pt, al, ptg in backends
            ]

            for fut in concurrent.futures.as_completed(futures):
                host, html, parse_fn, pool_elapsed, pool_tag = fut.result()
                if parse_fn is None:
                    print(
                        f"[SEARCH] {host}[{pool_tag}] failed after {pool_elapsed:.2f}s: {html[:100] if html else 'unknown'}",
                        file=sys.stderr,
                        flush=True,
                    )
                    continue
                _parse_start = time.time()
                try:
                    results = parse_fn(html)
                except Exception as _parse_err:
                    _parse_elapsed = time.time() - _parse_start
                    print(f"[SEARCH] {host}[{pool_tag}] parse error: {_parse_err}", file=sys.stderr, flush=True)
                    continue
                _parse_elapsed = time.time() - _parse_start
                if results:
                    # Derive engine name from pool_tag (strip trailing _pgN)
                    _engine = "_".join(pool_tag.split("_")[:-1]) if "_pg" in pool_tag else pool_tag
                    with pool_lock:
                        page_any_success[0] = True
                        for r in results:
                            url_key = r["url"].lower().rstrip("/")
                            if url_key not in seen_urls:
                                seen_urls.add(url_key)
                                r["_source_engine"] = _engine
                                page_results.append(r)
                    print(
                        f"[SEARCH] {host}[{pool_tag}] returned {len(results)} results "
                        f"(+{len(page_results)} new after dedup)",
                        file=sys.stderr,
                        flush=True,
                    )
                    SearchEngine._log_timing(
                        f"[TIMING] pool={pool_tag} fetch={pool_elapsed:.2f}s "
                        f"parse={_parse_elapsed:.2f}s results={len(results)}\n"
                    )
                else:
                    print(
                        f"[SEARCH] {host}[{pool_tag}] returned 0 parsed results "
                        f"(HTML {len(html)} bytes) fetch={pool_elapsed:.2f}s",
                        file=sys.stderr,
                        flush=True,
                    )

        _batch_ms = int((time.time() - _batch_start) * 1000)
        return page_results, page_any_success[0], _batch_ms

    def _search_filter_domains(self, all_results, include_domains, exclude_domains):
        """Post-filter results by domain whitelist/blacklist. Mutates list in-place."""
        if include_domains and all_results:
            include_set = {d.lower().strip() for d in include_domains}
            before = len(all_results)
            filtered = []
            for r in all_results:
                try:
                    dom = urlparse(r.get("url", "")).netloc.lower()
                except Exception:
                    dom = ""
                for inc in include_set:
                    if dom == inc or dom.endswith("." + inc):
                        filtered.append(r)
                        break
            all_results[:] = filtered
            kept = len(all_results)
            if kept < before:
                domain_list = ", ".join(sorted(include_set))
                print(
                    f"[SEARCH] include_domains: {before} → {kept} (only [{domain_list}])", file=sys.stderr, flush=True
                )
                SearchEngine._log_timing(f"[TIMING] include_domains kept={kept} before={before}\n")

        if exclude_domains and all_results:
            exclude_set = {d.lower().strip() for d in exclude_domains}
            before = len(all_results)
            filtered = []
            for r in all_results:
                matched = False
                try:
                    dom = urlparse(r.get("url", "")).netloc.lower()
                except Exception:
                    dom = ""
                for ex in exclude_set:
                    if dom == ex or dom.endswith("." + ex):
                        matched = True
                        break
                if not matched:
                    filtered.append(r)
            all_results[:] = filtered
            removed = before - len(all_results)
            if removed:
                domain_list = ", ".join(sorted(exclude_set))
                print(
                    f"[SEARCH] exclude_domains: {before} → {len(all_results)} (removed {removed} from [{domain_list}])",
                    file=sys.stderr,
                    flush=True,
                )
                SearchEngine._log_timing(
                    f"[TIMING] exclude_domains removed={removed} before={before} after={len(all_results)}\n"
                )
            else:
                SearchEngine._log_timing(f"[TIMING] exclude_domains no_match before={before}\n")

    # ── Web fetch ───────────────────────────────────────────

    def _http_blocked(self, status, body, host):
        """Zero-hardcode blocked-response detection.

        Pure statistical quality scoring — no keywords, no entity lists,
        no domain knowledge.  Same methodology as overlay dismiss:
        measure structure, not content."""
        if status in (401, 402, 403):
            # HTTP-standard auth/fee/forbidden — 402 Payment Required is a
            # protocol-level signal (RFC 7231 §6.5.2), not a domain hardcode.
            return True
        score = quality_score(body)
        blocked = score < 0.35
        if blocked:
            print(f"[{PRODUCT_NAME}] _http_blocked {host}: quality={score:.2f} → blocked", file=sys.stderr, flush=True)
        return blocked

    def fetch(self, url):
        """Fetch and return the text content of a URL."""
        return self._do_web_fetch(url)

    def _do_web_fetch(self, url):
        """Fetch a URL with a two-tier runtime-learned strategy cache.

        Tier 1 — 'ok':      bare HTTP works, extract content + structured data.
        Tier 2 — 'blocked':  CDN/WAF block confirmed (2h TTL, auto-retry after expiry).

        All strategy transitions are driven by measurable statistical
        properties (quality scores, text lengths) — zero hardcoded
        domain lists, zero keyword matching."""
        _fetch_start = time.time()
        if not url:
            return {"status": 0, "content_type": "", "body": "", "error": "empty url", "_timing": {"total": 0}}

        parsed = urlparse(url)
        host = parsed.netloc.split(":")[0].lower()
        port = 443 if parsed.scheme == "https" else 80
        if ":" in parsed.netloc:
            port = int(parsed.netloc.split(":")[1])
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        # ── Two-tier fetch strategy cache lookup ──────────
        strategy_entry = self._fetch_strategy.get(host)
        if strategy_entry:
            strategy, ts = strategy_entry
            if strategy == "blocked":
                if time.time() - ts < 7200:  # 2h TTL — auto-retry after expiry
                    _fetch_elapsed = time.time() - _fetch_start
                    print(
                        f"[{PRODUCT_NAME}] web_fetch {host} blocked (cached, {(time.time() - ts):.0f}s ago), skipping",
                        file=sys.stderr,
                        flush=True,
                    )
                    return {
                        "status": 0,
                        "content_type": "",
                        "body": "",
                        "error": f"Domain {host} blocked by CDN/WAF (cached, retry after TTL expiry)",
                        "_timing": {"total": round(_fetch_elapsed, 2)},
                    }
                else:
                    # TTL expired — remove cache entry and retry
                    print(
                        f"[{PRODUCT_NAME}] web_fetch {host} blocked cache expired "
                        f"({(time.time() - ts):.0f}s), retrying",
                        file=sys.stderr,
                        flush=True,
                    )
                    del self._fetch_strategy[host]
            # strategy == 'ok' → fall through to bare HTTP

        # ── Try bare HTTP ─────────────────────────────────────
        try:
            resp, body, _ = self._http_get(host, path, port=port, timeout=12, follow_redirects=True)
            status = resp.status
        except Exception as e:
            _fetch_elapsed = time.time() - _fetch_start
            print(f"[{PRODUCT_NAME}] web_fetch HTTP error for {host}: {e}", file=sys.stderr, flush=True)
            SearchEngine._log_timing(f"[TIMING] web_fetch={_fetch_elapsed:.2f}s ERROR {url[:80]}: {e}\n")
            return {
                "status": 0,
                "content_type": "",
                "body": "",
                "error": f"HTTP error: {e}",
                "_timing": {"total": round(_fetch_elapsed, 2)},
            }

        # ── Quality check → block detection ─────────────────
        if self._http_blocked(status, body, host):
            # Mark as blocked in strategy cache (2h TTL)
            self._fetch_strategy[host] = ("blocked", time.time())
            _fetch_elapsed = time.time() - _fetch_start
            print(f"[{PRODUCT_NAME}] {host} → cached blocked", file=sys.stderr, flush=True)
            SearchEngine._log_timing(f"[TIMING] web_fetch={_fetch_elapsed:.2f}s BLOCKED {url[:80]}\n")
            return {
                "status": 0,
                "content_type": "",
                "body": "",
                "error": f"Domain {host} blocked by CDN/WAF",
                "_timing": {"total": round(_fetch_elapsed, 2)},
            }

        # ── Normal extraction (bare HTTP succeeded) ───────────
        self._fetch_strategy[host] = ("ok", time.time())

        ct = resp.headers.get("Content-Type", "")
        charset = "utf-8"
        if "charset=" in ct:
            charset = ct.split("charset=")[-1].split(";")[0].strip()
        try:
            text = body.decode(charset, errors="replace")
        except Exception:
            text = body.decode("utf-8", errors="replace")

        raw_html = text  # save before extraction strips script/style tags
        extracted, _ = self._extract_text(text)
        if extracted:
            text = extracted
        # Structured data extraction — always runs (SSR hydration
        # payloads, JSON-LD, microdata are all discarded by the
        # standard tag-stripping pipeline above; extraction is
        # <20ms combined so no need to gate on content quality)
        text = structured_extract_process(raw_html, text)
        _fetch_elapsed = time.time() - _fetch_start
        SearchEngine._log_timing(f"[TIMING] web_fetch={_fetch_elapsed:.2f}s {url[:80]}\n")
        return {
            "status": status,
            "content_type": ct,
            "body": text,
            "error": None,
            "_timing": {"total": round(_fetch_elapsed, 2)},
        }

    def close(self):
        """Clean up resources."""
        # ── API connection ──
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
