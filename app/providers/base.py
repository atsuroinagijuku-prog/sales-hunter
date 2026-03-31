from __future__ import annotations
from abc import ABC, abstractmethod
from app.models.lead import CompanyCandidate


class SearchProvider(ABC):
    @abstractmethod
    def get_candidates(self, limit: int = None) -> list[CompanyCandidate]:
        """Return list of company candidates"""
        ...
