from __future__ import annotations
import csv
import uuid
import logging
from app.providers.base import SearchProvider
from app.models.lead import CompanyCandidate, SourceType


class CsvSeedProvider(SearchProvider):
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.logger = logging.getLogger(__name__)

    def get_candidates(self, limit=None) -> list[CompanyCandidate]:
        candidates: list[CompanyCandidate] = []
        try:
            with open(self.filepath, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    company_name = row.get("company_name", "").strip()
                    if not company_name:
                        continue
                    homepage_url = self._normalize_url(row.get("website", "").strip())
                    candidate = CompanyCandidate(
                        id=str(uuid.uuid4()),
                        company_name=company_name,
                        homepage_url=homepage_url,
                        source_type=SourceType.CSV,
                        industry=row.get("industry", "").strip(),
                        notes=row.get("notes", "").strip(),
                    )
                    candidates.append(candidate)
                    if limit is not None and len(candidates) >= limit:
                        break
        except FileNotFoundError:
            self.logger.error(f"CSV file not found: {self.filepath}")
        except Exception as e:
            self.logger.error(f"Error reading CSV {self.filepath}: {e}")
        self.logger.info(f"CsvSeedProvider loaded {len(candidates)} candidates from {self.filepath}")
        return candidates

    def _normalize_url(self, url: str) -> str:
        if not url:
            return ""
        if not url.startswith(("http://", "https://")):
            return "https://" + url
        return url
