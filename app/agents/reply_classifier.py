from __future__ import annotations
import logging
import os
from datetime import datetime

from app.models.prospect import Prospect, ProspectStatus, ReplyLabel
from app.integrations.llm_client import BaseLLMClient

logger = logging.getLogger(__name__)

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "prompts")

# Rule-based keyword lists
RULES: list[tuple[ReplyLabel, list[str]]] = [
    (ReplyLabel.UNSUBSCRIBE, ["配信停止", "unsubscribe", "停止", "不要", "結構です"]),
    (ReplyLabel.NOT_INTERESTED, ["興味ない", "不要", "必要ない", "検討しない", "遠慮"]),
    (ReplyLabel.OUT_OF_OFFICE, ["不在", "休暇", "out of office", "vacation"]),
    (ReplyLabel.INTERESTED, ["興味", "詳しく", "聞かせて", "お願い", "検討", "打ち合わせ", "ミーティング"]),
    (ReplyLabel.QUESTION, ["？", "?", "教えて", "どのように", "いくら", "費用", "料金"]),
]


def _load_prompt(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {path}")
        return ""


VALID_LABELS = {label.value for label in ReplyLabel}


class ReplyClassifier:
    def __init__(self, config: dict, llm_client: BaseLLMClient):
        self.config = config
        self.llm = llm_client

    def classify(self, prospect: Prospect) -> Prospect:
        reply_lower = prospect.reply_text.lower()

        label, confidence = self._rule_based(reply_lower)

        if label is None:
            label, confidence = self._llm_based(prospect.reply_text)

        if label is None:
            label = ReplyLabel.OTHER
            confidence = 0.5

        prospect.reply_label = label
        prospect.reply_confidence = confidence
        prospect.updated_at = datetime.now()

        # Set status and flags based on label
        if label == ReplyLabel.UNSUBSCRIBE:
            prospect.status = ProspectStatus.UNSUBSCRIBED
            prospect.requires_human = False
        elif label == ReplyLabel.INTERESTED:
            prospect.status = ProspectStatus.INTERESTED
            prospect.requires_human = False
        elif label == ReplyLabel.QUESTION:
            prospect.requires_human = False
        elif label == ReplyLabel.NOT_INTERESTED:
            prospect.requires_human = False
        elif label == ReplyLabel.OUT_OF_OFFICE:
            prospect.requires_human = False
        else:  # OTHER
            prospect.requires_human = True

        logger.info(
            f"Classified reply for '{prospect.company_name}': "
            f"{label.value} (confidence={confidence:.2f})"
        )
        return prospect

    def _rule_based(self, reply_lower: str) -> tuple[ReplyLabel | None, float]:
        for label, keywords in RULES:
            for kw in keywords:
                if kw.lower() in reply_lower:
                    return label, 0.95
        return None, 0.0

    def _llm_based(self, reply_text: str) -> tuple[ReplyLabel | None, float]:
        template = _load_prompt("reply_classify.txt")
        if not template:
            return None, 0.0

        prompt = template.format(reply_text=reply_text)
        response = self.llm.complete(prompt=prompt).strip().lower()

        # Extract first word / line
        first_line = response.split("\n")[0].strip()

        for label_value in VALID_LABELS:
            if label_value in first_line:
                try:
                    return ReplyLabel(label_value), 0.75
                except ValueError:
                    pass

        logger.warning(f"LLM returned unrecognized label: '{response}'")
        return ReplyLabel.OTHER, 0.5
