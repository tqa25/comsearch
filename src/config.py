import json
import os

from dotenv import load_dotenv

load_dotenv()


def _parse_int(value, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _parse_float(value, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _parse_bool(value, default: bool) -> bool:
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes")


def _parse_json_dict(value, default: dict) -> dict:
    if value is None:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


class Config:
    """Centralized configuration loaded from environment variables."""

    def __init__(self):
        # ── Search ──
        self.SEARCH_LIMIT: int = _parse_int(os.getenv("SEARCH_LIMIT"), 100)
        self.EARLY_STOP_COUNT: int = _parse_int(os.getenv("EARLY_STOP_COUNT"), 10)
        self.EARLY_STOP_SCORE: int = _parse_int(os.getenv("EARLY_STOP_SCORE"), 35)

        # ── Scoring ──
        default_domain_scores = {
            "official": 15,
            "legal": 30,
            "job": 30,
            "social": -100,
        }
        self.DOMAIN_SCORES: dict = _parse_json_dict(
            os.getenv("DOMAIN_SCORES"), default_domain_scores
        )

        default_keyword_scores = {
            "contact": 10, "lien-he": 10, "lienhe": 10, "contacts": 10,
            "admin": 10, "hanh-chinh": 10, "hanchinh": 10, "administration": 10,
            "recruitment": 5, "tuyen-dung": 5, "tuyendung": 5, "career": 5,
            "careers": 5, "jobs": 5,
        }
        self.KEYWORD_SCORES: dict = _parse_json_dict(
            os.getenv("KEYWORD_SCORES"), default_keyword_scores
        )

        default_tld_scores = {
            ".vn": 5, ".com.vn": 5, ".com": 5, ".net": 5, ".org": 5, ".org.vn": 5,
            ".info": 2, ".biz": 2, ".top": 2, ".xyz": 2, ".club": 2,
            ".tk": 2, ".ml": 2, ".ga": 2,
        }
        self.TLD_SCORES: dict = _parse_json_dict(
            os.getenv("TLD_SCORES"), default_tld_scores
        )

        # ── Scrape ──
        self.TOP_N: int = _parse_int(os.getenv("TOP_N"), 10)
        self.CONTACT_DISCOVERY_ENABLED: bool = _parse_bool(
            os.getenv("CONTACT_DISCOVERY_ENABLED"), True
        )

        # ── Dedup ──
        self.ENABLE_QUERY_DEDUP: bool = _parse_bool(
            os.getenv("ENABLE_QUERY_DEDUP"), True
        )
        self.CACHE_TTL_DAYS: int = _parse_int(os.getenv("CACHE_TTL_DAYS"), 7)

        # ── Rate limit ──
        self.DELAY_SECONDS: float = _parse_float(os.getenv("DELAY_SECONDS"), 3.0)
        self.MAX_RETRIES: int = _parse_int(os.getenv("MAX_RETRIES"), 3)

        # ── Gemini ──
        self.GEMINI_QUICK_MODEL: str = os.getenv(
            "GEMINI_QUICK_MODEL", "gemini-2.0-flash"
        )
        self.GEMINI_DAILY_LIMIT: int = _parse_int(
            os.getenv("GEMINI_DAILY_LIMIT"), 1450
        )

        # ── Serper ──
        self.SERPER_ENABLED: bool = _parse_bool(os.getenv("SERPER_ENABLED"), True)
        self.SERPER_NUM_RESULTS: int = _parse_int(
            os.getenv("SERPER_NUM_RESULTS"), 10
        )


default_config = Config()
