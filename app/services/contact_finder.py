from __future__ import annotations
import re
import logging
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.models.lead import WebsiteSnapshot, ContactInfo

EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
PHONE_PATTERN = re.compile(r'(?:0\d{1,4}[-\s]?\d{1,4}[-\s]?\d{4})')

CONTACT_URL_HINTS = ["contact", "お問い合わせ", "inquiry", "toiawase", "contact-us"]
COMPANY_URL_HINTS = ["company", "about", "会社概要", "corporate", "gaisha", "kaisha"]

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico"}


class ContactFinder:
    def __init__(self, timeout: int = 8, fetcher=None):
        self.timeout = timeout
        self.fetcher = fetcher  # WebsiteFetcher instance
        self.logger = logging.getLogger(__name__)

    def find(self, snapshot: WebsiteSnapshot) -> ContactInfo:
        if not snapshot.fetch_success:
            return ContactInfo()

        base_url = snapshot.url

        # 1. Extract emails from body text
        emails = self._extract_emails_from_text(snapshot.body_text)

        # 2. Find contact page URL from links
        all_links = [
            urljoin(base_url, href) if not href.startswith("http") else href
            for href in snapshot.links
            if href
        ]
        contact_page_url = self._find_url_by_hints(all_links, base_url, CONTACT_URL_HINTS)

        # Try common contact paths if not found via links
        if not contact_page_url:
            contact_page_url = self._probe_common_paths(base_url, CONTACT_URL_HINTS)

        # Try fetching contact page for more emails
        if contact_page_url and not emails and self.fetcher:
            try:
                contact_snapshot = self.fetcher.fetch(contact_page_url)
                if contact_snapshot.fetch_success:
                    emails.extend(self._extract_emails_from_text(contact_snapshot.body_text))
                    emails = list(dict.fromkeys(emails))  # deduplicate preserving order
            except Exception as e:
                self.logger.debug(f"Failed to fetch contact page {contact_page_url}: {e}")

        # 3. Find company page URL
        company_page_url = self._find_url_by_hints(all_links, base_url, COMPANY_URL_HINTS)

        # 4. Extract phone
        phone_numbers = PHONE_PATTERN.findall(snapshot.body_text)
        phone_number = phone_numbers[0] if phone_numbers else ""

        # 5. Pick primary email
        contact_email = emails[0] if emails else ""

        # 6. Confidence
        if contact_email:
            confidence = 0.9
        elif contact_page_url:
            confidence = 0.6
        else:
            confidence = 0.1

        return ContactInfo(
            contact_email=contact_email,
            contact_page_url=contact_page_url,
            company_page_url=company_page_url,
            phone_number=phone_number,
            extraction_confidence=confidence,
        )

    def _probe_common_paths(self, base_url: str, hints: list[str]) -> str:
        parsed = urlparse(base_url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        paths = ["/contact", "/inquiry", "/contact-us"]
        headers = {"User-Agent": "Mozilla/5.0 (compatible; SalesHunterBot/1.0; research purposes)"}
        for path in paths:
            url = root + path
            try:
                resp = requests.head(url, headers=headers, timeout=5, allow_redirects=True)
                if resp.status_code == 200:
                    return url
            except Exception:
                pass
        return ""

    def _find_url_by_hints(self, links: list[str], base_url: str, hints: list[str]) -> str:
        for link in links:
            lower_link = link.lower()
            for hint in hints:
                if hint.lower() in lower_link:
                    return link
        return ""

    def _extract_emails_from_text(self, text: str) -> list[str]:
        found = EMAIL_PATTERN.findall(text)
        # Filter out image extensions and deduplicate
        filtered = []
        seen: set[str] = set()
        for email in found:
            lower = email.lower()
            if any(lower.endswith(ext) for ext in _IMAGE_EXTS):
                continue
            if lower in seen:
                continue
            seen.add(lower)
            filtered.append(email)
        return filtered
