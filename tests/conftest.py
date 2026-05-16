"""Shared fixtures for tests."""

import os
import tempfile

import pytest

from src.database import DatabaseManager


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    # Save original DB path
    from src import database as db_module

    original_path = db_module.DB_PATH

    # Create temp DB
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, "test_company_data.db")
    db_module.DB_PATH = temp_path

    db = DatabaseManager()
    yield db

    # Cleanup
    db_module.DB_PATH = original_path
    if os.path.exists(temp_path):
        os.remove(temp_path)
    os.rmdir(temp_dir)


@pytest.fixture
def mock_db():
    """Create a mock database."""
    from unittest.mock import MagicMock

    db = MagicMock(spec=DatabaseManager)
    db.get_company.return_value = {
        "id": 1,
        "original_name": "ABC Co., Ltd",
        "vietnamese_name": "Công ty TNHH ABC",
        "tax_code": "0123456789",
        "status": "pending",
        "address": "Hanoi",
    }
    db.get_all_companies.return_value = []
    db.get_search_results_for_company.return_value = []
    db.get_filtered_links_for_company.return_value = []
    db.get_scraped_pages_for_company.return_value = []
    db.get_extracted_contacts_for_company.return_value = []
    db.is_query_cached.return_value = False
    db.get_daily_quota.return_value = {
        "date": "2026-01-01",
        "gemini_grounding_used": 0,
        "serper_used": 0,
    }
    return db


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    from unittest.mock import MagicMock

    return MagicMock()
