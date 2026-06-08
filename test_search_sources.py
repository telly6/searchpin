#!/usr/bin/env python3
"""Test script: use proxy's DoH+IP-direct HTTPS to probe search sources."""
import ssl, http.client, json, socket, time, sys, os

sys.path.insert(0, os.path.dirname(__file__))

# Import the proxy's own _https_get (bypasses system DNS using DoH)
from proxy import _https_get

CANDIDATES = [
    # ── DuckDuckGo API (JSON, no key needed) ──────────────────
    ("DuckDuckGo API", "api.duckduckgo.com",
     "/?q=test&format=json&no_html=1&skip_disambig=1"),

    # ── Brave Search API (key needed but test connectivity) ──
    ("Brave API", "api.search.brave.com",
     "/res/v1/web/search?q=test&count=3"),

    # ── SearXNG public instances ─────────────────────────────
    ("SearXNG (searx.be)", "searx.be",
     "/search?q=test&format=json"),
    ("SearXNG (search.sapti.me)", "search.sapti.me",
     "/search?q=test&format=json"),

    # ── Google Custom Search (via programmable search) ───────
    ("Google CSE", "www.googleapis.com",
     "/customsearch/v1?q=test&cx=test"),

    # ── Bing Web Search API ──────────────────────────────────
    ("Bing API", "api.bing.microsoft.com",
     "/v7.0/search?q=test&count=3"),

    # ── SerpAPI ──────────────────────────────────────────────
    ("SerpAPI", "serpapi.com",
     "/search?q=test&engine=google"),

    # ── Wikipedia API (not search but proves connectivity) ───
    ("Wikipedia", "en.wikipedia.org",
     "/w/api.php?action=query&list=search&srsearch=test&format=json"),

    # ── Baidu (via DoH) ──────────────────────────────────────
    ("Baidu", "www.baidu.com", "/s?wd=test"),
]

print("Testing search source connectivity via proxy _https_get…\n")
print(f"{'Source':<30} {'HTTP':>5} {'Time':>7} {'Size':>8}  Error")
print("-" * 80)

results = []
for name, host, path in CANDIDATES:
    t0 = time.time()
    try:
        resp, body = _https_get(host, path, timeout=8)
        elapsed = time.time() - t0
        status = resp.status
        size = len(body)
        err = ""
        print(f"{name:<30} {status:>5} {elapsed:>6.1f}s {size:>7}B  {err}")
        results.append((name, host, status, elapsed, size, ""))
    except Exception as e:
        elapsed = time.time() - t0
        print(f"{name:<30} {'---':>5} {elapsed:>6.1f}s {'---':>7}  {str(e)[:60]}")
        results.append((name, host, 0, elapsed, 0, str(e)[:60]))

print("\n" + "=" * 80)
print("Summary: sources with HTTP 2xx/3xx are reachable and can be used as search backend.")
print("Sources with timeout/error are blocked from your network.")