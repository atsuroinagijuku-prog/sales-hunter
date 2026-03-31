from __future__ import annotations
import logging
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.models.lead import WebsiteSnapshot


class WebsiteFetcher:
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (compatible; SalesHunterBot/1.0; research purposes)"
    }

    def __init__(self, timeout: int = 10, retry_count: int = 2, delay_seconds: float = 1.0):
        self.timeout = timeout
        self.retry_count = retry_count
        self.delay = delay_seconds
        self.logger = logging.getLogger(__name__)

    def fetch(self, url: str) -> WebsiteSnapshot:
        url = self.normalize_url(url)
        last_error = ""
        for attempt in range(self.retry_count):
            try:
                resp = requests.get(
                    url,
                    headers=self.DEFAULT_HEADERS,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
                soup = BeautifulSoup(resp.text, "lxml")

                # Title
                title = ""
                if soup.title and soup.title.string:
                    title = soup.title.string.strip()

                # Meta description
                meta_description = ""
                meta_tag = soup.find("meta", {"name": "description"})
                if meta_tag:
                    meta_description = meta_tag.get("content", "").strip()

                # Body text
                body_text = soup.get_text(separator=" ", strip=True)[:3000]

                # Links
                links = [a.get("href") for a in soup.find_all("a", href=True)]

                return WebsiteSnapshot(
                    url=url,
                    status_code=resp.status_code,
                    title=title,
                    meta_description=meta_description,
                    body_text=body_text,
                    links=links,
                    fetch_success=True,
                )
            except (
                requests.exceptions.SSLError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.TooManyRedirects,
                Exception,
            ) as e:
                last_error = str(e)
                self.logger.warning(f"Fetch attempt {attempt + 1}/{self.retry_count} failed for {url}: {e}")
                if attempt < self.retry_count - 1:
                    time.sleep(self.delay)

        return WebsiteSnapshot(
            url=url,
            fetch_success=False,
            error=last_error,
        )

    def normalize_url(self, url: str) -> str:
        if not url.startswith(("http://", "https://")):
            return "https://" + url
        return url
