import logging
import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional
from urllib.parse import urlparse

from src.config import default_config
from src.database import DatabaseManager

logger = logging.getLogger(__name__)


# ── Domain Classifications ──

BLACKLISTED_DOMAINS = [
    "infocom.vn", "xinvoice.vn", "dauthau.info",
    "dauthau.net", "thuonghieuviet.info.vn", "fiingate.vn",
]

SKIP_DOMAINS = [
    "google.com", "youtube.com", "wikipedia.org", "baomoi.com",
    "vnexpress.net", "bing.com", "twitter.com", "tiktok.com",
    "pinterest.com", "amazon.com", "shopee.vn", "lazada.vn",
]

KNOWN_DOMAINS = {
    "thuvienphapluat.vn":  ("thuvienphapluat", "legal"),
    "hosocongty.vn":       ("hosocongty",       "legal"),
    "masothue.com":        ("masothue",         "legal"),
    "yellowpages.vn":      ("yellowpages",      "official"),
    "vietnamworks.com":    ("vietnamworks",     "job"),
    "topcv.vn":            ("topcv",            "job"),
    "vietcareer.vn":       ("vietcareer",       "job"),
    "jobsgo.vn":           ("jobsgo",           "job"),
    "facebook.com":        ("facebook",         "social"),
    "linkedin.com":        ("linkedin",         "social"),
}

# Stop words to remove when comparing company names
STOP_WORDS = [
    "company", "limited", "joint", "stock", "co", "ltd",
    "cong", "ty", "tnhh", "cp", "co", "ltd", "jsc",
    "the", "and", "for", "of",
]


