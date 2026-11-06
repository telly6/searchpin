"""Exercise merging and news fallback at the agent-facing tools/call boundary."""

import json
from types import SimpleNamespace

from search_server import handle_mcp_request
from searchpin.engine import SearchEngine


def test_news_falls_back_once_and_labels_general_results(monkeypatch):
    engine = SearchEngine(embedding_mode="api")
    requests = []

    def fetch(host, path, **kwargs):
        requests.append((host, path))
        if path.startswith("/news/search"):
            return (
                SimpleNamespace(status=200, url=f"https://{host}/", getheader=lambda _: None),
                (b'<footer><a href="https://outside.example/">Legal notice</a></footer>'),
                None,
            )
        page = b'<li class="b_algo"><h2><a href="https://example.net/page">Relevant article</a></h2></li>'
        return SimpleNamespace(status=200, url=f"https://{host}{path}", getheader=lambda _: None), page, None

    monkeypatch.setattr(engine, "_http_get", fetch)
    monkeypatch.setattr(engine, "_embed", lambda texts: [[1.0] for _ in texts])
    req = {
        "id": 1,
        "method": "tools/call",
        "params": {"name": "web_search", "arguments": {"query": "sample", "topic": "news"}},
    }
    reply = handle_mcp_request(req, engine)["result"]
    out = json.loads(reply["content"][0]["text"])
    assert out["requested_topic"] == "news" and out["effective_topic"] == "general"
    assert [r["title"] for r in out["results"]] == ["Relevant article"]
    assert sum(path.startswith("/news/search") for _, path in requests) == 2


def test_empty_page_does_not_trigger_backend_cooldown(monkeypatch):
    engine = SearchEngine(embedding_mode="api")
    page = b'<footer><a href="https://anything.example/privacy">Privacy</a></footer>'
    monkeypatch.setattr(
        engine,
        "_http_get",
        lambda *a, **k: (SimpleNamespace(status=200, url=None, getheader=lambda _: None), page, None),
    )
    out = engine.search("anything")
    assert out["results"] == [] and "error" not in out
    assert engine._search_cooldown_until == 0


def test_dedup_keeps_the_best_ranked_title_not_the_first_backend(monkeypatch):
    engine = SearchEngine(embedding_mode="api")
    url = "https://article.example/One"

    def fetch(host, path, **kwargs):
        title = "Specific article" if host == "www.bing.com" else "Generic article"
        page = f'<li class="b_algo"><h2><a href="{url}">{title}</a></h2></li>'
        return SimpleNamespace(status=200, url=None, getheader=lambda _: None), page.encode(), None

    monkeypatch.setattr(engine, "_http_get", fetch)
    monkeypatch.setattr(engine, "_embed", lambda texts: [[1, 0] if "Specific" in t else [0, 1] for t in texts])
    out = engine.search("Specific")
    assert [(r["title"], r["url"]) for r in out["results"]] == [("Specific article", url)]


def test_news_without_an_allowed_source_retries_general_with_the_same_filter(monkeypatch):
    engine = SearchEngine(embedding_mode="api")

    def fetch(host, path, **kwargs):
        if path.startswith("/news/search"):
            page = (
                '<article class="news-card"><a class="title" href="https://elsewhere.example/news">Story</a></article>'
            )
        else:
            page = '<li class="b_algo"><h2><a href="https://wanted.example/a">Allowed article</a></h2></li>'
        return SimpleNamespace(status=200, url=None, getheader=lambda _: None), page.encode(), None

    monkeypatch.setattr(engine, "_http_get", fetch)
    monkeypatch.setattr(engine, "_embed", lambda texts: [[1] for _ in texts])
    result = engine.search("sample", topic="news", include_domains=["wanted.example"])
    assert (result["requested_topic"], result["effective_topic"]) == ("news", "general")
    assert [r["url"] for r in result["results"]] == ["https://wanted.example/a"]
