from __future__ import annotations
import logging
import uuid
from urllib.parse import urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup

from app.providers.base import SearchProvider
from app.models.lead import CompanyCandidate, SourceType, DiscoveryQuery

_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
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
            for result_div in soup.find_all("div", class_="result__body"):
                a_tag = result_div.find("a", class_="result__a")
                if not a_tag:
                    continue
                title = a_tag.get_text(strip=True)
                href = a_tag.get("href", "")
                # Extract real URL from DuckDuckGo redirect: //duckduckgo.com/l/?uddg=<encoded_url>
                real_url = ""
                if "uddg=" in href:
                    try:
                        # Normalize: //duckduckgo.com/... -> https://duckduckgo.com/...
                        normalized = href if href.startswith("http") else "https:" + href
                        qs = parse_qs(urlparse(normalized).query)
                        uddg = qs.get("uddg", [""])[0]
                        real_url = unquote(uddg)
                    except Exception:
                        pass
                if not real_url:
                    real_url = href
                if not real_url or not title:
                    continue
                if "duckduckgo.com" in real_url:
                    continue
                # Normalize to root domain URL
                parsed = urlparse(real_url)
                if parsed.scheme and parsed.netloc:
                    clean_url = f"{parsed.scheme}://{parsed.netloc}"
                else:
                    continue
                results.append({"title": title, "url": clean_url})
            self.logger.debug(f"DuckDuckGo query '{query}' returned {len(results)} results")
            return results
        except Exception as e:
            self.logger.error(f"DuckDuckGo search failed for query '{query}': {e}", exc_info=True)
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
