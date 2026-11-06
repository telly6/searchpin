#!/usr/bin/env python3
"""
Search backend parsers and URL builders for Searchpin.
Each backend is a pure function — HTML in, list[dict] out.
No instance state, no HTTP, no cookies.  SearchEngine wires them together.
"""

import json
import os
import re
import sys
import urllib.parse
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Comment

# Search operators must remain separate tokens, including next to CJK words.
_SEARCH_SYNTAX = re.compile(r'["()|]|(?:^|\s)(?:[-+]?[A-Za-z][\w-]*:|[-+]\S|(?:AND|OR|NOT)\b)')
# Consume quoted text as a unit; a quoted "site:..." is an ordinary search phrase.
_SITE_TOKEN = re.compile(r'"[^"]*(?:"|$)|(?<![^\s(])site:([^\s()"]+)', re.IGNORECASE)
_DOMAIN_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


def prep_query(raw):
    """Keep term boundaries, quoted phrases and search operators as the caller supplied them."""
    return raw.strip()


def bing_query_matches(sent, returned):
    """Accept an exact query echo, or Bing's old CJK space normalization."""
    if not sent or not returned or len(sent) != 1 or len(returned) != 1:
        return False
    expected, actual = sent[0], returned[0]
    if expected == actual:
        return True
    if _SEARCH_SYNTAX.search(expected):
        return False
    compact = re.sub(r"(?<=[一-鿿㐀-䶿])\s+|\s+(?=[一-鿿㐀-䶿])", "", expected)
    return actual == compact


_HEADWORD = re.compile(r"^([一-鿿]{1,4})(?=\s*(?:[-_（(]|的(?:意思|拼音|解释)|怎么读|[a-zA-Z]))")
_DICTIONARY_TITLE = re.compile(r"字典|汉典|漢典|词典|詞典|新华字典|汉语文字|汉语词语|字源|拼音|释义|笔顺|汉语国学|字义|怎[么麽]读")
_DICTIONARY_REQUEST = re.compile(r"字典|字义|拼音|笔顺|释义|字源|读音|怎么读|的意思|是什么意思|怎么写|部首")

def _source_headword(query, rows):
    """Detect a pool of dictionaries defining a short prefix of a longer question.

    Require consensus across distinct URLs. An overlapping substantive term
    protects a row even if its title happens to look like a headword.
    """
    if len(query) < 6 or _SEARCH_SYNTAX.search(query) or _DICTIONARY_REQUEST.search(query):
        return None, rows
    votes = {}
    seen = set()
    for row in rows:
        if row["url"] in seen:
            continue
        seen.add(row["url"])
        title = row["title"].strip()
        match = _HEADWORD.match(title)
        if match and query.startswith(match[1]) and _DICTIONARY_TITLE.search(title):
            word = match[1]
            votes[word] = votes.get(word, 0) + 1
    if not votes:
        return None, rows
    word = max(votes, key=votes.get)
    if votes[word] < 3 or votes[word] * 2 < len(seen):
        return None, rows
    rest = query[len(word):]
    other_terms = set(re.findall(r"(?=([一-鿿]{2}))", rest)) - {"什么", "怎么", "如何", "哪些", "哪个"}
    if not other_terms:
        return None, rows
    def keep(row):
        title = row["title"]
        content = title + " " + row.get("snippet", "")
        return word not in title or any(term in content for term in other_terms)
    kept = [row for row in rows if keep(row)]
    return (word if len(kept) < len(rows) else None), kept


def filter_headword_drift(query, rows):
    """Evaluate each index separately; another provider may have useful results."""
    by_source = {}
    for row in rows:
        by_source.setdefault(row["_source_engine"], []).append(row)
    drift = {}
    survivors = set()
    for source, pool in by_source.items():
        word, kept = _source_headword(query, pool)
        if word:
            drift[source] = word
        survivors.update(id(row) for row in kept)
    if not drift:
        return {}, rows

    # When one index clearly collapsed, do not fill its place with Chinese
    # cards that share no word at all with the question. Leave foreign-language
    # candidates alone: their spelling alone cannot establish relevance.
    terms = set(re.findall(r"(?=([一-鿿]{2}))", query))
    def has_search_term(row):
        text = row["title"] + " " + row.get("snippet", "")
        return not re.search(r"[一-鿿]", text) or any(term in text for term in terms)
    return drift, [row for row in rows if id(row) in survivors and has_search_term(row)]


