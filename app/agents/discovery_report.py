from __future__ import annotations
import json
import logging
import os
from datetime import datetime, date

from app.models.lead import LeadRecord, ReportSummary, Priority


def _json_default(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class DiscoveryReportAgent:
    def __init__(self, output_dir: str = "data/output"):
        self.output_dir = output_dir
        self.logger = logging.getLogger(__name__)

    def generate(self, leads: list[LeadRecord], run_id: str = "") -> ReportSummary:
        if not run_id:
            run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        total = len(leads)
        valid_sites = sum(1 for l in leads if l.fetch_success)
        emails_found = sum(1 for l in leads if l.contact_email)
        contact_pages = sum(1 for l in leads if l.contact_page_url)
        high_priority = sum(1 for l in leads if l.priority == Priority.HIGH)
        medium_priority = sum(1 for l in leads if l.priority == Priority.MEDIUM)
        low_priority = sum(1 for l in leads if l.priority == Priority.LOW)

        # Top 5 by score
        sorted_leads = sorted(leads, key=lambda l: l.score, reverse=True)
        top_leads = [
            {
                "company_name": l.company_name,
                "score": l.score,
                "priority": l.priority.value if hasattr(l.priority, "value") else l.priority,
                "contact_email": l.contact_email,
                "homepage_url": l.homepage_url,
            }
            for l in sorted_leads[:5]
        ]

        summary = ReportSummary(
            run_id=run_id,
            generated_at=datetime.now(),
            total_companies=total,
            valid_sites=valid_sites,
            emails_found=emails_found,
            contact_pages_found=contact_pages,
            high_priority_leads=high_priority,
            medium_priority_leads=medium_priority,
            low_priority_leads=low_priority,
            top_leads=top_leads,
        )

        date_str = datetime.now().strftime("%Y%m%d")
        json_path = os.path.join(self.output_dir, f"discovery_report_{date_str}.json")
        md_path = os.path.join(self.output_dir, f"discovery_report_{date_str}.md")

        # Write JSON report
        os.makedirs(self.output_dir, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary.model_dump(), f, ensure_ascii=False, indent=2, default=_json_default)

        # Write Markdown report
        md_lines = [
            f"# Lead Discovery Report",
            f"",
            f"**Run ID:** {run_id}",
            f"**Generated At:** {summary.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"## Summary",
            f"",
            f"| 項目 | 件数 |",
            f"|------|------|",
            f"| 対象企業数 | {total} |",
            f"| サイト取得成功 | {valid_sites} |",
            f"| メール取得 | {emails_found} |",
            f"| 問い合わせページあり | {contact_pages} |",
            f"| HIGH優先度 | {high_priority} |",
            f"| MEDIUM優先度 | {medium_priority} |",
            f"| LOW優先度 | {low_priority} |",
            f"",
            f"## Top Leads",
            f"",
            f"| 企業名 | スコア | 優先度 | メール | URL |",
            f"|--------|--------|--------|--------|-----|",
        ]
        for lead in top_leads:
            md_lines.append(
                f"| {lead['company_name']} | {lead['score']:.1f} | {lead['priority']} "
                f"| {lead['contact_email'] or '-'} | {lead['homepage_url'] or '-'} |"
            )

        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines) + "\n")

        # Console output
        print(f"\n{'='*50}")
        print(f"Lead Discovery Report - {run_id}")
        print(f"{'='*50}")
        print(f"  Total companies  : {total}")
        print(f"  Valid sites      : {valid_sites}")
        print(f"  Emails found     : {emails_found}")
        print(f"  Contact pages    : {contact_pages}")
        print(f"  HIGH priority    : {high_priority}")
        print(f"  MEDIUM priority  : {medium_priority}")
        print(f"  LOW priority     : {low_priority}")
        if top_leads:
            print(f"\n  Top Leads:")
            for i, lead in enumerate(top_leads, 1):
                print(f"    {i}. {lead['company_name']} (score={lead['score']:.1f}, {lead['priority']})")
        print(f"{'='*50}\n")
        print(f"  JSON report: {json_path}")
        print(f"  MD report  : {md_path}")

        self.logger.info(f"Discovery report generated: {json_path}")
        return summary
