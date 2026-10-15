from __future__ import annotations

from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.url_security import UrlSafetyPolicy
from app.crawler.fetcher import HttpxFetcher
from app.crawler.site_crawler import WebsiteCrawler
from app.db.base import Base
from app.db.session import create_app_engine, create_session_factory
from app.embeddings.providers import (
    DeterministicEmbeddingProvider,
    EmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
)
from app.llm.providers import LLMProvider, MockLLMProvider, OpenAICompatibleProvider
from app.models.page import ContentChunk as ContentChunkModel
from app.models.page import Page
from app.processing.chunking import StructureAwareChunker
from app.rag.context import ContextBuilder
from app.rag.service import GroundedRAGService
from app.repositories.pages import ChunkRepository
from app.reranking.providers import CrossEncoderReranker, NoOpReranker, Reranker
from app.retrieval.bm25 import BM25Index
from app.retrieval.service import RetrievalService
from app.retrieval.vector_store import InMemoryVectorStore, QdrantVectorStore, VectorStore
from app.schemas.content import ContentChunk
from app.services.competitor_intelligence import CompetitorIntelligenceService
from app.services.crawling import CrawlService
from app.services.indexing import IndexingService
from app.services.pages import PageService
from app.services.projects import ProjectService
from app.services.seo_audits import SeoAuditService


class ServiceContainer:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        settings = get_settings()
        if session_factory is None:
            engine = create_app_engine(settings.database_url)
            if settings.database_url.startswith("sqlite"):
                Base.metadata.create_all(engine)
            session_factory = create_session_factory(engine)
        self.session_factory = session_factory

        embedding_provider = _build_embedding_provider(settings)
        selected_vector_store = vector_store or _build_vector_store(settings)

        self.projects = ProjectService(self.session_factory)
        self.competitors = CompetitorIntelligenceService(
            self.session_factory,
            embedding_provider=embedding_provider,
        )
        self.pages = PageService(self.session_factory)
        self.retrieval = RetrievalService(
            embedding_provider=embedding_provider,
            vector_store=selected_vector_store,
            bm25_index=BM25Index(),
            persisted_chunk_loader=self._load_chunks_for_bm25,
            reranker=_build_reranker(settings),
            bm25_top_k=settings.bm25_top_k,
            dense_top_k=settings.dense_top_k,
            fusion_top_k=settings.fusion_top_k,
            rerank_top_k=settings.rerank_top_k,
        )
        self.rag = GroundedRAGService(
            retrieval_service=self.retrieval,
            llm_provider=_build_llm_provider(settings),
            context_builder=ContextBuilder(max_chars=settings.rag_context_max_chars),
        )
        fetcher = HttpxFetcher(
            user_agent=settings.crawler_user_agent,
            timeout_seconds=settings.crawler_timeout_seconds,
            max_response_bytes=settings.crawler_max_response_bytes,
            safety_policy=UrlSafetyPolicy(allow_local_urls=settings.allow_local_urls),
        )
        self.indexing = IndexingService(
            session_factory=self.session_factory,
            fetcher=fetcher,
            chunker=StructureAwareChunker(),
            retrieval_service=self.retrieval,
        )
        self.crawling = CrawlService(
            session_factory=self.session_factory,
            crawler=WebsiteCrawler(
                fetcher=fetcher,
                safety_policy=UrlSafetyPolicy(allow_local_urls=settings.allow_local_urls),
                request_delay_seconds=settings.crawler_request_delay_seconds,
            ),
            indexing_service=self.indexing,
        )
        self.seo_audits = SeoAuditService(
            session_factory=self.session_factory,
            fetcher=fetcher,
            safety_policy=UrlSafetyPolicy(allow_local_urls=settings.allow_local_urls),
        )

    def _load_chunks_for_bm25(
        self,
        tenant_id: str,
        project_id: str,
        website_ids: list[str] | None,
    ) -> list[ContentChunk]:
        with self.session_factory() as session:
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
            chunk_repo = ChunkRepository(session)
            return [chunk_repo.to_schema(model, url=url, title=title) for model, url, title in rows]


def _build_vector_store(settings: Settings) -> VectorStore:
    provider = settings.vector_store_provider.lower()
    if provider == "qdrant":
        return QdrantVectorStore(
            url=settings.qdrant_url,
            collection_name=settings.qdrant_collection,
            vector_size=settings.embedding_dimensions,
            embedding_version=settings.embedding_version,
        )
    return InMemoryVectorStore()


def _build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    provider = settings.embedding_provider.lower()
    if provider in {"sentence_transformers", "sentence-transformers"}:
        return SentenceTransformerEmbeddingProvider(
            model_name=settings.embedding_model,
            version=settings.embedding_version,
        )
    return DeterministicEmbeddingProvider(
        dimensions=settings.embedding_dimensions,
        version=settings.embedding_version,
    )


def _build_reranker(settings: Settings) -> Reranker:
    provider = settings.reranker_provider.lower()
    if provider in {"cross_encoder", "cross-encoder"}:
        return CrossEncoderReranker(model_name=settings.reranker_model)
    return NoOpReranker()


def _build_llm_provider(settings: Settings) -> LLMProvider:
    provider = settings.llm_provider.lower()
    if provider == "mock":
        return MockLLMProvider()
    if provider in {"openai", "openai_compatible"}:
        api_key = settings.llm_api_key
        if api_key is None or not api_key.get_secret_value():
            raise ValueError("LLM_API_KEY is required for the configured real LLM provider")
        return OpenAICompatibleProvider(
            api_key=api_key.get_secret_value(),
            model=settings.llm_model,
            base_url=settings.llm_api_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
            input_cost_per_million=settings.llm_input_cost_per_million,
            output_cost_per_million=settings.llm_output_cost_per_million,
        )
    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


@lru_cache
def get_container() -> ServiceContainer:
    return ServiceContainer()
