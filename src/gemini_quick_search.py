import json
import logging
import time
from datetime import datetime
from typing import Dict, Optional

import google.generativeai as genai
from google.generativeai.types import GenerateContentResponse

from src.config import default_config
from src.database import DatabaseManager
from src.errors import CriticalError, RetryableError

logger = logging.getLogger(__name__)

GEMINI_QUICK_SEARCH_PROMPT = """\
Tìm thông tin liên hệ của công ty "{company_name}".
Trả về JSON với các trường sau, KHÔNG thêm text ngoài JSON:
{{
  "core_name_vi": "Tên đăng ký kinh doanh bằng tiếng Việt",
  "tax_code": "Mã số thuế (10 hoặc 13 chữ số)",
  "phone": "Số điện thoại liên hệ",
  "address": "Địa chỉ công ty",
  "website": "Website chính thức",
  "confidence": 0.0
}}
- core_name_vi: Tên pháp lý đầy đủ bằng tiếng Việt (nếu biết)
- tax_code: Mã số thuế, chỉ số, không có ký tự khác
- phone: Số điện thoại, nếu không tìm thấy thì null
- address: Địa chỉ đầy đủ, nếu không tìm thấy thì null
- website: URL website, nếu không tìm thấy thì null
- confidence: Độ tin cậy từ 0.0 đến 1.0
"""


class GeminiQuickSearch:
    """Bước 2: AI Quick Search using Gemini with Google Search Grounding."""

    def __init__(
        self,
        db: DatabaseManager,
        logger: logging.Logger = None,
        config=None,
    ):
        self.config = config or default_config
        self.db = db
        self.logger = logger or logging.getLogger(__name__)

        api_key = self._get_gemini_api_key()
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(
                model_name=self.config.GEMINI_QUICK_MODEL
            )
            self.enabled = True
        else:
            self.logger.warning(
                "GEMINI_API_KEY not set. GeminiQuickSearch disabled."
            )
            self.model = None
            self.enabled = False

        # Rate limiting: RPM limit for Gemini 2.5 Flash = 5
        self._last_request_time: float = 0
        self._rpm_interval = 60.0 / 5.0  # 12 seconds between requests

    def _get_gemini_api_key(self) -> Optional[str]:
        import os
        return os.getenv("GEMINI_API_KEY")

    def _wait_for_rate_limit(self):
        """Wait to respect RPM limit."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._rpm_interval:
            wait_time = self._rpm_interval - elapsed
            self.logger.debug(
                f"Rate limit wait: {wait_time:.1f}s (RPM=5)"
            )
            time.sleep(wait_time)
        self._last_request_time = time.time()

    def _increment_gemini_quota(self):
        """Track daily Gemini usage."""
        today = datetime.now().strftime("%Y-%m-%d")
        quota = self.db.get_daily_quota(today)
        current = quota.get("gemini_grounding_used", 0)
        self.db.upsert_daily_quota(
            date_str=today,
            gemini_grounding_used=current + 1,
        )

    def _extract_grounding_urls(
        self, response: GenerateContentResponse
    ) -> list:
        """Extract grounding URLs from Gemini response metadata."""
        urls = []
        try:
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "grounding_metadata"):
                    metadata = candidate.grounding_metadata
                    if hasattr(metadata, "grounding_chunks"):
                        for chunk in metadata.grounding_chunks:
                            if hasattr(chunk, "web") and chunk.web:
                                if hasattr(chunk.web, "uri"):
                                    urls.append(chunk.web.uri)
        except Exception as e:
            self.logger.warning(f"Failed to extract grounding URLs: {e}")
        return urls

    def _parse_json_response(self, text: str) -> dict:
        """Parse JSON from Gemini text response."""
        text = text.strip()

        # Try to extract JSON from markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json or ```)
            lines = lines[1:]
            # Remove last line if it's ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in text (handle trailing text)
        start = text.find("{")
        if start >= 0:
            # Count braces to find the matching closing brace
            depth = 0
            end = start
            for i in range(start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if depth == 0:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass

        raise json.JSONDecodeError("No valid JSON found", text, 0)

    def search(self, company_id: int) -> dict:
        """Bước 2: AI Quick Search.

        Args:
            company_id: The company ID to search for.

        Returns:
            Dict with result, grounding_urls, token counts, is_sufficient.

        Raises:
            RetryableError: If rate limited.
            CriticalError: If credits exhausted.
        """
        company = self.db.get_company(company_id)
        if not company:
            raise ValueError(f"Company {company_id} not found")

        company_name = company["original_name"]

        if not self.enabled or self.model is None:
            self.logger.warning(
                f"[{company_id}] Gemini disabled, skipping quick search"
            )
            return {
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
                "fallback_reason": "Gemini API key not configured",
            }

        prompt = GEMINI_QUICK_SEARCH_PROMPT.format(
            company_name=company_name
        )

        self._wait_for_rate_limit()

        try:
            # Gemma models don't support grounding tools, use plain generation
            response = self.model.generate_content(prompt)

            self._increment_gemini_quota()

            # Extract grounding URLs
            grounding_urls = self._extract_grounding_urls(response)

            # Extract token usage (approximate)
            input_tokens = 0
            output_tokens = 0
            try:
                usage = response.usage_metadata
                if usage:
                    input_tokens = getattr(
                        usage, "prompt_token_count", 0
                    )
                    output_tokens = getattr(
                        usage, "candidates_token_count", 0
                    )
            except Exception:
                pass

            # Parse JSON result
            result = self._parse_json_response(response.text)

            # Build return dict
            search_result = {
                "core_name_vi": result.get("core_name_vi"),
                "tax_code": result.get("tax_code"),
                "phone": result.get("phone"),
                "address": result.get("address"),
                "website": result.get("website"),
                "confidence": float(result.get("confidence", 0.0)),
            }

            # Determine sufficiency
            has_phone = bool(search_result.get("phone"))
            confidence_ok = search_result["confidence"] >= 0.7
            is_sufficient = has_phone and confidence_ok

            fallback_reason = ""
            if not is_sufficient:
                reasons = []
                if not has_phone:
                    reasons.append("no phone")
                if not confidence_ok:
                    reasons.append(
                        f"low confidence ({search_result['confidence']})"
                    )
                fallback_reason = ", ".join(reasons)

            return {
                "result": search_result,
                "grounding_urls": grounding_urls,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "is_sufficient": is_sufficient,
                "fallback_reason": fallback_reason,
            }

        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "rate" in error_msg:
                raise RetryableError(
                    f"Gemini rate limited: {e}"
                ) from e
            if "402" in error_msg:
                raise CriticalError(
                    f"Gemini credits exhausted: {e}"
                ) from e

            # For all other errors, log and return empty result
            # (don't stop the pipeline for Gemini errors)
            self.logger.error(
                f"[{company_id}] Gemini Quick Search error: {e}"
            )
            return {
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
                "fallback_reason": f"Error: {e}",
            }
