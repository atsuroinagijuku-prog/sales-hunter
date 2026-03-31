from __future__ import annotations
import logging
import uuid
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from app.providers.base import SearchProvider
from app.models.lead import CompanyCandidate, SourceType, DiscoveryQuery

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SalesHunterBot/1.0; research purposes)"}
_DUCKDUCKGO_HOSTS = {"duckduckgo.com", "www.duckduckgo.com", "html.duckduckgo.com"}


class WebSearchProvider(SearchProvider):
    """
    Web search provider using DuckDuckGo HTML search as a free option.
    Falls back to returning empty list if search fails.
    Future: replace with Google Custom Search API or SerpAPI.
    """

    def __init__(self, queries: list[str], config: dict = None):
        self.queries = queries
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

    def get_candidates(self, limit=None) -> list[CompanyCandidate]:
        seen_urls: set[str] = set()
        candidates: list[CompanyCandidate] = []

        for query in self.queries:
            results = self._search_duckduckgo(query)
            for result in results:
                url = result.get("url", "").strip()
                title = result.get("title", "").strip()
                if not url or not title:
                    continue
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                candidate = CompanyCandidate(
                    id=str(uuid.uuid4()),
                    company_name=title,
                    homepage_url=url,
                    source_type=SourceType.WEB_SEARCH,
                    source_query=query,
                )
                candidates.append(candidate)
                if limit is not None and len(candidates) >= limit:
                    return candidates

        self.logger.info(f"WebSearchProvider found {len(candidates)} candidates across {len(self.queries)} queries")
        return candidates

    def _search_duckduckgo(self, query: str) -> list[dict]:
        try:
            resp = requests.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers=_HEADERS,
                timeout=10,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            results = []
            for a_tag in soup.find_all("a", class_="result__a"):
                href = a_tag.get("href", "")
                title = a_tag.get_text(strip=True)
                if not href or not title:
                    continue
                # Filter out DuckDuckGo's own links and ad links
                parsed = urlparse(href)
                host = parsed.netloc.lower().lstrip("www.")
                if host in _DUCKDUCKGO_HOSTS:
                    continue
                if href.startswith("/") or "duckduckgo.com" in href:
                    continue
                results.append({"title": title, "url": href})
            self.logger.debug(f"DuckDuckGo query '{query}' returned {len(results)} results")
            return results
        except Exception as e:
            self.logger.warning(f"DuckDuckGo search failed for query '{query}': {e}")
            return []

    @classmethod
    def from_file(cls, filepath: str, config: dict = None) -> "WebSearchProvider":
        with open(filepath, encoding="utf-8") as f:
            queries = [
                line.strip()
                for line in f
                if line.strip() and not line.strip().startswith("#")
            ]
        return cls(queries=queries, config=config)
