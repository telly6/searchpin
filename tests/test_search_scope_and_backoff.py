"""Behavioral checks at the agent-facing entry point. No external network or real sleeps."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from search_server import handle_mcp_request
from searchpin.backends import build_backends, focused_query, normalize_domains, scoped_query
from searchpin.engine import SearchEngine


def call(engine, query, **opts):
    req = {"id": 1, "method": "tools/call", "params": {"name": "web_search", "arguments": {"query": query, **opts}}}
    payload = handle_mcp_request(req, engine)["result"]
    return json.loads(payload["content"][0]["text"])


@pytest.fixture
def engine(monkeypatch):
    instance = SearchEngine(embedding_mode="api")
    monkeypatch.setattr(instance, "_embed", lambda texts: [[1.0] for _ in texts])
    return instance


def response(code=200, location="", body=b"<html></html>"):
    return SimpleNamespace(status=code, getheader=lambda name: location if name == "Location" else None), body, None


def bing_html(rows):
    return (
        "<ol id='b_results'>"
        + "".join(f"<li class='b_algo'><h2><a href='{url}'>{title}</a></h2></li>" for title, url in rows)
        + "</ol>"
    ).encode()


def test_captcha_skips_only_its_host_then_recovers(engine, monkeypatch):
    now = [100.0]
    monkeypatch.setattr("searchpin.engine.time.monotonic", lambda: now[0])
    attempts = []

    def http(host, path, **kwargs):
        if host == "www.baidu.com":
            attempts.append(path)
            if len(attempts) in (1, 3):
                return response(302, "https://wappass.baidu.com/check")
            return response()
        if host == "cn.bing.com":
            return response(body=bing_html([("Any topic", "https://result.example/ok")]))
        return response()

    monkeypatch.setattr(engine, "_http_get", http)
    monkeypatch.setattr("searchpin.engine.time.sleep", lambda *_: pytest.fail("cooldown must never sleep a tool call"))

    def lookup():
        out = call(engine, "unrelated query")
        assert [r["url"] for r in out["results"]] == ["https://result.example/ok"]
        return out["search_pages"][0]

    first = lookup()
    assert first["engines"]["www.baidu.com"] == "captcha"
    assert first["retry_after_seconds"]["www.baidu.com"] == 600
    now[0] += 5
    page = lookup()
    assert page["engines"]["www.baidu.com"] == "cooldown"
    assert page["retry_after_seconds"]["www.baidu.com"] == 595 and len(attempts) == 1
    now[0] += 594.99
    assert lookup()["engines"]["www.baidu.com"] == "cooldown" and len(attempts) == 1
    now[0] = 700
    assert lookup()["engines"]["www.baidu.com"] == "empty" and len(attempts) == 2
    assert lookup()["engines"]["www.baidu.com"] == "paced" and len(attempts) == 2
    now[0] += 20
    assert lookup()["retry_after_seconds"]["www.baidu.com"] == 600


def test_only_one_recovery_probe_and_failed_probe_backs_off(engine, monkeypatch):
    now = [10.0]
    host = "www.baidu.com"
    engine._engine_backoff_until[host] = now[0]
    engine._engine_backoff_secs[host] = 600
    monkeypatch.setattr("searchpin.engine.time.monotonic", lambda: now[0])
    active, release = Event(), Event()

    def http(*args, **kwargs):
        active.set()
        assert release.wait(4)
        return response(302, "https://wappass.baidu.com/check")

    monkeypatch.setattr(engine, "_http_get", http)
    backend = build_backends("sample")[0]
    with ThreadPoolExecutor(max_workers=1) as pool:
        probe = pool.submit(engine._search_fetch_one, *backend)
        assert active.wait(2)
        try:
            assert engine._search_fetch_one(*backend)[1] == "cooldown"
        finally:
            release.set()
        assert probe.result()[1] == "captcha"
    assert engine._engine_backoff_until[host] == now[0] + 600
    assert engine._search_cooldown_until == 0
    assert not engine._engine_recovery_probes


def test_all_temporarily_unavailable_do_not_extend_global_timer(engine, monkeypatch):
    now = [40.0]
    monkeypatch.setattr("searchpin.engine.time.monotonic", lambda: now[0])
    for host, *_ in build_backends("x"):
        engine._engine_backoff_until[host] = 45.0
        engine._engine_backoff_secs[host] = 30

    def no_http(*args, **kwargs):
        pytest.fail("attempted HTTP before expiry")

    monkeypatch.setattr(engine, "_http_get", no_http)
    out = call(engine, "x", include_domains=["allowed.test"])
    assert out["error"] == "all backends failed" and out["domain_search"]["status"] == "sources_unavailable"
    assert set(out["search_pages"][0]["engines"].values()) == {"cooldown"}
    assert engine._search_cooldown_until == 0
    now[0] = 45
    monkeypatch.setattr(engine, "_http_get", lambda *a, **k: response())
    out = call(engine, "x", include_domains=["allowed.test"])
    assert "error" not in out and out["domain_search"]["status"] == "no_match_in_sample"


@pytest.mark.parametrize("location", ["/captcha/?m=1", "https://www.sogou.com/antispider/"])
def test_sogou_redirect_to_challenge_is_not_successful_empty_html(engine, monkeypatch, location):
    engine._host_cookies["www.sogou.com"] = "anonymous=yes"
    monkeypatch.setattr(engine, "_http_get", lambda *a, **k: response(302, location, b"x" * 6000))
    args = build_backends("probe")[1]
    assert engine._search_fetch_one(*args)[1] == "antispider"
    assert engine._search_fetch_one(*args)[1] == "cooldown"


def test_sogou_consecutive_challenges_and_healthy_reset(engine, monkeypatch):
    now = [10.]
    host = "www.sogou.com"
    monkeypatch.setattr("searchpin.engine.time.monotonic", lambda: now[0])
    engine._host_cookies[host] = "anonymous=yes"
    replies = iter([response(302, "/antispider/") for _ in range(3)] +
                   [response(), response(302, "/antispider/")])
    monkeypatch.setattr(engine, "_http_get", lambda *a, **k: next(replies))
    args = build_backends("sample")[1]
    for expected in (60, 120, 120, None, 60):
        reply = engine._search_fetch_one(*args)
        if expected is None:
            assert reply[2] is not None and host not in engine._engine_backoff_until
            continue
        assert reply[1] == "antispider" and engine._engine_backoff_until[host] == now[0] + expected
        now[0] += expected - 0.01
        assert engine._search_fetch_one(*args)[1] == "cooldown"
        now[0] = engine._engine_backoff_until[host]


@pytest.mark.parametrize("title,blocked", [("百度安全验证", True), ("百度安全验证怎么办_百度搜索", False)])
def test_baidu_200_challenge_page_not_a_search_about_captchas(engine, monkeypatch, title, blocked):
    body = f"<html><title>{title}</title></html>".encode()
    monkeypatch.setattr(engine, "_http_get", lambda *a, **kw: response(body=body))
    reply = engine._search_fetch_one(*build_backends("百度安全验证")[0])
    assert (reply[1] == "captcha") is blocked
    assert ("www.baidu.com" in engine._engine_backoff_until) is blocked


def test_query_operators_and_phrases_survive_all_provider_url_builders():
    q = '文档 "多 个词" site:docs.example.test/ref filetype:pdf'
    wanted = scoped_query(q, normalize_domains(["Example.Test."]))
    assert wanted == 'site:docs.example.test/ref 文档 "多 个词" filetype:pdf'
    for topic in ("general", "news"):
        for host, path, *_ in build_backends(wanted, topic=topic):
            param = {"www.baidu.com": "wd", "www.sogou.com": "query"}.get(host, "q")
            assert parse_qs(urlsplit(path).query)[param] == [wanted]
    assert scoped_query("甲 OR 乙", ["a.test", "b.test"]) == "(site:a.test OR site:b.test) (甲 OR 乙)"
    assert scoped_query('找 "site:not-a-site.test"', ["a.test"]).startswith("site:a.test ")
    assert scoped_query("查 -site:bad.test", ["a.test"]).startswith("site:a.test ")
    assert scoped_query("中文 搜索", ["a.test", "sub.a.test"]) == "site:a.test 中文 搜索"


def test_sparse_scope_goes_to_next_page_without_leaking_or_duplicating(engine, monkeypatch):
    seen = []

    def http(host, path, **kwargs):
        if host not in ("cn.bing.com", "www.bing.com"):
            return response()
        data = parse_qs(urlsplit(path).query)
        seen.append((host, data["q"][0], data["first"][0]))
        rows = [
            ("Impostor", "https://good.test.evil.invalid/path"),
            ("Excluded", "https://blocked.good.test/post"),
            ("Valid one", "https://www.good.test:443/one"),
        ]
        if data["first"] == ["11"]:
            rows.append(("Valid two", "https://docs.good.test/Two"))
        return response(body=bing_html(rows))

    monkeypatch.setattr(engine, "_http_get", http)
    out = call(engine, "原文 site:good.test", include_domains=["GOOD.TEST."], exclude_domains=["blocked.good.test"])
    assert {r["url"] for r in out["results"]} == {"https://www.good.test:443/one", "https://docs.good.test/Two"}
    assert {query for _, query, _ in seen} == {"site:good.test 原文"}
    assert [p["page"] for p in out["search_pages"]] == [1, 2]
    assert out["domain_search"]["matched_urls"] == 2


def test_focused_retry_preserves_modifiers_and_ranks_against_original(engine, monkeypatch):
    original = '1234.05678 英文资料 "two words" filetype:pdf -site:old.test'
    full = scoped_query(original, ["a.test", "b.test"])
    focus = '(site:a.test OR site:b.test) 1234.05678 "two words" filetype:pdf -site:old.test'
    queries = []
    texts = []

    def http(host, path, **kwargs):
        if host != "cn.bing.com":
            return response()
        q = parse_qs(urlsplit(path).query)["q"][0]
        queries.append(q)
        url = "https://b.test/paper" if q == focus else "https://different.test/x"
        return response(body=bing_html([("Article", url)]))

    monkeypatch.setattr(engine, "_http_get", http)
    monkeypatch.setattr(engine, "_embed", lambda t: texts.extend(t) or [[1.0] for _ in t])
    out = call(engine, original, include_domains=["a.test", "b.test"])
    assert queries == [full, focus] and texts[0] == original
    assert [p["strategy"] for p in out["search_pages"]] == ["initial", "focused_terms"]
    assert [r["url"] for r in out["results"]] == ["https://b.test/paper"]
    assert focused_query('("one" OR "two") 文档') is None


def test_original_terms_can_rescue_previously_valid_results_without_widening_output(engine, monkeypatch):
    def http(host, path, **kwargs):
        if host != "cn.bing.com":
            return response()
        q = parse_qs(urlsplit(path).query)["q"][0]
        rows = [("Other", "https://offsite.test/x")]
        if q == "previous query":
            rows.append(("Official", "https://sub.allowed.test/doc"))
        return response(body=bing_html(rows))

    monkeypatch.setattr(engine, "_http_get", http)
    out = call(engine, "previous query", include_domains=["allowed.test"])
    assert [(p["strategy"], p["query"]) for p in out["search_pages"]] == [
        ("initial", "site:allowed.test previous query"),
        ("original_terms", "previous query"),
    ]
    assert [r["url"] for r in out["results"]] == ["https://sub.allowed.test/doc"]


def test_invalid_allowlist_cannot_turn_into_an_unrestricted_search(engine, monkeypatch):
    monkeypatch.setattr(engine, "_http_get", lambda *a, **kw: pytest.fail("invalid filter made an HTTP request"))
    for bad in [["foo.test OR site:other.test"], [""], ["https://example.test/page"], "example.test"]:
        out = call(engine, "test", include_domains=bad)
        assert out.get("error") and out["results"] == []
    assert normalize_domains(["例子.公司", "XN--FSQU00A.XN--55QX5D."]) == ("xn--fsqu00a.xn--55qx5d",)


def test_challenge_redirect_is_not_followed_by_the_search_transport(engine, monkeypatch):
    from email.message import Message
    from unittest.mock import Mock

    from searchpin import engine as engine_module

    conn = Mock()
    redirect = Mock(status=302, headers=Message())
    redirect.info.return_value = redirect.headers
    redirect.getheader.return_value = "/captcha/?m=1"
    conn.getresponse.return_value = redirect
    constructor = Mock(return_value=conn)
    monkeypatch.setattr(engine_module.http.client, "HTTPSConnection", constructor)
    monkeypatch.setattr(engine, "resolve_host", lambda *a, **kw: "127.0.0.1")
    resp, body, _ = engine._http_get("www.sogou.com", "/web", follow_redirects=True, stop_at_challenge=True)
    assert resp is redirect and body == b""
    constructor.assert_called_once()
    conn.request.assert_called_once()
    conn.close.assert_called_once()


def test_enough_matches_and_unrestricted_queries_remain_one_batch(engine, monkeypatch):
    calls = []

    def http(host, path, **kwargs):
        if host == "cn.bing.com":
            calls.append(path)
            return response(body=bing_html([("One", "https://docs.allowed.test/a")]))
        return response()

    monkeypatch.setattr(engine, "_http_get", http)
    scoped = call(engine, "X", max_results=1, include_domains=["allowed.test"])
    general = call(engine, "X")
    assert len(calls) == 2
    assert scoped["domain_search"]["matched_urls"] == 1 and len(scoped["search_pages"]) == 1
    assert len(general["search_pages"]) == 1 and "domain_search" not in general


def test_large_scope_is_not_truncated_to_some_of_the_allowed_domains(engine, monkeypatch):
    domains = [f"long-domain-{i:03}.example" for i in range(80)]

    def http(host, path, **kwargs):
        if host != "cn.bing.com":
            return response()
        params = parse_qs(urlsplit(path).query)
        assert params["q"] == ["some query"]
        url = f"https://{domains[-1]}/doc" if params["first"] == ["11"] else "https://outside.test/no"
        return response(body=bing_html([("Candidate", url)]))

    monkeypatch.setattr(engine, "_http_get", http)
    out = call(engine, "some query", include_domains=domains)
    assert [r["url"] for r in out["results"]] == [f"https://{domains[-1]}/doc"]
    assert [p["strategy"] for p in out["search_pages"]] == ["initial", "next_page"]


def test_underfilled_generated_scope_keeps_original_hits_even_after_a_redirect(engine, monkeypatch):
    def http(host, path, **kwargs):
        if host not in ("cn.bing.com", "www.bing.com"):
            return response()
        query = parse_qs(urlsplit(path).query)["q"][0]
        if host == "cn.bing.com":
            return response(body=bing_html([("Scoped result", "https://allowed.test/article")]))
        if query.startswith("site:"):
            resp, body, cookies = response()
            resp.url = "https://www.bing.com/"
            return resp, body, cookies
        return response(
            body=bing_html(
                [("Older valid result", "https://docs.allowed.test/manual"), ("Outside", "https://disallowed.test/no")]
            )
        )

    monkeypatch.setattr(engine, "_http_get", http)
    out = call(engine, "search words", include_domains=["allowed.test"], max_results=5)
    assert {r["url"] for r in out["results"]} == {"https://allowed.test/article", "https://docs.allowed.test/manual"}
    first, second = out["search_pages"]
    assert first["engines"]["www.bing.com"] == "redirected" and second["strategy"] == "original_terms"
    assert second["engines"]["www.bing.com"] == "results"


@pytest.mark.parametrize("domains, sent_host", [(None, "example.test"), (["guide.example.test"], "guide.example.test")])
def test_standalone_or_narrowed_site_path_cannot_return_home_or_sibling(engine, monkeypatch, domains, sent_host):
    sent = []

    def http(host, path, **kwargs):
        if host != "cn.bing.com":
            return response()
        sent.append(parse_qs(urlsplit(path).query)["q"][0])
        return response(
            body=bing_html(
                [
                    ("Good", "https://guide.example.test/文档/one"),
                    ("Wrong directory", "https://guide.example.test/文档别处"),
                    ("Site homepage", "https://guide.example.test/"),
                    ("Other host", "https://example.test.bad/文档/a"),
                ]
            )
        )

    monkeypatch.setattr(engine, "_http_get", http)
    out = call(engine, "查 文档 site:example.test/%E6%96%87%E6%A1%A3", include_domains=domains, max_results=1)
    assert sent == [f"site:{sent_host}/%E6%96%87%E6%A1%A3 查 文档"]
    assert [r["url"] for r in out["results"]] == ["https://guide.example.test/文档/one"]
    assert out["domain_search"]["domains"] == [sent_host] and out["domain_search"]["status"] == "matches"


def test_disjoint_explicit_site_and_allowlist_do_not_touch_network(engine, monkeypatch):
    monkeypatch.setattr(engine, "_http_get", lambda *a, **kw: pytest.fail("impossible scope was requested"))
    out = call(engine, "site:other.test invoice", include_domains=["allowed.test"])
    assert out["domain_search"]["status"] == "conflicting_scopes" and not out["results"] and not out["search_pages"]

def test_baidu_search_interval_skips_concurrent_and_early_calls(engine, monkeypatch):
    now = [10.0]
    monkeypatch.setattr("searchpin.engine.time.monotonic", lambda: now[0])
    entered, release = Event(), Event()
    attempts = []

    def http(host, path, **kwargs):
        if host == "www.baidu.com":
            attempts.append(now[0])
            entered.set()
            assert release.wait(4)
        if host == "cn.bing.com":
            return response(body=bing_html([("Other source", "https://other.example/item")]))
        return response()

    monkeypatch.setattr(engine, "_http_get", http)
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(call, engine, "first question")
        assert entered.wait(2)
        try:
            now[0] = 11
            fast = call(engine, "another question")
            page = fast["search_pages"][0]
            assert page["engines"]["www.baidu.com"] == "paced"
            assert page["retry_after_seconds"]["www.baidu.com"] == 19
            assert fast["results"][0]["url"] == "https://other.example/item"
        finally:
            release.set()
        assert first.result()["search_pages"][0]["engines"]["www.baidu.com"] == "empty"
    now[0] = 29.99
    assert call(engine, "still early")["search_pages"][0]["engines"]["www.baidu.com"] == "paced"
    now[0] = 30
    assert call(engine, "ready")["search_pages"][0]["engines"]["www.baidu.com"] == "empty"
    assert attempts == [10, 30]


def test_repeated_cookies_replace_by_scope_and_expire_across_redirects(engine, monkeypatch):
    from email.message import Message
    from unittest.mock import Mock
    from searchpin import engine as module

    events = []
    def conn(*args, **kwargs):
        c = Mock()
        def req(method, path, headers):
            events.append((headers['Host'], path, headers.get('Cookie', '')))
        def res():
            host, path, _ = events[-1]
            head = Message()
            status = 200
            if path == '/start':
                head['Location'] = 'https://other.example.net/next'
                head['Set-Cookie'] = 'id=one; Path=/'
                head['Set-Cookie'] = 'narrow=x; Path=/private; Expires=Tue, 19 Jan 2038 03:14:07 GMT'
                status = 302
            elif path == '/rotate':
                head['Set-Cookie'] = 'id=two; Path=/'
            elif path == '/expire':
                head['Set-Cookie'] = 'id=; Max-Age=0; Path=/'
            return SimpleNamespace(status=status, headers=head, info=lambda:head,
                                   getheader=head.get, read=lambda:b'')
        c.request.side_effect = req
        c.getresponse.side_effect = res
        return c
    monkeypatch.setattr(engine, 'resolve_host', lambda *a, **kw:'127.0.0.1')
    monkeypatch.setattr(module.http.client, 'HTTPSConnection', conn)
    _, _, jar = engine._http_get('a.example.com','/start',follow_redirects=True)
    for path in ('/rotate','/rotate','/private/item','/expire','/final'):
        _, _, jar = engine._http_get('a.example.com',path,cookies=jar)
    assert [line[2] for line in events] == ['', '', 'id=one', 'id=two', 'narrow=x; id=two', 'id=two', '']


def test_dictionary_pool_has_an_actionable_fallback_and_http_status(engine, monkeypatch):
    heads = ['航（汉语文字）', '航-字典释义', '航的拼音和笔顺']
    def http(host,path,**kwargs):
        if host=='cn.bing.com' and path.startswith('/search'):
            return response(body=bing_html([(h,f'https://lex.example/{n}') for n,h in enumerate(heads)]))
        if host=='cn.bing.com' and path.startswith('/news'):
            return response(body=b'<article class="news-card"><a class="title" href="https://mission.example/item">Mission</a></article>')
        if host=='www.bing.com': return response(400)
        return response()
    monkeypatch.setattr(engine, '_http_get', http)
    out=call(engine,'航天器使用哪种燃料')
    assert out['search_pages'][0]['off_topic_headword']=={'bing_cn':'航'}
    assert out['search_pages'][0]['http_status']['www.bing.com']==400
    assert [r['url'] for r in out['results']]==['https://mission.example/item']
    out=call(engine,'航字的拼音是什么')
    assert len(out['search_pages'])==1 and len(out['results'])==3
