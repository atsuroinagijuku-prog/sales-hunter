import logging
import os
from datetime import datetime

from app.models.prospect import Prospect, ProspectStatus, ReplyLabel
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


class FollowupMessageAgent:
    def __init__(self, config: dict, llm_client: BaseLLMClient):
        self.config = config
        self.llm = llm_client
        self.sender = config.get("sender", {})
        outreach = config.get("outreach", {})
        self.max_followups: int = outreach.get("max_followups", 2)

    def generate(self, prospect: Prospect) -> Prospect:
        if prospect.followup_count >= self.max_followups:
            logger.info(
                f"'{prospect.company_name}' reached max followups "
                f"({self.max_followups}). Skipping."
            )
            prospect.status = ProspectStatus.CLOSED
            prospect.updated_at = datetime.now()
            return prospect

        label = prospect.reply_label

        if label == ReplyLabel.INTERESTED:
            body = self._generate_interested(prospect)
        elif label == ReplyLabel.QUESTION:
            body = self._generate_question(prospect)
        elif label == ReplyLabel.NOT_INTERESTED:
            body = self._template_not_interested(prospect)
        elif label == ReplyLabel.UNSUBSCRIBE:
            body = self._template_unsubscribe(prospect)
        elif label == ReplyLabel.OUT_OF_OFFICE:
            body = self._template_out_of_office(prospect)
        else:
            # OTHER or None: draft for human review
            body = self._template_human_review(prospect)
            prospect.requires_human = True

        prospect.followup_body = body
        prospect.followup_count += 1
        prospect.status = ProspectStatus.FOLLOWUP_READY
        prospect.updated_at = datetime.now()

        logger.info(
            f"Generated followup for '{prospect.company_name}' "
            f"(label={label}, count={prospect.followup_count})"
        )
        return prospect

    def _generate_interested(self, prospect: Prospect) -> str:
        template = _load_prompt("followup_interested.txt")
        if not template:
            return self._fallback_interested(prospect)

        prompt = template.format(
            company_name=prospect.company_name,
            contact_name=prospect.contact_name or "ご担当者",
            reply_text=prospect.reply_text,
            calendar_link=self.sender.get("calendar_link", ""),
        )
        response = self.llm.complete(prompt=prompt)
        return response.strip() if response.strip() else self._fallback_interested(prospect)

    def _generate_question(self, prospect: Prospect) -> str:
        template = _load_prompt("followup_question.txt")
        if not template:
            return self._fallback_question(prospect)

        prompt = template.format(
            company_name=prospect.company_name,
            reply_text=prospect.reply_text,
            offer_summary=self.sender.get("offer_summary", ""),
        )
        response = self.llm.complete(prompt=prompt)
        return response.strip() if response.strip() else self._fallback_question(prospect)

    def _fallback_interested(self, prospect: Prospect) -> str:
        calendar = self.sender.get("calendar_link", "")
        cta = f"\nご都合の良い日程はこちらからお選びいただけます：{calendar}" if calendar else ""
        return (
            f"{prospect.contact_name or 'ご担当者'}様\n\n"
            f"ご興味をお持ちいただきありがとうございます！\n"
            f"ぜひ一度、オンラインにてご説明させてください。{cta}\n\n"
            f"ご都合の良いお日程をお聞かせいただけますでしょうか？\n\n"
            f"{self.sender.get('name', '')}\n{self.sender.get('company', '')}"
        )

    def _fallback_question(self, prospect: Prospect) -> str:
        offer = self.sender.get("offer_summary", "")
        return (
            f"{prospect.contact_name or 'ご担当者'}様\n\n"
            f"ご質問いただきありがとうございます。\n"
            f"弊社のサービス（{offer}）について、詳しくご説明させていただきます。\n\n"
            f"30分ほどオンラインでご説明する機会をいただけますでしょうか？\n\n"
            f"{self.sender.get('name', '')}\n{self.sender.get('company', '')}"
        )

    def _template_not_interested(self, prospect: Prospect) -> str:
        return (
            f"{prospect.contact_name or 'ご担当者'}様\n\n"
            f"ご返信いただきありがとうございます。\n"
            f"今回はご縁がなかったようですが、またの機会がございましたらお声がけください。\n\n"
            f"{self.sender.get('name', '')}\n{self.sender.get('company', '')}"
        )

    def _template_unsubscribe(self, prospect: Prospect) -> str:
        return (
            f"{prospect.contact_name or 'ご担当者'}様\n\n"
            f"ご連絡いただきありがとうございます。\n"
            f"今後のご連絡は差し控えさせていただきます。ご迷惑をおかけして申し訳ございませんでした。\n\n"
            f"{self.sender.get('name', '')}\n{self.sender.get('company', '')}"
        )

    def _template_out_of_office(self, prospect: Prospect) -> str:
        return (
            f"{prospect.contact_name or 'ご担当者'}様\n\n"
            f"ご不在との自動返信を確認いたしました。\n"
            f"ご帰社後、改めてご連絡させていただきます。\n\n"
            f"{self.sender.get('name', '')}\n{self.sender.get('company', '')}"
        )

    def _template_human_review(self, prospect: Prospect) -> str:
        return (
            f"[要人間確認] {prospect.company_name}様からの返信:\n\n"
            f"{prospect.reply_text}\n\n"
            f"---\n"
            f"上記に対して適切な返信を作成してください。"
        )
