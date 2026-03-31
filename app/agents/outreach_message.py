import logging
import os
from datetime import datetime

from app.models.prospect import Prospect
from app.integrations.llm_client import BaseLLMClient

logger = logging.getLogger(__name__)

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "prompts")


def _load_prompt(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {path}")
        return ""


class OutreachMessageAgent:
    def __init__(self, config: dict, llm_client: BaseLLMClient):
        self.config = config
        self.llm = llm_client
        self.sender = config.get("sender", {})

    def generate(self, prospect: Prospect) -> Prospect:
        system_prompt = _load_prompt("outreach_system.txt")
        user_template = _load_prompt("outreach_user.txt")

        user_prompt = user_template.format(
            company_name=prospect.company_name,
            contact_name=prospect.contact_name or "ご担当者",
            industry=prospect.industry or "不明",
            notes=prospect.notes or "なし",
            offer_summary=self.sender.get("offer_summary", ""),
        )

        response = self.llm.complete(prompt=user_prompt, system=system_prompt)

        subject, body = self._parse_response(response, prospect)

        prospect.email_subject = subject
        prospect.email_body = body
        prospect.updated_at = datetime.now()

        logger.info(
            f"Generated outreach message for '{prospect.company_name}': subject='{subject}'"
        )
        return prospect

    def _parse_response(self, response: str, prospect: Prospect) -> tuple[str, str]:
        subject = ""
        body = ""

        if response:
            lines = response.strip().split("\n")
            subject_prefix = "件名:"
            body_marker = "本文:"
            in_body = False

            for line in lines:
                stripped = line.strip()
                if stripped.startswith(subject_prefix):
                    subject = stripped[len(subject_prefix):].strip()
                elif stripped.startswith(body_marker):
                    # Body may be on same line or following lines
                    inline = stripped[len(body_marker):].strip()
                    if inline:
                        body = inline
                    in_body = True
                elif in_body:
                    body = (body + "\n" + line).strip()

        # Fallback if parsing fails
        if not subject:
            subject = f"{prospect.company_name}様へ - AIによる業務効率化のご提案"

        if not body:
            sender_name = self.sender.get("name", "")
            sender_company = self.sender.get("company", "")
            offer = self.sender.get("offer_summary", "")
            cta = self.sender.get("call_to_action", "まずは無料でお試しいただけます。")
            body = (
                f"{prospect.contact_name or 'ご担当者'}様\n\n"
                f"突然のご連絡失礼いたします。{sender_company}の{sender_name}と申します。\n\n"
                f"弊社では{offer}をご提供しております。\n"
                f"{cta}\n\n"
                f"ご興味がございましたら、ぜひご返信ください。\n\n"
                f"{sender_name}\n{sender_company}"
            )

        return subject, body
