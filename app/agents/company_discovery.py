from __future__ import annotations
import logging
import uuid
from urllib.parse import urlparse

from app.providers.base import SearchProvider
from app.models.lead import CompanyCandidate


class CompanyDiscoveryAgent:
    def __init__(self, providers: list[SearchProvider], config: dict = None):
        self.providers = providers
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

    def discover(self, limit: int = None) -> list[CompanyCandidate]:
        all_candidates: list[CompanyCandidate] = []

        for provider in self.providers:
            try:
                candidates = provider.get_candidates()
                all_candidates.extend(candidates)
            except Exception as e:
                self.logger.error(f"Provider {provider.__class__.__name__} failed: {e}")

        # Deduplicate by homepage_url (if set) then by company_name
        seen_urls: set[str] = set()
        seen_names: set[str] = set()
        deduplicated: list[CompanyCandidate] = []
        for candidate in all_candidates:
            url_key = candidate.homepage_url.strip().lower().rstrip("/")
            name_key = candidate.company_name.strip().lower()
            if url_key and url_key in seen_urls:
                continue
            if not url_key and name_key in seen_names:
                continue
            if url_key:
                seen_urls.add(url_key)
            seen_names.add(name_key)
            deduplicated.append(candidate)

        # Filter blocked/excluded
        filtered = [c for c in deduplicated if not self._is_blocked(c)]

        # Apply limit
        if limit is not None:
            filtered = filtered[:limit]

        self.logger.info(
            f"CompanyDiscoveryAgent: {len(all_candidates)} raw candidates, "
            f"{len(deduplicated)} after dedup, {len(filtered)} after filtering, "
            f"limit={limit}"
        )
        return filtered

    def _is_blocked(self, candidate: CompanyCandidate) -> bool:
        blocked_domains = self.config.get("blocked_domains", [])
        excluded_keywords = self.config.get("excluded_keywords", [])

        # Check blocked domains against homepage_url
        if candidate.homepage_url and blocked_domains:
            parsed = urlparse(candidate.homepage_url)
            host = parsed.netloc.lower().lstrip("www.")
            for domain in blocked_domains:
                if domain.lower() in host:
                    return True

        # Check excluded keywords against company_name and notes
        if excluded_keywords:
            text_to_check = (candidate.company_name + " " + candidate.notes).lower()
            for keyword in excluded_keywords:
                if keyword.lower() in text_to_check:
                    return True

        return False
