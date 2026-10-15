from pydantic import BaseModel, Field

from app.schemas.retrieval import RetrievalStrategy, RetrievedChunkResult


class RAGQueryRequest(BaseModel):
    tenant_id: str
    project_id: str
    question: str = Field(min_length=1)
    search_strategy: RetrievalStrategy = RetrievalStrategy.hybrid_rerank
    top_k: int = Field(default=5, ge=1, le=20)
    website_ids: list[str] | None = None
    include_debug: bool = False


class Citation(BaseModel):
    citation_number: int
    page_title: str | None
    url: str
    page_id: str
    chunk_id: str
    heading_path: list[str]
    supporting_snippet: str


class RAGUsage(BaseModel):
    provider: str = "none"
    model: str = "none"
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    estimated_cost_usd: float | None = None


class RAGQueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    retrieval_strategy: RetrievalStrategy
    retrieved_chunks: list[RetrievedChunkResult]
    latency_ms: float
    grounded: bool = True
    usage: RAGUsage = Field(default_factory=RAGUsage)
    debug: dict[str, float | int | str] = Field(default_factory=dict)
