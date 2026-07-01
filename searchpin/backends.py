#!/usr/bin/env python3
"""
Search backend parsers and URL builders for Searchpin.
Each backend is a pure function — HTML in, list[dict] out.
No instance state, no HTTP, no cookies.  SearchEngine wires them together.
"""

import os
import re
import sys
import urllib.parse
from html import unescape
from urllib.parse import urlparse

# ── CJK query preprocessing ──────────────────────────────────
# CJK-aware space removal: when a space has a Chinese character
# on either side, cn.bing.com's tokenizer treats it as a word boundary
# and re-splits the CJK text character-by-character, triggering dictionary
# pollution.  Removing these spaces keeps Chinese compound words intact
# while preserving English word boundaries.
_CJK_SPACE_RE = re.compile(
    r"(?<=[一-鿿㐀-䶿])\s+"
    r"|"
    r"\s+(?=[一-鿿㐀-䶿])"
)


def prep_query(raw):
    return _CJK_SPACE_RE.sub("", raw)


# ── Bing URL builders ────────────────────────────────────────


def make_cn_bing_path(query, extra="", freshness_suffix=""):
    """Build a cn.bing.com search URL with browser-realistic parameters.
    These parameters tell Bing this is a real search-form query — without
    them the Chinese tokenizer splits compound words into single characters."""
    q = prep_query(query)
    char_count = len(q)
    word_count = max(1, len(q.split()))
    sc_value = f"{char_count}-{word_count}"
    cvid = os.urandom(16).hex().upper()
    browser_params = f"&qs=n&form=QBRE&sp=-1&lq=0&pq={urllib.parse.quote(q)}&sc={sc_value}&sk=&cvid={cvid}"
    return f"/search?q={urllib.parse.quote(q)}{browser_params}&count=15{extra}{freshness_suffix}"


def make_www_bing_path(query, extra="", freshness_suffix=""):
    """Build a www.bing.com (international) search URL.
    setmkt=en-US pulls from the global English-language index."""
    q = prep_query(query)
    char_count = len(q)
    word_count = max(1, len(q.split()))
    sc_value = f"{char_count}-{word_count}"
    cvid = os.urandom(16).hex().upper()
    browser_params = f"&setmkt=en-US&qs=n&form=QBRE&sp=-1&lq=0&pq={urllib.parse.quote(q)}&sc={sc_value}&sk=&cvid={cvid}"
    return f"/search?q={urllib.parse.quote(q)}{browser_params}&count=15{extra}{freshness_suffix}"


# ── Bing parser ──────────────────────────────────────────────


def make_bing_parser(bing_host):
    """Return a parser for Bing search result pages.
    bing_host is used to filter out self-referencing links in the fallback."""

    def _parse(html):
        results = []
        blocks = re.findall(r'<li[^>]*class="[^"]*b_algo[^"]*"[^>]*>(.*?)</li>', html, re.DOTALL)
        for blk in blocks:
            h2_m = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', blk, re.DOTALL)
            if not h2_m:
                continue
            title = re.sub(r"<[^>]+>", "", h2_m.group(2)).strip()
            title = unescape(title)

            url = h2_m.group(1)

            snip_m = re.search(r'<p[^>]*class="[^"]*b_lineclamp[^"]*"[^>]*>(.*?)</p>', blk, re.DOTALL)
            snippet = ""
            if snip_m:
                snippet = re.sub(r"<[^>]+>", "", snip_m.group(1)).strip()
                snippet = unescape(snippet)
                snippet = snippet.replace("&ensp;", " ").replace("&#0183;", "·")
            if title:
                results.append({"title": title, "url": url, "snippet": snippet})

        if not results:
            print("[SEARCH] b_algo miss, trying generic <a> fallback", file=sys.stderr, flush=True)
            seen = set()
            for m in re.finditer(
                r'<a[^>]*href="((?:https?://)?[^"]+)"[^>]*>(.*?)</a>',
                html,
                re.DOTALL,
            ):
                url = m.group(1)
                if not url.startswith("http"):
                    continue
                parsed_url = urlparse(url)
                domain = parsed_url.netloc.lower()
                if domain.endswith("." + bing_host) or domain == bing_host:
                    continue
                url_key = url.lower().rstrip("/")
                if url_key in seen:
                    continue
                seen.add(url_key)
                title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                title = unescape(title)
                if not title or len(title) < 4:
                    continue
                results.append({"title": title, "url": url, "snippet": ""})
                if len(results) >= 15:
                    break
            if results:
                print(f"[SEARCH] fallback found {len(results)} links", file=sys.stderr, flush=True)

        return results

    return _parse


