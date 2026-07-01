#!/usr/bin/env python3
"""
Structured data extraction from raw HTML.

Extracts data that lives inside <script> tags (SSR hydration payloads,
JSON-LD) and HTML attributes (microdata) — all of which are discarded by
the standard tag-stripping pipeline.

Design principles:
  - Zero domain hardcoding.  All patterns are based on framework conventions
    (__NEXT_DATA__, __NUXT__, etc.) or W3C standards (application/ld+json,
    itemscope/itemprop).
  - Always runs: extraction is lightweight (<20ms combined for JSON-LD,
    microdata, SSR hydration).
  - CSR labeling gated by _quality_score (same statistical scoring that
    _http_blocked uses), not by heuristic signal counting.
  - Fail-safe: every JSON parse is inside try/except.  A malformed payload
    never crashes the pipeline.
"""

import json
import re
from typing import Any

from searchpin.quality import quality_score as _quality_score

# ──────────────────────────────────────────────────────────────────────
# Quality scoring — imported from searchpin.quality (single source of
# truth shared with engine.py).  Aliased as _quality_score for local use
# in the CSR labeling gate below.
# ──────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────
# 1. SSR Hydration Slot Extraction
# ──────────────────────────────────────────────────────────────────────


def _get_nested(obj: Any, dotted_path: str) -> Any:
    """Walk a dotted path like 'props.pageProps.data' into a nested dict.

    Returns None for any missing key, never raises.
    """
    if not dotted_path:
        return obj
    cur = obj
    for key in dotted_path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(key)
        elif isinstance(cur, list) and key.isdigit():
            idx = int(key)
            cur = cur[idx] if idx < len(cur) else None
        else:
            return None
        if cur is None:
            return None
    return cur


def _normalize_json_value(val: Any, max_str_len: int = 500) -> Any:
    """Recursively truncate long strings so LLMs don't drown in noise."""
    if isinstance(val, str):
        if len(val) > max_str_len:
            return val[:max_str_len] + "... [truncated]"
        return val
    if isinstance(val, dict):
        return {k: _normalize_json_value(v, max_str_len) for k, v in val.items()}
    if isinstance(val, list):
        if len(val) > 20:
            return [_normalize_json_value(v, max_str_len) for v in val[:20]] + [f"... [{len(val) - 20} more items]"]
        return [_normalize_json_value(v, max_str_len) for v in val]
    return val


# ── Pattern registry ─────────────────────────────────────────────────

