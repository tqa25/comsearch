"""Step 5.2: AI contact extraction from scraped pages."""

import json
import logging
import os
import re
import time
from typing import Dict, List, Optional

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from src.config import default_config
from src.database import DatabaseManager
from src.errors import CriticalError, RetryableError, SkippableError

logger = logging.getLogger(__name__)

PHONE_PATTERN = r'(?:\+84|0)\d{9,10}'
_MAX_CONTENT_CHARS = 30_000
_MAX_RETRIES = 3
_RETRY_BACKOFF = 60

_SOURCE_PRIORITY = {
    "masothue": 0,
    "legal": 1,
    "official": 2,
    "job": 3,
    "social": 4,
}


class AIExtractor:
    """Step 5.2: Extract contact info from scraped pages using Gemini AI.

    Performs regex pre-filter before AI calls to save API credits,
    processes pages in priority order (masothue -> legal -> official -> job -> social),
    and resolves conflicts by keeping the highest confidence result.
    """

    def __init__(self, db: DatabaseManager, logger, config=None):
        self.config = config or default_config
        self.db = db
        self.logger = logger or logging.getLogger(__name__)

        self.api_key = os.getenv("GEMINI_API_KEY")
        self._initialized = False
        if self.api_key:
            genai.configure(api_key=self.api_key)
            model_name = getattr(
                self.config, "GEMINI_QUICK_MODEL", "models/gemma-4-31b-it"
            )
            self.model = genai.GenerativeModel(model_name)
            self._initialized = True
        else:
            self.logger.warning(
                "GEMINI_API_KEY not set. AIExtractor will skip AI extraction."
            )

    def extract_for_company(self, company_id: int, delay: float = 3.0):
        """Extract contact info from all scraped pages of a company.

        1. Fetches scraped_pages (scrape_status='success')
        2. Sorts by priority: masothue first, social last
        3. For each page:
           a. Regex pre-filter: check for phone-like patterns
           b. If found -> call Gemini AI to extract JSON
           c. Store result in extracted_contacts

        Args:
            company_id: The company ID to extract for.
            delay: Seconds to wait between AI calls.

        Raises:
            CriticalError: If credits exhausted (402).
        """
        pages = self.db.get_scraped_pages_for_company(company_id)
        success_pages = [
            p for p in pages if p.get("scrape_status") == "success"
        ]

        if not success_pages:
            self.logger.info(
                f"[{company_id}] No successfully scraped pages found"
            )
            return

        sorted_pages = sorted(
            success_pages,
            key=lambda p: _SOURCE_PRIORITY.get(p.get("source_type", ""), 99),
        )

        self.logger.info(
            f"[{company_id}] Extracting from {len(sorted_pages)} pages"
        )

        best_contact = None
        best_confidence = -1.0

        for page in sorted_pages:
            markdown = page.get("markdown_content") or ""

            if not markdown.strip():
                self.logger.info(
                    f"[{company_id}] Page {page.get('id')}: empty content, skipping"
                )
                continue

            if not re.search(PHONE_PATTERN, markdown):
                self.logger.info(
                    f"[{company_id}] Page {page.get('id')}: no phone pattern, "
                    f"skipping AI call"
                )
                continue

            result = self._extract_from_page_data(page)

            if result and result.get("confidence", 0) > best_confidence:
                best_contact = result
                best_confidence = result.get("confidence", 0)
                self.logger.info(
                    f"[{company_id}] Page {page.get('id')}: "
                    f"new best confidence={best_confidence:.2f}"
                )

            time.sleep(delay)

        if best_contact:
            self._merge_contact(company_id, best_contact)

    def extract_from_page(self, page_id: int) -> dict:
        """Extract contact info from a single scraped page by ID.

        Args:
            page_id: The scraped page ID.

        Returns:
            Dict with extracted fields, or empty dict if extraction fails.
        """
        page = self.db.get_scraped_page(page_id)
        if not page:
            self.logger.warning(f"[page={page_id}] Page not found")
            return {}

        result = self._extract_from_page_data(page)

        if result:
            self.db.insert_extracted_contact(
                company_id=page.get("company_id", 0),
                source_type=result.get("source_type", ""),
                source_url=result.get("source_url", ""),
                phone=result.get("phone"),
                email=result.get("email"),
                address=result.get("address"),
                fax=result.get("fax"),
                representative=result.get("representative"),
                raw_ai_response=json.dumps(result, ensure_ascii=False),
                confidence_score=result.get("confidence", 0.0),
            )

        return result

    def _extract_from_page_data(self, page: dict) -> dict:
        """Extract contact info from a scraped page dict.

        Args:
            page: Scraped page dict from DB.

        Returns:
            Dict with extracted fields, or empty dict.
        """
        markdown = page.get("markdown_content") or ""
        url = page.get("url", "")
        source_type = page.get("source_type", "")

        if len(markdown) > _MAX_CONTENT_CHARS:
            self.logger.info(
                f"[page={page.get('id')}] Truncating markdown from "
                f"{len(markdown)} to {_MAX_CONTENT_CHARS} chars"
            )
            markdown = markdown[:_MAX_CONTENT_CHARS]

        if not re.search(PHONE_PATTERN, markdown):
            return {}

        if not self._initialized:
            self.logger.warning(
                f"[page={page.get('id')}] Gemini not initialized, skipping"
            )
            return {}

        prompt = self._build_extraction_prompt(markdown)
        response_text = self._call_gemini(prompt, page.get("id", 0))

        if not response_text:
            return {}

        parsed = self._parse_extraction_response(response_text, page.get("id", 0))
        if not parsed:
            return {}

        parsed["source_url"] = url
        parsed["source_type"] = source_type
        return parsed

    def _build_extraction_prompt(self, markdown: str) -> str:
        return (
            "Trích xuất thông tin liên hệ từ nội dung sau. Trả về JSON:\n"
            "{\n"
            '  "phone": "số điện thoại",\n'
            '  "email": "email",\n'
            '  "address": "địa chỉ",\n'
            '  "representative": "người đại diện",\n'
            '  "fax": "số fax",\n'
            '  "confidence": 0.0-1.0\n'
            "}\n"
            "Nếu không tìm thấy trường nào, để null.\n"
            "Trả về ONLY valid JSON, không markdown formatting.\n\n"
            f"Nội dung:\n{markdown}"
        )

    def _call_gemini(self, prompt: str, page_id: int) -> Optional[str]:
        """Call Gemini API with retry for extraction.

        Args:
            prompt: The prompt to send.
            page_id: Page ID for logging.

        Returns:
            Response text, or None on failure.

        Raises:
            CriticalError: If credits exhausted.
        """
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = self.model.generate_content(prompt)
                return response.text if response else None

            except google_exceptions.ResourceExhausted as e:
                if attempt < _MAX_RETRIES:
                    wait = _RETRY_BACKOFF * attempt
                    self.logger.warning(
                        f"[page={page_id}] Gemini rate limited (429). "
                        f"Waiting {wait}s (attempt {attempt}/{_MAX_RETRIES})"
                    )
                    time.sleep(wait)
                else:
                    raise RetryableError(
                        f"Gemini rate limited after {_MAX_RETRIES} retries: {e}"
                    )

            except google_exceptions.InvalidArgument as e:
                if "API_KEY" in str(e) or "API key" in str(e):
                    raise CriticalError(f"Invalid Gemini API key: {e}")
                raise SkippableError(f"Invalid argument: {e}")

            except google_exceptions.PermissionDenied as e:
                if "billing" in str(e).lower() or "402" in str(e):
                    raise CriticalError(f"Gemini credits exhausted: {e}")
                raise SkippableError(f"Permission denied: {e}")

            except (
                google_exceptions.Aborted,
                google_exceptions.ServiceUnavailable,
                google_exceptions.DeadlineExceeded,
                google_exceptions.InternalServerError,
            ) as e:
                if attempt < _MAX_RETRIES:
                    self.logger.warning(
                        f"[page={page_id}] Gemini server error, retrying "
                        f"({attempt}/{_MAX_RETRIES})"
                    )
                    time.sleep(5)
                else:
                    raise RetryableError(
                        f"Gemini server error after retries: {e}"
                    )

        return None

    def _parse_extraction_response(
        self, text: str, page_id: int
    ) -> Optional[Dict]:
        """Parse JSON from Gemini extraction response.

        Args:
            text: Raw response text.
            page_id: Page ID for logging.

        Returns:
            Parsed dict or None.
        """
        if not text or not text.strip():
            self.logger.warning(f"[page={page_id}] Empty extraction response")
            return None

        cleaned = text.strip()
        json_match = re.search(
            r"```(?:json)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL
        )
        if json_match:
            cleaned = json_match.group(1).strip()
        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not json_match:
            self.logger.warning(
                f"[page={page_id}] No JSON in extraction response: {text[:200]}"
            )
            return None

        try:
            parsed = json.loads(json_match.group(0))
        except json.JSONDecodeError as e:
            self.logger.warning(f"[page={page_id}] JSON parse error: {e}")
            return None

        result = {
            "phone": parsed.get("phone") or None,
            "email": parsed.get("email") or None,
            "address": parsed.get("address") or None,
            "representative": parsed.get("representative") or None,
            "fax": parsed.get("fax") or None,
            "confidence": 0.0,
        }
        try:
            result["confidence"] = float(parsed.get("confidence", 0.0))
        except (ValueError, TypeError):
            result["confidence"] = 0.0

        has_any = any(v for k, v in result.items() if k != "confidence")
        if not has_any:
            self.logger.info(f"[page={page_id}] Extraction returned no fields")
            result["confidence"] = 0.0

        return result

    def _merge_contact(self, company_id: int, contact: dict) -> None:
        """Merge extracted contact, keeping the highest confidence version.

        Args:
            company_id: The company ID.
            contact: Contact dict to save.
        """
        existing = self.db.get_extracted_contacts_for_company(company_id)
        new_conf = contact.get("confidence", 0.0)

        if existing:
            best = max(existing, key=lambda x: x.get("confidence_score", 0))
            if new_conf > best.get("confidence_score", 0):
                self._insert_contact(company_id, contact)
                self.logger.info(
                    f"[{company_id}] Replaced previous best contact "
                    f"(confidence={new_conf:.2f})"
                )
        else:
            self._insert_contact(company_id, contact)
            self.logger.info(
                f"[{company_id}] Saved first contact "
                f"(confidence={new_conf:.2f})"
            )

    def _insert_contact(self, company_id: int, contact: dict) -> None:
        self.db.insert_extracted_contact(
            company_id=company_id,
            source_type=contact.get("source_type", ""),
            source_url=contact.get("source_url", ""),
            phone=contact.get("phone"),
            email=contact.get("email"),
            address=contact.get("address"),
            fax=contact.get("fax"),
            representative=contact.get("representative"),
            raw_ai_response=json.dumps(
                {k: v for k, v in contact.items() if k not in ("source_type", "source_url")},
                ensure_ascii=False,
            ),
            confidence_score=contact.get("confidence", 0.0),
        )
