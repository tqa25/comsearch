"""Tests for config module."""

import os
from unittest.mock import patch

import pytest

from src.config import Config, _parse_bool, _parse_float, _parse_int


class TestParseHelpers:
    """Test config parsing helpers."""

    def test_parse_int_valid(self):
        assert _parse_int("100", 0) == 100

    def test_parse_int_invalid(self):
        assert _parse_int("abc", 42) == 42

    def test_parse_int_none(self):
        assert _parse_int(None, 42) == 42

    def test_parse_float_valid(self):
        assert _parse_float("3.5", 0.0) == 3.5

    def test_parse_float_none(self):
        assert _parse_float(None, 1.0) == 1.0

    def test_parse_bool_true(self):
        assert _parse_bool("true", False) is True
        assert _parse_bool("1", False) is True
        assert _parse_bool("yes", False) is True

    def test_parse_bool_false(self):
        assert _parse_bool("false", True) is False
        assert _parse_bool("0", True) is False
        assert _parse_bool(None, True) is True


class TestConfigDefaults:
    """Test default config values."""

    def test_search_limit(self):
        config = Config()
        assert config.SEARCH_LIMIT == 100

    def test_early_stop(self):
        config = Config()
        assert config.EARLY_STOP_COUNT == 10
        assert config.EARLY_STOP_SCORE == 35

    def test_domain_scores(self):
        config = Config()
        assert config.DOMAIN_SCORES["official"] == 15
        assert config.DOMAIN_SCORES["legal"] == 30
        assert config.DOMAIN_SCORES["social"] == -100

    def test_tld_scores(self):
        config = Config()
        assert config.TLD_SCORES[".vn"] == 5
        assert config.TLD_SCORES[".com"] == 5

    def test_delay_seconds(self):
        config = Config()
        assert config.DELAY_SECONDS == 3.0

    def test_max_retries(self):
        config = Config()
        assert config.MAX_RETRIES == 3
