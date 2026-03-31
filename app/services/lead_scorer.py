from __future__ import annotations
import logging
from app.models.lead import LeadRecord, ScoreResult, Priority

_BONUS_KEYWORDS = [
    "営業", "マーケ", "外注", "代行", "EC", "効率化", "自動化", "採用", "集客",
]


class LeadDiscoveryScorer:
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.rules = self.config.get("score_rules", {}) if config else {}
        self.logger = logging.getLogger(__name__)

    def score(self, lead: LeadRecord) -> ScoreResult:
        score = 0.0
        reasons: list[str] = []

        # +20: has homepage_url and fetch_success
        if lead.homepage_url and lead.fetch_success:
            score += 20
            reasons.append("サイト取得成功(+20)")

        # +20: has contact_email
        if lead.contact_email:
            score += 20
            reasons.append("メールあり(+20)")

        # +15: has contact_page_url
        if lead.contact_page_url:
            score += 15
            reasons.append("問い合わせページあり(+15)")

        # +15: likely_b2b
        if lead.likely_b2b:
            score += 15
            reasons.append("BtoB企業(+15)")

        # +10: has company_page_url
        if lead.company_page_url:
            score += 10
            reasons.append("会社概要ページあり(+10)")

        # +10: likely_needs_outsourcing
        if lead.likely_needs_outsourcing:
            score += 10
            reasons.append("外注ニーズあり(+10)")

        # +5: has phone_number
        if lead.phone_number:
            score += 5
            reasons.append("電話番号あり(+5)")

        # -20: not fetch_success (site unreachable)
        if not lead.fetch_success:
            score -= 20
            reasons.append("サイト取得失敗(-20)")

        # -10: no contact_email AND no contact_page_url
        if not lead.contact_email and not lead.contact_page_url:
            score -= 10
            reasons.append("連絡先なし(-10)")

        # Bonus keywords: check notes and profile_notes
        text_to_check = (lead.profile_notes + " " + lead.business_summary + " " + lead.industry).lower()
        keyword_bonus = 0.0
        bonus_max = self.rules.get("keyword_bonus_max", 20)
        bonus_per_hit = self.rules.get("keyword_bonus_per_hit", 5)
        for keyword in _BONUS_KEYWORDS:
            if keyword in text_to_check:
                keyword_bonus = min(keyword_bonus + bonus_per_hit, bonus_max)
                reasons.append(f"キーワード'{keyword}'(+{bonus_per_hit})")
        score += keyword_bonus

        # Clamp to 0-100
        score = max(0.0, min(100.0, score))

        # Priority thresholds
        if score >= 60:
            priority = Priority.HIGH
        elif score >= 35:
            priority = Priority.MEDIUM
        else:
            priority = Priority.LOW

        return ScoreResult(
            score=score,
            priority=priority,
            score_reason="; ".join(reasons),
        )
