"""Integration tests for the full pipeline."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.database import DatabaseManager
from src.errors import CriticalError


SAMPLE_COMPANIES = [
    "Vietnam Digital Solutions Company Limited",
    "An Phat Commercial Service Joint Stock Company",
    "Tan Tien Production Import Export Company Limited",
    "Sao Mai Technology Media Joint Stock Company",
    "Minh Khang Investment Consulting Company Limited",
]


@pytest.fixture
def temp_db():
    """Create a temporary database with sample companies."""
    from src import database as db_module

    original_path = db_module.DB_PATH
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, "test_integration.db")
    db_module.DB_PATH = temp_path

    db = DatabaseManager()
    for name in SAMPLE_COMPANIES:
        db.insert_company(original_name=name)

    yield db

    db_module.DB_PATH = original_path
    if os.path.exists(temp_path):
        os.remove(temp_path)
    os.rmdir(temp_dir)


class TestFullPipelineFlow:
    """Test full pipeline with mocked APIs."""

    @patch("src.pipeline.GeminiQuickSearch")
    @patch("src.pipeline.SearchModule")
    @patch("src.pipeline.ScrapeModule")
    @patch("src.pipeline.AIExtractor")
    def test_pipeline_completes_all_companies(
        self, mock_extractor_cls, mock_scrape_cls, mock_search_cls, mock_gemini_cls, temp_db
    ):
        """Test that pipeline completes all companies."""
        # Configure mocks
        mock_gemini_instance = MagicMock()
        mock_gemini_instance.search.return_value = {
            "result": {
                "core_name_vi": "Công ty TNHH ABC",
                "tax_code": "0123456789",
                "phone": None,
                "address": "Hanoi",
                "website": "https://abc.com",
                "confidence": 0.8,
            },
            "grounding_urls": ["https://abc.com"],
            "input_tokens": 100,
            "output_tokens": 50,
            "is_sufficient": False,
            "fallback_reason": "no phone",
        }
        mock_gemini_cls.return_value = mock_gemini_instance

        mock_search_instance = MagicMock()
        mock_search_instance.search_company.return_value = [
            {
                "url": "https://abc.com",
                "source_type": "official",
                "should_scrape": True,
                "relevance_score": 20,
                "id": 1,
            }
        ]
        mock_search_cls.return_value = mock_search_instance

        mock_scrape_instance = MagicMock()
        mock_scrape_instance.scrape_company.return_value = [
            {
                "id": 1,
                "url": "https://abc.com",
                "content_length": 1000,
                "source_type": "official",
            }
        ]
        mock_scrape_cls.return_value = mock_scrape_instance

        mock_extractor_instance = MagicMock()
        # Make the mock also insert into temp_db
        def extract_and_insert(company_id):
            contact_data = {
                "id": 1,
                "phone": "0123456789",
                "email": "info@abc.com",
                "address": "123 Hanoi",
                "representative": "Nguyen Van A",
                "fax": None,
                "confidence": 0.9,
            }
            # Actually insert into the temp_db
            temp_db.insert_extracted_contact(
                company_id=company_id,
                source_type="official",
                source_url="https://abc.com",
                phone=contact_data["phone"],
                email=contact_data["email"],
                address=contact_data["address"],
                website=None,
                fax=contact_data["fax"],
                representative=contact_data["representative"],
                raw_ai_response="",
                confidence_score=contact_data["confidence"],
            )
            return [contact_data]

        mock_extractor_instance.extract_for_company.side_effect = extract_and_insert
        mock_extractor_cls.return_value = mock_extractor_instance

        from src.pipeline import Pipeline

        pipeline = Pipeline(config=None)
        pipeline.db = temp_db  # Use temp DB

        # Run for first company only
        pipeline.run(company_ids=[1])

        # Check company status
        company = temp_db.get_company(1)
        assert company["status"] == "done"

        # Check contacts were extracted
        contacts = temp_db.get_extracted_contacts_for_company(1)
        assert len(contacts) > 0


class TestResumeAfterInterrupt:
    """Test resume functionality."""

    def test_resume_continues_from_checkpoint(self, temp_db):
        """Test that resume continues from correct status."""
        # Simulate: company 1 done, company 2 searched, company 3 pending
        temp_db.update_company(1, status="done")
        temp_db.update_company(2, status="searched")
        temp_db.update_company(3, status="pending")

        # Get companies not done
        all_companies = temp_db.get_all_companies()
        not_done = [
            c for c in all_companies
            if c["status"] not in ("done", "permanently_failed")
        ]

        # Should have 4 companies to resume (2, 3, 4, 5)
        assert len(not_done) == 4
        assert not_done[0]["id"] == 2


class TestNoPhoneStillCompletes:
    """Test that companies without phone still complete."""

    @patch("src.pipeline.GeminiQuickSearch")
    @patch("src.pipeline.SearchModule")
    @patch("src.pipeline.ScrapeModule")
    @patch("src.pipeline.AIExtractor")
    def test_no_phone_status_done(
        self, mock_extractor_cls, mock_scrape_cls, mock_search_cls, mock_gemini_cls, temp_db
    ):
        """Test company completes even without phone."""
        mock_gemini_cls.return_value.search.return_value = {
            "result": {
                "core_name_vi": None,
                "tax_code": None,
                "phone": None,
                "address": None,
                "website": None,
                "confidence": 0.0,
            },
            "grounding_urls": [],
            "input_tokens": 0,
            "output_tokens": 0,
            "is_sufficient": False,
            "fallback_reason": "no data",
        }
        mock_search_cls.return_value.search_company.return_value = []
        mock_scrape_cls.return_value.scrape_company.return_value = []
        mock_extractor_cls.return_value.extract_for_company.return_value = []

        from src.pipeline import Pipeline

        pipeline = Pipeline(config=None)
        pipeline.db = temp_db
        pipeline.run(company_ids=[1])

        company = temp_db.get_company(1)
        assert company["status"] == "done"
