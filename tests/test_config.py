"""Tests for configuration constants."""

from searchpin.config import DEFAULT_MODEL_NAME, DOH_ENDPOINTS, PRODUCT_NAME


class TestConfig:
    def test_product_name_is_string(self):
        assert isinstance(PRODUCT_NAME, str)
        assert len(PRODUCT_NAME) > 0

    def test_default_model_name(self):
        assert isinstance(DEFAULT_MODEL_NAME, str)
        assert "/" in DEFAULT_MODEL_NAME  # huggingface format

    def test_doh_endpoints(self):
        """DNS-over-HTTPS endpoints should have valid format."""
        assert len(DOH_ENDPOINTS) >= 1
        for url, ip in DOH_ENDPOINTS:
            assert url.startswith("https://")
            assert "." in ip  # valid IP format
