from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class SourceType(str, Enum):
    CSV = "csv"
    WEB_SEARCH = "web_search"
    MANUAL = "manual"


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DiscoveryQuery(BaseModel):
    query: str
    industry: str = ""
    region: str = ""
    source_type: SourceType = SourceType.WEB_SEARCH


class CompanyCandidate(BaseModel):
    id: str  # uuid4
    company_name: str
    homepage_url: str = ""
    source_type: SourceType = SourceType.CSV
    source_query: str = ""
    industry: str = ""
    notes: str = ""
    created_at: datetime = Field(default_factory=datetime.now)


class WebsiteSnapshot(BaseModel):
    url: str
    status_code: int = 0
    title: str = ""
    meta_description: str = ""
    body_text: str = ""  # first 3000 chars
    links: list = Field(default_factory=list)  # list of hrefs
    fetch_success: bool = False
    error: str = ""
    fetched_at: datetime = Field(default_factory=datetime.now)


class ContactInfo(BaseModel):
    contact_email: str = ""
    contact_page_url: str = ""
    company_page_url: str = ""
    phone_number: str = ""
    extraction_confidence: float = 0.0


class CompanyProfile(BaseModel):
    business_summary: str = ""
    likely_b2b: bool = False
    likely_needs_outsourcing: bool = False
    profile_notes: str = ""


class ScoreResult(BaseModel):
    score: float = 0.0
    priority: Priority = Priority.LOW
    score_reason: str = ""


class LeadRecord(BaseModel):
    id: str  # uuid4
    company_name: str
    homepage_url: str = ""
    source_type: SourceType = SourceType.CSV
    source_query: str = ""
    industry: str = ""
    business_summary: str = ""
    contact_email: str = ""
    contact_page_url: str = ""
    company_page_url: str = ""
    phone_number: str = ""
    likely_b2b: bool = False
    likely_needs_outsourcing: bool = False
    profile_notes: str = ""
    score: float = 0.0
    priority: Priority = Priority.LOW
    score_reason: str = ""
    fetch_success: bool = False
    error: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class DiscoveryRunState(BaseModel):
    run_id: str
    started_at: datetime
    total_candidates: int = 0
    fetched: int = 0
    fetch_failed: int = 0
    emails_found: int = 0
    contact_pages_found: int = 0
    scored: int = 0
    high_priority: int = 0
    errors: list = Field(default_factory=list)


class ReportSummary(BaseModel):
    run_id: str
    generated_at: datetime
    total_companies: int = 0
    valid_sites: int = 0
    emails_found: int = 0
    contact_pages_found: int = 0
    high_priority_leads: int = 0
    medium_priority_leads: int = 0
    low_priority_leads: int = 0
    top_leads: list = Field(default_factory=list)  # list of dicts
