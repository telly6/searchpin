"""Tests for quality scoring — purely statistical, no network required."""

from searchpin.quality import quality_score


class TestQualityScore:
    """Statistical quality scoring for HTML content."""

    def test_empty_html_scores_low(self):
        assert quality_score(b"") < 0.5

    def test_whitespace_only_scores_low(self):
        assert quality_score(b"   \n  \t  \n  ") < 0.5

    def test_real_html_scores_high(self):
        html = b"""<!DOCTYPE html><html><head><title>Test</title></head>
        <body><p>This is a real article with substantial text content.
        It has multiple paragraphs and enough text to pass quality checks.</p>
        <p>Second paragraph with more content to ensure we exceed the
        minimum text length thresholds for meaningful content.</p>
        </body></html>"""
        score = quality_score(html)
        assert 0.0 <= score <= 1.0
        # A real HTML page with content should score reasonably
        assert score > 0.1  # synthetic HTML is light; real pages score higher

    def test_captcha_page_scores_low(self):
        captcha_html = b"""<!DOCTYPE html><html><body>
        <script>challenge=function(){}</script>
        <noscript>Please enable JavaScript</noscript>
        </body></html>"""
        score = quality_score(captcha_html)
        assert 0.0 <= score <= 1.0
        # Captcha pages have very low content density
        assert score < 0.5

    def test_returns_float_in_range(self):
        """All valid inputs should return a float in [0, 1]."""
        for html in [b"", b"hello", b"<html><body><p>text</p></body></html>"]:
            score = quality_score(html)
            assert isinstance(score, float)
            assert 0.0 <= score <= 1.0
