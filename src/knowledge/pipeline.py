from typing import Dict, List

from .catalog import KnowledgeCatalog
from .schemas import KnowledgeRecord, SourceDocument


class KnowledgeIngestionPipeline:
    def __init__(self):
        self.catalog = KnowledgeCatalog()

    def extract(self, source_documents: List[SourceDocument]) -> List[Dict]:
        return [doc.model_dump() for doc in source_documents if doc.content and len(doc.content.strip()) > 0]

    def clean(self, extracted: List[Dict]) -> List[Dict]:
        cleaned = []
        for item in extracted:
            content = " ".join((item.get("content") or "").split())
            if len(content) < 40:
                continue
            item["content"] = content
            cleaned.append(item)
        return cleaned

    def normalize(self, cleaned: List[Dict]) -> List[KnowledgeRecord]:
        records: List[KnowledgeRecord] = []
        for item in cleaned:
            metadata = item.get("metadata") or {}
            topic = metadata.get("topic") or "general"
            name = metadata.get("crop") or metadata.get("name") or self._infer_crop_name(item.get("content", ""))
            source = item.get("source_name") or item.get("source_url") or "unknown"

            records.append(
                KnowledgeRecord(
                    entity_type=metadata.get("entity_type", "crop"),
                    name=name,
                    topic=topic,
                    content=item.get("content", ""),
                    source=source,
                    country=item.get("country"),
                    disease=metadata.get("disease"),
                    pest=metadata.get("pest"),
                    confidence=float(metadata.get("confidence", 0.7)),
                    tags=list(metadata.get("tags") or []),
                    normalized_facts=list(metadata.get("facts") or []),
                    metadata=metadata,
                )
            )
        return records

    def _infer_crop_name(self, text: str) -> str:
        value = (text or "").lower()
        if "زيتون" in value or "olive" in value:
            return "olive"
        if "قمح" in value or "wheat" in value:
            return "wheat"
        if "ذرة" in value or "corn" in value:
            return "corn"
        if "طماطم" in value or "tomato" in value:
            return "tomato"
        return "unknown"

    def tag(self, records: List[KnowledgeRecord]) -> List[KnowledgeRecord]:
        for record in records:
            extra_tags = {
                record.entity_type,
                record.topic,
                record.name,
                record.disease or "",
                record.pest or "",
            }
            record.tags = sorted({tag for tag in (record.tags + list(extra_tags)) if tag})
        return records

    def store(self, records: List[KnowledgeRecord]) -> List[Dict]:
        return [self.catalog.build_entry(record) for record in records]

    def run(self, source_documents: List[SourceDocument]) -> List[Dict]:
        extracted = self.extract(source_documents=source_documents)
        cleaned = self.clean(extracted=extracted)
        normalized = self.normalize(cleaned=cleaned)
        tagged = self.tag(records=normalized)
        return self.store(records=tagged)
