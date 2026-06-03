from typing import Dict, List

from .schemas import KnowledgeRecord


class KnowledgeCatalog:
    INDEX_KEYS = ("entity_type", "name", "topic", "disease", "pest", "source", "confidence")

    def build_entry(self, record: KnowledgeRecord) -> Dict:
        payload = record.model_dump()
        payload["catalog_keys"] = {
            key: payload.get(key)
            for key in self.INDEX_KEYS
        }
        return payload

    def filter_records(self, records: List[KnowledgeRecord], **filters) -> List[KnowledgeRecord]:
        filtered = records
        for key, value in filters.items():
            if value in (None, ""):
                continue
            filtered = [record for record in filtered if getattr(record, key, None) == value]
        return filtered