def domain_key(host):
    """Return the comparable DNS spelling. Unicode labels and A-labels compare equally."""
    try:
        return host.lower().rstrip(".").encode("idna").decode("ascii")
    except UnicodeError:
        return ""


def normalize_domains(values):
    if values is None:
        return ()
    if not isinstance(values, (list, tuple)):
        raise ValueError("domains must be a list of hostnames")
    names = {}
    for value in values:
        if not isinstance(value, str):
            raise ValueError("domains must contain only hostnames")
        name = domain_key(value.strip())
        if len(name) > 253 or not all(_DOMAIN_LABEL.fullmatch(label) for label in name.split(".")):
            raise ValueError(f"invalid hostname in domain filter: {value!r}")
        names[name] = None
    return tuple(names)


def within_domain(host, domain):
    return host == domain or host.endswith("." + domain)


def site_operators(query):
    return [m for m in _SITE_TOKEN.finditer(query) if m[1]]


def simple_site(query):
    """Only an unconditional positive site token is a hard local restriction."""
    outside_quotes = re.sub(r'"[^"]*"', "", query)
    operators = site_operators(query)
    if len(operators) != 1 or re.search(r"[()|]|\b(?:AND|OR|NOT)\b", outside_quotes):
        return None
    host, slash, path = operators[0][1].partition("/")
    try:
        host = normalize_domains([host])[0]
    except ValueError:
        return None
    return host, ("/" + path).rstrip("/") if slash else ""


def site_path_key(path):
    # Encode Unicode while leaving existing percent escapes and reserved slashes intact.
    path = urllib.parse.quote(path, safe="/%:@!$&'()*+,;=-._~").rstrip("/")
    return re.sub(r"%[0-9a-fA-F]{2}", lambda m: m[0].upper(), path)


def scoped_query(query, include_domains):
    """Express the allowlist to providers while preserving an explicit narrower site/path."""
    if not include_domains:
        return query
    operators = site_operators(query)
    site = simple_site(query)
    site_path = ""
    if site:
        host, site_path = site
        op = operators[0]
        # Keep the site/path but move it before the content terms, so a long
        # question doesn't push the operator off the end of the provider query.
        query = " ".join(filter(None, [query[: op.start()].strip(), query[op.end() :].strip()]))
        if any(within_domain(host, allowed) for allowed in include_domains):
            return f"{op[0]} {query}".rstrip()
    has_or = bool(re.search(r"\bOR\b|\|", query))
    # Do not insert redundant clauses for a subdomain when its parent already covers it.
    allowed = set(include_domains)
    distinct = [d for d in include_domains if not any(d[i + 1 :] in allowed for i, c in enumerate(d) if c == ".")]
    clause = " OR ".join(f"site:{d}{site_path}" for d in distinct)
    # A very large allowlist is still enforced in full. Avoid generating an
    # unusable request URI (Bing repeats the encoded query in both q and pq).
    if len(urllib.parse.quote(clause)) > 1536:
        return f"{operators[0][0]} {query}".rstrip() if site else query
    if len(distinct) > 1:
        clause = f"({clause})"
    if has_or:
        query = f"({query})"
    return f"{clause} {query}"


