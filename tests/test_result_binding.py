"""Regression fixtures exercise structural variants, independent of any search query."""

import pytest

from searchpin.backends import build_backends, make_baidu_parser, make_bing_parser, make_sogou_parser


def test_baidu_preserves_ownership_across_nested_cards_and_feedback():
    html = """
    <main id="content_left"><h3>Feedback on the previous search?</h3>
      <div class="result" mu="https://example.net/a">
        <div class="c-container"><h3><a href="/link?url=one">Article <em>A</em></a></h3></div>
        <section class="result" mu="https://baike.baidu.com/item/b">
          <h3><a href="/link?url=two">Article B</a></h3>
          <p class="c-abstract">Only B owns this summary.</p>
        </section>
      </div>
      <div class="result"><h3><a href="https://example.net/c">Article C</a></h3></div>
      <div class="result"><h3><a href="/link?url=opaque">Unknown target</a></h3></div>
      <aside><div class="result"><h3><a href="https://example.net/sidebar">Sidebar</a></h3></div></aside>
    </main>"""
    assert make_baidu_parser()(html) == [
        {"title": "Article A", "url": "https://example.net/a", "snippet": ""},
        {"title": "Article B", "url": "https://baike.baidu.com/item/b", "snippet": "Only B owns this summary."},
        {"title": "Article C", "url": "https://example.net/c", "snippet": ""},
    ]


def test_baidu_reads_only_a_same_card_hydration_summary():
    html = """<div id="content_left"><div class="result" mu="https://example.net/a">
    <h3><a href="/link?url=a">Article A</a></h3>
    <!--s-data:{"text":"feedback copied from somewhere else"}-->
    <!--s-data:{"summaryData":{"generalLines":[{"data":[{"text":"<em>A</em> summary"}]}]}}-->
    </div></div>"""
    assert make_baidu_parser()(html)[0]["snippet"] == "A summary"


@pytest.mark.parametrize("style", ["rb", "vrwrap"])
def test_sogou_keeps_results_even_if_other_cards_have_different_metadata(style):
    html = f"""<div class="results"><div class="{style}">
      <div><div><h3><a href="https://a.example/p">Article A</a></h3></div></div>
    </div><div class="vrwrap"><h3><a href="/link?url=b">Article B</a></h3>
      <div><div></div></div><span data-url="https://b.example/p?x=1&amp;y=2"></span>
      <p class="str-text">Only B owns this summary.</p>
    </div><div class="rb"><h3><a href="/link?url=unknown">Uncertain</a></h3></div></div>"""
    assert make_sogou_parser()(html) == [
        {"title": "Article A", "url": "https://a.example/p", "snippet": ""},
        {"title": "Article B", "url": "https://b.example/p?x=1&y=2", "snippet": "Only B owns this summary."},
    ]


def test_ambiguous_targets_do_not_consume_other_results():
    html = """<div class="vrwrap"><h3><a href="/link?url=opaque">Collection</a></h3>
    <span data-url="https://a.example/x"></span><span data-url="https://b.example/y"></span>
    <div class="rb"><h3><a href="https://c.example/z">Child article</a></h3></div></div>"""
    assert [r["title"] for r in make_sogou_parser()(html)] == ["Child article"]


@pytest.mark.parametrize("host", ["cn.bing.com", "www.bing.com"])
def test_bing_uses_exact_href_and_preserves_case_sensitive_paths(host):
    page = """<ol id="b_results">
    <li class="b_algo"><aside><h2><a href="https://wrong.example/sidebar">Sidebar</a></h2></aside><h2><a HREF='https://a.example/X?i=1&amp;j=2' data-href='https://b.example/Y'>Alpha</a></h2></li>
    <div class="b_algo"><h2><a href="https://a.example/x?i=1&amp;j=2">Beta</a></h2></div>
    </ol><footer><a href="https://footer.example/">Privacy and cookies</a></footer>"""
    assert [r["url"] for r in make_bing_parser(host)(page)] == [
        "https://a.example/X?i=1&j=2",
        "https://a.example/x?i=1&j=2",
    ]


def test_news_recognizes_news_cards_and_ignores_page_chrome():
    html = """<article class="news-card"><a class="title" href="https://source.example/story">Story title</a>
    <div class="snippet">Story summary.</div></article><footer><a href="https://x.example/">Help Center</a></footer>"""
    for _, _, parse, *_ in build_backends("sample", topic="news"):
        assert parse(html) == [
            {"title": "Story title", "url": "https://source.example/story", "snippet": "Story summary."}
        ]
        assert parse('<a href="https://x.example/">Footer title</a>') == []
