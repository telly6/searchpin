#!/usr/bin/env python3
"""Fetch Baidu search results and dump key HTML patterns to diagnose parser."""
import sys, os, re
sys.path.insert(0, os.path.dirname(__file__))
from proxy import _http_get
from urllib.parse import quote

query = "豆包 收费"
host = "www.baidu.com"
path = f"/s?wd={quote(query)}&rn=5"

print(f"Fetching http://{host}{path} ...")
try:
    resp, body = _http_get(host, path, timeout=10, follow_redirects=True, port=80)
    html = body.decode("utf-8", errors="replace")
    print(f"HTTP {resp.status}, {len(html)} bytes")
    
    # Save raw HTML for inspection
    with open("/tmp/baidu_search.html", "w") as f:
        f.write(html)
    print(f"Saved to /tmp/baidu_search.html ({len(html)} bytes)")
    
    # Find all class= patterns that contain "result"
    result_classes = set()
    for m in re.finditer(r'class="([^"]*)"', html):
        cls = m.group(1).lower()
        if 'result' in cls:
            result_classes.add(cls)
    print(f"\nClasses containing 'result': {sorted(result_classes)[:20]}")
    
    # Find all <a href="http..."> patterns (first 10)
    links = re.findall(r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
    print(f"\nFirst 10 external links found:")
    for url, text in links[:10]:
        text_clean = re.sub(r'<[^>]+>', '', text).strip()[:80]
        if not url.startswith(('https://www.baidu.com', 'http://www.baidu.com', 'javascript:')):
            print(f"  [{text_clean}] → {url}")
    
    # Find <h3> blocks (common title pattern)
    h3s = re.findall(r'<h3[^>]*>(.*?)</h3>', html, re.DOTALL)
    print(f"\nFound {len(h3s)} <h3> blocks, first 3:")
    for h in h3s[:3]:
        clean = re.sub(r'<[^>]+>', '', h).strip()[:120]
        print(f"  {clean}")
    
    # Check for common snippet classes
    for pat in ['c-abstract', 'content-right', 'c-span-last', 'c-summary']:
        matches = re.findall(f'<(?:span|div)[^>]*class="[^"]*{pat}[^"]*"[^>]*>(.*?)</(?:span|div)>', html, re.DOTALL)
        if matches:
            print(f"\nFound {len(matches)} '{pat}' snippets, first:")
            clean = re.sub(r'<[^>]+>', '', matches[0]).strip()[:150]
            print(f"  {clean}")
            break
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()