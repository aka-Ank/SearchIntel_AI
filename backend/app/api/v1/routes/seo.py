from fastapi import APIRouter, HTTPException, Query

from app.schemas.seo import AuditFindingRead, AuditRunRead, AuditSummaryRead
from app.services.container import get_container

router = APIRouter()


@router.get("/websites/{website_id}/seo-audits", response_model=list[AuditRunRead])
def list_website_seo_audits(
    website_id: str, tenant_id: str = Query(...)
) -> list[AuditRunRead]:
    runs = get_container().seo_audits.list_runs(tenant_id=tenant_id, website_id=website_id)
    if runs is None:
        raise HTTPException(status_code=404, detail="Website not found")
    return runs


@router.post("/websites/{website_id}/seo-audits", response_model=AuditRunRead, status_code=202)
async def start_seo_audit(website_id: str, tenant_id: str = Query(...)) -> AuditRunRead:
    try:
        run = await get_container().seo_audits.enqueue(tenant_id=tenant_id, website_id=website_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if run is None:
        raise HTTPException(status_code=404, detail="Website not found")
    return run


@router.get("/seo-audits/{audit_run_id}", response_model=AuditRunRead)
def get_seo_audit(audit_run_id: str, tenant_id: str = Query(...)) -> AuditRunRead:
    run = get_container().seo_audits.get_run(tenant_id=tenant_id, audit_run_id=audit_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="SEO audit not found")
    return run


@router.get("/seo-audits/{audit_run_id}/findings", response_model=list[AuditFindingRead])
def list_seo_findings(
    audit_run_id: str,
    tenant_id: str = Query(...),
    severity: str | None = Query(default=None, pattern="^(info|warning|error)$"),
    rule_id: str | None = Query(default=None),
    page_id: str | None = Query(default=None),
) -> list[AuditFindingRead]:
    findings = get_container().seo_audits.list_findings(
        tenant_id=tenant_id,
        audit_run_id=audit_run_id,
        severity=severity,
        rule_id=rule_id,
        page_id=page_id,
    )
    if findings is None:
        raise HTTPException(status_code=404, detail="SEO audit not found")
    return findings


@router.get("/seo-audits/{audit_run_id}/summary", response_model=AuditSummaryRead)
def get_seo_summary(audit_run_id: str, tenant_id: str = Query(...)) -> AuditSummaryRead:
    summary = get_container().seo_audits.summary(tenant_id=tenant_id, audit_run_id=audit_run_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="SEO audit not found")
    return summary


@router.get("/pages/{page_id}/seo-findings", response_model=list[AuditFindingRead])
def get_page_seo_findings(page_id: str, tenant_id: str = Query(...)) -> list[AuditFindingRead]:
    findings = get_container().seo_audits.page_findings(tenant_id=tenant_id, page_id=page_id)
    if findings is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return findings