# ── Baidu parser ─────────────────────────────────────────────


def make_baidu_parser():
    def _parse(html):
        results = []
        seen_urls_set = set()

        # Step 1: Extract real URLs from embedded JSON.
        # Filter baidu.com subdomains structurally — same approach as
        # Bing (endswith bing_host) and Sogou (sogou.com in netloc).
        # Zero hardcoded subdomain list.
        raw_urls = re.findall(r'"url"\s*:\s*"(https?://[^"]+)"', html)
        real_urls_ordered = []
        real_urls_seen = set()
        for u in raw_urls:
            parsed = urlparse(u)
            netloc = parsed.netloc.lower()
            if netloc.endswith(".baidu.com") or netloc == "baidu.com":
                continue
            clean = u.rstrip("/")
            if clean not in real_urls_seen:
                real_urls_seen.add(clean)
                real_urls_ordered.append(u)

        # Step 2: Extract titles from h3 blocks (with positions for Step 4)
        h3_matches = list(re.finditer(r"<h3[^>]*>(.*?)</h3>", html, re.DOTALL))
        titles = []
        title_h3_ends = []  # store end position of each h3 for Step 4
        for m in h3_matches:
            blk = m.group(1)
            hl_match = re.search(r'<span[^>]*class="[^"]*tts-b-hl[^"]*"[^>]*>(.*?)</span>', blk, re.DOTALL)
            if hl_match:
                t = re.sub(r"<[^>]+>", "", hl_match.group(1)).strip()
            else:
                t = re.sub(r"<[^>]+>", "", blk).strip()
            t = unescape(t)
            if t and len(t) >= 3:
                titles.append(t)
                title_h3_ends.append(m.end())

        # Step 3: Pair titles with real URLs by position
        for i, title in enumerate(titles):
            if i >= len(real_urls_ordered):
                break
            url = real_urls_ordered[i]
            url_key = url.lower().rstrip("/")
            if url_key in seen_urls_set:
                continue
            seen_urls_set.add(url_key)

            # Step 4: Extract snippet from nearby content.
            # Tier 1: s-data SSR hydration JSON (Baidu 2025+ format)
            # Tier 2: legacy CSS classes (c-span-last, c-abstract, etc.)
            # Tier 3: plain text fallback (百度百科 "简介：..." style)
            snippet = ""
            h3_end = title_h3_ends[i] if i < len(title_h3_ends) else -1
            if h3_end >= 0:
                tail = html[h3_end : h3_end + 3000]

                # ── Tier 1: s-data SSR hydration JSON ──────────
                # Baidu 2025+ format: snippet stored in <!--s-data:...--> comments.
                # The JSON payload can be several thousand characters long
                # (includes all hydration state, not just the snippet), so the
                # closing --> may fall outside the default 3000-char tail window.
                # Extend the window until --> is found or we hit 10000 chars.
                sdata_start = tail.find("<!--s-data:")
                if sdata_start >= 0:
                    _extended_tail = tail
                    _close_pos = _extended_tail.find("-->", sdata_start)
                    _extend_attempts = 0
                    while _close_pos < 0 and _extend_attempts < 4:
                        _extend_attempts += 1
                        _more = html[h3_end + len(_extended_tail) : h3_end + len(_extended_tail) + 3000]
                        _extended_tail += _more
                        _close_pos = _extended_tail.find("-->", sdata_start)
                    sdata_m = re.search(r"<!--s-data:(.*?)-->", _extended_tail, re.DOTALL) if _close_pos >= 0 else None
                else:
                    sdata_m = None

                if sdata_m:
                    text_m = re.search(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)"', sdata_m.group(1))
                    if text_m:
                        snippet = text_m.group(1)
                        snippet = (
                            snippet.replace('\\"', '"')
                            .replace("\\n", "\n")
                            .replace("\\t", "\t")
                            .replace("\\/", "/")
                            .replace("\\\\", "\\")
                        )
                        snippet = re.sub(r"</?em>", "", snippet).strip()
                        snippet = unescape(snippet)

                # ── Tier 2: legacy CSS classes ─────────────────
                if not snippet:
                    for cls in (
                        r"c-span-last",
                        r"content-right_",
                        r"c-abstract",
                        r"c-font-normal",
                        r"c-color-text",
                    ):
                        snip_m = re.search(
                            rf'<(?:span|div|p)[^>]*class="[^"]*{cls}[^"]*"[^>]*>(.*?)</(?:span|div|p)>', tail, re.DOTALL
                        )
                        if snip_m:
                            snippet = re.sub(r"<[^>]+>", "", snip_m.group(1)).strip()
                            snippet = unescape(snippet)
                            if len(snippet) > 10:
                                break

            results.append(
                {
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                }
            )
            if len(results) >= 15:
                break

        if not results:
            # Fallback: generic link extraction
            seen = set()
            for m in re.finditer(
                r'<a[^>]*href="((?:https?://)?[^"]+)"[^>]*>(.*?)</a>',
                html,
                re.DOTALL,
            ):
                url = m.group(1)
                if not url.startswith("http"):
                    continue
                parsed_url = urlparse(url)
                domain = parsed_url.netloc.lower()
                if domain.endswith(".baidu.com") or domain == "baidu.com" or "baidu.com" in domain:
                    continue
                url_key = url.lower().rstrip("/")
                if url_key in seen:
                    continue
                seen.add(url_key)
                title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                title = unescape(title)
                if not title or len(title) < 4:
                    continue
                results.append({"title": title, "url": url, "snippet": ""})
                if len(results) >= 15:
                    break

        print(f"[SEARCH] baidu parsed {len(results)} results", file=sys.stderr, flush=True)
        return results

    return _parse


