import json
import logging
import os
from datetime import datetime
from typing import Optional

from app.models.prospect import Prospect, ProspectStatus
from app.integrations.gmail_client import GmailClient

logger = logging.getLogger(__name__)

SEND_LOG_PATH = os.path.join("data", "output", "send_log.jsonl")


class OutreachSender:
    def __init__(self, config: dict, gmail_client: GmailClient):
        self.config = config
        self.gmail = gmail_client
        outreach = config.get("outreach", {})
        self.daily_send_limit: int = outreach.get("daily_send_limit", 20)

    def send(
        self,
        prospects: list[Prospect],
        dry_run: bool = False,
        limit: Optional[int] = None,
    ) -> list[Prospect]:
        # Filter eligible prospects
        eligible = [
            p for p in prospects
            if p.email_subject
            and p.email_body
            and p.status == ProspectStatus.SCORED
            and p.status != ProspectStatus.UNSUBSCRIBED
        ]

        # Apply limits
        max_sends = self.daily_send_limit
        if limit is not None:
            max_sends = min(max_sends, limit)

        to_send = eligible[:max_sends]

        if len(eligible) > max_sends:
            logger.info(
                f"Capping sends to {max_sends} (eligible={len(eligible)}, "
                f"daily_limit={self.daily_send_limit})."
            )

        sent_count = 0
        updated = []

        os.makedirs(os.path.dirname(SEND_LOG_PATH), exist_ok=True)

        for prospect in prospects:
            if prospect in to_send:
                result = self.gmail.send_email(
                    to=prospect.contact_email,
                    subject=prospect.email_subject,
                    body=prospect.email_body,
                    dry_run=dry_run,
                )

                log_entry = {
                    "prospect_id": prospect.id,
                    "company_name": prospect.company_name,
                    "contact_email": prospect.contact_email,
                    "subject": prospect.email_subject,
                    "status": result.get("status"),
                    "message_id": result.get("message_id", ""),
                    "thread_id": result.get("thread_id", ""),
                    "sent_at": datetime.now().isoformat(),
                    "dry_run": dry_run,
                }
                self._append_send_log(log_entry)

                if result.get("status") in ("sent", "dry_run"):
                    prospect.status = ProspectStatus.FIRST_SENT
                    prospect.sent_at = datetime.now()
                    prospect.message_id = result.get("message_id", "")
                    prospect.thread_id = result.get("thread_id", "")
                    prospect.updated_at = datetime.now()
                    sent_count += 1
                    logger.info(
                        f"{'[DRY-RUN] ' if dry_run else ''}Sent to "
                        f"{prospect.contact_email} ({prospect.company_name})"
                    )
                else:
                    prospect.error = f"Send failed: {result.get('status')}"
                    logger.warning(
                        f"Failed to send to {prospect.contact_email}: {result}"
                    )

            updated.append(prospect)

        logger.info(
            f"{'[DRY-RUN] ' if dry_run else ''}Sent {sent_count}/{len(to_send)} emails."
        )
        return updated

    def _append_send_log(self, entry: dict):
        try:
            with open(SEND_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write send log: {e}")
