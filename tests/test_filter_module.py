"""Tests for filter module (URL scoring)."""

import pytest

from src.filter_module import LinkFilter


@pytest.fixture
def link_filter(mock_db, mock_logger):
    return LinkFilter(db=mock_db, logger=mock_logger)


class TestClassifyUrl:
    """Test URL classification and scoring."""

    def test_official_website(self, link_filter):
        result = link_filter.classify_url(
            "https://abc-vina.com.vn/lien-he", "ABC Vina Co., Ltd"
        )
        assert result["should_scrape"] is True
        assert result["relevance_score"] > 0
        assert result["source_type"] == "official"

    def test_legal_domain(self, link_filter):
        result = link_filter.classify_url(
            "https://masothue.com/0123456789-cong-ty-abc", "ABC Co., Ltd"
        )
        assert result["should_scrape"] is True
        assert result["relevance_score"] >= 30
        assert result["source_type"] == "legal"

    def test_social_domain(self, link_filter):
        result = link_filter.classify_url(
            "https://facebook.com/abc", "ABC Co., Ltd"
        )
        assert result["should_scrape"] is False
        assert result["relevance_score"] < 0

    def test_skip_domain(self, link_filter):
        result = link_filter.classify_url(
            "https://vnexpress.net/news/abc", "ABC Co., Ltd"
        )
        assert result["should_scrape"] is False
        assert result["relevance_score"] == 0

    def test_blacklisted_domain(self, link_filter):
        result = link_filter.classify_url(
            "https://infocom.vn/abc", "ABC Co., Ltd"
        )
        assert result["should_scrape"] is False
        assert result["relevance_score"] == 0
        assert result["source_type"] == "blacklisted"

    def test_keyword_bonus(self, link_filter):
        result = link_filter.classify_url(
            "https://example.com/lien-he", "Example Co"
        )
        assert result["score_breakdown"].get("keyword", 0) > 0

    def test_tld_bonus(self, link_filter):
        result = link_filter.classify_url(
            "https://example.com.vn", "Example Co"
        )
        assert result["score_breakdown"].get("tld", 0) > 0


class TestScoreUrlsBatch:
    """Test batch URL scoring."""

    def test_score_batch(self, link_filter):
        urls = [
            {"url": "https://masothue.com/123", "title": "ABC", "snippet": ""},
            {"url": "https://facebook.com/abc", "title": "ABC", "snippet": ""},
        ]
        results = link_filter.score_urls_batch(urls, "ABC Co., Ltd")
        assert len(results) == 2
        # Legal should score higher than social
        legal = [r for r in results if "masothue" in r["url"]][0]
        social = [r for r in results if "facebook" in r["url"]][0]
        assert legal["relevance_score"] > social["relevance_score"]

    def test_dedup_by_domain(self, link_filter):
        urls = [
            {"url": "https://example.com/page1", "title": "", "snippet": ""},
            {"url": "https://example.com/page2", "title": "", "snippet": ""},
        ]
        results = link_filter.score_urls_batch(urls, "Test")
        # Only one URL per domain should be kept
        assert len(results) == 1


class TestEarlyStop:
    """Test early stop logic."""

    def test_early_stop_triggered(self, link_filter):
        links = [
            {"relevance_score": 40, "should_scrape": True}
            for _ in range(10)
        ]
        assert link_filter.check_early_stop(links) is True

    def test_early_stop_not_triggered(self, link_filter):
        links = [
            {"relevance_score": 20, "should_scrape": True}
            for _ in range(10)
        ]
        assert link_filter.check_early_stop(links) is False