SSR_HYDRATION_PATTERNS = [
    # Next.js (React)
    {
        "name": "nextjs",
        "extractors": [
            # <script id="__NEXT_DATA__" type="application/json">...</script>
            {
                "type": "script_tag",
                "selector": r'id\s*=\s*["\']__NEXT_DATA__["\']',
                "content_type": "application/json",
            },
            # window.__NEXT_DATA__ = {...}
            {
                "type": "inline_script",
                "regex": r"window\.__NEXT_DATA__\s*=\s*({.+?});?",
            },
        ],
        "json_paths": [
            {"path": "props.pageProps", "label": "page_props"},
            {"path": "props.initialState", "label": "initial_state"},
            {"path": "props.apolloState", "label": "apollo_state"},
            {"path": "query", "label": "query_params"},
            {"path": "props", "label": "all_props"},
        ],
    },
    # Nuxt.js (Vue)
    {
        "name": "nuxt",
        "extractors": [
            {
                "type": "inline_script",
                "regex": r"window\.__NUXT__\s*=\s*({.+?});?",
            },
        ],
        "json_paths": [
            {"path": "state", "label": "state"},
            {"path": "data", "label": "page_data"},
            {"path": "fetch", "label": "fetch_data"},
        ],
    },
    # Vue SSR (generic)
    {
        "name": "vue_init_state",
        "extractors": [
            {
                "type": "inline_script",
                "regex": r"(?:window\.)?__INITIAL_STATE__\s*=\s*({.+?});?",
            },
        ],
        "json_paths": [
            {"path": "", "label": "full_state"},
        ],
    },
    # Remix
    {
        "name": "remix",
        "extractors": [
            {
                "type": "inline_script",
                "regex": r"window\.__remixContext\s*=\s*({.+?});?",
            },
            {
                "type": "inline_script",
                "regex": r"window\.__remixManifest\s*=\s*({.+?});?",
            },
        ],
        "json_paths": [
            {"path": "state.loaderData", "label": "loader_data"},
            {"path": "state.actionData", "label": "action_data"},
        ],
    },
    # Angular Universal
    {
        "name": "angular_universal",
        "extractors": [
            {
                "type": "script_tag",
                "selector": r'id\s*=\s*["\']serverApp-state["\']',
                "content_type": "application/json|text/plain",
            },
        ],
        "json_paths": [
            {"path": "", "label": "full_state"},
        ],
    },
    # Gatsby
    {
        "name": "gatsby",
        "extractors": [
            {
                "type": "inline_script",
                "regex": r"window\.___loader\s*=\s*({.+?});?",
            },
            {
                "type": "inline_script",
                "regex": r"window\.__GATSBY__\s*=\s*({.+?});?",
            },
        ],
        "json_paths": [
            {"path": "pageResources.json", "label": "page_json"},
            {"path": "staticQueryResults", "label": "static_queries"},
        ],
    },
    # ICE (Alibaba — Taobao etc.)
    {
        "name": "alibaba_ice",
        "extractors": [
            {
                "type": "inline_script",
                "regex": r"window\.__ICE_APP_CONTEXT__\s*=\s*({.+?});?",
            },
        ],
        "json_paths": [
            {"path": "appData", "label": "app_data"},
            {"path": "loaderData", "label": "loader_data"},
        ],
    },
    # Redux preload (generic)
    {
        "name": "redux_preload",
        "extractors": [
            {
                "type": "inline_script",
                "regex": r"(?:window\.__PRELOADED_STATE__|window\.__REDUX_STATE__)\s*=\s*({.+?});?",
            },
        ],
        "json_paths": [
            {"path": "", "label": "redux_state"},
        ],
    },
    # Generic: all <script type="application/json">
    # (many bespoke frameworks use this)
    {
        "name": "generic_app_json",
        "extractors": [
            {
                "type": "script_tags_by_type",
                "content_type": "application/json",
            },
        ],
        "json_paths": [
            {"path": "", "label": "raw_json"},
        ],
    },
]


def _normalize_js_json(raw: str) -> str:
    """Convert JS object literals to valid JSON.

    Some SSR frameworks emit JavaScript values like 'undefined', 'NaN',
    and 'Infinity' rather than their JSON equivalents.  This function
    performs lossless normalization so Python's json.loads can parse.
    Only converts outside of JSON string values.
    """
    result = []
    in_string = False
    escape_next = False
    i = 0
    while i < len(raw):
        ch = raw[i]
        if escape_next:
            escape_next = False
            result.append(ch)
            i += 1
            continue
        if ch == "\\":
            escape_next = True
            result.append(ch)
            i += 1
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            i += 1
            continue
        if in_string:
            result.append(ch)
            i += 1
            continue
        # Outside string: normalize JS literals
        if (
            raw[i : i + 9] == "undefined"
            and not raw[i + 9 : i + 10].isalnum()
            and raw[i + 9 : i + 10] not in ("_", "$")
        ):
            result.append("null")
            i += 9
            continue
        if raw[i : i + 3] == "NaN" and not raw[i + 3 : i + 4].isalnum() and raw[i + 3 : i + 4] not in ("_", "$"):
            result.append("null")
            i += 3
            continue
        if raw[i : i + 8] == "Infinity" and not raw[i + 8 : i + 9].isalnum() and raw[i + 8 : i + 9] not in ("_", "$"):
            result.append("1e999")  # approximate; LLMs won't use this numeric value
            i += 8
            continue
        if (
            raw[i : i + 9] == "-Infinity"
            and not raw[i + 9 : i + 10].isalnum()
            and raw[i + 9 : i + 10] not in ("_", "$")
        ):
            result.append("-1e999")
            i += 9
            continue
        result.append(ch)
        i += 1
    return "".join(result)


