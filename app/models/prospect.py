from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class ProspectStatus(str, Enum):
    NEW = "new"
    ENRICHED = "enriched"
    SCORED = "scored"
    FIRST_SENT = "first_sent"
    REPLIED = "replied"
    INTERESTED = "interested"
    FOLLOWUP_READY = "followup_ready"
    FOLLOWUP_SENT = "followup_sent"
    CLOSED = "closed"
    UNSUBSCRIBED = "unsubscribed"


class ReplyLabel(str, Enum):
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    QUESTION = "question"
    UNSUBSCRIBE = "unsubscribe"
    OUT_OF_OFFICE = "out_of_office"
    OTHER = "other"


class Prospect(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_name: str
    website: str = ""
    contact_name: str = ""
    contact_email: str = ""
    industry: str = ""
    notes: str = ""
    status: ProspectStatus = ProspectStatus.NEW
    score: float = 0.0
    score_reason: str = ""
    priority: str = "medium"  # high/medium/low
    email_subject: str = ""
    email_body: str = ""
    sent_at: Optional[datetime] = None
    reply_text: str = ""
    reply_label: Optional[ReplyLabel] = None
    reply_confidence: float = 0.0
    requires_human: bool = False
    followup_count: int = 0
    followup_body: str = ""
    thread_id: str = ""
    message_id: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    error: str = ""
    metadata: dict = {}