def focused_query(query):
    """On a miss, try the user's quoted names or identifiers without surrounding prose.
    Preserve operators and signed terms. Leave Boolean expressions intact.
    """
    tokens = re.findall(r'(?:[^\s"]|"[^"]*")+', query)
    outside_quotes = re.sub(r'"[^"]*"', "", query)
    if query.count('"') % 2 or re.search(r"[()|]|\b(?:AND|OR|NOT)\b", outside_quotes):
        return None
    retained = []
    has_anchor = False
    for token in tokens:
        modifier = token.startswith(("+", "-")) or re.match(r"^[A-Za-z][\w-]*:", token)
        identifier = re.fullmatch(r"[\w]+(?:[-./][\w]+)+", token) and re.search(r"\d", token)
        if modifier:
            retained.append(token)
        elif token.startswith('"') or identifier:
            retained.append(token)
            has_anchor = True
    return " ".join(retained) if has_anchor and len(retained) < len(tokens) else None


# ── Bing URL builders ────────────────────────────────────────


def make_cn_bing_path(query, extra="", freshness_suffix=""):
    """Build a cn.bing.com search URL with browser-realistic parameters.
    Keep the search query intact across the form parameters."""
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


# A result owns its heading, destination and snippet. Extract all the containers
# first, then detach them so nested results cannot donate fields to their parent.
def _result_blocks(html, selector, region=None, *, allow_fragment=False):
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(region) if region else soup
    if root is None:
        if not allow_fragment:
            return []
        root = soup
    blocks = [b for b in root.select(selector) if not b.find_parent(["nav", "footer", "aside", "template", "noscript"])]
    for block in blocks:
        block.extract()
    for block in blocks:
        for decoration in reversed(block.select("script, style, nav, footer, aside, template, noscript")):
            decoration.decompose()
    return blocks


def _text(node):
    return " ".join(node.get_text().split()) if node else ""


def _http_url(value):
    if not isinstance(value, str):
        return ""
    value = value.strip()
    try:
        parts = urlsplit(value)
        if (
            parts.scheme in ("http", "https")
            and parts.hostname
            and parts.username is None
            and not re.search(r"[\s\\]", parts.netloc)
        ):
            _ = parts.port  # Reject malformed or out-of-range ports.
            return value
    except ValueError:
        pass
    return ""


def url_key(url):
    # Paths and query values can be case sensitive. A host-only URL has path "/".
    parts = urlsplit(url)
    return parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, parts.fragment


def _heading_link(heading):
    if heading is None:
        return None
    anchors = [a for a in heading.select("a[href]") if _text(a)]
    enclosing = heading.find_parent("a", href=True)
    if enclosing is not None and not anchors:
        return enclosing
    if anchors and len({a["href"] for a in anchors}) == 1:
        return anchors[0]
    return None


def _result(title, url, snippet):
    if title and url:
        return {"title": title, "url": url, "snippet": snippet}
    return None


def _collect(blocks, extract, limit=None):
    results = []
    seen = set()
    for block in blocks:
        result = extract(block)
        if result is None:
            continue
        key = url_key(result["url"])
        if key in seen:
            continue
        seen.add(key)
        results.append(result)
        if limit and len(results) >= limit:
            break
    return results


def _href_url(base, href):
    href = href.strip()
    if not href or href.startswith("#"):
        return ""
    try:
        return _http_url(urljoin(base, href))
    except ValueError:
        return ""


def _destination(anchor, base, block_target):
    """Use the clickable href; only resolve an engine hop from its own result."""
    url = _href_url(base, anchor["href"])
    if not url:
        return ""
    parts = urlsplit(url)
    same_engine = parts.hostname in {urlsplit(base).hostname, urlsplit(base).hostname.removeprefix("www.")}
    if same_engine and parts.path.rstrip("/") == "/link":
        return _http_url(block_target())
    # A search-page navigation, ad redirect, or fragment is not an article link.
    if same_engine and parts.path.rstrip("/") in ("", "/s", "/web", "/baidu.php"):
        return ""
    return url


