from __future__ import annotations
import csv
import json
import logging
import os
from datetime import datetime, date
from app.models.lead import LeadRecord


def _json_default(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class LeadRepository:
    def __init__(self, output_dir: str = "data/output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self._records: dict[str, LeadRecord] = {}  # key: homepage_url or company_name

    def _key(self, lead: LeadRecord) -> str:
        return lead.homepage_url.strip().lower().rstrip("/") if lead.homepage_url else lead.company_name.strip().lower()

    def upsert(self, lead: LeadRecord):
        key = self._key(lead)
        if key in self._records:
            lead = lead.model_copy(update={"updated_at": datetime.now()})
        self._records[key] = lead

    def get_all(self) -> list[LeadRecord]:
        return list(self._records.values())

    def save_csv(self, filename: str = None) -> str:
        if filename is None:
            date_str = datetime.now().strftime("%Y%m%d")
            filename = f"leads_{date_str}.csv"
        filepath = os.path.join(self.output_dir, filename)

        records = self.get_all()
        if not records:
            self.logger.info("No records to save to CSV.")
            return filepath

        # Use all fields from LeadRecord schema
        fieldnames = list(LeadRecord.model_fields.keys())

        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for record in records:
                row = record.model_dump()
                # Convert datetimes to strings
                for k, v in row.items():
                    if isinstance(v, datetime):
                        row[k] = v.isoformat()
                    elif hasattr(v, "value"):
                        row[k] = v.value
                writer.writerow(row)

        self.logger.info(f"Saved {len(records)} leads to CSV: {filepath}")
        return filepath

    def save_json(self, filename: str = None) -> str:
        if filename is None:
            date_str = datetime.now().strftime("%Y%m%d")
            filename = f"leads_{date_str}.json"
        filepath = os.path.join(self.output_dir, filename)

        records = self.get_all()
        data = [r.model_dump() for r in records]

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=_json_default)

        self.logger.info(f"Saved {len(records)} leads to JSON: {filepath}")
        return filepath

    def load_json(self, filepath: str):
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                record = LeadRecord(**item)
                self._records[self._key(record)] = record
            self.logger.info(f"Loaded {len(data)} leads from {filepath}")
        except FileNotFoundError:
            self.logger.warning(f"JSON file not found: {filepath}")
        except Exception as e:
            self.logger.error(f"Failed to load JSON {filepath}: {e}")
