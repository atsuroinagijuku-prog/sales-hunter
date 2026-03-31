import json
import logging
import os
from datetime import datetime
from typing import Optional

from app.models.prospect import Prospect, ProspectStatus

logger = logging.getLogger(__name__)

STATE_FILE = os.path.join("data", "state", "prospects.json")


def _default_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class CRMStateManager:
    def __init__(self, state_file: str = STATE_FILE):
        self.state_file = state_file
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)

    def load_all(self) -> list[Prospect]:
        if not os.path.exists(self.state_file):
            return []
        try:
            with open(self.state_file, encoding="utf-8") as f:
                data = json.load(f)
            prospects = []
            for item in data:
                try:
                    prospects.append(Prospect.model_validate(item))
                except Exception as e:
                    logger.warning(f"Failed to parse prospect from state: {e}")
            return prospects
        except Exception as e:
            logger.error(f"Failed to load CRM state: {e}")
            return []

    def save_all(self, prospects: list[Prospect]):
        try:
            data = [p.model_dump() for p in prospects]
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=_default_serializer)
            logger.debug(f"Saved {len(prospects)} prospects to {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to save CRM state: {e}")

    def upsert(self, prospect: Prospect):
        prospects = self.load_all()
        index = {p.id: i for i, p in enumerate(prospects)}

        if prospect.id in index:
            prospects[index[prospect.id]] = prospect
        else:
            prospects.append(prospect)

        self.save_all(prospects)

    def upsert_many(self, new_prospects: list[Prospect]):
        """Efficient bulk upsert."""
        prospects = self.load_all()
        index = {p.id: i for i, p in enumerate(prospects)}

        for prospect in new_prospects:
            if prospect.id in index:
                prospects[index[prospect.id]] = prospect
            else:
                prospects.append(prospect)
                index[prospect.id] = len(prospects) - 1

        self.save_all(prospects)

    def get_by_status(self, status: ProspectStatus) -> list[Prospect]:
        return [p for p in self.load_all() if p.status == status]

    def get_by_statuses(self, statuses: list[ProspectStatus]) -> list[Prospect]:
        status_set = set(statuses)
        return [p for p in self.load_all() if p.status in status_set]

    def get_by_email(self, email: str) -> Optional[Prospect]:
        email_lower = email.lower()
        for p in self.load_all():
            if p.contact_email.lower() == email_lower:
                return p
        return None

    def get_unsubscribed_emails(self) -> set[str]:
        return {
            p.contact_email.lower()
            for p in self.load_all()
            if p.status == ProspectStatus.UNSUBSCRIBED
        }