# ── Sogou parser ─────────────────────────────────────────────


def make_sogou_parser():
    def _parse(html):
        results = []
        seen = set()

        # Step 1: Find result wrapper blocks with data-url
        vr_blocks = re.findall(r'<div[^>]*class="[^"]*vrwrap[^"]*"[^>]*>(.*?)</div>\s*</div>', html, re.DOTALL)
        for blk in vr_blocks:
            url_m = re.search(r'data-url="(https?://[^"]+)"', blk)
            if not url_m:
                continue
            url = url_m.group(1)
            url_key = url.lower().rstrip("/")
            if url_key in seen:
                continue
            seen.add(url_key)

            h3_m = re.search(r'<h3[^>]*class="[^"]*vr-title[^"]*"[^>]*>(.*?)</h3>', blk, re.DOTALL)
            if not h3_m:
                h3_m = re.search(r"<h3[^>]*>(.*?)</h3>", blk, re.DOTALL)
            title = ""
            if h3_m:
                title = re.sub(r"<[^>]+>", "", h3_m.group(1)).strip()
                title = unescape(title)
            if not title or len(title) < 3:
                continue

            snippet = ""
            for cls in ("text-layout", "star-wiki", "space-txt", "str-text"):
                snip_m = re.search(rf'<[^>]*class="[^"]*{cls}[^"]*"[^>]*>(.*?)</(?:div|p|span)>', blk, re.DOTALL)
                if snip_m:
                    snippet = re.sub(r"<[^>]+>", "", snip_m.group(1)).strip()
                    snippet = unescape(snippet)
                    if len(snippet) > 10:
                        break

            results.append({"title": title, "url": url, "snippet": snippet})
            if len(results) >= 15:
                break

        # Step 2: Fallback — h3 blocks with nearby data-url
        if not results:
            for h3_match in re.finditer(r"<h3[^>]*>(.*?)</h3>", html, re.DOTALL):
                title = re.sub(r"<[^>]+>", "", h3_match.group(1)).strip()
                title = unescape(title)
                if not title or len(title) < 4:
                    continue
                rest = html[h3_match.end() : h3_match.end() + 3000]
                data_url = re.search(r'data-url="(https?://[^"]+)"', rest)
                if not data_url:
                    continue
                url = data_url.group(1)
                url_key = url.lower().rstrip("/")
                if url_key in seen:
                    continue
                seen.add(url_key)
                snippet = ""
                for cls in ("text-layout", "star-wiki", "space-txt", "str-text"):
                    snip_m = re.search(rf'<[^>]*class="[^"]*{cls}[^"]*"[^>]*>(.*?)</(?:div|p|span)>', rest, re.DOTALL)
                    if snip_m:
                        snippet = re.sub(r"<[^>]+>", "", snip_m.group(1)).strip()
                        snippet = unescape(snippet)
                        break
                results.append({"title": title, "url": url, "snippet": snippet})
                if len(results) >= 15:
                    break

        # Step 3: Last resort — generic link extraction
        if not results:
            for m in re.finditer(r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL):
                url = m.group(1)
                if "sogou.com" in urlparse(url).netloc:
                    continue
                url_key = url.lower().rstrip("/")
                if url_key in seen:
                    continue
                seen.add(url_key)
                title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                title = unescape(title)
                if not title or len(title) < 4:
                    continue
                results.append({"title": title, "url": url, "snippet": ""})
                if len(results) >= 15:
                    break

        print(f"[SEARCH] sogou parsed {len(results)} results", file=sys.stderr, flush=True)
        return results

    return _parse


