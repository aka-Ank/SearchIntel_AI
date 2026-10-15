from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.crawler.parser import parse_html
from app.models.common import WebsiteType
from app.models.page import ContentChunk
from app.processing.chunking import StructureAwareChunker
from app.repositories.pages import ChunkRepository, PageRepository
from app.repositories.projects import ProjectRepository
from app.repositories.websites import WebsiteRepository


def test_project_website_page_and_chunk_persistence(
    session_factory: sessionmaker[Session],
) -> None:
    html = """
    <html><head><title>Persistent SEO</title></head>
    <body><h1>Persistent SEO</h1><p>PostgreSQL stores crawled SEO content.</p></body></html>
    """
    with session_factory() as session:
        project = ProjectRepository(session).create(tenant_id="tenant-a", name="Site")
        website = WebsiteRepository(session).create(
            tenant_id="tenant-a",
            project_id=project.id,
            base_url="https://example.com",
            website_type=WebsiteType.own,
        )
        parsed = parse_html("https://example.com", html)
        page, changed = PageRepository(session).upsert_parsed_page(
            tenant_id="tenant-a",
            project_id=project.id,
            website_id=website.id,
            fetched_url="https://example.com/",
            normalized_url="https://example.com/",
            status_code=200,
            content_type="text/html",
            parsed=parsed,
        )
        chunks = StructureAwareChunker(target_chars=200).chunk_page(
            tenant_id="tenant-a",
            project_id=project.id,
            website_id=website.id,
            page_id=page.id,
            page=parsed,
        )
        ChunkRepository(session).replace_for_page(page_id=page.id, chunks=chunks)
        session.commit()

    with session_factory() as session:
        assert ProjectRepository(session).get(tenant_id="tenant-a", project_id=project.id)
        assert WebsiteRepository(session).get(tenant_id="tenant-a", website_id=website.id)
        assert PageRepository(session).get(tenant_id="tenant-a", page_id=page.id)
        assert changed is True
        assert len(session.scalars(select(ContentChunk)).all()) == len(chunks)


def test_unchanged_page_reports_no_processing_needed(
    session_factory: sessionmaker[Session],
) -> None:
    html = "<html><body><h1>Same</h1><p>Stable content hash.</p></body></html>"
    parsed = parse_html("https://example.com", html)
    with session_factory() as session:
        project = ProjectRepository(session).create(tenant_id="tenant-a", name="Site")
        website = WebsiteRepository(session).create(
            tenant_id="tenant-a",
            project_id=project.id,
            base_url="https://example.com",
            website_type=WebsiteType.own,
        )
        repo = PageRepository(session)
        page, first_changed = repo.upsert_parsed_page(
            tenant_id="tenant-a",
            project_id=project.id,
            website_id=website.id,
            fetched_url="https://example.com/",
            normalized_url="https://example.com/",
            status_code=200,
            content_type="text/html",
            parsed=parsed,
        )
        same_page, second_changed = repo.upsert_parsed_page(
            tenant_id="tenant-a",
            project_id=project.id,
            website_id=website.id,
            fetched_url="https://example.com/",
            normalized_url="https://example.com/",
            status_code=200,
            content_type="text/html",
            parsed=parsed,
        )

    assert page.id == same_page.id
    assert first_changed is True
    assert second_changed is False
