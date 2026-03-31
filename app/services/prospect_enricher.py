import logging
import re
from typing import Optional

from app.models.prospect import Prospect, ProspectStatus

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


class ProspectEnricher:
    def __init__(self, config: dict):
        targeting = config.get("targeting", {})
        self.blocked_domains: list[str] = [
            d.lower() for d in targeting.get("blocked_domains", [])
        ]
        self.blocked_keywords: list[str] = [
            kw.lower() for kw in targeting.get("blocked_keywords", [])
        ]

    def enrich(self, prospects: list[Prospect]) -> list[Prospect]:
        valid = []
        seen_emails: set[str] = set()

        for prospect in prospects:
            error = self._validate(prospect, seen_emails)
            if error:
                prospect.error = error
                logger.warning(
                    f"Invalid prospect '{prospect.company_name}': {error}"
                )
                continue

            # Normalize
            prospect.company_name = prospect.company_name.strip().title()
            prospect.contact_name = prospect.contact_name.strip()
            prospect.contact_email = prospect.contact_email.strip().lower()
            prospect.website = prospect.website.strip()
            prospect.notes = prospect.notes.strip()
            prospect.industry = prospect.industry.strip()

            prospect.status = ProspectStatus.ENRICHED
            seen_emails.add(prospect.contact_email)
            valid.append(prospect)

        logger.info(
            f"Enriched {len(valid)}/{len(prospects)} valid prospects "
            f"({len(prospects) - len(valid)} rejected)."
        )
        return valid

    def _validate(self, prospect: Prospect, seen_emails: set[str]) -> str:
        # Required fields
        if not prospect.company_name:
            return "Missing company_name"

        if not prospect.contact_email:
            return "Missing contact_email"

        # Email format
        if not EMAIL_REGEX.match(prospect.contact_email):
            return f"Invalid email format: {prospect.contact_email}"

        # Blocked domains
        domain = prospect.contact_email.split("@")[-1].lower()
        if domain in self.blocked_domains:
            return f"Blocked domain: {domain}"

        # Blocked keywords in company_name or notes
        combined_text = (
            prospect.company_name.lower() + " " + prospect.notes.lower()
        )
        for kw in self.blocked_keywords:
            if kw in combined_text:
                return f"Blocked keyword found: {kw}"

        # Duplicate email
        if prospect.contact_email in seen_emails:
            return f"Duplicate email: {prospect.contact_email}"

        return ""
