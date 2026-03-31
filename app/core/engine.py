import logging
import os
import glob as glob_module
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

        # Discovery components
        from app.services.website_fetcher import WebsiteFetcher
        from app.services.contact_finder import ContactFinder
        from app.agents.company_profiler import CompanyProfiler
        from app.services.lead_scorer import LeadDiscoveryScorer
        from app.services.lead_repository import LeadRepository
        from app.agents.discovery_report import DiscoveryReportAgent

        discovery_cfg = config.get("discovery", {})
        self.website_fetcher = WebsiteFetcher(
            timeout=discovery_cfg.get("request_timeout_seconds", 10),
            retry_count=discovery_cfg.get("request_retry_count", 2),
            delay_seconds=discovery_cfg.get("delay_between_requests", 1.0),
        )
        self.contact_finder = ContactFinder(fetcher=self.website_fetcher)
        self.profiler = CompanyProfiler(llm_client=self.llm, use_llm=False)
        self.discovery_scorer = LeadDiscoveryScorer(config=discovery_cfg)
        self.lead_repo = LeadRepository(output_dir=config.get("output_dir", "data/output"))
        self.discovery_report_agent = DiscoveryReportAgent(output_dir=config.get("output_dir", "data/output"))

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

    # ------------------------------------------------------------------
    # Lead Discovery methods
    # ------------------------------------------------------------------

    def discover(
        self,
        source: str = "csv",
        input_path: str = None,
        queries_path: str = None,
        limit: int = None,
        dry_run: bool = False,
    ) -> int:
        from app.providers.csv_provider import CsvSeedProvider
        from app.providers.web_provider import WebSearchProvider
        from app.agents.company_discovery import CompanyDiscoveryAgent
        from app.models.lead import LeadRecord
        import uuid
        from datetime import datetime

        discovery_cfg = self.config.get("discovery", {})

        providers = []
        if source in ("csv", "both"):
            csv_path = input_path or "data/input/seed_companies.csv"
            providers.append(CsvSeedProvider(filepath=csv_path))
        if source in ("web", "both"):
            q_path = queries_path or "data/input/search_queries.txt"
            providers.append(WebSearchProvider.from_file(q_path, config=discovery_cfg))

        discovery_agent = CompanyDiscoveryAgent(providers=providers, config=discovery_cfg)
        candidates = discovery_agent.discover(limit=limit)

        logger.info(f"Processing {len(candidates)} candidates (dry_run={dry_run})")
        count = 0

        for candidate in candidates:
            try:
                if dry_run:
                    logger.info(f"[DRY RUN] Would process: {candidate.company_name} ({candidate.homepage_url})")
                    lead = LeadRecord(
                        id=candidate.id,
                        company_name=candidate.company_name,
                        homepage_url=candidate.homepage_url,
                        source_type=candidate.source_type,
                        source_query=candidate.source_query,
                        industry=candidate.industry,
                    )
                    score_result = self.discovery_scorer.score(lead)
                    lead = lead.model_copy(update={
                        "score": score_result.score,
                        "priority": score_result.priority,
                        "score_reason": score_result.score_reason,
                    })
                    self.lead_repo.upsert(lead)
                    count += 1
                    continue

                # Fetch website
                if candidate.homepage_url:
                    snapshot = self.website_fetcher.fetch(candidate.homepage_url)
                else:
                    from app.models.lead import WebsiteSnapshot
                    snapshot = WebsiteSnapshot(url="", fetch_success=False, error="No URL provided")

                # Find contacts
                contact_info = self.contact_finder.find(snapshot)

                # Profile company
                profile = self.profiler.profile(snapshot)

                # Build LeadRecord
                lead = LeadRecord(
                    id=candidate.id,
                    company_name=candidate.company_name,
                    homepage_url=candidate.homepage_url,
                    source_type=candidate.source_type,
                    source_query=candidate.source_query,
                    industry=candidate.industry,
                    business_summary=profile.business_summary,
                    contact_email=contact_info.contact_email,
                    contact_page_url=contact_info.contact_page_url,
                    company_page_url=contact_info.company_page_url,
                    phone_number=contact_info.phone_number,
                    likely_b2b=profile.likely_b2b,
                    likely_needs_outsourcing=profile.likely_needs_outsourcing,
                    profile_notes=profile.profile_notes,
                    fetch_success=snapshot.fetch_success,
                    error=snapshot.error,
                )

                # Score
                score_result = self.discovery_scorer.score(lead)
                lead = lead.model_copy(update={
                    "score": score_result.score,
                    "priority": score_result.priority,
                    "score_reason": score_result.score_reason,
                })

                self.lead_repo.upsert(lead)
                count += 1
                logger.info(
                    f"Processed: {lead.company_name} | score={lead.score:.1f} "
                    f"priority={lead.priority.value} | email={lead.contact_email or '-'}"
                )

            except Exception as e:
                logger.error(f"Error processing candidate {candidate.company_name}: {e}")

        # Persist results
        self.lead_repo.save_csv()
        self.lead_repo.save_json()

        return count

    def score_leads(self) -> int:
        # Load leads from latest JSON in data/output/
        output_dir = self.config.get("output_dir", "data/output")
        json_files = sorted(
            glob_module.glob(os.path.join(output_dir, "leads_*.json")),
            reverse=True,
        )
        if not json_files:
            logger.warning("No leads JSON found to score.")
            return 0

        latest = json_files[0]
        self.lead_repo.load_json(latest)
        leads = self.lead_repo.get_all()

        for lead in leads:
            score_result = self.discovery_scorer.score(lead)
            updated = lead.model_copy(update={
                "score": score_result.score,
                "priority": score_result.priority,
                "score_reason": score_result.score_reason,
            })
            self.lead_repo.upsert(updated)

        self.lead_repo.save_csv()
        self.lead_repo.save_json()
        logger.info(f"Re-scored {len(leads)} leads.")
        return len(leads)

    def discovery_report(self) -> dict:
        output_dir = self.config.get("output_dir", "data/output")
        json_files = sorted(
            glob_module.glob(os.path.join(output_dir, "leads_*.json")),
            reverse=True,
        )
        if not json_files:
            logger.warning("No leads JSON found to generate report.")
            return {}

        latest = json_files[0]
        self.lead_repo.load_json(latest)
        leads = self.lead_repo.get_all()

        summary = self.discovery_report_agent.generate(leads)
        return summary.model_dump()
