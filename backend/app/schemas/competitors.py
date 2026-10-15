from pydantic import BaseModel


class TopicEvidence(BaseModel):
    page_id: str
    url: str
    title: str | None
    snippet: str


class TopicCoverage(BaseModel):
    phrase: str
    coverage: str
    match_method: str
    page_count: int
    evidence: list[TopicEvidence]


class CompetitorWebsiteCoverage(BaseModel):
    website_id: str
    domain: str
    pages_indexed: int
    topics: list[TopicCoverage]


class CompetitorCoverageResponse(BaseModel):
    project_id: str
    own_website_id: str | None
    own_pages_indexed: int
    competitors: list[CompetitorWebsiteCoverage]
    limitations: list[str]
