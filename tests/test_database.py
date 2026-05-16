"""Tests for database module."""

import os
import tempfile

import pytest

from src.database import DatabaseManager


@pytest.fixture
def db():
    """Create a temporary database."""
    from src import database as db_module

    original_path = db_module.DB_PATH
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, "test.db")
    db_module.DB_PATH = temp_path

    db = DatabaseManager()
    yield db

    db_module.DB_PATH = original_path
    if os.path.exists(temp_path):
        os.remove(temp_path)
    os.rmdir(temp_dir)


class TestDatabaseCRUD:
    """Test database CRUD operations."""

    def test_insert_company(self, db):
        company_id = db.insert_company(original_name="Test Company")
        assert company_id is not None
        assert company_id > 0

    def test_get_company(self, db):
        company_id = db.insert_company(
            original_name="Test Company", tax_code="0123456789"
        )
        company = db.get_company(company_id)
        assert company is not None
        assert company["original_name"] == "Test Company"
        assert company["tax_code"] == "0123456789"

    def test_get_company_not_found(self, db):
        company = db.get_company(99999)
        assert company is None

    def test_update_company(self, db):
        company_id = db.insert_company(original_name="Test Company")
        db.update_company(company_id, status="searched", vietnamese_name="Công ty Test")
        company = db.get_company(company_id)
        assert company["status"] == "searched"
        assert company["vietnamese_name"] == "Công ty Test"

    def test_get_all_companies(self, db):
        db.insert_company(original_name="Company A")
        db.insert_company(original_name="Company B")
        companies = db.get_all_companies()
        assert len(companies) == 2

    def test_get_all_companies_by_status(self, db):
        db.insert_company(original_name="A", status="pending")
        db.insert_company(original_name="B", status="done")
        pending = db.get_all_companies(status="pending")
        assert len(pending) == 1
        assert pending[0]["original_name"] == "A"


class TestSearchResults:
    """Test search results operations."""

    def test_insert_search_result(self, db):
        company_id = db.insert_company(original_name="Test")
        result_id = db.insert_search_result(
            company_id=company_id,
            url="https://example.com",
            search_type="step1_contact",
            result_rank=1,
            title="Example",
            snippet="Test snippet",
        )
        assert result_id is not None

    def test_get_search_results(self, db):
        company_id = db.insert_company(original_name="Test")
        db.insert_search_result(
            company_id=company_id, url="https://a.com", result_rank=1
        )
        db.insert_search_result(
            company_id=company_id, url="https://b.com", result_rank=2
        )
        results = db.get_search_results_for_company(company_id)
        assert len(results) == 2
        assert results[0]["url"] == "https://a.com"


class TestFilteredLinks:
    """Test filtered links operations."""

    def test_insert_filtered_link(self, db):
        company_id = db.insert_company(original_name="Test")
        link_id = db.insert_filtered_link(
            company_id=company_id,
            url="https://example.com",
            source_type="official",
            relevance_score=20,
            should_scrape=True,
        )
        assert link_id is not None

    def test_get_filtered_links(self, db):
        company_id = db.insert_company(original_name="Test")
        db.insert_filtered_link(
            company_id=company_id, url="https://a.com", should_scrape=True
        )
        db.insert_filtered_link(
            company_id=company_id, url="https://b.com", should_scrape=False
        )
        scrapeable = db.get_filtered_links_for_company(company_id, should_scrape=True)
        assert len(scrapeable) == 1


class TestQueryCache:
    """Test query cache operations."""

    def test_insert_and_check_cache(self, db):
        db.insert_query_cache(
            query_text="test query", company_id=1, result_count=5
        )
        assert db.is_query_cached("test query") is True

    def test_cache_miss(self, db):
        assert db.is_query_cached("nonexistent query") is False


class TestDailyQuota:
    """Test daily quota operations."""

    def test_upsert_quota(self, db):
        db.upsert_daily_quota("2026-01-01", gemini_grounding_used=10)
        quota = db.get_daily_quota("2026-01-01")
        assert quota["gemini_grounding_used"] == 10

    def test_quota_default(self, db):
        quota = db.get_daily_quota("2099-01-01")
        assert quota["gemini_grounding_used"] == 0
