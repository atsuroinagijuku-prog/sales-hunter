import logging
import re
from datetime import datetime

from app.models.prospect import Prospect, ProspectStatus
from app.integrations.gmail_client import GmailClient

logger = logging.getLogger(__name__)

EMAIL_EXTRACT_RE = re.compile(r"[\w._%+\-]+@[\w.\-]+\.[a-zA-Z]{2,}")


class ReplyFetcher:
    def __init__(self, config: dict, gmail_client: GmailClient):
        self.config = config
        self.gmail = gmail_client

    def fetch(self, prospects: list[Prospect]) -> list[Prospect]:
        replies = self.gmail.get_replies(since_hours=72)

        if not replies:
            logger.info("No replies fetched from Gmail.")
            return prospects

        # Build lookup maps for matching
        email_to_prospect: dict[str, Prospect] = {
            p.contact_email.lower(): p
            for p in prospects
            if p.contact_email
        }
        thread_to_prospect: dict[str, Prospect] = {
            p.thread_id: p
            for p in prospects
            if p.thread_id
        }

        matched_count = 0

        for reply in replies:
            prospect = None

            # Try matching by thread_id first
            reply_thread_id = reply.get("thread_id", "")
            if reply_thread_id and reply_thread_id in thread_to_prospect:
                prospect = thread_to_prospect[reply_thread_id]

            # Fallback: match by sender email
            if prospect is None:
                from_field = reply.get("from", "")
                email_matches = EMAIL_EXTRACT_RE.findall(from_field)
                for email in email_matches:
                    email_lower = email.lower()
                    if email_lower in email_to_prospect:
                        prospect = email_to_prospect[email_lower]
                        break

            if prospect is None:
                logger.debug(
                    f"No matching prospect for reply from '{reply.get('from', '')}' "
                    f"thread_id='{reply_thread_id}'"
                )
                continue

            # Only update if not already processed beyond FIRST_SENT
            if prospect.status not in (ProspectStatus.FIRST_SENT,):
                logger.debug(
                    f"Skipping reply for '{prospect.company_name}' "
                    f"(status={prospect.status})"
                )
                continue

            prospect.reply_text = reply.get("body", "")
            prospect.thread_id = reply_thread_id or prospect.thread_id
            prospect.status = ProspectStatus.REPLIED
            prospect.updated_at = datetime.now()
            matched_count += 1

            logger.info(
                f"Matched reply to '{prospect.company_name}' "
                f"from '{reply.get('from', '')}'"
            )

        logger.info(
            f"Fetched {len(replies)} replies, matched {matched_count} prospects."
        )
        return prospects
