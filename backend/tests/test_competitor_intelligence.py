from types import SimpleNamespace

from app.models.page import Page
from app.models.project import Project
from app.models.tenant import Tenant
from app.models.website import Website
from app.services.competitor_intelligence import CompetitorIntelligenceService


def test_competitor_coverage_returns_evidence_and_is_tenant_scoped(session_factory) -> None:
    with session_factory.begin() as session:
        tenant = Tenant(id="tenant-a", name="Tenant A")
        project = Project(id="project-a", tenant_id=tenant.id, name="Project A")
        own = Website(
            id="own-a",
            tenant_id=tenant.id,
            project_id=project.id,
            base_url="https://ours.test",
            domain="ours.test",
            website_type="OWN",
        )
        competitor = Website(
            id="competitor-a",
            tenant_id=tenant.id,
            project_id=project.id,
            base_url="https://rival.test",
            domain="rival.test",
            website_type="COMPETITOR",
        )
        session.add_all([tenant, project, own, competitor])
        session.flush()
        session.add_all(
            [
                Page(
                    id="page-own",
                    tenant_id=tenant.id,
                    project_id=project.id,
                    website_id=own.id,
                    url="https://ours.test/",
                    normalized_url="https://ours.test/",
                    title="Analytics reporting overview",
                    status_code=200,
                    content_type="text/html",
                    normalized_text="Analytics reporting for clear weekly business results.",
                    content_hash="a" * 64,
                    word_count=7,
                ),
                Page(
                    id="page-competitor",
                    tenant_id=tenant.id,
                    project_id=project.id,
                    website_id=competitor.id,
                    url="https://rival.test/quantum",
                    normalized_url="https://rival.test/quantum",
                    title="Quantum analytics platform",
                    status_code=200,
                    content_type="text/html",
                    normalized_text="Quantum analytics dashboard for scientific laboratories.",
                    content_hash="b" * 64,
                    word_count=7,
                ),
            ]
        )

    service = CompetitorIntelligenceService(session_factory)
    report = service.compare(tenant_id="tenant-a", project_id="project-a")
    assert report is not None
    rival = report.competitors[0]
    candidate = next(topic for topic in rival.topics if topic.phrase == "quantum")
    assert candidate.coverage == "competitor_only"
    assert candidate.evidence[0].page_id == "page-competitor"
    assert "Quantum analytics" in candidate.evidence[0].snippet
    assert candidate.recommended_action is not None
    assert "does not establish demand" in candidate.recommended_action
    assert service.compare(tenant_id="other-tenant", project_id="project-a") is None

    class SemanticStub:
        metadata = SimpleNamespace(provider="sentence_transformers")

        def embed_batch(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, 0.0] for _ in texts]

    semantic_report = CompetitorIntelligenceService(
        session_factory,
        embedding_provider=SemanticStub(),  # type: ignore[arg-type]
    ).compare(tenant_id="tenant-a", project_id="project-a")
    assert semantic_report is not None
    semantic_topic = next(
        topic for topic in semantic_report.competitors[0].topics if topic.phrase == "quantum"
    )
    assert semantic_topic.coverage == "shared"
    assert semantic_topic.match_method == "semantic_embedding"
    assert semantic_topic.recommended_action is None
