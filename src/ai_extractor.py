import json
import logging
import re
import time
from typing import Dict, List, Optional

import google.generativeai as genai

from src.config import default_config
from src.database import DatabaseManager
from src.errors import CriticalError, RetryableError

logger = logging.getLogger(__name__)

PHONE_PATTERN = re.compile(r"(?:\+84|0)\d{9,10}")

AI_EXTRACT_PROMPT = """\
Trích xuất thông tin liên hệ từ nội dung sau. Trả về JSON, KHÔNG thêm text ngoài JSON:
{{
  "phone": "số điện thoại",
  "email": "email",
  "address": "địa chỉ",
  "representative": "người đại diện",
  "fax": "số fax",
  "confidence": 0.0
}}
Nếu không tìm thấy trường nào, để null.
Chỉ trích xuất thông tin liên hệ của công ty, không phải thông tin khác.
"""

MAX_MARKDOWN_LENGTH = 30000

# Processing order: legal first, social last
SOURCE_TYPE_PRIORITY = {
    "legal": 0,
    "official": 1,
    "job": 2,
    "unknown": 3,
    "social": 4,
    "contact_discovery": 5,
}


class AIExtractor:
    """Bước 5.2: Extract contact info from scraped pages using Gemini AI."""

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
                "GEMINI_API_KEY not set. AIExtractor disabled."
            )
            self.model = None
            self.enabled = False

        # Rate limiting: RPM = 5
        self._last_request_time: float = 0
        self._rpm_interval = 60.0 / 5.0  # 12 seconds

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
                f"AI Extract rate limit wait: {wait_time:.1f}s"
            )
            time.sleep(wait_time)
        self._last_request_time = time.time()

    def _has_phone_pattern(self, text: str) -> bool:
        """Check if text contains phone-like patterns."""
        return bool(PHONE_PATTERN.search(text))

    def _parse_json_response(self, text: str) -> dict:
        """Parse JSON from AI response text."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            raise

    def extract_from_page(self, page_id: int) -> Optional[Dict]:
        """Extract contact info from a single scraped page.

        Args:
            page_id: The scraped page ID.

        Returns:
            Dict with extracted contact info, or None.
        """
        pages = self.db.get_scraped_pages_for_company(0)  # placeholder
        page = None
        # Find the specific page
        all_pages = self.db.get_scraped_pages_for_company(0)
        for p in all_pages:
            if p["id"] == page_id:
                page = p
                break

        if not page:
            self.logger.warning(f"Page {page_id} not found")
            return None

        markdown = page.get("markdown_content", "")
        if not markdown:
            return None

        # Regex pre-filter
        if not self._has_phone_pattern(markdown):
            self.logger.debug(
                f"Page {page_id} has no phone pattern, skipping AI"
            )
            return None

        if not self.enabled or self.model is None:
            self.logger.warning("AIExtractor disabled, skipping")
            return None

        # Truncate if too long
        if len(markdown) > MAX_MARKDOWN_LENGTH:
            markdown = markdown[:MAX_MARKDOWN_LENGTH]
            self.logger.debug(f"Truncated page {page_id} to {MAX_MARKDOWN_LENGTH} chars")

        self._wait_for_rate_limit()

        try:
            response = self.model.generate_content(
                AI_EXTRACT_PROMPT + "\n\n---\n" + markdown
            )

            result = self._parse_json_response(response.text)

            # Validate result
            if not any(
                result.get(field)
                for field in ["phone", "email", "address", "representative"]
            ):
                return None

            return {
                "phone": result.get("phone"),
                "email": result.get("email"),
                "address": result.get("address"),
                "representative": result.get("representative"),
                "fax": result.get("fax"),
                "confidence": float(result.get("confidence", 0.5)),
                "raw_ai_response": response.text[:500],
            }

        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "rate" in error_msg:
                raise RetryableError(f"AI Extract rate limited: {e}") from e
            if "402" in error_msg or "quota" in error_msg:
                raise CriticalError(f"AI Extract quota exhausted: {e}") from e

            self.logger.error(f"AI Extract error for page {page_id}: {e}")
            return None

    def extract_for_company(self, company_id: int, delay: float = None) -> List[Dict]:
        """Extract contact info from all scraped pages of a company.

        Args:
            company_id: The company ID.
            delay: Delay between API calls.

        Returns:
            List of extracted contact dicts.
        """
        # Get successful scraped pages
        pages = self.db.get_scraped_pages_for_company(company_id)
        success_pages = [p for p in pages if p.get("scrape_status") == "success"]

        if not success_pages:
            self.logger.info(f"[{company_id}] No scraped pages to extract from")
            return []

        # Sort by priority: legal first, social last
        def sort_key(page):
            source = page.get("source_type", "unknown")
            return SOURCE_TYPE_PRIORITY.get(source, 99)

        success_pages.sort(key=sort_key)

        self.logger.info(
            f"[{company_id}] Extracting from {len(success_pages)} pages"
        )

        all_contacts = []
        for page in success_pages:
            page_id = page["id"]
            url = page.get("url", "")

            # Regex pre-filter
            markdown = page.get("markdown_content", "")
            if not markdown or not self._has_phone_pattern(markdown):
                continue

            try:
                result = self.extract_from_page(page_id)
                if result:
                    contact_id = self.db.insert_extracted_contact(
                        company_id=company_id,
                        source_type=page.get("source_type", ""),
                        source_url=url,
                        phone=result.get("phone"),
                        email=result.get("email"),
                        address=result.get("address"),
                        website=None,
                        fax=result.get("fax"),
                        representative=result.get("representative"),
                        raw_ai_response=result.get("raw_ai_response", ""),
                        confidence_score=result.get("confidence", 0.5),
                    )
                    result["id"] = contact_id
                    all_contacts.append(result)
                    self.logger.info(
                        f"[{company_id}] Extracted contact from {url}"
                    )
            except CriticalError:
                raise
            except Exception as e:
                self.logger.error(
                    f"[{company_id}] Extract error for page {page_id}: {e}"
                )

        # Resolve conflicts: keep highest confidence for each field
        resolved = self._resolve_conflicts(all_contacts)

        self.logger.info(
            f"[{company_id}] Extracted {len(resolved)} contacts "
            f"(from {len(all_contacts)} raw)"
        )

        return resolved

    def _resolve_conflicts(self, contacts: List[Dict]) -> List[Dict]:
        """Resolve conflicts between multiple contacts.

        Keep the highest confidence value for each field.
        """
        if not contacts:
            return []

        # Sort by confidence descending
        contacts.sort(key=lambda x: x.get("confidence", 0), reverse=True)

        # Take the best contact as base
        best = contacts[0]

        # For each field, take the highest confidence source
        resolved = {
            "phone": best.get("phone"),
            "email": best.get("email"),
            "address": best.get("address"),
            "representative": best.get("representative"),
            "fax": best.get("fax"),
            "confidence": best.get("confidence", 0),
        }

        for contact in contacts[1:]:
            for field in ["phone", "email", "address", "representative", "fax"]:
                if not resolved.get(field) and contact.get(field):
                    resolved[field] = contact[field]

        return [resolved]