class LinkFilter:
    """Score and filter URLs based on relevance to a company."""

    def __init__(
        self,
        db: DatabaseManager,
        logger: logging.Logger = None,
        config=None,
    ):
        self.config = config or default_config
        self.db = db
        self.logger = logger or logging.getLogger(__name__)

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    def _get_tld(self, domain: str) -> str:
        """Extract TLD from domain."""
        parts = domain.split(".")
        if len(parts) >= 3 and parts[-2] in ("com", "net", "org"):
            return "." + parts[-2] + "." + parts[-1]
        if len(parts) >= 2:
            return "." + parts[-1]
        return ""

    def _normalize_name(self, name: str) -> str:
        """Normalize company name for comparison."""
        if not name:
            return ""
        name = name.lower().strip()
        # Remove Vietnamese diacritics (basic)
        import unicodedata
        name = unicodedata.normalize("NFD", name)
        name = "".join(c for c in name if unicodedata.category(c) != "Mn")
        # Remove stop words
        words = name.split()
        words = [w for w in words if w not in STOP_WORDS]
        return " ".join(words)

    def _calculate_name_match_score(
        self, name: str, text: str
    ) -> float:
        """Calculate fuzzy name match score (0-20 points)."""
        if not name or not text:
            return 0.0

        norm_name = self._normalize_name(name)
        norm_text = self._normalize_name(text)

        if not norm_name or not norm_text:
            return 0.0

        # Sliding window comparison
        name_len = len(norm_name)
        if name_len < 3:
            return 0.0

        best_ratio = 0.0
        text_words = norm_text.split()

        # Try matching against individual words and phrases
        for window_size in range(1, min(5, len(text_words) + 1)):
            for i in range(len(text_words) - window_size + 1):
                window = " ".join(text_words[i:i + window_size])
                ratio = SequenceMatcher(
                    None, norm_name, window
                ).ratio()
                best_ratio = max(best_ratio, ratio)

        # Convert ratio to bonus (0-20 points, linear from 80%)
        if best_ratio >= 0.80:
            bonus = (best_ratio - 0.80) / 0.20 * 20.0
            return round(bonus, 1)
        return 0.0

    def _get_keyword_bonus(self, url_path: str) -> int:
        """Calculate keyword bonus from URL path."""
        path_lower = url_path.lower()
        bonus = 0
        keyword_scores = self.config.KEYWORD_SCORES
        for keyword, score in keyword_scores.items():
            if keyword.lower() in path_lower:
                bonus += score
        return bonus

    def _get_tld_bonus(self, domain: str) -> int:
        """Calculate TLD bonus."""
        tld = self._get_tld(domain)
        tld_scores = self.config.TLD_SCORES
        return tld_scores.get(tld, 0)

    def classify_url(
        self,
        url: str,
        company_name: str,
        title: str = "",
        vn_name: str = "",
    ) -> dict:
        """Score a single URL.

        Args:
            url: The URL to classify.
            company_name: English company name.
            title: Page title (optional).
            vn_name: Vietnamese company name (optional).

        Returns:
            Dict with source_type, should_scrape, reason, relevance_score, score_breakdown.
        """
        domain = self._get_domain(url)
        parsed = urlparse(url)
        path = parsed.path

        score_breakdown = {}
        source_type = "unknown"
        reason = ""

        # ── Check blacklist ──
        for bl in BLACKLISTED_DOMAINS:
            if bl in domain:
                return {
                    "source_type": "blacklisted",
                    "should_scrape": False,
                    "reason": f"Blacklisted domain: {bl}",
                    "relevance_score": 0,
                    "score_breakdown": {"blacklisted": 0},
                }

        # ── Check skip list ──
        for sk in SKIP_DOMAINS:
            if sk in domain:
                return {
                    "source_type": "skipped",
                    "should_scrape": False,
                    "reason": f"Skipped domain: {sk}",
                    "relevance_score": 0,
                    "score_breakdown": {"skipped": 0},
                }

        # ── Check known domains ──
        if domain in KNOWN_DOMAINS:
            source_type = KNOWN_DOMAINS[domain][1]
            domain_scores = self.config.DOMAIN_SCORES
            domain_score = domain_scores.get(source_type, 0)
            score_breakdown["domain"] = domain_score

            if source_type == "social":
                return {
                    "source_type": source_type,
                    "should_scrape": False,
                    "reason": f"Social media: {domain}",
                    "relevance_score": domain_score,
                    "score_breakdown": score_breakdown,
                }
        else:
            # Default: official website
            source_type = "official"
            domain_scores = self.config.DOMAIN_SCORES
            domain_score = domain_scores.get("official", 15)
            score_breakdown["domain"] = domain_score

        # ── TLD Bonus ──
        tld_bonus = self._get_tld_bonus(domain)
        if tld_bonus > 0:
            score_breakdown["tld"] = tld_bonus

        # ── Keyword Bonus ──
        keyword_bonus = self._get_keyword_bonus(path)
        if keyword_bonus > 0:
            score_breakdown["keyword"] = keyword_bonus

        # ── Name Match Bonus ──
        name_match = 0
        name_match = max(
            self._calculate_name_match_score(company_name, domain),
            self._calculate_name_match_score(vn_name, domain),
            self._calculate_name_match_score(company_name, title),
            self._calculate_name_match_score(vn_name, title),
        )
        if name_match > 0:
            score_breakdown["name_match"] = name_match

        # ── Total Score ──
        total = sum(score_breakdown.values())

        should_scrape = total > 0 and source_type != "social"

        return {
            "source_type": source_type,
            "should_scrape": should_scrape,
            "reason": reason or f"Score: {total}",
            "relevance_score": total,
            "score_breakdown": score_breakdown,
        }

    def score_urls_batch(
        self,
        urls: List[Dict],
        company_name: str,
        vn_name: str = "",
    ) -> List[Dict]:
        """Score a batch of URLs without saving to DB.

        Args:
            urls: List of dicts with 'url', 'title', 'snippet'.
            company_name: English company name.
            vn_name: Vietnamese company name.

        Returns:
            List of scored URL dicts.
        """
        results = []
        seen_domains = set()

        for url_data in urls:
            url = url_data.get("url", "")
            if not url:
                continue

            domain = self._get_domain(url)

            # Dedup by domain
            if domain in seen_domains:
                continue
            seen_domains.add(domain)

            scored = self.classify_url(
                url=url,
                company_name=company_name,
                title=url_data.get("title", ""),
                vn_name=vn_name,
            )
            scored["url"] = url
            scored["title"] = url_data.get("title", "")
            scored["snippet"] = url_data.get("snippet", "")
            results.append(scored)

        return results

    def filter_company_links(self, company_id: int) -> List[Dict]:
        """Classify, score, persist, and return filtered links for a company.

        Args:
            company_id: The company ID.

        Returns:
            List of scored and filtered link dicts.
        """
        company = self.db.get_company(company_id)
        if not company:
            self.logger.warning(f"Company {company_id} not found")
            return []

        company_name = company["original_name"]
        vn_name = company.get("vietnamese_name", "")

        # Get search results for this company
        search_results = self.db.get_search_results_for_company(company_id)
        if not search_results:
            return []

        # Convert to URL dicts
        url_list = [
            {
                "url": sr["url"],
                "title": sr.get("title", ""),
                "snippet": sr.get("snippet", ""),
                "search_result_id": sr["id"],
            }
            for sr in search_results
        ]

        # Score URLs
        scored = self.score_urls_batch(url_list, company_name, vn_name)

        # Persist to DB
        filtered_links = []
        for s in scored:
            link_id = self.db.insert_filtered_link(
                company_id=company_id,
                url=s["url"],
                search_result_id=s.get("search_result_id"),
                source_type=s["source_type"],
                should_scrape=s["should_scrape"],
                reason=s["reason"],
                relevance_score=s["relevance_score"],
            )
            s["id"] = link_id
            filtered_links.append(s)

        # Sort by score descending
        filtered_links.sort(key=lambda x: x["relevance_score"], reverse=True)

        self.logger.info(
            f"[{company_id}] Filtered {len(filtered_links)} links "
            f"({sum(1 for l in filtered_links if l['should_scrape'])} scrapeable)"
        )

        return filtered_links

    def check_early_stop(self, filtered_links: List[Dict]) -> bool:
        """Check if early stop condition is met.

        Args:
            filtered_links: List of scored link dicts.

        Returns:
            True if early stop should trigger.
        """
        threshold = self.config.EARLY_STOP_SCORE
        count = self.config.EARLY_STOP_COUNT

        high_score_count = sum(
            1 for link in filtered_links
            if link["relevance_score"] >= threshold and link["should_scrape"]
        )

        return high_score_count >= count