def _extract_json_balanced(raw_html: str, pos: int) -> dict | None:
    """From a position pointing to '{', extract a balanced JSON object.

    Handles nested braces correctly, unlike simple regex approaches.
    When depth returns to 0, verifies that the closing '}' looks like
    an end-of-statement boundary (followed by ';', newline, or other
    JS keyword), to avoid extending past the JSON into subsequent JS
    objects in the same script block.

    Returns None if extraction or parsing fails.
    """
    if pos >= len(raw_html) or raw_html[pos] != "{":
        return None

    depth = 0
    in_string = False
    escape_next = False

    for i in range(pos, len(raw_html)):
        ch = raw_html[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                # Verify this is likely the end-of-statement boundary:
                # the next non-whitespace char should be ';', end of input,
                # or a new JS keyword/variable name.
                next_pos = end
                while next_pos < len(raw_html) and raw_html[next_pos] in " \t":
                    next_pos += 1
                if next_pos >= len(raw_html):
                    break  # end of input
                after = raw_html[next_pos]
                if after in (";", "\n", "\r"):
                    break  # natural end of JS statement
                if next_pos + 6 < len(raw_html):
                    lookahead = raw_html[next_pos : next_pos + 6]
                    if lookahead.startswith(
                        (
                            "window",
                            "docume",
                            "var ",
                            "let ",
                            "const",
                            "functi",
                            "__NEXT",
                            "__NUXT",
                            "__INIT",
                            "__remi",
                            "__ICE_",
                            "__GATS",
                            "__PREP",
                            "__REDU",
                            "if (",
                            "for (",
                            "while",
                            "class",
                            "expor",
                            "impor",
                        )
                    ):
                        break  # new JS statement starts
                if after == "<":
                    break  # likely </script> or HTML follows
                # If after is '{', adjacent JSON objects — continue counting.
                # Otherwise accept this as the boundary.
                if after != "{":
                    break

    if depth != 0:
        return None  # unbalanced

    json_str = raw_html[pos:end]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Normalize JS literals (undefined→null, NaN→null, etc.) and retry
        normalized = _normalize_js_json(json_str)
        try:
            return json.loads(normalized)
        except json.JSONDecodeError:
            return None


def extract_ssr_hydration(raw_html: str) -> dict[str, Any]:
    """Walk all known hydration patterns and extract JSON data.

    Returns: {framework_name: {path_label: extracted_value, ...}, ...}
    """
    results = {}

    for framework in SSR_HYDRATION_PATTERNS:
        framework_data = {}

        for extractor in framework["extractors"]:
            extracted_json = None

            if extractor["type"] == "script_tag":
                # Locate <script id="X" type="Y">data</script>
                selector = extractor["selector"]
                pattern = rf"<script\s+[^>]*{selector}[^>]*>(.*?)</script>"
                match = re.search(pattern, raw_html, re.DOTALL | re.IGNORECASE)
                if match:
                    try:
                        extracted_json = json.loads(match.group(1))
                    except json.JSONDecodeError:
                        pass

            elif extractor["type"] == "inline_script":
                # Two-pass approach: (1) find the assignment with regex,
                # (2) extract balanced JSON from the opening brace.
                # For robustness, first find the enclosing <script> block,
                # extract its text content, then search within that cleaner
                # context (avoids HTML-brace confusion in SSR payloads).
                match = re.search(extractor["regex"], raw_html, re.DOTALL)
                if match:
                    # match.group(1) is the { ... } captured by ({.+?});?
                    # For deeply nested JSON, the non-greedy .+? stops early.
                    # Extract the script block's text for clean brace counting.
                    brace_pos = match.group(1).find("{")
                    if brace_pos >= 0:
                        abs_pos = match.start(1) + brace_pos
                        # Isolate to script text context if possible
                        script_start = raw_html.rfind("<script", 0, abs_pos)
                        script_end = raw_html.find("</script>", abs_pos)
                        if script_start >= 0 and script_end > script_start:
                            script_text = raw_html[script_start:script_end]
                            # Adjust position relative to script_text
                            rel_brace = abs_pos - script_start
                            extracted_json = _extract_json_balanced(script_text, rel_brace)
                        else:
                            extracted_json = _extract_json_balanced(raw_html, abs_pos)

                    if extracted_json is None:
                        # Last resort: try regex capture directly
                        try:
                            extracted_json = json.loads(match.group(1))
                        except (json.JSONDecodeError, ValueError):
                            raw_match = match.group(1).strip()
                            last_brace = raw_match.rfind("}")
                            if last_brace > 0:
                                try:
                                    extracted_json = json.loads(raw_match[: last_brace + 1])
                                except json.JSONDecodeError:
                                    pass

            elif extractor["type"] == "script_tags_by_type":
                # Find all <script type="X"> blocks
                ct = extractor["content_type"]
                pattern = rf'<script\s+[^>]*type\s*=\s*["\']{ct}["\'][^>]*>(.*?)</script>'
                matches = re.findall(pattern, raw_html, re.DOTALL | re.IGNORECASE)
                for match_text in matches:
                    try:
                        data = json.loads(match_text)
                        if isinstance(data, dict):
                            if extracted_json is None:
                                extracted_json = data
                            else:
                                extracted_json = {**extracted_json, **data}
                    except json.JSONDecodeError:
                        pass

            if extracted_json:
                # Extract semantic sub-fields via json_paths
                for path_spec in framework["json_paths"]:
                    value = _get_nested(extracted_json, path_spec["path"])
                    if value is not None:
                        framework_data[path_spec["label"]] = _normalize_json_value(value)

        if framework_data:
            results[framework["name"]] = framework_data

    return results


# ──────────────────────────────────────────────────────────────────────
# 2. JSON-LD (Schema.org structured data) Extraction
# ──────────────────────────────────────────────────────────────────────

# Schema.org types most useful for LLM consumption
USEFUL_TYPES = {
    "Product",
    "Offer",
    "NewsArticle",
    "Article",
    "BlogPosting",
    "Event",
    "Organization",
    "Person",
    "Recipe",
    "Review",
    "FAQPage",
    "HowTo",
    "JobPosting",
    "Course",
    "Book",
    "Movie",
    "TVSeries",
    "LocalBusiness",
    "Restaurant",
    "Dataset",
    "SoftwareApplication",
    "WebApplication",
    "MobileApplication",
}

PRODUCT_CORE_FIELDS = {
    "name",
    "description",
    "sku",
    "image",
    "brand",
    "offers",
    "aggregateRating",
    "review",
}

ARTICLE_CORE_FIELDS = {
    "headline",
    "description",
    "articleBody",
    "datePublished",
    "dateModified",
    "author",
    "publisher",
}

EVENT_CORE_FIELDS = {
    "name",
    "description",
    "startDate",
    "endDate",
    "location",
    "organizer",
    "offers",
    "eventStatus",
}


def _classify_jsonld_entity(organized: dict[str, list[dict]], entity: dict):
    """Classify a single JSON-LD entity by @type and clean noise."""
    entity_type = entity.get("@type", "Unknown")
    # Handle lists of types
    if isinstance(entity_type, list):
        entity_type = entity_type[0] if entity_type else "Unknown"

    if entity_type not in USEFUL_TYPES:
        return

    if entity_type not in organized:
        organized[entity_type] = []

    # For Product, extract only core fields to reduce noise
    if entity_type == "Product":
        slim = {"@type": "Product"}
        for key in PRODUCT_CORE_FIELDS:
            if key in entity:
                slim[key] = _normalize_json_value(entity[key])
        organized[entity_type].append(slim)
    elif entity_type == "NewsArticle" or entity_type == "Article" or entity_type == "BlogPosting":
        slim = {"@type": entity_type}
        for key in ARTICLE_CORE_FIELDS:
            if key in entity:
                slim[key] = _normalize_json_value(entity[key])
        organized[entity_type].append(slim)
    elif entity_type == "Event":
        slim = {"@type": "Event"}
        for key in EVENT_CORE_FIELDS:
            if key in entity:
                slim[key] = _normalize_json_value(entity[key])
        organized[entity_type].append(slim)
    else:
        organized[entity_type].append(_normalize_json_value(entity))


def extract_jsonld(raw_html: str) -> dict[str, list[dict]]:
    """Extract all application/ld+json blocks from HTML.

    Returns: {"Product": [...], "NewsArticle": [...], ...}
    """
    pattern = r'<script\s+[^>]*type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>'
    matches = re.findall(pattern, raw_html, re.DOTALL)

    organized: dict[str, list[dict]] = {}
    for match_text in matches:
        data = None
        # Try raw parse
        try:
            data = json.loads(match_text)
        except json.JSONDecodeError:
            # Common: HTML entities inside JSON string values
            try:
                cleaned = (
                    match_text.replace("&quot;", '"')
                    .replace("&amp;", "&")
                    .replace("&lt;", "<")
                    .replace("&gt;", ">")
                    .replace("&#x27;", "'")
                    .replace("&#x2F;", "/")
                )
                data = json.loads(cleaned)
            except json.JSONDecodeError:
                pass

        if data is None:
            continue

        # Handle @graph (multi-entity payload)
        if "@graph" in data:
            for entity in data["@graph"]:
                _classify_jsonld_entity(organized, entity)
        # Handle single entity
        elif "@type" in data:
            _classify_jsonld_entity(organized, data)
        # Handle array of entities
        elif isinstance(data, list):
            for entity in data:
                if isinstance(entity, dict) and "@type" in entity:
                    _classify_jsonld_entity(organized, entity)

    return organized


# ──────────────────────────────────────────────────────────────────────
# 3. Microdata (itemscope/itemprop) Extraction
# ──────────────────────────────────────────────────────────────────────


def extract_microdata(raw_html: str) -> dict[str, list[dict]]:
    """Extract Schema.org microdata from HTML attributes.

    Uses regex-based parsing — fast enough for the <20ms budget and avoids
    a DOM parser dependency.

    Returns: {"Product": [{"name": "...", "price": "..."}, ...], ...}
    """
    results: dict[str, list[dict]] = {}

    # Split HTML into itemscope blocks (non-overlapping, top-level only)
    itemtype_re = re.compile(r'itemtype\s*=\s*["\'](?:https?://schema\.org/)?(\w+)["\']', re.IGNORECASE)
    itemprop_re = re.compile(r'itemprop\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
    content_re = re.compile(r">([^<]*)<", re.IGNORECASE)

    # Collect all itemscope ranges first to avoid nested overlap
    itemscope_spans = []
    for m in re.finditer(r"<(\w+)[^>]*\bitemscope\b[^>]*>", raw_html, re.IGNORECASE):
        itemscope_spans.append((m.start(), m.group(1)))

    for start_pos, tag_name in itemscope_spans:
        # Find matching closing tag (naive: count nesting depth)
        depth = 1
        pos = start_pos + 1
        open_pat = re.compile(rf"<{tag_name}\b", re.IGNORECASE)
        close_pat = re.compile(rf"</{tag_name}\s*>", re.IGNORECASE)

        while depth > 0 and pos < len(raw_html):
            next_open = open_pat.search(raw_html, pos)
            next_close = close_pat.search(raw_html, pos)
            if not next_close:
                break  # malformed HTML
            if next_open and next_open.start() < next_close.start():
                depth += 1
                pos = next_open.end()
            else:
                depth -= 1
                pos = next_close.end()

        block = raw_html[start_pos:pos]

        # Extract type
        type_match = itemtype_re.search(block)
        if not type_match:
            continue
        schema_type = type_match.group(1)

        # Extract properties — look for itemprop attributes and grab text content
        props = {}
        # Find itemprop="key" ... >value<
        for prop_match in itemprop_re.finditer(block):
            key = prop_match.group(1)
            # Content is the text after the closing '>' of this tag
            after_tag = block[prop_match.end() :]
            content_match = content_re.search(after_tag)
            if content_match:
                value = content_match.group(1).strip()
                if value and len(value) < 2000:  # ignore huge text blocks
                    props[key] = value

        if props:
            if schema_type not in results:
                results[schema_type] = []
            results[schema_type].append(props)

    return results


# ──────────────────────────────────────────────────────────────────────
# 4. CSR-Only Marking (when all phases fail)
# ──────────────────────────────────────────────────────────────────────

CSR_SIGNATURES = [
    # WAF / anti-bot challenge page
    (
        "waf_challenge",
        r"(_waf_|captcha|challenge|verify|点击按钮|Click the button|验证码"
        r"|请完成以下验证|人机验证|安全检测|just a moment|checking your browser)",
    ),
    # SPA empty shell: <div id="root">  </div> or <div id="app">  </div>
    ("spa_shell", r'<div\s+id\s*=\s*["\'](?:root|app|__next|__nuxt)["\'][^>]*>\s*</div>'),
    # Template placeholders (Vue/React unrendered)
    ("template_placeholders", r"(@\{\{|@\w+@|%7B%7B|{{\s*\w+\s*}})"),
    # Geo-restriction
    (
        "geo_restriction",
        r"(no longer (?:be |)accessible from|not available in your"
        r"|本服务暂不支持您所在地区|抱歉，你所在的位置|不支持(?:\w+)地区)",
    ),
    # Login wall (only login form, no content)
    ("login_wall", r"(?:登录|注册|sign\s*in).{0,50}(?:忘记密码|获取短信验证码|验证码登录|captcha|password)"),
]


def mark_csr_only(raw_html: str) -> dict:
    """When all extraction phases fail, return diagnostic metadata.

    Helps LLMs understand WHY the page is empty, and suggests alternatives.
    """
    detected = []
    for sig_name, sig_pattern in CSR_SIGNATURES:
        if re.search(sig_pattern, raw_html, re.IGNORECASE):
            detected.append(sig_name)

    # Pull meta description + title from raw HTML
    meta_desc = ""
    m = re.search(
        r'<meta[^>]*name\s*=\s*["\']description["\'][^>]*content\s*=\s*["\']([^"\']*)["\']', raw_html, re.IGNORECASE
    )
    if m:
        meta_desc = m.group(1)

    title = ""
    m = re.search(r"<title>([^<]+)</title>", raw_html, re.IGNORECASE)
    if m:
        title = m.group(1).strip()

    if not detected:
        # No specific signature found but still no data —
        # fall back to a generic CSR hypothesis
        detected.append("csr_presumed")

    return {
        "_csr_only": True,
        "detected_signatures": detected,
        "title": title,
        "meta_description": meta_desc,
    }


# ──────────────────────────────────────────────────────────────────────
# 5. Orchestrator
# ──────────────────────────────────────────────────────────────────────


def extract_structured(raw_html: str) -> dict:
    """Run all extraction phases and return combined structured data.

    Phases are ordered from highest signal (SSR hydration) to lowest
    (microdata).  All phases run — we collect everything, then merge at
    the output stage.
    """
    result = {}

    # Phase 1: SSR Hydration
    ssr = extract_ssr_hydration(raw_html)
    if ssr:
        result["ssr_hydration"] = ssr

    # Phase 2: JSON-LD
    jsonld = extract_jsonld(raw_html)
    if jsonld:
        result["jsonld"] = jsonld

    # Phase 3: Microdata
    micro = extract_microdata(raw_html)
    if micro:
        result["microdata"] = micro

    return result


# ──────────────────────────────────────────────────────────────────────
# 6. Merge Decision Layer
# ──────────────────────────────────────────────────────────────────────


def _format_json_compact(obj: Any, indent: int = 0, max_items: int = 5) -> str:
    """Format JSON for LLM consumption — compact but readable.

    Uses Python repr-style for scalars, indented dicts for structured data.
    """
    prefix = "  " * indent

    if isinstance(obj, str):
        return f'"{obj}"' if "\n" not in obj and len(obj) < 80 else f'"{obj[:200]}..."'

    if isinstance(obj, (int, float, bool)):
        return repr(obj)

    if obj is None:
        return "null"

    if isinstance(obj, list):
        if not obj:
            return "[]"
        if len(obj) <= max_items:
            items = []
            for v in obj:
                items.append(f"{prefix}  - {_format_json_compact(v, indent + 1, max_items)}")
            return "\n".join(items)
        # Truncated list
        items = []
        for v in obj[:max_items]:
            items.append(f"{prefix}  - {_format_json_compact(v, indent + 1, max_items)}")
        items.append(f"{prefix}  ... [{len(obj) - max_items} more items]")
        return "\n".join(items)

    if isinstance(obj, dict):
        if not obj:
            return "{}"
        lines = []
        for k, v in obj.items():
            val_str = _format_json_compact(v, indent + 1, max_items)
            lines.append(f"{prefix}  {k}: {val_str}")
        return "\n".join(lines)

    return str(obj)


def _format_csr_notice(csr_data: dict) -> str:
    """Generate a user-friendly notice for CSR-only pages."""
    title = csr_data.get("title", "未知页面")
    desc = csr_data.get("meta_description", "")
    sigs = csr_data.get("detected_signatures", [])
    sig_labels = {
        "waf_challenge": "WAF/反爬挑战页",
        "spa_shell": "SPA空壳(无预渲染内容)",
        "template_placeholders": "存在模板占位符(数据未注入)",
        "geo_restriction": "地域封锁(当前地区无法访问)",
        "login_wall": "登录墙(需登录后可见)",
        "csr_presumed": "疑似客户端渲染(CSR)",
    }
    sig_desc = ", ".join(sig_labels.get(s, s) for s in sigs)

    parts = [
        "",
        "---",
        "> ⚠️ **内容受限**: 此页面由客户端动态渲染，web_fetch 无法提取完整数据。",
        f"> 页面标题: {title}",
        f"> 检测到的特征: {sig_desc}",
    ]
    if desc:
        parts.append(f"> 页面描述: {desc}")
    parts.extend(
        [
            "> ",
            "> **建议**: 如需获取此页面的实际数据内容，可尝试:",
            "> 1. 在搜索引擎中搜索相关关键词，查看搜索结果摘要(snippet)",
            "> 2. 寻找该站点的移动版或新闻页(通常为服务端渲染)",
            "> 3. 搜索第三方对该页面内容的转述或引用",
        ]
    )
    return "\n".join(parts)


def merge_results(text_result: str, structured_result: dict) -> str:
    """Merge text extraction output with structured data extraction output.

    Decision logic:
      1. If structured_result is CSR-only → append notice
      2. If structured_result has real data → append as enrichment
      3. Otherwise → return text as-is
    """
    # CSR-only: add notice
    if structured_result.get("_csr_only"):
        csr = {k: v for k, v in structured_result.items() if k != "_csr_only"}
        return (text_result or "") + _format_csr_notice(csr)

    # No structured data found → return text as-is
    useful = {k: v for k, v in structured_result.items() if k != "_csr_only"}
    if not useful:
        return text_result

    parts = [text_result or ""]

    # SSR Hydration data
    ssr = useful.get("ssr_hydration")
    if ssr:
        parts.append("\n\n---\n## 提取的结构化数据 (SSR)\n")
        for framework, data in ssr.items():
            parts.append(f"\n### {framework}\n")
            parts.append("```json")
            parts.append(_format_json_compact(data))
            parts.append("```")

    # JSON-LD enriched
    jsonld = useful.get("jsonld")
    if jsonld:
        parts.append("\n\n---\n## Schema.org 结构化数据 (JSON-LD)\n")
        parts.append("```json")
        parts.append(_format_json_compact(jsonld))
        parts.append("```")

    # Microdata enriched
    micro = useful.get("microdata")
    if micro:
        parts.append("\n\n---\n## 页面 Microdata\n")
        parts.append("```json")
        parts.append(_format_json_compact(micro))
        parts.append("```")

    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────
# 7. Convenience: full pipeline entry point
# ──────────────────────────────────────────────────────────────────────


def process(raw_html: str, text_extracted: str) -> str:
    """Run the full structured extraction pipeline and return merged output.

    This is the single entry point callers should use.

    Args:
        raw_html: the original HTTP response body (HTML string)
        text_extracted: the text already extracted by the text pipeline

    Returns:
        Either the original text (if data is sufficient), or text enriched
        with structured data, or text with a CSR notice.
    """
    # Always run structured extraction for enrichment
    # (JSON-LD, microdata, SSR hydration — all <20ms combined)
    structured = extract_structured(raw_html)

    # CSR labeling: use the same 4-dimension statistical quality score
    # that _http_blocked uses to detect blocked/empty responses.
    # A page that has real content (quality ≥ 0.35) never gets a CSR
    # label regardless of what heuristic signals say — the quality
    # score measures actual content mass, not ratio artefacts.
    if _quality_score(raw_html) < 0.35 and not structured:
        structured = mark_csr_only(raw_html)

    return merge_results(text_extracted, structured)
