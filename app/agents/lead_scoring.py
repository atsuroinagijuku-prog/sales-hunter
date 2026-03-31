import logging
from datetime import datetime

from app.models.prospect import Prospect, ProspectStatus

logger = logging.getLogger(__name__)

BTOB_SIGNALS = ["株式会社", "合同会社", "有限会社"]


class LeadScoringAgent:
    def __init__(self, config: dict):
        score_rules = config.get("score_rules", {})
        targeting = config.get("targeting", {})

        self.rule_has_email: float = score_rules.get("has_email", 20)
        self.rule_has_website: float = score_rules.get("has_website", 10)
        self.rule_allowed_industry: float = score_rules.get("allowed_industry", 15)
        self.rule_btob_signal: float = score_rules.get("btob_signal", 5)
        self.notes_max_bonus: float = score_rules.get("notes_max_bonus", 40)
        self.notes_keywords: dict = score_rules.get("notes_keywords", {
            "外注": 20, "代行": 20, "自動化": 20, "効率化": 20,
            "マーケ": 15, "営業": 15, "リスト": 15, "入力": 10,
        })
        self.allowed_industries: list[str] = targeting.get("allowed_industries", [])

    def score(self, prospects: list[Prospect]) -> list[Prospect]:
        for prospect in prospects:
            score, reasons = self._calculate_score(prospect)
            prospect.score = min(score, 100.0)
            prospect.score_reason = "; ".join(reasons)
            prospect.priority = self._priority(prospect.score)
            prospect.status = ProspectStatus.SCORED
            prospect.updated_at = datetime.now()
            logger.debug(
                f"Scored '{prospect.company_name}': {prospect.score:.1f} "
                f"({prospect.priority}) - {prospect.score_reason}"
            )

        logger.info(f"Scored {len(prospects)} prospects.")
        return prospects

    def _calculate_score(self, prospect: Prospect) -> tuple[float, list[str]]:
        score = 0.0
        reasons = []

        if prospect.contact_email:
            score += self.rule_has_email
            reasons.append(f"has_email(+{self.rule_has_email})")

        if prospect.website:
            score += self.rule_has_website
            reasons.append(f"has_website(+{self.rule_has_website})")

        if prospect.industry and prospect.industry in self.allowed_industries:
            score += self.rule_allowed_industry
            reasons.append(f"allowed_industry(+{self.rule_allowed_industry})")

        # Notes keyword scoring
        notes_lower = prospect.notes.lower()
        notes_bonus = 0.0
        matched_keywords = []
        for kw, pts in self.notes_keywords.items():
            if kw in notes_lower:
                notes_bonus += pts
                matched_keywords.append(kw)

        notes_bonus = min(notes_bonus, self.notes_max_bonus)
        if notes_bonus > 0:
            score += notes_bonus
            reasons.append(f"notes_keywords({','.join(matched_keywords)}, +{notes_bonus})")

        # BtoB signal
        for signal in BTOB_SIGNALS:
            if signal in prospect.company_name:
                score += self.rule_btob_signal
                reasons.append(f"btob_signal({signal}, +{self.rule_btob_signal})")
                break

        return score, reasons

    def _priority(self, score: float) -> str:
        if score >= 70:
            return "high"
        if score >= 40:
            return "medium"
        return "low"
