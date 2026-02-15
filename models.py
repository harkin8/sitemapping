"""Pydantic models for request/response schemas."""

from pydantic import BaseModel
from typing import Optional


class AccountIn(BaseModel):
    account_name: str
    domain: Optional[str] = None
    account_id: Optional[str] = None


class CampaignCreate(BaseModel):
    name: str
    created_by: Optional[str] = None
    accounts: list[AccountIn]


class CampaignOut(BaseModel):
    id: str
    name: str
    status: str
    created_by: Optional[str]
    account_count: int


class CampaignStatus(BaseModel):
    id: str
    name: str
    status: str
    account_count: int
    accounts_sent: int
    enriched_people_count: int
    stable: bool  # True if count hasn't changed in 3 consecutive polls


class ClayWebhookPayload(BaseModel):
    campaign_id: str
    account_name: Optional[str] = None
    account_id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    job_title: Optional[str] = None
    persona: Optional[str] = None
    persona_score: Optional[str] = None
    company_domain: Optional[str] = None
    domain: Optional[str] = None
    linkedin_profile: Optional[str] = None
    enrich_person: Optional[str] = None
    final_location: Optional[str] = None
