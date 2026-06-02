import re
from typing import List

from models.db_schemes import RetrievedDocument

ARABIC_STOP_WORDS = {
    "في", "من", "إلى", "على", "ما", "هل", "كيف", "أن", "هذا", "هذه", "ذلك",
    "التي", "الذي", "عن", "مع", "أو", "و", "لا", "لم", "لن", "قد", "كان",
    "كل", "بعض", "أي", "هو", "هي", "هم", "نحن", "أنت", "أنا", "The", "the",
    "best", "way", "what", "when", "where", "why", "how", "is", "are", "the",
    "زراعة", "إنتاج", "كتاب", "دليل", "مرجع", "أساسيات", "الشامل", "الشاملة",
}


def normalize_arabic(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def extract_search_terms(query: str) -> List[str]:
    normalized = normalize_arabic(query)
    words = normalized.split()
    terms = []
    seen = set()

    for word in words:
        if len(word) < 2 or word in ARABIC_STOP_WORDS:
            continue
        if word not in seen:
            seen.add(word)
            terms.append(word)

    return terms


def metadata_match_score(query_terms: List[str], metadata: dict, text: str) -> float:
    if not query_terms:
        return 0.0

    metadata = metadata or {}
    title = normalize_arabic(metadata.get("title", ""))
    category = normalize_arabic(metadata.get("category", ""))
    body_preview = normalize_arabic(text[:600])

    title_hits = sum(1 for term in query_terms if term in title)
    category_hits = sum(1 for term in query_terms if term in category)
    body_hits = sum(1 for term in query_terms if term in body_preview)

    title_score = title_hits / len(query_terms)
    category_score = category_hits / len(query_terms)
    body_score = body_hits / len(query_terms)

    return min(1.0, (title_score * 0.55) + (category_score * 0.25) + (body_score * 0.20))


def rerank_documents(
    documents: List[RetrievedDocument],
    query: str,
    limit: int,
) -> List[RetrievedDocument]:
    if not documents:
        return []

    query_terms = extract_search_terms(query)
    if not query_terms:
        return documents[:limit]

    ranked = []
    for doc in documents:
        meta_score = metadata_match_score(query_terms, doc.metadata or {}, doc.text)
        combined_score = (0.60 * doc.score) + (0.40 * meta_score)
        ranked.append((combined_score, meta_score, doc))

    ranked.sort(key=lambda item: (item[0], item[1], item[2].score), reverse=True)

    title_matches = [
        item for item in ranked
        if item[1] >= 0.25 and any(
            term in normalize_arabic((item[2].metadata or {}).get("title", ""))
            for term in query_terms
        )
    ]

    if title_matches:
        ranked = title_matches + [item for item in ranked if item not in title_matches]

    reranked = []
    for combined_score, meta_score, doc in ranked[:limit]:
        reranked.append(
            RetrievedDocument(
                text=doc.text,
                score=round(combined_score, 4),
                metadata=doc.metadata or {},
                chunk_id=doc.chunk_id,
                vector_score=round(doc.score, 4),
                metadata_score=round(meta_score, 4),
            )
        )

    return reranked


def build_source_citation(metadata: dict) -> str:
    metadata = metadata or {}
    title = metadata.get("title") or "مصدر غير معروف"
    source_url = metadata.get("source_url") or ""
    category = metadata.get("category") or ""

    parts = [title]
    if category:
        parts.append(f"({category})")
    if source_url:
        parts.append(f"- {source_url}")

    return " ".join(parts)
