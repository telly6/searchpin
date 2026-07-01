"""Tests for search backend parsers — uses static HTML snippets, no network."""

from searchpin.backends import (
    build_backends,
    make_baidu_parser,
    make_bing_parser,
    make_cn_bing_path,
    make_sogou_parser,
    make_www_bing_path,
    prep_query,
)


class TestPrepQuery:
    def test_english_unchanged(self):
        assert prep_query("hello world") == "hello world"

    def test_chinese_no_spaces_removed(self):
        """CJK spaces between Chinese chars should be removed."""
        # Chinese chars on both sides → space removed
        assert prep_query("你好 世界") == "你好世界"

    def test_mixed_cjk_english(self):
        """Space on either side of CJK is removed — both English→CJK and CJK→CJK."""
        result = prep_query("Python 编程 语言")
        # Regex: \s+(?=CJK) removes "Python " (space before CJK)
        #        (?<=CJK)\s+ removes "程 语" (space after CJK)
        assert result == "Python编程语言"


class TestBingPaths:
    def test_cn_bing_path(self):
        path = make_cn_bing_path("test query", freshness_suffix="&tbs=qdr:d")
        assert path.startswith("/search?q=")
        # URL-encoded space is %20, not +
        assert "test%20query" in path.lower()
        assert "qdr" in path  # freshness filter present

    def test_www_bing_path(self):
        path = make_www_bing_path("test query")
        assert "setmkt=en-US" in path
        assert path.startswith("/search?q=")


class TestBuildBackends:
    def test_general_build(self):
        backends = build_backends("test", page=0)
        assert len(backends) == 4  # baidu, sogou, bing_cn, bing_intl
        hosts = {b[0] for b in backends}
        assert hosts == {"www.baidu.com", "www.sogou.com", "cn.bing.com", "www.bing.com"}

    def test_news_build(self):
        backends = build_backends("breaking news", page=0, topic="news")
        for host, path, *_ in backends:
            if "bing" in host:
                assert "/news/search" in path

    def test_pagination(self):
        backends_p0 = build_backends("test", page=0)
        backends_p1 = build_backends("test", page=1)
        # Page 1 paths should differ from page 0
        p0_paths = [b[1] for b in backends_p0 if "bing" in b[0]]
        p1_paths = [b[1] for b in backends_p1 if "bing" in b[0]]
        assert p0_paths != p1_paths


class TestParsers:
    """Parser tests with minimal valid HTML snippets."""

    def test_baidu_parser_handles_empty(self):
        parser = make_baidu_parser()
        results = parser("<html></html>")
        assert isinstance(results, list)
        assert len(results) == 0

    def test_sogou_parser_handles_empty(self):
        parser = make_sogou_parser()
        results = parser("<html></html>")
        assert isinstance(results, list)
        assert len(results) == 0

    def test_bing_parser_handles_empty(self):
        parser = make_bing_parser("cn.bing.com")
        results = parser("<html></html>")
        assert isinstance(results, list)
        assert len(results) == 0

    def test_bing_parser_b_algo(self):
        """Bing parser should extract results from b_algo blocks."""
        parser = make_bing_parser("cn.bing.com")
        html = """<html><body>
        <li class="b_algo"><h2><a href="https://example.com/article">
        Article Title</a></h2>
        <p class="b_lineclamp">This is a search result snippet.</p>
        </li>
        </body></html>"""
        results = parser(html)
        assert len(results) >= 1
        assert results[0]["title"] == "Article Title"
        assert results[0]["url"] == "https://example.com/article"
        assert "snippet" in results[0]["snippet"]

    def test_bing_parser_fallback_filters_bing_links(self):
        """Fallback parser (no b_algo blocks) filters bing self-referencing links."""
        parser = make_bing_parser("cn.bing.com")
        # No b_algo blocks → triggers fallback generic <a> extraction
        html = """<html><body>
        <a href="https://example.com/page">Real Result Title Text</a>
        <a href="https://cn.bing.com/something">Bing Self Link Here</a>
        <a href="https://other-site.com/thing">Another Real One</a>
        </body></html>"""
        results = parser(html)
        urls = [r["url"] for r in results]
        assert "https://cn.bing.com/something" not in urls
        assert len(results) >= 2  # got the two real links
