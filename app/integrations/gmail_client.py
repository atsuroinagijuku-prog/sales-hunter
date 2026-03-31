import base64
import logging
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)


class GmailClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        from_address: str,
    ):
        self.from_address = from_address
        self.service = None

        if not all([client_id, client_secret, refresh_token, from_address]):
            logger.warning(
                "Gmail credentials incomplete. Running in degraded mode (dry-run only)."
            )
            return

        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
                token_uri="https://oauth2.googleapis.com/token",
                scopes=["https://www.googleapis.com/auth/gmail.modify"],
            )
            self.service = build("gmail", "v1", credentials=creds)
            logger.info("Gmail client initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Gmail client: {e}")
            self.service = None

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
        dry_run: bool = False,
    ) -> dict:
        if dry_run:
            logger.info(f"[DRY-RUN] Would send email to={to} subject={subject}")
            return {"status": "dry_run", "to": to, "subject": subject, "message_id": "", "thread_id": thread_id or ""}

        if self.service is None:
            logger.error("Gmail service not available. Cannot send email.")
            return {"status": "failed", "to": to, "subject": subject, "message_id": "", "thread_id": ""}

        try:
            message = MIMEText(body, "plain", "utf-8")
            message["to"] = to
            message["from"] = self.from_address
            message["subject"] = subject

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            body_payload: dict = {"raw": raw}

            if thread_id:
                body_payload["threadId"] = thread_id

            result = (
                self.service.users()
                .messages()
                .send(userId="me", body=body_payload)
                .execute()
            )

            message_id = result.get("id", "")
            returned_thread_id = result.get("threadId", "")
            logger.info(f"Email sent to={to} message_id={message_id}")
            return {
                "status": "sent",
                "message_id": message_id,
                "thread_id": returned_thread_id,
            }
        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            return {"status": "failed", "message_id": "", "thread_id": ""}

    def get_replies(self, since_hours: int = 24) -> list[dict]:
        if self.service is None:
            logger.warning("Gmail service not available. Returning empty replies.")
            return []

        try:
            since_dt = datetime.utcnow() - timedelta(hours=since_hours)
            # Gmail query format: after:YYYY/MM/DD
            after_str = since_dt.strftime("%Y/%m/%d")
            query = f"in:inbox after:{after_str}"

            results = (
                self.service.users()
                .messages()
                .list(userId="me", q=query, maxResults=100)
                .execute()
            )

            messages = results.get("messages", [])
            replies = []

            for msg_ref in messages:
                try:
                    msg = (
                        self.service.users()
                        .messages()
                        .get(userId="me", id=msg_ref["id"], format="full")
                        .execute()
                    )

                    headers = {
                        h["name"].lower(): h["value"]
                        for h in msg.get("payload", {}).get("headers", [])
                    }

                    body_text = self._extract_body(msg.get("payload", {}))
                    internal_date = int(msg.get("internalDate", 0)) / 1000
                    received_at = datetime.utcfromtimestamp(internal_date).isoformat()

                    replies.append(
                        {
                            "message_id": msg["id"],
                            "thread_id": msg.get("threadId", ""),
                            "from": headers.get("from", ""),
                            "subject": headers.get("subject", ""),
                            "body": body_text,
                            "received_at": received_at,
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to parse message {msg_ref['id']}: {e}")

            logger.info(f"Fetched {len(replies)} replies from Gmail.")
            return replies

        except Exception as e:
            logger.error(f"Failed to fetch replies from Gmail: {e}")
            return []

    def _extract_body(self, payload: dict) -> str:
        """Recursively extract plain text body from Gmail message payload."""
        mime_type = payload.get("mimeType", "")

        if mime_type == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            return ""

        parts = payload.get("parts", [])
        for part in parts:
            text = self._extract_body(part)
            if text:
                return text

        return ""
