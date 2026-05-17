import hashlib
import logging
import re
import time
from typing import Dict, List, Optional

import requests

from src.config import default_config
from src.database import DatabaseManager
from src.errors import CriticalError, RetryableError, SkippableError
from src.filter_module import LinkFilter

logger = logging.getLogger(__name__)


class SearchModule:
    """Bước 4: Deep Search — 4-step search strategy with dedup and scoring."""

    def __init__(
        self,
        db: DatabaseManager,
        logger: logging.Logger = None,
        config=None,
    ):
        self.config = config or default_config
        self.db = db
        self.logger = logger or logging.getLogger(__name__)
        self.link_filter = LinkFilter(db, logger, config)

        self._session = requests.Session()
        self._serper_api_key = self._get_serper_api_key()
        self._last_request_time: float = 0

    def _get_serper_api_key(self) -> Optional[str]:
        import os
        return os.getenv("SERPER_API_KEY")

    def _wait_for_rate_limit(self, delay: float = 1.0):
        """Wait between API calls."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request_time = time.time()

    def _serper_search(self, query: str) -> List[Dict]:
        """Execute a Serper search query.

        Args:
            query: Search query string.

        Returns:
            List of result dicts with url, title, snippet.

        Raises:
            RetryableError: If rate limited.
            CriticalError: If credits exhausted.
        """
        if not self._serper_api_key:
            self.logger.warning("SERPER_API_KEY not set, skipping search")
            return []

        self._wait_for_rate_limit(delay=1.0)

        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": self._serper_api_key,
            "Content-Type": "application/json",
        }
        params = {
            "q": query,
            "num": self.config.SERPER_NUM_RESULTS,
            "gl": "vn",
            "hl": "vi",
        }

        try:
            response = self._session.post(
                url, json=params, headers=headers, timeout=15
            )

            if response.status_code == 402:
                raise CriticalError(
                    "Serper credits exhausted. STOP immediately."
                )
            if response.status_code == 403:
                self.logger.error(
                    f"[{company_id}] Serper API 403: Invalid API key. "
                    f"Check SERPER_API_KEY in .env"
                )
                raise SkippableError("Serper API key invalid")
            if response.status_code == 429:
                raise RetryableError("Serper rate limited")
            if response.status_code != 200:
                self.logger.error(
                    f"Serper API error {response.status_code}: "
                    f"{response.text[:200]}"
                )
                return []

            data = response.json()
            results = []
            for item in data.get("organic", []):
                results.append({
                    "url": item.get("link", ""),
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                })
            return results

        except (CriticalError, RetryableError, SkippableError):
            raise
        except requests.RequestException as e:
            self.logger.error(f"Serper network error: {e}")
            return []

    def _get_existing_urls(self, company_id: int) -> set:
        """Get all URLs already scored for this company (dedup set)."""
        existing = set()

        # From filtered_links
        links = self.db.get_filtered_links_for_company(company_id)
        for link in links:
            existing.add(link["url"])

        # From grounding_urls in search_results (Step 2)
        search_results = self.db.get_search_results_for_company(company_id)
        for sr in search_results:
            if sr.get("url"):
                existing.add(sr["url"])

        return existing

    def _step1_contact_query(
        self, company_id: int, en_name: str, vn_name: str = ""
    ) -> List[Dict]:
        """Step 4.1: Contact query — (EN OR VN) AND contact keywords."""
        queries = []
        if en_name:
            queries.append(f'"{en_name}" ("liên hệ" OR "contact")')
        if vn_name and vn_name != en_name:
            queries.append(f'"{vn_name}" ("liên hệ" OR "contact")')

        all_results = []
        for query in queries:
            # Check cache
            if self.config.ENABLE_QUERY_DEDUP:
                if self.db.is_query_cached(query):
                    self.logger.debug(f"[{company_id}] Cache hit: {query[:50]}...")
                    continue

            self.logger.info(f"[{company_id}] Step 4.1: {query[:80]}...")
            results = self._serper_search(query)

            if results:
                self.db.insert_query_cache(
                    query_text=query,
                    company_id=company_id,
                    result_count=len(results),
                )

            for r in results:
                r["search_type"] = "step1_contact"
            all_results.extend(results)

        return all_results

    def _step2_infer_vn_data(
        self, company_id: int, results: List[Dict]
    ) -> Optional[Dict]:
        """Step 4.2: Infer Vietnamese data from legal domain URLs.

        Extract company name and tax code from URLs like:
        - masothue.com/0123456789-cong-ty-abc
        - hosocongty.vn/...
        """
        tax_pattern = r"(\d{10,13})"
        company_pattern = r"cong-ty[-\w]+"

        for result in results:
            url = result.get("url", "")
            domain = ""
            try:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc.lower()
            except Exception:
                pass

            if domain in ("masothue.com", "hosocongty.vn", "thuvienphapluat.vn"):
                # Try to extract tax code
                tax_match = re.search(tax_pattern, url)
                if tax_match:
                    tax_code = tax_match.group(1)
                    self.db.update_company(
                        company_id,
                        tax_code=tax_code,
                        vn_data_source="inferred_from_url",
                    )
                    self.logger.info(
                        f"[{company_id}] Inferred tax code: {tax_code}"
                    )
                    return {"tax_code": tax_code}

        return None

    def _step3_tax_query(
        self, company_id: int, tax_code: str
    ) -> List[Dict]:
        """Step 4.3: Tax code query — search by MST."""
        if not tax_code:
            return []

        query = f'"{tax_code}"'

        # Check cache
        if self.config.ENABLE_QUERY_DEDUP:
            if self.db.is_query_cached(query):
                self.logger.debug(f"[{company_id}] Cache hit: {query}")
                return []

        self.logger.info(f"[{company_id}] Step 4.3: {query}")
        results = self._serper_search(query)

        if results:
            self.db.insert_query_cache(
                query_text=query,
                company_id=company_id,
                result_count=len(results),
            )

        for r in results:
            r["search_type"] = "step3_tax"

        return results

    def _step4_bare_query(
        self, company_id: int, en_name: str, vn_name: str = ""
    ) -> List[Dict]:
        """Step 4.4: Bare query — EN OR VN (last resort)."""
        queries = []
        if en_name:
            queries.append(f'"{en_name}"')
        if vn_name and vn_name != en_name:
            queries.append(f'"{vn_name}"')

        all_results = []
        for query in queries:
            # Check cache
            if self.config.ENABLE_QUERY_DEDUP:
                if self.db.is_query_cached(query):
                    self.logger.debug(f"[{company_id}] Cache hit: {query[:50]}...")
                    continue

            self.logger.info(f"[{company_id}] Step 4.4: {query[:80]}...")
            results = self._serper_search(query)

            if results:
                self.db.insert_query_cache(
                    query_text=query,
                    company_id=company_id,
                    result_count=len(results),
                )

            for r in results:
                r["search_type"] = "step4_bare"
            all_results.extend(results)

        return all_results

    def _dedupe_results(
        self, new_results: List[Dict], existing_urls: set
    ) -> List[Dict]:
        """Remove URLs already seen."""
        deduped = []
        seen = set(existing_urls)
        for r in new_results:
            url = r.get("url", "")
            if url and url not in seen:
                seen.add(url)
                deduped.append(r)
        return deduped

    def _save_search_results(
        self, company_id: int, results: List[Dict]
    ) -> None:
        """Save search results to DB."""
        for rank, r in enumerate(results, start=1):
            self.db.insert_search_result(
                company_id=company_id,
                url=r.get("url", ""),
                search_query="",
                search_type=r.get("search_type", ""),
                result_rank=rank,
                title=r.get("title", ""),
                snippet=r.get("snippet", ""),
                credits_used=1,
            )

    def search_company(
        self,
        company_id: int,
        vn_name: str = None,
        tax_code: str = None,
    ) -> List[Dict]:
        """Execute deep search strategy (4.1 → 4.2 → 4.3 → 4.4).

        Args:
            company_id: The company ID.
            vn_name: Vietnamese name (from Step 2).
            tax_code: Tax code (from Step 2).

        Returns:
            List of scored and filtered link dicts.
        """
        company = self.db.get_company(company_id)
        if not company:
            self.logger.warning(f"Company {company_id} not found")
            return []

        en_name = company["original_name"]
        if vn_name is None:
            vn_name = company.get("vietnamese_name", "")
        if tax_code is None:
            tax_code = company.get("tax_code", "")

        self.logger.info(
            f"[{company_id}] Starting deep search: EN='{en_name}', "
            f"VN='{vn_name}', MST='{tax_code}'"
        )

        existing_urls = self._get_existing_urls(company_id)
        all_scored_links = []

        # ── Step 4.1: Contact Query ──
        step1_results = self._step1_contact_query(company_id, en_name, vn_name)
        step1_deduped = self._dedupe_results(step1_results, existing_urls)
        if step1_deduped:
            self._save_search_results(company_id, step1_deduped)
            existing_urls.update(r["url"] for r in step1_deduped)

        # Score and filter
        self.db.update_company(company_id, status="searching")
        scored_links = self.link_filter.filter_company_links(company_id)
        all_scored_links.extend(scored_links)

        # Check early stop
        if self.link_filter.check_early_stop(all_scored_links):
            self.logger.info(
                f"[{company_id}] Early stop after Step 4.1 "
                f"({len(all_scored_links)} high-score links)"
            )
            return all_scored_links

        # ── Step 4.2: Infer VN Data ──
        if not vn_name or not tax_code:
            inferred = self._step2_infer_vn_data(company_id, step1_results)
            if inferred:
                if inferred.get("tax_code"):
                    tax_code = inferred["tax_code"]

        # ── Step 4.3: Tax Code Query ──
        if tax_code:
            step3_results = self._step3_tax_query(company_id, tax_code)
            step3_deduped = self._dedupe_results(step3_results, existing_urls)
            if step3_deduped:
                self._save_search_results(company_id, step3_deduped)
                existing_urls.update(r["url"] for r in step3_deduped)

            # Re-score all links (including new ones)
            scored_links = self.link_filter.filter_company_links(company_id)
            all_scored_links = scored_links

            # Check early stop
            if self.link_filter.check_early_stop(all_scored_links):
                self.logger.info(
                    f"[{company_id}] Early stop after Step 4.3 "
                    f"({len(all_scored_links)} high-score links)"
                )
                return all_scored_links

        # ── Step 4.4: Bare Query ──
        step4_results = self._step4_bare_query(company_id, en_name, vn_name)
        step4_deduped = self._dedupe_results(step4_results, existing_urls)
        if step4_deduped:
            self._save_search_results(company_id, step4_deduped)
            existing_urls.update(r["url"] for r in step4_deduped)

        # Final score and filter
        scored_links = self.link_filter.filter_company_links(company_id)
        all_scored_links = scored_links

        self.logger.info(
            f"[{company_id}] Deep search complete: "
            f"{len(all_scored_links)} filtered links"
        )

        return all_scored_links