# ── Multi-engine backend builder ─────────────────────────────


def build_backends(query, page=0, topic="general", freshness_suffix=""):
    """Build the list of (host, path, parse_fn, follow_redirects, port,
    Accept-Language, pool_tag) tuples for a given query and result page.
    All 4 engines are included; embedding rerank selects the best results."""
    _q_encoded_nospace = urllib.parse.quote(prep_query(query))

    p_backends = []
    p_backends.append(
        (
            "www.baidu.com",
            f"/s?wd={_q_encoded_nospace}&pn={page * 10}",
            make_baidu_parser(),
            False,
            443,
            "zh-CN,zh;q=0.9",
            f"baidu_pg{page}",
        )
    )
    p_backends.append(
        (
            "www.sogou.com",
            f"/web?query={_q_encoded_nospace}&page={page + 1}",
            make_sogou_parser(),
            True,
            443,
            "zh-CN,zh;q=0.9",
            f"sogou_pg{page}",
        )
    )

    bing_offset = page * 10 + 1
    if topic == "news":
        q = prep_query(query)
        _cn_path = f"/news/search?q={urllib.parse.quote(q)}&first={bing_offset}{freshness_suffix}"
        _www_path = f"/news/search?q={urllib.parse.quote(q)}&setmkt=en-US&first={bing_offset}{freshness_suffix}"
        print("[SEARCH] topic=news → using Bing News vertical", file=sys.stderr, flush=True)
    else:
        _cn_path = make_cn_bing_path(query, extra=f"&first={bing_offset}", freshness_suffix=freshness_suffix)
        _www_path = make_www_bing_path(query, extra=f"&first={bing_offset}", freshness_suffix=freshness_suffix)
    p_backends.append(
        (
            "cn.bing.com",
            _cn_path,
            make_bing_parser("cn.bing.com"),
            True,
            443,
            "zh-CN,zh;q=0.9,en;q=0.5",
            f"bing_cn_pg{page}",
        )
    )
    p_backends.append(
        (
            "www.bing.com",
            _www_path,
            make_bing_parser("www.bing.com"),
            True,
            443,
            "en-US,en;q=0.9",
            f"bing_intl_pg{page}",
        )
    )
    return p_backends
