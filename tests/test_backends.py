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

    def test_preserves_distinct_search_terms_on_every_backend(self):
        from urllib.parse import parse_qs, urlsplit
        for query in ("天文 观测", "Python 字典 顺序", '查 "完整 短语" site:example.org'):
            for host, path, *_ in build_backends(query):
                param = {"www.baidu.com": "wd", "www.sogou.com": "query"}.get(host, "q")
                assert parse_qs(urlsplit(path).query)[param] == [query]


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

    def test_bing_search_chrome_is_not_a_result(self):
        page = '<footer><a href="https://other.example/legal">Legal information</a></footer>'
        assert make_bing_parser("www.bing.com")(page) == []


def test_one_bad_index_does_not_hide_an_independently_relevant_source():
    from searchpin.backends import filter_headword_drift
    rows = [dict(title=t, snippet='', url=f'https://cn.example/{i}', _source_engine='bing_cn')
            for i,t in enumerate(['鲸的拼音','鲸-字典','鲸（汉语文字）'])]
    rows += [dict(title=f'流行歌曲 {i}', snippet='歌词', url=f'https://intl.example/{i}', _source_engine='bing_intl') for i in range(12)]
    good = dict(title='海洋研究：鲸类如何迁徙', snippet='观测迁徙路线', url='https://marine.example/path', _source_engine='sogou')
    rows.append(good)
    which, kept = filter_headword_drift('鲸类如何迁徙', rows)
    assert which == {'bing_cn':'鲸'} and kept == [good]


def test_bing_query_echo_accepts_only_the_plain_cjk_space_variant():
    from searchpin.backends import bing_query_matches
    assert bing_query_matches(['VLC 官方下载'], ['VLC官方下载'])
    for sent, final in [
        ('2026 北京 降雨','北京降雨'), ('VLC 官网','VLC 安装'),
        ('foo bar','foobar'), ('"甲 乙"','"甲乙"'), ('site:a.test 北京','site:a.test北京')
    ]:
        assert not bing_query_matches([sent], [final])
    assert not bing_query_matches(['天问 一号'], None)
