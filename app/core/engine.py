import logging
import os
from typing import Optional

from dotenv import load_dotenv

from app.agents.followup_message import FollowupMessageAgent
from app.agents.lead_scoring import LeadScoringAgent
from app.agents.outreach_message import OutreachMessageAgent
from app.agents.reply_classifier import ReplyClassifier
from app.agents.report_agent import ReportAgent
from app.integrations.gmail_client import GmailClient
from app.integrations.llm_client import get_llm_client
from app.models.prospect import ProspectStatus
from app.services.crm_state import CRMStateManager
from app.services.outreach_sender import OutreachSender
from app.services.prospect_enricher import ProspectEnricher
from app.services.prospect_source import CSVProspectSource
from app.services.reply_fetcher import ReplyFetcher
from app.utils.logger import setup_logger

logger = logging.getLogger(__name__)


class SalesHunterEngine:
    def __init__(self, config: dict, dry_run: bool = False):
        load_dotenv()

        self.config = config
        self.dry_run = dry_run

        log_cfg = config.get("logging", {})
        setup_logger(
            "sales_hunter",
            log_dir=log_cfg.get("log_dir", "data/logs"),
            level=log_cfg.get("level", "INFO"),
        )

        # LLM client
        llm_cfg = config.get("llm", {})
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.llm = get_llm_client(
            provider=llm_cfg.get("provider", "gemini"),
            model=llm_cfg.get("model", "gemini-2.5-flash"),
            api_key=api_key,
        )

        # Gmail client
        gmail_creds = {
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
            "refresh_token": os.getenv("GOOGLE_REFRESH_TOKEN", ""),
            "from_address": os.getenv(
                "GMAIL_FROM_ADDRESS",
                config.get("sender", {}).get("email", ""),
            ),
        }
        self.gmail = GmailClient(**gmail_creds)

        # CRM state
        self.crm = CRMStateManager()

        # Services
        self.enricher = ProspectEnricher(config)
        self.sender = OutreachSender(config, self.gmail)
        self.reply_fetcher = ReplyFetcher(config, self.gmail)

        # Agents
        self.scorer = LeadScoringAgent(config)
        self.outreach_agent = OutreachMessageAgent(config, self.llm)
        self.classifier = ReplyClassifier(config, self.llm)
        self.followup_agent = FollowupMessageAgent(config, self.llm)
        self.report_agent = ReportAgent(config)

        logger.info(
            f"SalesHunterEngine initialized (dry_run={dry_run})"
        )

    def ingest(self, input_path: str) -> int:
        logger.info(f"Ingesting prospects from {input_path}")
        source = CSVProspectSource(input_path)
        raw_prospects = source.load()

        enriched = self.enricher.enrich(raw_prospects)
        self.crm.upsert_many(enriched)

        logger.info(f"Ingested {len(enriched)} prospects.")
        return len(enriched)

    def score(self) -> int:
        prospects = self.crm.get_by_statuses(
            [ProspectStatus.NEW, ProspectStatus.ENRICHED]
        )
        if not prospects:
            logger.info("No prospects to score.")
            return 0

        scored = self.scorer.score(prospects)
        self.crm.upsert_many(scored)

        logger.info(f"Scored {len(scored)} prospects.")
        return len(scored)

    def send_first(self, limit: Optional[int] = None, draft: bool = False) -> int:
        prospects = self.crm.get_by_status(ProspectStatus.SCORED)
        if not prospects:
            logger.info("No scored prospects to send to.")
            return 0

        # Generate messages for prospects that don't have them yet
        needs_message = [p for p in prospects if not p.email_body]
        logger.info(
            f"Generating messages for {len(needs_message)}/{len(prospects)} prospects."
        )
        for i, prospect in enumerate(needs_message):
            prospects[prospects.index(prospect)] = self.outreach_agent.generate(prospect)

        if draft:
            # Save messages to CRM but don't send
            self.crm.upsert_many(prospects)
            logger.info(
                f"[DRAFT] Generated {len(needs_message)} messages, saved to CRM. Not sending."
            )
            return len(needs_message)

        # Send
        updated = self.sender.send(
            prospects,
            dry_run=self.dry_run,
            limit=limit,
        )
        self.crm.upsert_many(updated)

        sent_count = sum(
            1 for p in updated if p.status == ProspectStatus.FIRST_SENT
        )
        return sent_count

    def fetch_replies(self) -> int:
        prospects = self.crm.get_by_status(ProspectStatus.FIRST_SENT)
        if not prospects:
            logger.info("No FIRST_SENT prospects to check for replies.")
            return 0

        updated = self.reply_fetcher.fetch(prospects)
        self.crm.upsert_many(updated)

        new_replies = sum(1 for p in updated if p.status == ProspectStatus.REPLIED)
        logger.info(f"Found {new_replies} new replies.")
        return new_replies

    def process_replies(self) -> int:
        prospects = self.crm.get_by_status(ProspectStatus.REPLIED)
        if not prospects:
            logger.info("No REPLIED prospects to process.")
            return 0

        processed = []
        for prospect in prospects:
            classified = self.classifier.classify(prospect)
            with_followup = self.followup_agent.generate(classified)
            processed.append(with_followup)

        self.crm.upsert_many(processed)

        logger.info(f"Processed {len(processed)} replies.")
        return len(processed)

    def generate_report(self) -> dict:
        all_prospects = self.crm.load_all()
        return self.report_agent.generate(all_prospects)
