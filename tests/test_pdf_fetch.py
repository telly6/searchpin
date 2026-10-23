"""PDF boundary regressions; no network, embedding model, or paid API calls."""

import io
import json
from types import SimpleNamespace

import pytest
import searchpin.engine as engine_module
from pypdf import PdfWriter
from pypdf.errors import PdfReadError
from search_server import handle_mcp_request
from searchpin.engine import SearchEngine


def pdf_engine(body=b"%PDF-1.7\nfixture", status=200):
    engine = SearchEngine.__new__(SearchEngine)
    engine._fetch_strategy = {}
    engine._http_get = lambda *a, **kw: (
        SimpleNamespace(status=status, headers={"Content-Type": "application/pdf"}),
        body,
        None,
    )
    return engine


def assert_document_failure(result, message):
    assert result["status"] == 200
    assert result["body"] == ""
    assert "PDF" in result["error"]
    assert message.lower() in result["error"].lower()


class TestPdfSafetyBoundaries:
    def test_parse_failure_is_also_an_mcp_tool_error(self):
        reply = handle_mcp_request(
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {"name": "web_fetch", "arguments": {"url": "https://fixture.example/broken.pdf"}},
            },
            pdf_engine(),
        )
        assert reply["result"]["isError"] is True
        result = json.loads(reply["result"]["content"][0]["text"])
        assert result["body"] == ""
        assert "PDF text extraction failed" in result["error"]

    def test_encrypted_pdf_is_explicit_failure(self):
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.encrypt("fixture-password")
        stream = io.BytesIO()
        writer.write(stream)
        engine = pdf_engine(stream.getvalue())
        result = engine.fetch("https://fixture.example/encrypted")
        assert_document_failure(result, "encrypted")
        assert "fixture.example" not in engine._fetch_strategy

    def test_later_page_error_does_not_publish_earlier_page_as_success(self, monkeypatch):
        class GoodPage:
            def extract_text(self):
                return "Earlier text must not escape as a successful complete document."

        class BrokenPage:
            def extract_text(self):
                raise PdfReadError("damaged second page stream")

        monkeypatch.setattr(
            "pypdf.PdfReader", lambda data: SimpleNamespace(is_encrypted=False, pages=[GoodPage(), BrokenPage()])
        )
        engine = pdf_engine()
        result = engine.fetch("https://fixture.example/broken-later-page")
        assert_document_failure(result, "damaged second page")
        assert "fixture.example" not in engine._fetch_strategy

    @pytest.mark.parametrize("status", [301, 401, 403, 404, 429, 500])
    def test_http_error_is_not_parsed_or_reported_as_text_success(self, monkeypatch, status):
        attempts = []
        monkeypatch.setattr("pypdf.PdfReader", lambda data: attempts.append(data))
        engine = pdf_engine(status=status)
        result = engine.fetch("https://fixture.example/not-successful")
        assert result["status"] == status
        assert result["body"] == ""
        assert f"HTTP {status}" in result["error"]
        assert attempts == []
        assert engine._fetch_strategy.get("fixture.example", (None,))[0] != "blocked"

    def test_byte_limit_rejects_before_parser(self, monkeypatch):
        monkeypatch.setattr(engine_module, "PDF_MAX_BYTES", 32)
        attempts = []
        monkeypatch.setattr("pypdf.PdfReader", lambda data: attempts.append(data))
        result = pdf_engine(b"%PDF-" + b"x" * 28).fetch("https://fixture.example/large")
        assert_document_failure(result, "extraction limit")
        assert attempts == []

    def test_page_limit_rejects_without_extracting_any_page(self, monkeypatch):
        class UnreadPage:
            def extract_text(self):
                raise AssertionError("over-limit PDF pages must not be extracted")

        monkeypatch.setattr(engine_module, "PDF_MAX_PAGES", 2)
        monkeypatch.setattr(
            "pypdf.PdfReader",
            lambda data: SimpleNamespace(is_encrypted=False, pages=[UnreadPage(), UnreadPage(), UnreadPage()]),
        )
        result = pdf_engine().fetch("https://fixture.example/too-many-pages")
        assert_document_failure(result, "2-page")

    def test_text_limit_does_not_publish_partial_document(self, monkeypatch):
        monkeypatch.setattr(engine_module, "PDF_MAX_TEXT_CHARS", 50)
        page = SimpleNamespace(extract_text=lambda: "This is a long page of genuine text. " * 10)
        monkeypatch.setattr("pypdf.PdfReader", lambda data: SimpleNamespace(is_encrypted=False, pages=[page]))
        result = pdf_engine().fetch("https://fixture.example/too-much-text")
        assert_document_failure(result, "50-character")

    def test_allowed_document_still_preserves_all_page_boundaries(self, monkeypatch):
        monkeypatch.setattr(engine_module, "PDF_MAX_PAGES", 2)
        pages = [
            SimpleNamespace(extract_text=lambda: "First source page."),
            SimpleNamespace(extract_text=lambda: "Second source page."),
        ]
        monkeypatch.setattr("pypdf.PdfReader", lambda data: SimpleNamespace(is_encrypted=False, pages=pages))
        result = pdf_engine().fetch("https://fixture.example/two-pages")
        assert result["error"] is None
        assert "## Page 1" in result["body"]
        assert "## Page 2" in result["body"]
        assert "First source page." in result["body"]
        assert "Second source page." in result["body"]
