#!/usr/bin/env python3
"""
Shared quality scoring utilities for Searchpin.

Used by both engine.py (_http_blocked, _do_web_fetch) and
structured_extract.py (CSR labeling gate).  Single source of truth
— update here and both modules stay in sync.
"""

import re


def quality_score(html):
    """Zero-hardcode statistical quality scoring.

    Pure measurable properties — zero keywords, zero entity knowledge,
    zero domain-specific thresholds.  Same principle as the overlay
    dismiss heuristic: detect structure, not content.

    Returns float 0.0-1.0.  Score < 0.35 strongly suggests a blocked/
    empty/stale response (CDN challenge, captcha stub, JS shell)."""
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="replace")

    # Strip script/style blocks — their text is not human-readable content
    _clean = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    _clean = re.sub(r"<style[^>]*>.*?</style>", " ", _clean, flags=re.DOTALL | re.IGNORECASE)
    _clean = re.sub(r"<[^>]+>", " ", _clean)
    _clean = re.sub(r"\s+", " ", _clean).strip()

    text_len = len(_clean)

    # Raw HTML length (including scripts) for DOM complexity measurement
    html_len = max(len(html), 1)

    # 1. DOM complexity — unique HTML tag types.
    #    Real pages use 30-60+ unique tags.  CDN challenge pages
    #    use 5-8 (html, head, body, script, meta, div, p).
    tags = [t.lower() for t in re.findall(r"</?(\w+)", html)]
    unique_tags = len(set(tags))
    dom_score = min(1.0, unique_tags / 20)

    # 2. Text density — stripped text vs raw HTML ratio,
    #    volume-weighted: a CDN page can have high ratio (simple HTML)
    #    but not high ratio AND high volume.  Real articles have both.
    text_ratio = text_len / html_len
    volume_factor = min(1.0, text_len / 1000)  # <1000 chars → penalty
    ratio_score = min(1.0, text_ratio / 0.30) * volume_factor

    # 3. Sentence count — number of >10 char coherent segments,
    #    also volume-weighted for the same reason.
    segments = [s.strip() for s in re.split(r"[.。!！?？\n]{1,3}", _clean) if len(s.strip()) > 10]
    sent_score = min(1.0, len(segments) / 10) * volume_factor

    # 4. Absolute body mass — raw text character count.
    #    Real articles: 2000-50000+.  CDN pages: 50-500.
    mass_score = min(1.0, text_len / 2000)

    return 0.30 * dom_score + 0.20 * ratio_score + 0.20 * sent_score + 0.30 * mass_score
