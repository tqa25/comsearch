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
Trích xuất thông tin liên hệ của công ty từ nội dung sau. Trả về JSON, KHÔNG thêm text ngoài JSON:
{{
  "phone": "số điện thoại thực tế",
  "email": "email thực tế",
  "address": "địa chỉ thực tế",
  "representative": "người đại diện",
  "fax": "số fax",
  "confidence": 0.0
}}
QUAN TRỌNG:
- Nếu không tìm thấy thông tin thực tế, để null — KHÔNG dùng placeholder như "phone number", "email", "N/A", "unknown", "not found"
- Chỉ trích xuất giá trị thực (số điện thoại thật, email thật)
- Không bịa thông tin, không dùng tên field làm giá trị
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
        """Parse JSON from AI response text, handling markdown and trailing text.

        Args:
            text: Raw AI response text.

        Returns:
            Parsed dict from JSON.

        Raises:
            json.JSONDecodeError: If no valid JSON is found.
        """
        text = text.strip()

        # Strip markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Find JSON object by counting braces (handle string escapes)
        start = text.find("{")
        if start >= 0:
            depth = 0
            end = start
            in_string = False
            escape_next = False
            for i in range(start, len(text)):
                ch = text[i]
                if escape_next:
                    escape_next = False
                    continue
                if ch == '\\':
                    escape_next = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
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

    def _validate_extracted_value(self, value) -> Optional[str]:
        """Reject placeholder/fake values from AI response.

        Args:
            value: Raw value from AI response.

        Returns:
            Cleaned string value, or None if placeholder/empty.
        """
        if not value:
            return None
        if not isinstance(value, str):
            return str(value) if value else None
        stripped = value.strip()
        if not stripped:
            return None
        placeholders = {
            "phone number", "email", "n/a", "unknown", "null", "none",
            "not found", "not available", "contact us", "see website",
            "phone", "address", "fax", "representative",
        }
        if stripped.lower() in placeholders:
            return None
        return stripped

    def extract_from_page(
        self, company_id: int, page: dict, max_retries: int = 2
    ) -> Optional[Dict]:
        """Extract contact info from a single scraped page.

        Args:
            company_id: The company ID.
            page: The scraped page dict (already loaded, no need to query DB).
            max_retries: Max retry attempts for 500 errors.

        Returns:
            Dict with extracted contact info, or None.
        """
        markdown = page.get("markdown_content", "")
        page_id = page.get("id")
        url = page.get("url", "")

        if not markdown:
            return None

        # Regex pre-filter
        if not self._has_phone_pattern(markdown):
            self.logger.debug(
                f"[{company_id}] Page {page_id} has no phone pattern, skipping AI"
            )
            return None

        if not self.enabled or self.model is None:
            self.logger.warning("AIExtractor disabled, skipping")
            return None

        # Truncate if too long
        if len(markdown) > MAX_MARKDOWN_LENGTH:
            markdown = markdown[:MAX_MARKDOWN_LENGTH]
            self.logger.debug(
                f"[{company_id}] Truncated page {page_id} to "
                f"{MAX_MARKDOWN_LENGTH} chars"
            )

        for attempt in range(max_retries + 1):
            self._wait_for_rate_limit()

            try:
                response = self.model.generate_content(
                    AI_EXTRACT_PROMPT + "\n\n---\n" + markdown
                )

                result = self._parse_json_response(response.text)

                # Validate — reject placeholder values
                if not any(
                    self._validate_extracted_value(result.get(field))
                    for field in ["phone", "email", "address", "representative"]
                ):
                    return None

                return {
                    "phone": self._validate_extracted_value(result.get("phone")),
                    "email": self._validate_extracted_value(result.get("email")),
                    "address": self._validate_extracted_value(result.get("address")),
                    "representative": self._validate_extracted_value(
                        result.get("representative")
                    ),
                    "fax": self._validate_extracted_value(result.get("fax")),
                    "confidence": float(result.get("confidence", 0.5)),
                    "raw_ai_response": response.text[:500],
                }

            except Exception as e:
                error_msg = str(e).lower()
                if "429" in error_msg or "rate" in error_msg:
                    raise RetryableError(
                        f"AI Extract rate limited: {e}"
                    ) from e
                if "402" in error_msg:
                    raise CriticalError(
                        f"AI Extract credits exhausted: {e}"
                    ) from e

                # Retry on 500/internal errors
                if (
                    ("500" in error_msg or "internal" in error_msg)
                    and attempt < max_retries
                ):
                    wait = 2 ** attempt  # 1s, 2s
                    self.logger.warning(
                        f"[{company_id}] AI Extract 500 error for page {page_id}, "
                        f"retry {attempt + 1}/{max_retries} in {wait}s"
                    )
                    time.sleep(wait)
                    continue

                self.logger.error(
                    f"[{company_id}] AI Extract error for page {page_id}: {e}"
                )
                return None

    def extract_for_company(self, company_id: int, delay: float = None) -> List[Dict]:
        """Extract contact info from all scraped pages of a company.

        Args:
            company_id: The company ID.
            delay: Delay between API calls.

        Returns:
            List of ALL extracted contact dicts (one per source URL, no merge).
        """
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

        # Track already-extracted URLs to avoid duplicates
        existing_contacts = self.db.get_extracted_contacts_for_company(company_id)
        extracted_urls = {
            c["source_url"] for c in existing_contacts if c.get("source_url")
        }

        self.logger.info(
            f"[{company_id}] Extracting from {len(success_pages)} pages"
        )

        all_contacts = []
        for page in success_pages:
            url = page.get("url", "")

            # Skip if already extracted from this URL
            if url in extracted_urls:
                self.logger.debug(
                    f"[{company_id}] Skipping already-extracted URL: {url}"
                )
                continue

            # Regex pre-filter (check before calling AI)
            markdown = page.get("markdown_content", "")
            if not markdown or not self._has_phone_pattern(markdown):
                continue

            try:
                result = self.extract_from_page(company_id, page)
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
                    result["source_url"] = url  # Track URL for dedup
                    all_contacts.append(result)
                    extracted_urls.add(url)  # Add to set immediately
                    self.logger.info(
                        f"[{company_id}] Extracted contact from {url}"
                    )
            except CriticalError:
                raise
            except Exception as e:
                self.logger.error(
                    f"[{company_id}] Extract error for page {page.get('id')}: {e}"
                )

        # Return ALL contacts — no merge
        self.logger.info(
            f"[{company_id}] Extracted {len(all_contacts)} contacts "
            f"from {len(success_pages)} pages"
        )

        return all_contacts
