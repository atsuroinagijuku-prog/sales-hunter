from __future__ import annotations
import logging
from app.models.lead import WebsiteSnapshot, CompanyProfile

BTOB_SIGNALS = [
    "法人", "企業", "BtoB", "B2B", "ビジネス", "業務", "導入事例",
    "料金プラン", "お問い合わせ", "会社概要", "採用情報",
]
OUTSOURCING_SIGNALS = [
    "外注", "代行", "委託", "アウトソース", "効率化", "自動化",
    "業務改善", "省力化", "コスト削減",
]
CONSUMER_SIGNALS = [
    "カート", "ショッピング", "個人のお客様", "一般のお客様", "主婦", "学生向け",
]


class CompanyProfiler:
    def __init__(self, llm_client=None, use_llm: bool = False):
        self.llm = llm_client
        self.use_llm = use_llm
        self.logger = logging.getLogger(__name__)

    def profile(self, snapshot: WebsiteSnapshot) -> CompanyProfile:
        if not snapshot.fetch_success:
            return CompanyProfile()

        text = snapshot.body_text

        # 1. likely_b2b: presence of B2B signals and absence of consumer signals
        btob_hits = [s for s in BTOB_SIGNALS if s in text]
        consumer_hits = [s for s in CONSUMER_SIGNALS if s in text]
        likely_b2b = len(btob_hits) > 0 and len(consumer_hits) == 0

        # 2. likely_needs_outsourcing
        outsource_hits = [s for s in OUTSOURCING_SIGNALS if s in text]
        likely_needs_outsourcing = len(outsource_hits) > 0

        # 3. business_summary: meta description or first 150 chars of body text
        if snapshot.meta_description:
            business_summary = snapshot.meta_description[:200]
        elif text:
            business_summary = text[:150]
        else:
            business_summary = ""

        # 4. profile_notes: matched signals
        matched_signals = btob_hits + outsource_hits
        profile_notes = ", ".join(matched_signals) if matched_signals else ""

        # 5. Optionally use LLM for better summary
        if self.use_llm and self.llm and text:
            try:
                prompt = f"以下のサイトテキストから企業の事業内容を50文字以内で要約してください:\n{text[:500]}"
                llm_summary = self.llm.generate(prompt)
                if llm_summary and isinstance(llm_summary, str):
                    business_summary = llm_summary.strip()[:200]
            except Exception as e:
                self.logger.debug(f"LLM profiling failed, using rule-based summary: {e}")

        return CompanyProfile(
            business_summary=business_summary,
            likely_b2b=likely_b2b,
            likely_needs_outsourcing=likely_needs_outsourcing,
            profile_notes=profile_notes,
        )
