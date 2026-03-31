import csv
import logging
import uuid
from abc import ABC, abstractmethod
from typing import Optional

from app.models.prospect import Prospect, ProspectStatus

logger = logging.getLogger(__name__)


class BaseProspectSource(ABC):
    @abstractmethod
    def load(self) -> list[Prospect]:
        ...


class CSVProspectSource(BaseProspectSource):
    def __init__(self, filepath: str):
        self.filepath = filepath

    def load(self) -> list[Prospect]:
        prospects = []

        try:
            with open(self.filepath, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    try:
                        prospect = Prospect(
                            id=str(uuid.uuid4()),
                            company_name=row.get("company_name", "").strip(),
                            website=row.get("website", "").strip(),
                            contact_name=row.get("contact_name", "").strip(),
                            contact_email=row.get("contact_email", "").strip(),
                            industry=row.get("industry", "").strip(),
                            notes=row.get("notes", "").strip(),
                            status=ProspectStatus.NEW,
                        )
                        prospects.append(prospect)
                    except Exception as e:
                        logger.warning(f"Failed to parse row {i + 1}: {row}. Error: {e}")
        except FileNotFoundError:
            logger.error(f"CSV file not found: {self.filepath}")
        except Exception as e:
            logger.error(f"Failed to load CSV from {self.filepath}: {e}")

        logger.info(f"Loaded {len(prospects)} prospects from {self.filepath}")
        return prospects
