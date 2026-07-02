"""Tests for CLI entry point."""

import subprocess
import sys


class TestCLI:
    def test_help_output(self):
        """python -m searchpin --help should exit 0 and show usage."""
        result = subprocess.run([sys.executable, "-m", "searchpin", "--help"], capture_output=True, text=True, cwd=".")
        assert result.returncode == 0
        assert "Searchpin MCP Server" in result.stdout
        assert "--model" in result.stdout

    def test_search_server_help(self):
        """search_server.py --help should also work."""
        result = subprocess.run([sys.executable, "search_server.py", "--help"], capture_output=True, text=True, cwd=".")
        assert result.returncode == 0
        assert "Searchpin MCP Server" in result.stdout
