"""Step 2: AI Quick Search using Gemini with Google Search Grounding."""

import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Dict, List, Optional

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from google.generativeai import protos

from src.config import default_config
from src.database import DatabaseManager
from src.errors import CriticalError, RetryableError, SkippableError

logger = logging.getLogger(__name__)

_CONFIDENCE_THRESHOLD = 0.5
_MAX_RETRIES = 3
_RETRY_BACKOFF = 60


class GeminiQuickSearch:
    """Step 2: AI Quick Search using Gemini with Google Search Grounding.

    Uses Gemini model with google_search tool to find Vietnamese company
    contact information from an English company name.
    """

    def __init__(self, db: DatabaseManager, logger, config=None):
        """Initialize GeminiQuickSearch.

        Args:
            db: DatabaseManager instance.
            logger: Logger instance.
            config: Optional Config override.
        """
        self.config = config or default_config
        self.db = db
        self.logger = logger or logging.getLogger(__name__)

        self.api_key = os.getenv("GEMINI_API_KEY")
        self._initialized = False
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.config.GEMINI_QUICK_MODEL)
            self._initialized = True
        else:
            self.logger.warning(
                "GEMINI_API_KEY not set. GeminiQuickSearch will return empty."
            )

    def search(self, company_id: int) -> dict:
        """Run Gemini Quick Search for a company.

        Args:
            company_id: The company ID to search for.

        Returns:
            Dict with result, grounding_urls, input_tokens, output_tokens,
            is_sufficient, and fallback_reason.

        Raises:
            CriticalError: If credits exhausted (402).
        """
        company = self.db.get_company(company_id)
        if not company:
            return self._empty_result("Company not found")

        company_name = company.get("original_name", "")
        if not company_name:
            return self._empty_result("Company name is empty")

        if not self._initialized:
            return self._empty_result("GEMINI_API_KEY not configured")

        today = datetime.now().strftime("%Y-%m-%d")
        quota = self.db.get_daily_quota(today)
        used = quota.get("gemini_grounding_used", 0)
        if used >= self.config.GEMINI_DAILY_LIMIT:
            self.logger.warning(
                f"[{company_id}] Daily Gemini grounding quota exceeded "
                f"({used}/{self.config.GEMINI_DAILY_LIMIT})"
            )
            return self._empty_result("Daily quota exceeded")

        prompt = self._build_prompt(company_name)

        response, latency_ms = self._call_with_retry(prompt, company_id)

        result = self._parse_response(response, company_id)

        grounding_urls = self._extract_grounding_urls(response)

        input_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0)
            output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0)

        has_phone = bool(result.get("phone"))
        confidence = result.get("confidence", 0.0)
        is_sufficient = has_phone and confidence >= _CONFIDENCE_THRESHOLD

        fallback_reason = ""
        if not is_sufficient:
            reasons = []
            if not has_phone:
                reasons.append("No phone found")
            if confidence < _CONFIDENCE_THRESHOLD:
                reasons.append(f"Low confidence ({confidence:.2f})")
            fallback_reason = "; ".join(reasons)

        new_used = used + 1
        self.db.upsert_daily_quota(today, gemini_grounding_used=new_used)

        updates = {}
        if result.get("core_name_vi"):
            updates["vietnamese_name"] = result["core_name_vi"]
        if result.get("tax_code"):
            updates["tax_code"] = result["tax_code"]
        if updates:
            updates["status"] = "searched"
            self.db.update_company(company_id, **updates)

        return {
            "result": result,
            "grounding_urls": grounding_urls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "is_sufficient": is_sufficient,
            "fallback_reason": fallback_reason,
        }

    def _build_prompt(self, company_name: str) -> str:
        """Build the search prompt for Gemini."""
        return (
            f'Find contact information for company "{company_name}".\n'
            "Return JSON with fields: core_name_vi, tax_code, phone, address, website, confidence.\n"
            "- core_name_vi: Vietnamese registered business name\n"
            "- tax_code: Tax code (10 or 13 digits)\n"
            "- phone: Contact phone number\n"
            "- address: Business address in Vietnam\n"
            "- website: Official website URL\n"
            "- confidence: Confidence score (0.0 - 1.0)\n"
            "Return ONLY valid JSON, no markdown formatting."
        )

    def _call_with_retry(
        self, prompt: str, company_id: int
    ):
        """Call Gemini API with retry logic for rate limits."""
        start = time.time()
        last_error = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = self.model.generate_content(
                    prompt,
                    tools=[protos.Tool(google_search=protos.Tool.GoogleSearch())],
                )
                elapsed = (time.time() - start) * 1000
                return response, elapsed

            except google_exceptions.ResourceExhausted as e:
                last_error = e
                if attempt < _MAX_RETRIES:
                    wait = _RETRY_BACKOFF * attempt
                    self.logger.warning(
                        f"[{company_id}] Rate limited (429). "
                        f"Waiting {wait}s (attempt {attempt}/{_MAX_RETRIES})"
                    )
                    time.sleep(wait)
                else:
                    raise RetryableError(
                        f"Rate limited after {_MAX_RETRIES} retries: {e}"
                    )

            except google_exceptions.InvalidArgument as e:
                if "API_KEY" in str(e) or "API key" in str(e):
                    raise CriticalError(f"Invalid API key: {e}")
                raise SkippableError(f"Invalid argument: {e}")

            except google_exceptions.PermissionDenied as e:
                if "billing" in str(e).lower() or "402" in str(e):
                    raise CriticalError(f"Credits exhausted: {e}")
                raise SkippableError(f"Permission denied: {e}")

            except (
                google_exceptions.Aborted,
                google_exceptions.ServiceUnavailable,
                google_exceptions.DeadlineExceeded,
            ) as e:
                last_error = e
                if attempt < _MAX_RETRIES:
                    self.logger.warning(
                        f"[{company_id}] Server error, retrying ({attempt}/{_MAX_RETRIES})"
                    )
                    time.sleep(5)
                else:
                    raise RetryableError(f"Server error after retries: {e}")

        raise RetryableError(f"Failed after retries: {last_error}")

    def _parse_response(self, response, company_id: int) -> dict:
        """Extract JSON result from Gemini response text."""
        default = {
            "core_name_vi": "",
            "tax_code": "",
            "phone": "",
            "address": "",
            "website": "",
            "confidence": 0.0,
        }

        if not response or not response.text:
            self.logger.warning(f"[{company_id}] Empty response from Gemini")
            return default

        text = response.text.strip()

        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if json_match:
            text = json_match.group(1).strip()

        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if not json_match:
            self.logger.warning(
                f"[{company_id}] No JSON found in response: {text[:200]}"
            )
            return default

        try:
            parsed = json.loads(json_match.group(0))
        except json.JSONDecodeError as e:
            self.logger.warning(f"[{company_id}] JSON parse error: {e}")
            return default

        result = dict(default)
        for key in default:
            val = parsed.get(key)
            if key == "confidence":
                try:
                    result[key] = float(val) if val is not None else 0.0
                except (ValueError, TypeError):
                    result[key] = 0.0
            elif val and isinstance(val, str):
                result[key] = val.strip()

        return result

    def _extract_grounding_urls(self, response) -> List[str]:
        """Extract grounding URLs from Gemini grounding metadata."""
        urls = []
        try:
            candidates = response.candidates
            if not candidates:
                return urls
            grounding_meta = getattr(candidates[0], "grounding_metadata", None)
            if not grounding_meta:
                return urls
            chunks = getattr(grounding_meta, "grounding_chunks", [])
            for chunk in chunks:
                web = getattr(chunk, "web", None)
                if web and getattr(web, "uri", None):
                    urls.append(web.uri)
        except Exception:
            pass
        return urls

    def _empty_result(self, reason: str) -> dict:
        """Return an empty result dict with fallback reason."""
        return {
            "result": {
                "core_name_vi": "",
                "tax_code": "",
                "phone": "",
                "address": "",
                "website": "",
                "confidence": 0.0,
            },
            "grounding_urls": [],
            "input_tokens": 0,
            "output_tokens": 0,
            "is_sufficient": False,
            "fallback_reason": reason,
        }
