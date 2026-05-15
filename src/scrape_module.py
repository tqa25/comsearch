"""Step 5.1: Firecrawl web scraping module."""

import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional

import requests

from src.config import default_config
from src.database import DatabaseManager
from src.errors import CriticalError, RetryableError, SkippableError

logger = logging.getLogger(__name__)

_FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"
_MAX_RETRIES = 3
_RETRY_BACKOFF_429 = 60
_RETRY_BACKOFF_NETWORK = 5


class ScrapeModule:
    """Step 5.1: Scrape top N URLs using Firecrawl API.

    Fetches filtered_links from DB, calls Firecrawl Scrape API for each URL,
    and stores markdown content into scraped_pages table.
    """

    def __init__(self, db: DatabaseManager, logger, config=None):
        """Initialize ScrapeModule.

        Args:
            db: DatabaseManager instance.
            logger: Logger instance.
            config: Optional Config override.
        """
        self.config = config or default_config
        self.db = db
        self.logger = logger or logging.getLogger(__name__)

        self.api_key = os.getenv("FIRECRAWL_API_KEY")
        if not self.api_key:
            self.logger.warning("FIRECRAWL_API_KEY not set. ScrapeModule will skip.")

        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def scrape_company(self, company_id: int, delay: float = 3.0) -> List[Dict]:
        """Scrape top N URLs (by relevance_score) for a company.

        1. Fetches filtered_links from DB (should_scrape=1, ordered by relevance_score DESC)
        2. Takes top N links (config.TOP_N, default 10)
        3. Calls Firecrawl Scrape API for each URL
        4. Stores markdown content into scraped_pages table

        Args:
            company_id: The company ID to scrape.
            delay: Seconds to wait between requests.

        Returns:
            List of dicts with scrape results.

        Raises:
            CriticalError: If credits exhausted (402).
        """
        if not self.api_key:
            self.logger.warning(f"[{company_id}] FIRECRAWL_API_KEY not configured")
            return []

        top_n = self.config.TOP_N
        links = self.db.get_top_filtered_links(company_id, limit=top_n)

        if not links:
            self.logger.info(f"[{company_id}] No filtered links to scrape")
            return []

        self.logger.info(
            f"[{company_id}] Scraping up to {len(links)} URLs "
            f"(TOP_N={top_n})"
        )

        results = []
        for link in links:
            url = link.get("url", "")
            source_type = link.get("source_type", "")
            link_id = link.get("id")

            self.logger.info(f"[{company_id}] Scraping: {url}")

            result = self._scrape_single_url(
                company_id=company_id,
                url=url,
                source_type=source_type,
                filtered_link_id=link_id,
            )

            if result:
                results.append(result)

            time.sleep(delay)

        self.logger.info(
            f"[{company_id}] Scraped {len(results)}/{len(links)} URLs successfully"
        )
        return results

    def discover_contact_pages(
        self, company_id: int, delay: float = 3.0
    ) -> List[Dict]:
        """Discover additional contact pages from the company's main website.

        If a main website is available, tries scraping:
        - /contact, /lien-he, /about

        Args:
            company_id: The company ID to discover pages for.
            delay: Seconds to wait between requests.

        Returns:
            List of dicts with scrape results.
        """
        if not self.config.CONTACT_DISCOVERY_ENABLED:
            return []

        company = self.db.get_company(company_id)
        if not company:
            return []

        existing_links = self.db.get_top_filtered_links(company_id, limit=1)
        if not existing_links:
            return []

        main_url = existing_links[0].get("url", "")
        if not main_url:
            return []

        parsed = self._parse_base_url(main_url)
        if not parsed:
            return []

        contact_paths = ["/contact", "/lien-he", "/about"]
        results = []

        for path in contact_paths:
            full_url = f"{parsed}{path}"
            self.logger.info(
                f"[{company_id}] Discovering contact page: {full_url}"
            )

            result = self._scrape_single_url(
                company_id=company_id,
                url=full_url,
                source_type="contact_discovery",
                filtered_link_id=None,
            )

            if result:
                results.append(result)

            time.sleep(delay)

        return results

    def _scrape_single_url(
        self,
        company_id: int,
        url: str,
        source_type: str,
        filtered_link_id: Optional[int] = None,
    ) -> Optional[Dict]:
        """Scrape a single URL via Firecrawl API and store the result.

        Args:
            company_id: The company ID.
            url: The URL to scrape.
            source_type: The source type label.
            filtered_link_id: Optional FK to filtered_links.

        Returns:
            Dict with scrape result, or None if failed.
        """
        payload = {
            "url": url,
            "formats": ["markdown"],
            "timeout": 30000,
        }

        start_time = time.time()
        response_data = self._call_with_retry(payload, company_id)

        elapsed_ms = (time.time() - start_time) * 1000
        success = response_data is not None

        if success:
            markdown = response_data.get("data", {}).get("markdown", "")
            content_length = len(markdown) if markdown else 0

            self.db.insert_scraped_page(
                company_id=company_id,
                filtered_link_id=filtered_link_id,
                url=url,
                source_type=source_type,
                markdown_content=markdown,
                content_length=content_length,
                scrape_status="success",
            )

            self.logger.info(
                f"[{company_id}] Scraped {url} "
                f"({content_length} chars)"
            )

            return {
                "url": url,
                "status": "success",
                "content_length": content_length,
            }
        else:
            self.db.insert_scraped_page(
                company_id=company_id,
                filtered_link_id=filtered_link_id,
                url=url,
                source_type=source_type,
                markdown_content=None,
                content_length=0,
                scrape_status="failed",
            )

            self.logger.warning(f"[{company_id}] Failed to scrape {url}")

            return None

    def _call_with_retry(
        self, payload: dict, company_id: int
    ) -> Optional[Dict]:
        """Call Firecrawl API with retry logic.

        Args:
            payload: Request payload.
            company_id: The company ID for logging.

        Returns:
            Response dict, or None if all retries failed.

        Raises:
            CriticalError: If HTTP 402 (credits exhausted).
        """
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = self._session.post(
                    _FIRECRAWL_SCRAPE_URL,
                    json=payload,
                    timeout=35,
                )

                if resp.status_code == 200:
                    return resp.json()

                if resp.status_code == 402:
                    body = resp.text
                    raise CriticalError(
                        f"Firecrawl credits exhausted (402): {body}"
                    )

                if resp.status_code == 429:
                    if attempt < _MAX_RETRIES:
                        wait = _RETRY_BACKOFF_429 * attempt
                        self.logger.warning(
                            f"[{company_id}] Firecrawl rate limited (429). "
                            f"Waiting {wait}s (attempt {attempt}/{_MAX_RETRIES})"
                        )
                        time.sleep(wait)
                    else:
                        raise RetryableError(
                            f"Firecrawl rate limited after {_MAX_RETRIES} retries"
                        )

                elif resp.status_code == 403:
                    self.logger.warning(
                        f"[{company_id}] Firecrawl forbidden (403): {url}"
                    )
                    return None

                elif resp.status_code >= 500:
                    if attempt < _MAX_RETRIES:
                        self.logger.warning(
                            f"[{company_id}] Firecrawl server error "
                            f"({resp.status_code}), retrying "
                            f"({attempt}/{_MAX_RETRIES})"
                        )
                        time.sleep(_RETRY_BACKOFF_NETWORK)
                    else:
                        raise RetryableError(
                            f"Firecrawl server error after {_MAX_RETRIES} retries: "
                            f"{resp.status_code}"
                        )

                else:
                    self.logger.warning(
                        f"[{company_id}] Firecrawl unexpected status "
                        f"{resp.status_code}: {resp.text[:200]}"
                    )
                    return None

            except requests.Timeout:
                if attempt < _MAX_RETRIES:
                    self.logger.warning(
                        f"[{company_id}] Firecrawl timeout, retrying "
                        f"({attempt}/{_MAX_RETRIES})"
                    )
                    time.sleep(_RETRY_BACKOFF_NETWORK)
                else:
                    raise RetryableError(
                        f"Firecrawl timeout after {_MAX_RETRIES} retries"
                    )

            except requests.RequestException as e:
                if attempt < _MAX_RETRIES:
                    self.logger.warning(
                        f"[{company_id}] Firecrawl network error: {e}, "
                        f"retrying ({attempt}/{_MAX_RETRIES})"
                    )
                    time.sleep(_RETRY_BACKOFF_NETWORK)
                else:
                    raise RetryableError(
                        f"Firecrawl network error after {_MAX_RETRIES} retries: {e}"
                    )

        return None

    def _parse_base_url(self, url: str) -> Optional[str]:
        """Extract base URL (scheme + host) from a full URL.

        Args:
            url: Full URL string.

        Returns:
            Base URL like 'https://example.com', or None if parsing fails.
        """
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"
            return None
        except Exception:
            return None
