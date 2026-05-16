import logging
import time
from typing import Dict, List, Optional

import requests

from src.config import default_config
from src.database import DatabaseManager
from src.errors import CriticalError, RetryableError

logger = logging.getLogger(__name__)

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"

CONTACT_PATHS = ["/contact", "/lien-he", "/lienhe", "/about", "/about-us", "/gioi-thieu"]


class ScrapeModule:
    """Bước 5.1: Scrape web pages using Firecrawl API."""

    def __init__(
        self,
        db: DatabaseManager,
        logger: logging.Logger = None,
        config=None,
    ):
        self.config = config or default_config
        self.db = db
        self.logger = logger or logging.getLogger(__name__)
        self._api_key = self._get_firecrawl_api_key()
        self._session = requests.Session()
        self._last_request_time: float = 0

    def _get_firecrawl_api_key(self) -> Optional[str]:
        import os
        return os.getenv("FIRECRAWL_API_KEY")

    def _wait(self, delay: float):
        """Wait between API calls."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request_time = time.time()

    def _scrape_url(self, url: str, timeout: int = 35000) -> Optional[str]:
        """Scrape a single URL and return markdown content.

        Args:
            url: URL to scrape.
            timeout: Timeout in milliseconds.

        Returns:
            Markdown content string, or None on failure.

        Raises:
            RetryableError: If rate limited.
            CriticalError: If credits exhausted.
        """
        if not self._api_key:
            self.logger.warning("FIRECRAWL_API_KEY not set")
            return None

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "url": url,
            "formats": ["markdown"],
            "timeout": timeout,
        }

        self._wait(self.config.DELAY_SECONDS)

        try:
            response = self._session.post(
                FIRECRAWL_SCRAPE_URL,
                json=payload,
                headers=headers,
                timeout=35,
            )

            if response.status_code == 402:
                raise CriticalError(
                    "Firecrawl credits exhausted. STOP immediately."
                )
            if response.status_code == 429:
                raise RetryableError("Firecrawl rate limited")
            if response.status_code != 200:
                self.logger.error(
                    f"Firecrawl error {response.status_code}: {response.text[:200]}"
                )
                return None

            data = response.json()
            markdown = data.get("data", {}).get("markdown", "")
            return markdown if markdown else None

        except (CriticalError, RetryableError):
            raise
        except requests.RequestException as e:
            self.logger.error(f"Firecrawl network error for {url}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Firecrawl unexpected error: {e}")
            return None

    def scrape_company(
        self, company_id: int, delay: float = None
    ) -> List[Dict]:
        """Scrape top N URLs for a company.

        Args:
            company_id: The company ID.
            delay: Delay between requests (uses config default if None).

        Returns:
            List of scraped page dicts.
        """
        if delay is None:
            delay = self.config.DELAY_SECONDS

        # Get filtered links ordered by score
        links = self.db.get_filtered_links_for_company(
            company_id, should_scrape=True
        )
        if not links:
            self.logger.info(f"[{company_id}] No scrapeable links found")
            return []

        # Sort by relevance_score descending, take top N
        links.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        top_links = links[: self.config.TOP_N]

        self.logger.info(
            f"[{company_id}] Scraping {len(top_links)} URLs (top {self.config.TOP_N})"
        )

        scraped_pages = []
        for link in top_links:
            url = link["url"]
            self.logger.debug(f"[{company_id}] Scraping: {url}")

            try:
                markdown = self._scrape_url(url)

                if markdown:
                    page_id = self.db.insert_scraped_page(
                        company_id=company_id,
                        url=url,
                        filtered_link_id=link.get("id"),
                        source_type=link.get("source_type", ""),
                        markdown_content=markdown,
                        content_length=len(markdown),
                        scrape_status="success",
                    )
                    scraped_pages.append({
                        "id": page_id,
                        "url": url,
                        "content_length": len(markdown),
                        "source_type": link.get("source_type", ""),
                    })
                else:
                    page_id = self.db.insert_scraped_page(
                        company_id=company_id,
                        url=url,
                        filtered_link_id=link.get("id"),
                        source_type=link.get("source_type", ""),
                        markdown_content="",
                        content_length=0,
                        scrape_status="failed",
                    )

            except CriticalError:
                self.logger.error(
                    f"[{company_id}] Critical error, stopping scrape"
                )
                raise
            except RetryableError:
                self.logger.warning(
                    f"[{company_id}] Rate limited, retrying with backoff"
                )
                # Retry once with longer delay
                time.sleep(60)
                try:
                    markdown = self._scrape_url(url)
                    if markdown:
                        page_id = self.db.insert_scraped_page(
                            company_id=company_id,
                            url=url,
                            filtered_link_id=link.get("id"),
                            source_type=link.get("source_type", ""),
                            markdown_content=markdown,
                            content_length=len(markdown),
                            scrape_status="success",
                        )
                        scraped_pages.append({
                            "id": page_id,
                            "url": url,
                            "content_length": len(markdown),
                            "source_type": link.get("source_type", ""),
                        })
                except Exception:
                    pass
            except Exception as e:
                self.logger.error(f"[{company_id}] Scrape error: {e}")

        self.logger.info(
            f"[{company_id}] Scraped {len(scraped_pages)}/{len(top_links)} pages"
        )
        return scraped_pages

    def discover_contact_pages(
        self, company_id: int, website: str, delay: float = None
    ) -> List[Dict]:
        """Discover additional contact pages from main website.

        Args:
            company_id: The company ID.
            website: Main website URL.
            delay: Delay between requests.

        Returns:
            List of newly scraped contact pages.
        """
        if not self.config.CONTACT_DISCOVERY_ENABLED:
            return []

        if not website:
            return []

        if delay is None:
            delay = self.config.DELAY_SECONDS

        # Build contact page URLs
        from urllib.parse import urlparse

        parsed = urlparse(website)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        contact_urls = [f"{base_url}{path}" for path in CONTACT_PATHS]

        new_pages = []
        for url in contact_urls:
            try:
                markdown = self._scrape_url(url)
                if markdown:
                    page_id = self.db.insert_scraped_page(
                        company_id=company_id,
                        url=url,
                        source_type="contact_discovery",
                        markdown_content=markdown,
                        content_length=len(markdown),
                        scrape_status="success",
                    )
                    new_pages.append({
                        "id": page_id,
                        "url": url,
                        "content_length": len(markdown),
                    })
            except CriticalError:
                raise
            except Exception as e:
                self.logger.debug(f"Contact discovery failed for {url}: {e}")

        if new_pages:
            self.logger.info(
                f"[{company_id}] Discovered {len(new_pages)} contact pages"
            )

        return new_pages
