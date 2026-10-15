from __future__ import annotations

import argparse

from sqlalchemy import select

from app.models.page import ContentChunk as ContentChunkModel
from app.models.page import Page
from app.repositories.pages import ChunkRepository
from app.services.container import get_container


def main() -> None:
    parser = argparse.ArgumentParser(description="SearchIntel maintenance commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    reindex_parser = subparsers.add_parser(
        "reindex",
        help="Reindex persisted chunks into vector store",
    )
    reindex_parser.add_argument("--tenant", dest="tenant_id", required=True)
    reindex_parser.add_argument("--project", dest="project_id", required=True)
    reindex_parser.add_argument("--website", dest="website_ids", action="append")

    args = parser.parse_args()
    if args.command == "reindex":
        count = reindex_project(
            tenant_id=args.tenant_id,
            project_id=args.project_id,
            website_ids=args.website_ids,
        )
        print(f"Reindexed {count} chunks")


def reindex_project(
    *,
    tenant_id: str,
    project_id: str,
    website_ids: list[str] | None = None,
) -> int:
    container = get_container()
    with container.session_factory() as session:
        statement = (
            select(ContentChunkModel, Page.url, Page.title)
            .join(Page, Page.id == ContentChunkModel.page_id)
            .where(
                ContentChunkModel.tenant_id == tenant_id,
                ContentChunkModel.project_id == project_id,
            )
        )
        if website_ids:
            statement = statement.where(ContentChunkModel.website_id.in_(website_ids))
        rows = session.execute(statement).all()
        repo = ChunkRepository(session)
        chunks = [repo.to_schema(model, url=url, title=title) for model, url, title in rows]
    container.retrieval.index_chunks(chunks)
    return len(chunks)


if __name__ == "__main__":
    main()
