import json
import logging
import os
from datetime import datetime

from app.models.prospect import Prospect, ProspectStatus

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.join("data", "output")


class ReportAgent:
    def __init__(self, config: dict):
        self.config = config

    def generate(self, prospects: list[Prospect]) -> dict:
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        total = len(prospects)

        sent = sum(
            1 for p in prospects
            if p.status not in (ProspectStatus.NEW, ProspectStatus.ENRICHED, ProspectStatus.SCORED)
        )
        replied = sum(
            1 for p in prospects
            if p.status in (
                ProspectStatus.REPLIED,
                ProspectStatus.INTERESTED,
                ProspectStatus.FOLLOWUP_READY,
                ProspectStatus.FOLLOWUP_SENT,
                ProspectStatus.CLOSED,
            )
        )
        interested = sum(
            1 for p in prospects
            if p.status in (
                ProspectStatus.INTERESTED,
                ProspectStatus.FOLLOWUP_READY,
                ProspectStatus.FOLLOWUP_SENT,
            )
            or (p.reply_label and p.reply_label.value == "interested")
        )
        not_interested = sum(
            1 for p in prospects
            if p.reply_label and p.reply_label.value == "not_interested"
        )
        unsubscribed = sum(
            1 for p in prospects
            if p.status == ProspectStatus.UNSUBSCRIBED
        )

        reply_rate = replied / sent if sent > 0 else 0.0
        positive_rate = interested / replied if replied > 0 else 0.0

        # By status counts
        by_status: dict[str, int] = {}
        for p in prospects:
            key = p.status.value
            by_status[key] = by_status.get(key, 0) + 1

        # By priority counts
        by_priority: dict[str, int] = {}
        for p in prospects:
            key = p.priority
            by_priority[key] = by_priority.get(key, 0) + 1

        # High score prospects
        top_prospects = sorted(
            [p for p in prospects if p.score > 0],
            key=lambda p: p.score,
            reverse=True,
        )[:10]

        report = {
            "generated_at": datetime.now().isoformat(),
            "total": total,
            "sent": sent,
            "replied": replied,
            "interested": interested,
            "not_interested": not_interested,
            "unsubscribed": unsubscribed,
            "reply_rate": round(reply_rate, 4),
            "positive_rate": round(positive_rate, 4),
            "by_status": by_status,
            "by_priority": by_priority,
            "top_prospects": [
                {
                    "company": p.company_name,
                    "email": p.contact_email,
                    "score": p.score,
                    "priority": p.priority,
                    "status": p.status.value,
                }
                for p in top_prospects
            ],
        }

        date_str = datetime.now().strftime("%Y%m%d")
        json_path = os.path.join(OUTPUT_DIR, f"report_{date_str}.json")
        md_path = os.path.join(OUTPUT_DIR, f"report_{date_str}.md")

        # Write JSON
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info(f"Report JSON saved to {json_path}")
        except Exception as e:
            logger.error(f"Failed to write JSON report: {e}")

        # Write Markdown
        try:
            md_content = self._build_markdown(report)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            logger.info(f"Report Markdown saved to {md_path}")
        except Exception as e:
            logger.error(f"Failed to write Markdown report: {e}")

        # Print summary to console
        self._print_summary(report)

        return report

    def _build_markdown(self, report: dict) -> str:
        lines = [
            f"# Sales Hunter レポート",
            f"",
            f"生成日時: {report['generated_at']}",
            f"",
            f"## サマリー",
            f"",
            f"| 指標 | 値 |",
            f"|------|-----|",
            f"| 総リード数 | {report['total']} |",
            f"| 送信済み | {report['sent']} |",
            f"| 返信あり | {report['replied']} |",
            f"| 興味あり | {report['interested']} |",
            f"| 興味なし | {report['not_interested']} |",
            f"| 配信停止 | {report['unsubscribed']} |",
            f"| 返信率 | {report['reply_rate']:.1%} |",
            f"| ポジティブ率 | {report['positive_rate']:.1%} |",
            f"",
            f"## ステータス別",
            f"",
        ]
        for status, count in sorted(report["by_status"].items()):
            lines.append(f"- {status}: {count}")

        lines += [
            f"",
            f"## 優先度別",
            f"",
        ]
        for priority, count in sorted(report["by_priority"].items()):
            lines.append(f"- {priority}: {count}")

        lines += [
            f"",
            f"## スコアTOP10",
            f"",
            f"| 会社名 | スコア | 優先度 | ステータス |",
            f"|--------|--------|--------|------------|",
        ]
        for p in report["top_prospects"]:
            lines.append(
                f"| {p['company']} | {p['score']:.1f} | {p['priority']} | {p['status']} |"
            )

        return "\n".join(lines) + "\n"

    def _print_summary(self, report: dict):
        print("\n" + "=" * 50)
        print("  Sales Hunter レポート")
        print("=" * 50)
        print(f"  総リード数   : {report['total']}")
        print(f"  送信済み     : {report['sent']}")
        print(f"  返信あり     : {report['replied']}")
        print(f"  興味あり     : {report['interested']}")
        print(f"  返信率       : {report['reply_rate']:.1%}")
        print(f"  ポジティブ率 : {report['positive_rate']:.1%}")
        print("=" * 50 + "\n")
