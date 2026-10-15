from enum import StrEnum

from pydantic import BaseModel, Field


class RetrievalStrategy(StrEnum):
    bm25 = "bm25"
    dense = "dense"
    vector = "vector"
    hybrid = "hybrid"
    hybrid_rerank = "hybrid_rerank"


class SearchRequest(BaseModel):
    tenant_id: str
    project_id: str
    query: str = Field(min_length=1)
    strategy: RetrievalStrategy = RetrievalStrategy.hybrid
    top_k: int = Field(default=5, ge=1, le=50)
    website_ids: list[str] | None = None
    include_debug: bool = False


class RetrievedChunkResult(BaseModel):
    chunk_id: str
    tenant_id: str
    project_id: str
    website_id: str
    page_id: str
    url: str
    title: str | None
    heading_path: list[str] = Field(default_factory=list)
    snippet: str
    content: str
    score: float
    source_scores: dict[str, float] = Field(default_factory=dict)
    debug: dict[str, float | int | str] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    strategy: RetrievalStrategy
    results: list[RetrievedChunkResult]
