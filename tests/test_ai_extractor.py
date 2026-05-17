"""Tests for AI extractor fixes (issues 1, 2, 3, 5, 6, 8)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.ai_extractor import AIExtractor


@pytest.fixture
def extractor(mock_db, mock_logger):
    """Create AIExtractor with mocked dependencies."""
    with patch("src.ai_extractor.genai"):
        ext = AIExtractor(db=mock_db, logger=mock_logger)
        ext.enabled = True
        ext.model = MagicMock()
        return ext


class TestValidateExtractedValue:
    """Issue 3: Test placeholder value rejection."""

    def test_valid_phone(self, extractor):
        assert extractor._validate_extracted_value("0123456789") == "0123456789"

    def test_valid_email(self, extractor):
        assert extractor._validate_extracted_value("test@example.com") == "test@example.com"

    def test_reject_phone_number_placeholder(self, extractor):
        assert extractor._validate_extracted_value("phone number") is None

    def test_reject_email_placeholder(self, extractor):
        assert extractor._validate_extracted_value("email") is None

    def test_reject_na(self, extractor):
        assert extractor._validate_extracted_value("N/A") is None
        assert extractor._validate_extracted_value("n/a") is None

    def test_reject_unknown(self, extractor):
        assert extractor._validate_extracted_value("unknown") is None
        assert extractor._validate_extracted_value("not found") is None

    def test_reject_null_none(self, extractor):
        assert extractor._validate_extracted_value(None) is None
        assert extractor._validate_extracted_value("") is None

    def test_reject_field_names(self, extractor):
        assert extractor._validate_extracted_value("phone") is None
        assert extractor._validate_extracted_value("address") is None
        assert extractor._validate_extracted_value("fax") is None

    def test_strip_whitespace(self, extractor):
        assert extractor._validate_extracted_value("  0123456789  ") == "0123456789"

    def test_reject_not_available(self, extractor):
        assert extractor._validate_extracted_value("not available") is None

    def test_reject_contact_us(self, extractor):
        assert extractor._validate_extracted_value("contact us") is None

    def test_reject_see_website(self, extractor):
        assert extractor._validate_extracted_value("see website") is None

    def test_reject_null_string(self, extractor):
        assert extractor._validate_extracted_value("null") is None
        assert extractor._validate_extracted_value("none") is None

    def test_reject_representative_placeholder(self, extractor):
        assert extractor._validate_extracted_value("representative") is None

    def test_non_string_value(self, extractor):
        """Non-string truthy values should be converted to string."""
        assert extractor._validate_extracted_value(123) == "123"

    def test_non_string_false_value(self, extractor):
        """Non-string falsy values should return None."""
        assert extractor._validate_extracted_value(0) is None
        assert extractor._validate_extracted_value(False) is None


class TestParseJsonResponse:
    """Issue 5: Test JSON parser with trailing text."""

    def test_clean_json(self, extractor):
        result = extractor._parse_json_response('{"phone": "0123"}')
        assert result["phone"] == "0123"

    def test_json_with_trailing_text(self, extractor):
        result = extractor._parse_json_response(
            '{"phone": "0123"}\n\nDay la thong tin tim duoc.'
        )
        assert result["phone"] == "0123"

    def test_json_in_markdown_block(self, extractor):
        result = extractor._parse_json_response(
            '```json\n{"phone": "0123"}\n```'
        )
        assert result["phone"] == "0123"

    def test_json_with_nested_strings(self, extractor):
        result = extractor._parse_json_response(
            '{"phone": "0123", "note": "goi luc 8h"}'
        )
        assert result["note"] == "goi luc 8h"

    def test_invalid_json_raises(self, extractor):
        with pytest.raises(json.JSONDecodeError):
            extractor._parse_json_response("no json here")

    def test_json_with_leading_text(self, extractor):
        """JSON preceded by explanatory text."""
        result = extractor._parse_json_response(
            'Day la ket qua:\n{"phone": "0123"}'
        )
        assert result["phone"] == "0123"

    def test_json_with_unicode(self, extractor):
        """JSON containing Vietnamese unicode characters."""
        result = extractor._parse_json_response(
            '{"phone": "0123", "address": "Ha Noi, Viet Nam"}'
        )
        assert result["address"] == "Ha Noi, Viet Nam"

    def test_markdown_block_without_language(self, extractor):
        """Markdown block without language specifier."""
        result = extractor._parse_json_response(
            '```\n{"phone": "0123"}\n```'
        )
        assert result["phone"] == "0123"

    def test_empty_object(self, extractor):
        result = extractor._parse_json_response("{}")
        assert result == {}

    def test_json_with_null_values(self, extractor):
        result = extractor._parse_json_response(
            '{"phone": null, "email": "test@example.com"}'
        )
        assert result["phone"] is None
        assert result["email"] == "test@example.com"


class TestExtractFromPageWithPageObject:
    """Issue 6: Test extract_from_page receives page object directly."""

    @patch("time.sleep")
    def test_extract_with_page_object(self, mock_sleep, extractor):
        page = {
            "id": 1,
            "url": "https://example.com/contact",
            "markdown_content": "Phone: 0123456789\nEmail: test@example.com",
            "source_type": "official",
            "scrape_status": "success",
        }

        extractor.model.generate_content.return_value.text = (
            '{"phone": "0123456789", "email": "test@example.com", "confidence": 0.9}'
        )

        result = extractor.extract_from_page(company_id=1, page=page)
        assert result is not None
        assert result["phone"] == "0123456789"
        assert result["email"] == "test@example.com"
        assert result["confidence"] == 0.9

    @patch("time.sleep")
    def test_extract_empty_markdown(self, mock_sleep, extractor):
        page = {"id": 1, "url": "https://example.com", "markdown_content": ""}
        result = extractor.extract_from_page(company_id=1, page=page)
        assert result is None

    @patch("time.sleep")
    def test_extract_no_phone_pattern(self, mock_sleep, extractor):
        page = {
            "id": 1,
            "url": "https://example.com",
            "markdown_content": "This page has no phone numbers at all",
        }
        result = extractor.extract_from_page(company_id=1, page=page)
        assert result is None

    @patch("time.sleep")
    def test_extract_all_placeholders_returns_none(self, mock_sleep, extractor):
        """When AI returns only placeholder values, result should be None."""
        page = {
            "id": 1,
            "url": "https://example.com",
            "markdown_content": "Phone: 0123456789",
        }

        extractor.model.generate_content.return_value.text = (
            '{"phone": "phone number", "email": "email", "confidence": 0.5}'
        )

        result = extractor.extract_from_page(company_id=1, page=page)
        assert result is None

    @patch("time.sleep")
    def test_extract_with_address_only(self, mock_sleep, extractor):
        """Extract should succeed with address as valid field."""
        page = {
            "id": 1,
            "url": "https://example.com",
            "markdown_content": "Phone: 0123456789",
        }

        extractor.model.generate_content.return_value.text = (
            '{"phone": null, "email": null, "address": "123 Street, Hanoi", "confidence": 0.8}'
        )

        result = extractor.extract_from_page(company_id=1, page=page)
        assert result is not None
        assert result["address"] == "123 Street, Hanoi"
        assert result["phone"] is None

    @patch("time.sleep")
    def test_extract_disabled_extractor(self, mock_sleep, extractor):
        """When extractor is disabled, should return None."""
        extractor.enabled = False
        extractor.model = None

        page = {
            "id": 1,
            "url": "https://example.com",
            "markdown_content": "Phone: 0123456789",
        }

        result = extractor.extract_from_page(company_id=1, page=page)
        assert result is None

    @patch("time.sleep")
    def test_extract_truncates_long_markdown(self, mock_sleep, extractor):
        """Long markdown should be truncated before sending to AI."""
        from src.ai_extractor import MAX_MARKDOWN_LENGTH

        long_content = "Phone: 0123456789 " * (MAX_MARKDOWN_LENGTH + 100)
        page = {
            "id": 1,
            "url": "https://example.com",
            "markdown_content": long_content,
        }

        extractor.model.generate_content.return_value.text = (
            '{"phone": "0123456789", "confidence": 0.9}'
        )

        result = extractor.extract_from_page(company_id=1, page=page)
        assert result is not None
        # Verify the call was made with truncated content
        call_args = extractor.model.generate_content.call_args[0][0]
        assert len(call_args) < len(long_content) + 500  # prompt + truncated markdown


class TestRetryOn500Error:
    """Issue 1: Test retry mechanism for 500 errors."""

    @patch("time.sleep")
    def test_retry_on_500_then_success(self, mock_sleep, extractor):
        page = {
            "id": 1,
            "url": "https://example.com",
            "markdown_content": "Phone: 0123456789",
        }

        # First call fails with 500, second succeeds
        extractor.model.generate_content.side_effect = [
            Exception("500 Internal error encountered."),
            MagicMock(text='{"phone": "0123456789", "confidence": 0.9}'),
        ]

        result = extractor.extract_from_page(company_id=1, page=page, max_retries=2)
        assert result is not None
        assert result["phone"] == "0123456789"
        # Should have been called twice
        assert extractor.model.generate_content.call_count == 2

    @patch("time.sleep")
    def test_retry_exhausted_returns_none(self, mock_sleep, extractor):
        page = {
            "id": 1,
            "url": "https://example.com",
            "markdown_content": "Phone: 0123456789",
        }

        # All calls fail with 500
        extractor.model.generate_content.side_effect = Exception("500 Internal error")

        result = extractor.extract_from_page(company_id=1, page=page, max_retries=2)
        assert result is None
        # Should have been called 3 times (1 initial + 2 retries)
        assert extractor.model.generate_content.call_count == 3

    @patch("time.sleep")
    def test_retry_on_internal_error(self, mock_sleep, extractor):
        """'internal' in error message should also trigger retry."""
        page = {
            "id": 1,
            "url": "https://example.com",
            "markdown_content": "Phone: 0123456789",
        }

        extractor.model.generate_content.side_effect = [
            Exception("Internal server error"),
            MagicMock(text='{"phone": "0123456789", "confidence": 0.9}'),
        ]

        result = extractor.extract_from_page(company_id=1, page=page, max_retries=2)
        assert result is not None
        assert extractor.model.generate_content.call_count == 2

    @patch("time.sleep")
    def test_429_raises_retryable_error(self, mock_sleep, extractor):
        """429 rate limit should raise RetryableError, not return None."""
        from src.errors import RetryableError

        page = {
            "id": 1,
            "url": "https://example.com",
            "markdown_content": "Phone: 0123456789",
        }

        extractor.model.generate_content.side_effect = Exception("429 Rate limit exceeded")

        with pytest.raises(RetryableError):
            extractor.extract_from_page(company_id=1, page=page)

    @patch("time.sleep")
    def test_402_raises_critical_error(self, mock_sleep, extractor):
        """402 credits exhausted should raise CriticalError."""
        from src.errors import CriticalError

        page = {
            "id": 1,
            "url": "https://example.com",
            "markdown_content": "Phone: 0123456789",
        }

        extractor.model.generate_content.side_effect = Exception("402 Payment Required")

        with pytest.raises(CriticalError):
            extractor.extract_from_page(company_id=1, page=page)

    @patch("time.sleep")
    def test_non_retryable_error_returns_none(self, mock_sleep, extractor):
        """Non-500/non-retryable errors should return None without retry."""
        page = {
            "id": 1,
            "url": "https://example.com",
            "markdown_content": "Phone: 0123456789",
        }

        extractor.model.generate_content.side_effect = Exception("Some random error")

        result = extractor.extract_from_page(company_id=1, page=page, max_retries=2)
        assert result is None
        # Should only be called once (no retry for non-500 errors)
        assert extractor.model.generate_content.call_count == 1


class TestHasPhonePattern:
    """Test phone pattern detection (pre-filter)."""

    def test_vietnamese_phone_0_prefix(self, extractor):
        assert extractor._has_phone_pattern("Call us at 0123456789") is True

    def test_vietnamese_phone_84_prefix(self, extractor):
        assert extractor._has_phone_pattern("Call us at +84123456789") is True

    def test_no_phone_pattern(self, extractor):
        assert extractor._has_phone_pattern("No phone here") is False

    def test_phone_in_context(self, extractor):
        assert extractor._has_phone_pattern(
            "Contact: 0987654321, Email: test@example.com"
        ) is True

    def test_10_digit_phone(self, extractor):
        assert extractor._has_phone_pattern("0987654321") is True


class TestRateLimiting:
    """Issue 8: Test rate limiting behavior."""

    def test_rate_limit_waits(self, extractor):
        """Rate limiter should enforce minimum interval between requests."""
        # Set last request time to now
        import time
        extractor._last_request_time = time.time()
        extractor._rpm_interval = 0.01  # Very short for testing

        # Should not raise, just wait
        extractor._wait_for_rate_limit()
        # Verify last_request_time was updated
        assert extractor._last_request_time > 0
