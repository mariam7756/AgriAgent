from typing import Dict, List

from .catalog import KnowledgeCatalog
from .schemas import KnowledgeRecord, SourceDocument

NOISE_PHRASES = {
    "تنزيل الكتاب", "تحميل الكتاب", "اضغط هنا للتحميل",
    "download book", "click here", "روابط التحميل",
    "تحميل مباشر", "للتحميل اضغط", "اشترك الآن",
    "cookie", "javascript required",
}

AGRI_KEYWORDS = {
    "زراعة", "محصول", "تربة", "ري", "سماد", "مرض", "حشرة", "نبات",
    "بذور", "حصاد", "قمح", "طماطم", "زيتون", "ذرة", "تسميد", "رش",
    "agriculture", "crop", "soil", "irrigation", "fertilizer", "pest",
    "disease", "harvest", "wheat", "tomato", "corn", "seed",
}

CROP_INFERENCE = {
    "زيتون": "olive", "olive": "olive",
    "قمح": "wheat", "wheat": "wheat",
    "ذرة": "corn", "corn": "corn", "maize": "corn",
    "طماطم": "tomato", "tomato": "tomato",
    "أرز": "rice", "rice": "rice",
    "قطن": "cotton", "cotton": "cotton",
    "بطاطس": "potato", "potato": "potato",
    "بصل": "onion", "onion": "onion",
    "فلفل": "pepper", "pepper": "pepper",
    "قصب": "sugarcane", "sugarcane": "sugarcane",
}

TOPIC_INFERENCE = {
    "تسميد": "fertilization", "سماد": "fertilization", "يوريا": "fertilization",
    "fertiliz": "fertilization", "nitrogen": "fertilization",
    "ري": "irrigation", "سقي": "irrigation", "مياه": "irrigation",
    "irrigat": "irrigation", "water": "irrigation",
    "مرض": "disease_management", "فطر": "disease_management", "عفن": "disease_management",
    "disease": "disease_management", "fungus": "disease_management",
    "حشرة": "pest_management", "آفة": "pest_management", "دودة": "pest_management",
    "pest": "pest_management", "insect": "pest_management",
    "زراعة": "cultivation", "بذر": "cultivation", "شتل": "cultivation",
    "cultivat": "cultivation", "plant": "cultivation",
    "تربة": "soil_management", "soil": "soil_management",
    "حصاد": "harvest", "harvest": "harvest",
}


class KnowledgeIngestionPipeline:
    def __init__(self):
        self.catalog = KnowledgeCatalog()

    def extract(self, source_documents: List[SourceDocument]) -> List[Dict]:
        return [
            doc.model_dump()
            for doc in source_documents
            if doc.content and len(doc.content.strip()) > 0
        ]

    def clean(self, extracted: List[Dict]) -> List[Dict]:
        cleaned = []
        for item in extracted:
            content = " ".join((item.get("content") or "").split())

            # رفض المحتوى القصير
            if len(content) < 80:
                continue

            # رفض أو تنظيف noise
            if any(phrase in content for phrase in NOISE_PHRASES):
                lines = [l for l in content.split("\n") if len(l.strip()) > 50]
                content = "\n".join(lines)
                if len(content) < 80:
                    continue

            # seed knowledge تعدي بدون فلترة keyword
            if item.get("metadata", {}).get("source_type") == "seed":
                item["content"] = content
                cleaned.append(item)
                continue

            # تأكد إن المحتوى فيه keyword زراعي
            content_lower = content.lower()
            if not any(kw in content_lower for kw in AGRI_KEYWORDS):
                continue

            item["content"] = content
            cleaned.append(item)
        return cleaned

    def normalize(self, cleaned: List[Dict]) -> List[KnowledgeRecord]:
        records: List[KnowledgeRecord] = []
        for item in cleaned:
            metadata = item.get("metadata") or {}
            content_lower = (item.get("content") or "").lower()

            topic = (
                metadata.get("topic")
                or self._infer_topic(content_lower)
                or "general"
            )
            name = (
                metadata.get("crop")
                or metadata.get("name")
                or self._infer_crop(content_lower)
                or "general"
            )
            source = item.get("source_name") or item.get("source_url") or "unknown"
            confidence = float(metadata.get("confidence", 0.7))

            records.append(KnowledgeRecord(
                entity_type=metadata.get("entity_type", "crop"),
                name=name,
                topic=topic,
                content=item.get("content", ""),
                source=source,
                country=item.get("country"),
                disease=metadata.get("disease"),
                pest=metadata.get("pest"),
                confidence=confidence,
                tags=list(metadata.get("tags") or []),
                normalized_facts=list(metadata.get("facts") or []),
                metadata=metadata,
            ))
        return records

    def _infer_crop(self, text: str) -> str:
        for keyword, crop in CROP_INFERENCE.items():
            if keyword in text:
                return crop
        return "general"

    def _infer_topic(self, text: str) -> str:
        for keyword, topic in TOPIC_INFERENCE.items():
            if keyword in text:
                return topic
        return "general"

    def tag(self, records: List[KnowledgeRecord]) -> List[KnowledgeRecord]:
        for record in records:
            extra = {record.entity_type, record.topic, record.name}
            if record.disease:
                extra.add(record.disease)
            if record.pest:
                extra.add(record.pest)
            record.tags = sorted({t for t in (record.tags + list(extra)) if t and t != "general"})
        return records

    def store(self, records: List[KnowledgeRecord]) -> List[Dict]:
        return [self.catalog.build_entry(record) for record in records]

    def run(self, source_documents: List[SourceDocument]) -> List[Dict]:
        extracted = self.extract(source_documents)
        cleaned = self.clean(extracted)
        normalized = self.normalize(cleaned)
        tagged = self.tag(normalized)
        return self.store(tagged)