def make_bing_parser(bing_host, topic="general"):
    base = f"https://{bing_host}/"

    def extract(block):
        if topic == "news":
            anchor = block.select_one("a.title[href], a.news-card-title[href]")
            if anchor is None:
                anchor = _heading_link(block.select_one("h2, h3"))
            snippet = block.select_one(".snippet, .news-card-snippet, .news-card-body .description")
        else:
            anchor = _heading_link(block.find("h2"))
            snippet = block.select_one('p[class*="b_lineclamp"], .b_caption p')
        if anchor is None:
            return None
        url = _href_url(base, anchor["href"])
        return _result(_text(anchor), url, _text(snippet))

    def parse(html):
        selector = ".news-card, .newsitem" if topic == "news" else ".b_algo"
        region = None if topic == "news" else "#b_results"
        return _collect(_result_blocks(html, selector, region, allow_fragment=True), extract)

    return parse


def _baidu_snippet(block):
    visible = block.select_one('.c-abstract, [class*="summary-text"], [class*="content-right_"]')
    if _text(visible):
        return _text(visible)
    # Some templates hydrate their summary instead of rendering a text node.
    # Read only the schema for a summary, never a generic "text" from another module.
    for comment in block.find_all(string=lambda s: isinstance(s, Comment) and s.startswith("s-data:")):
        try:
            payload = json.loads(comment[7:])
            lines = payload["summaryData"]["generalLines"]
            texts = [part["text"] for line in lines for part in line["data"] if isinstance(part.get("text"), str)]
        except (AttributeError, KeyError, TypeError, ValueError, RecursionError):
            continue
        if texts:
            return _text(BeautifulSoup(" ".join(texts), "html.parser"))
    return ""


def _baidu_result(block):
    heading = block.find("h3")
    anchor = _heading_link(heading)
    if anchor is None:
        return None
    target = block.get("mu", "")
    if target:
        if not _http_url(target):
            return None
        host = urlsplit(target).hostname
        if host.startswith("nourl.") and host.endswith(".baidu.com"):
            return None

    def destination():
        return anchor.get("data-landurl") or target or block.get("data-landurl", "")

    url = _destination(anchor, "https://www.baidu.com/", destination)
    return _result(_text(anchor), url, _baidu_snippet(block))


def make_baidu_parser():
    def parse(html):
        blocks = _result_blocks(
            html, "div[mu], article[mu], section[mu], li[mu], .c-container[id], .result, .result-op", "#content_left"
        )
        return _collect(blocks, _baidu_result, limit=15)

    return parse


def _sogou_result(block):
    heading = block.find("h3")
    anchor = _heading_link(heading)
    if anchor is None:
        return None

    def target():
        # Multiple unrelated targets occur on compound cards. Only the title or
        # container itself can disambiguate those. Never consult a sibling card.
        for owner in (anchor, heading, block):
            if owner.has_attr("data-url"):
                return owner["data-url"]
        urls = {_http_url(node["data-url"]) for node in block.select("[data-url]")} - {""}
        return urls.pop() if len(urls) == 1 else ""

    url = _destination(anchor, "https://www.sogou.com/", target)
    snippet = block.select_one(".text-layout, .star-wiki, .space-txt, .str-text, .str_info")
    return _result(_text(anchor), url, _text(snippet))


def make_sogou_parser():
    def parse(html):
        blocks = _result_blocks(html, ".vrwrap, .rb, .results [data-url]:has(h3)", ".results", allow_fragment=True)
        return _collect(blocks, _sogou_result, limit=15)

    return parse


# ── Multi-engine backend builder ─────────────────────────────


def build_backends(query, page=0, topic="general", freshness_suffix=""):
    """Build the list of (host, path, parse_fn, follow_redirects, port,
    Accept-Language, pool_tag) tuples for a given query and result page.
    General search uses all four engines; news first uses the two Bing News routes."""
    _q_encoded_nospace = urllib.parse.quote(prep_query(query))

    p_backends = []
    if topic != "news":
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
            make_bing_parser("cn.bing.com", topic),
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
            make_bing_parser("www.bing.com", topic),
            True,
            443,
            "en-US,en;q=0.9",
            f"bing_intl_pg{page}",
        )
    )
    return p_backends
