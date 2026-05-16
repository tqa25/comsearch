"""Tests for error hierarchy."""

import pytest

from src.errors import CriticalError, PipelineError, RetryableError, SkippableError


class TestErrorHierarchy:
    """Test exception hierarchy."""

    def test_retryable_is_pipeline_error(self):
        err = RetryableError("test")
        assert isinstance(err, PipelineError)

    def test_critical_is_pipeline_error(self):
        err = CriticalError("test")
        assert isinstance(err, PipelineError)

    def test_skippable_is_pipeline_error(self):
        err = SkippableError("test")
        assert isinstance(err, PipelineError)

    def test_retryable_not_critical(self):
        err = RetryableError("test")
        assert not isinstance(err, CriticalError)

    def test_critical_not_retryable(self):
        err = CriticalError("test")
        assert not isinstance(err, RetryableError)

    def test_error_message(self):
        err = RetryableError("rate limited")
        assert str(err) == "rate limited"

    def test_catch_pipeline_error(self):
        errors = [
            RetryableError("retry"),
            CriticalError("critical"),
            SkippableError("skip"),
        ]
        for err in errors:
            with pytest.raises(PipelineError):
                raise err
