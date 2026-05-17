"""Tests for search module fixes (issue 4)."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.errors import CriticalError, RetryableError, SkippableError
from src.search_module import SearchModule


@pytest.fixture
def search_module(mock_db, mock_logger):
    """Create SearchModule with mocked dependencies."""
    with patch("src.search_module.requests.Session"):
        module = SearchModule(db=mock_db, logger=mock_logger)
        module._serper_api_key = "fake-key"
        module._session = MagicMock()
        return module


class TestSerperErrorHandling:
    """Issue 4: Test Serper error handling."""

    def test_402_raises_critical_error(self, search_module):
        """402 should raise CriticalError."""
        mock_response = MagicMock()
        mock_response.status_code = 402
        search_module._session.post.return_value = mock_response

        with pytest.raises(CriticalError):
            search_module._serper_search("test query")

    def test_429_raises_retryable_error(self, search_module):
        """429 should raise RetryableError."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        search_module._session.post.return_value = mock_response

        with pytest.raises(RetryableError):
            search_module._serper_search("test query")

    def test_403_raises_skippable_error(self, search_module):
        """403 should raise SkippableError."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        search_module._session.post.return_value = mock_response

        with pytest.raises(SkippableError):
            search_module._serper_search("test query")

    def test_500_returns_empty_list(self, search_module):
        """500 should return empty list (not raise)."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        search_module._session.post.return_value = mock_response

        result = search_module._serper_search("test query")
        assert result == []

    def test_network_error_returns_empty_list(self, search_module):
        """Network errors should return empty list."""
        search_module._session.post.side_effect = requests.RequestException(
            "Connection refused"
        )

        result = search_module._serper_search("test query")
        assert result == []

    def test_successful_search(self, search_module):
        """Successful search should return results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "organic": [
                {
                    "link": "https://example.com",
                    "title": "Example",
                    "snippet": "Test snippet",
                }
            ]
        }
        search_module._session.post.return_value = mock_response

        result = search_module._serper_search("test query")
        assert len(result) == 1
        assert result[0]["url"] == "https://example.com"
        assert result[0]["title"] == "Example"

    def test_no_api_key_returns_empty(self, mock_db, mock_logger):
        """No API key should return empty list."""
        with patch("src.search_module.requests.Session"):
            module = SearchModule(db=mock_db, logger=mock_logger)
            module._serper_api_key = None

        result = module._serper_search("test query")
        assert result == []


class TestErrorTypesExist:
    """Verify all error types are importable."""

    def test_critical_error_exists(self):
        assert CriticalError is not None

    def test_retryable_error_exists(self):
        assert RetryableError is not None

    def test_skippable_error_exists(self):
        assert SkippableError is not None

    def test_error_inheritance(self):
        """All custom errors should inherit from Exception."""
        assert issubclass(CriticalError, Exception)
        assert issubclass(RetryableError, Exception)
        assert issubclass(SkippableError, Exception)


class TestDedupeResults:
    """Test URL deduplication."""

    def test_dedupe_removes_duplicates(self, search_module):
        existing = {"https://a.com", "https://b.com"}
        new_results = [
            {"url": "https://a.com", "title": "A"},
            {"url": "https://c.com", "title": "C"},
        ]

        result = search_module._dedupe_results(new_results, existing)
        assert len(result) == 1
        assert result[0]["url"] == "https://c.com"

    def test_dedupe_empty_new_results(self, search_module):
        existing = {"https://a.com"}
        result = search_module._dedupe_results([], existing)
        assert result == []

    def test_dedupe_all_new(self, search_module):
        existing = set()
        new_results = [
            {"url": "https://a.com", "title": "A"},
            {"url": "https://b.com", "title": "B"},
        ]

        result = search_module._dedupe_results(new_results, existing)
        assert len(result) == 2


class TestGetExistingUrls:
    """Test getting existing URLs for dedup."""

    def test_get_existing_from_filtered_links(self, search_module):
        search_module.db.get_filtered_links_for_company.return_value = [
            {"url": "https://a.com"},
            {"url": "https://b.com"},
        ]
        search_module.db.get_search_results_for_company.return_value = []

        result = search_module._get_existing_urls(1)
        assert "https://a.com" in result
        assert "https://b.com" in result

    def test_get_existing_from_search_results(self, search_module):
        search_module.db.get_filtered_links_for_company.return_value = []
        search_module.db.get_search_results_for_company.return_value = [
            {"url": "https://c.com"},
        ]

        result = search_module._get_existing_urls(1)
        assert "https://c.com" in result
