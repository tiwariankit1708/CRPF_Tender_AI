"""
CRPF Tender AI — Pydantic Schemas
Strict-typed models for all API request/response payloads.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Verdict(str, Enum):
    eligible = "eligible"
    not_eligible = "not_eligible"
    manual_review = "manual_review"


class OverallStatus(str, Enum):
    eligible = "eligible"
    not_eligible = "not_eligible"
    manual_review = "manual_review"


# ---------------------------------------------------------------------------
# Criteria (Agent A output)
# ---------------------------------------------------------------------------

class CriterionItem(BaseModel):
    """A single eligibility criterion extracted from a tender document."""
    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str
    threshold: Optional[str] = None
    is_mandatory: bool = True
    weight: float = Field(default=1.0, ge=0.0, le=1.0)


class TenderCriteria(BaseModel):
    """Structured criteria returned by Agent A."""
    model_config = ConfigDict(populate_by_name=True)

    tender_id: str
    filename: str
    technical_criteria: list[CriterionItem] = []
    financial_criteria: list[CriterionItem] = []
    compliance_criteria: list[CriterionItem] = []
    extracted_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Bidder Data (Agent B output)
# ---------------------------------------------------------------------------

class ConfidenceScores(BaseModel):
    annual_turnover: float = Field(default=0.0, ge=0.0, le=1.0)
    projects_completed: float = Field(default=0.0, ge=0.0, le=1.0)
    certifications: float = Field(default=0.0, ge=0.0, le=1.0)
    registration_number: float = Field(default=0.0, ge=0.0, le=1.0)


class BidderData(BaseModel):
    """Extracted bidder facts returned by Agent B."""
    model_config = ConfigDict(populate_by_name=True)

    bidder_id: str
    tender_id: str
    filename: str
    annual_turnover: Optional[str] = None
    projects_completed: Optional[int] = None
    certifications: list[str] = []
    registration_number: Optional[str] = None
    additional_fields: dict = {}
    confidence_scores: ConfidenceScores = Field(default_factory=ConfidenceScores)
    parsed_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Evaluation (Agent C output)
# ---------------------------------------------------------------------------

class CriteriaResult(BaseModel):
    """Evaluation result for a single criterion."""
    model_config = ConfigDict(populate_by_name=True)

    criterion_name: str
    criterion_type: str  # technical / financial / compliance
    is_mandatory: bool = True
    verdict: Verdict
    reason: str  # Always populated — especially for not_eligible
    evidence_field: Optional[str] = None
    extracted_value: Optional[str] = None
    threshold: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class BidderEvaluationResult(BaseModel):
    """Full evaluation audit object for a single bidder."""
    model_config = ConfigDict(populate_by_name=True)

    bidder_id: str
    tender_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    criteria_results: list[CriteriaResult] = []
    overall_status: OverallStatus = OverallStatus.manual_review
    rejection_reasons: list[str] = []  # Clear list of why not eligible


# ---------------------------------------------------------------------------
# Audit (Agent D output)
# ---------------------------------------------------------------------------

class FlaggedItem(BaseModel):
    """A single item flagged by the auditor for human review."""
    criterion_name: str
    current_verdict: Verdict
    confidence: float
    review_note: str
    evidence_field: Optional[str] = None


class AuditResult(BaseModel):
    """Audit findings for a tender evaluation."""
    model_config = ConfigDict(populate_by_name=True)

    tender_id: str
    bidder_id: str
    flagged_items: list[FlaggedItem] = []
    human_review_required: bool = False
    audited_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Final Report
# ---------------------------------------------------------------------------

class BidderSummary(BaseModel):
    bidder_id: str
    overall_status: OverallStatus
    rejection_reasons: list[str] = []
    flagged_count: int = 0
    human_review_required: bool = False


class FinalReport(BaseModel):
    """Complete report with full audit trail."""
    model_config = ConfigDict(populate_by_name=True)

    tender_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_bidders: int = 0
    eligible_count: int = 0
    not_eligible_count: int = 0
    manual_review_count: int = 0
    bidder_summaries: list[BidderSummary] = []
    report_pdf_path: Optional[str] = None


# ---------------------------------------------------------------------------
# API Request / Response helpers
# ---------------------------------------------------------------------------

class TenderUpload(BaseModel):
    """Response after uploading a tender PDF."""
    tender_id: str
    filename: str
    criteria: TenderCriteria


class BidderUpload(BaseModel):
    """Response after uploading a bidder PDF."""
    bidder_id: str
    tender_id: str
    filename: str
    bidder_data: BidderData


class DashboardData(BaseModel):
    """All data needed for the React dashboard."""
    tender_id: str
    criteria: Optional[TenderCriteria] = None
    bidders: list[BidderData] = []
    evaluations: list[BidderEvaluationResult] = []
    audits: list[AuditResult] = []
    report: Optional[FinalReport] = None
