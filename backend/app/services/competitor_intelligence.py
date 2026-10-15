from __future__ import annotations

import re
from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.embeddings.providers import EmbeddingProvider, cosine_similarity
from app.models.page import Page
from app.models.project import Project
from app.models.website import Website
from app.schemas.competitors import (
    CompetitorCoverageResponse,
    CompetitorWebsiteCoverage,
    TopicCoverage,
    TopicEvidence,
)

_WORD_RE = re.compile(r"[a-z][a-z0-9-]{2,}")
_STOPWORDS = frozenset(
    (
        "about after again all also and any are back been before being between both but can could"
        " did does each few for from further had has have having here how into its itself just more"
        " most other our out over own same she should some such than that the their them then there"
        " these they this those through too under until very was were what when where which while"
        " who"
        " will with would your website page home contact privacy terms search learn get guide using"
    ).split()
)


class CompetitorIntelligenceService:
    """Derive explainable phrase coverage from already-crawled tenant pages."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._embedding_provider = embedding_provider

    def compare(self, *, tenant_id: str, project_id: str) -> CompetitorCoverageResponse | None:
        with self._session_factory() as session:
            project = session.scalar(
                select(Project).where(
                    Project.id == project_id,
                    Project.tenant_id == tenant_id,
                )
            )
            if project is None:
                return None
            websites = list(
                session.scalars(
                    select(Website).where(
                        Website.tenant_id == tenant_id,
                        Website.project_id == project_id,
                    )
                )
            )
            own_sites = [website for website in websites if website.website_type == "OWN"]
            competitor_sites = [
                website for website in websites if website.website_type == "COMPETITOR"
            ]
            site_ids = [website.id for website in websites]
            pages = list(
                session.scalars(
                    select(Page)
                    .where(
                        Page.tenant_id == tenant_id,
                        Page.project_id == project_id,
                        Page.website_id.in_(site_ids),
                        Page.status_code < 400,
                    )
                    .order_by(Page.url)
                )
            )
            pages_by_site: dict[str, list[Page]] = defaultdict(list)
            for page in pages:
                pages_by_site[page.website_id].append(page)

            own_pages = [page for site in own_sites for page in pages_by_site[site.id]]
            own_topics = _topic_counts(own_pages)
            competitors: list[CompetitorWebsiteCoverage] = []
            for website in competitor_sites:
                site_pages = pages_by_site[website.id]
                counts = _topic_counts(site_pages)
                candidate_phrases = [phrase for phrase, _ in counts.most_common(20)]
                semantic_matches = self._semantic_matches(
                    own_topics=own_topics,
                    candidate_phrases=candidate_phrases,
                )
                topics: list[TopicCoverage] = []
                for phrase in candidate_phrases:
                    matching = [page for page in site_pages if _contains_phrase(page, phrase)]
                    coverage = (
                        "shared"
                        if own_topics[phrase] or phrase in semantic_matches
                        else "competitor_only"
                    )
                    match_method = (
                        "exact_phrase"
                        if own_topics[phrase]
                        else "semantic_embedding"
                        if phrase in semantic_matches
                        else "unmatched"
                    )
                    evidence = [
                        TopicEvidence(
                            page_id=page.id,
                            url=page.url,
                            title=page.title,
                            snippet=_evidence_snippet(page, phrase),
                        )
                        for page in matching[:3]
                    ]
                    topics.append(
                        TopicCoverage(
                            phrase=phrase,
                            coverage=coverage,
                            match_method=match_method,
                            page_count=len(matching),
                            evidence=evidence,
                            recommended_action=(
                                "Review the linked pages and decide whether this topic fits your "
                                "audience and content plan. Competitor coverage alone does not "
                                "establish demand or justify publication."
                                if coverage == "competitor_only"
                                else None
                            ),
                        )
                    )
                competitors.append(
                    CompetitorWebsiteCoverage(
                        website_id=website.id,
                        domain=website.domain,
                        pages_indexed=len(site_pages),
                        topics=topics,
                    )
                )

            return CompetitorCoverageResponse(
                project_id=project_id,
                own_website_id=own_sites[0].id if own_sites else None,
                own_pages_indexed=len(own_pages),
                competitors=competitors,
                limitations=[
                    "Topics are candidate phrases extracted from crawled titles and page text. "
                    "Semantic matches use the configured sentence-transformers provider; "
                    "otherwise only exact phrase overlap is considered.",
                    "A competitor-only phrase is a research candidate, not proof of demand, "
                    "ranking, or traffic. Suggested actions only prompt human review.",
                    "Only successfully crawled project pages are compared; crawl competitors "
                    "separately to improve coverage.",
                ],
            )

    def _semantic_matches(
        self, *, own_topics: Counter[str], candidate_phrases: list[str]
    ) -> set[str]:
        provider = self._embedding_provider
        if (
            provider is None
            or provider.metadata.provider != "sentence_transformers"
            or not own_topics
            or not candidate_phrases
        ):
            return set()
        own_phrases = [phrase for phrase, _ in own_topics.most_common(50)]
        vectors = provider.embed_batch([*own_phrases, *candidate_phrases])
        own_vectors = vectors[: len(own_phrases)]
        candidate_vectors = vectors[len(own_phrases) :]
        return {
            phrase
            for phrase, vector in zip(candidate_phrases, candidate_vectors, strict=True)
            if max(cosine_similarity(vector, own) for own in own_vectors) >= 0.82
        }


def _topic_counts(pages: list[Page]) -> Counter[str]:
    scores: Counter[str] = Counter()
    for page in pages:
        title = (page.title or "").lower()
        text = page.normalized_text.lower()
        tokens = [token for token in _WORD_RE.findall(text) if token not in _STOPWORDS][:20_000]
        # Page titles receive a small weight; body phrase frequency is bounded per page.
        for token in _WORD_RE.findall(title):
            if token not in _STOPWORDS:
                scores[token] += 2
        for size in (1, 2, 3):
            for offset in range(max(0, len(tokens) - size + 1)):
                phrase = " ".join(tokens[offset : offset + size])
                scores[phrase] += 1
    return scores


def _contains_phrase(page: Page, phrase: str) -> bool:
    source = f"{page.title or ''} {page.normalized_text}".lower()
    return phrase in source


def _evidence_snippet(page: Page, phrase: str) -> str:
    text = " ".join(page.normalized_text.split())
    start = text.lower().find(phrase)
    if start < 0:
        text = page.title or text
        start = text.lower().find(phrase)
    if start < 0:
        return text[:220]
    start = max(0, start - 70)
    return text[start : start + 220]
