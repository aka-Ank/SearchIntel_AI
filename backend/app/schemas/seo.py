from datetime import datetime

from pydantic import BaseModel


class AuditRunRead(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    website_id: str
    status: str
    pages_total: int
    pages_processed: int
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None


class AuditFindingRead(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    website_id: str
    page_id: str | None
    audit_run_id: str
    rule_id: str
    severity: str
    affected_url: str
    explanation: str
    evidence: dict[str, object]
    recommended_action: str
    detected_at: datetime


class AuditSummaryRead(BaseModel):
    audit_run: AuditRunRead
    total_findings: int
    by_severity: dict[str, int]
    by_rule: dict[str, int]
