from typing import Dict, List, Optional

from .BaseController import BaseController

from .ProcessController import ProcessController
from knowledge.classifier import MessageClassifier
from knowledge.ontology import AgricultureOntology, FAQDataset, get_fertilization_plan, AGRI_ONTOLOGY
from knowledge.pipeline import KnowledgeIngestionPipeline
from knowledge.router import KnowledgeRouter
from knowledge.schemas import SourceDocument
from knowledge.seed_knowledge import get_seed_as_source_documents
from knowledge.validation import FeedbackLoopStore, ValidationLayer
from models.AssetModel import AssetModel
from models.KnowledgeModel import KnowledgeModel
from models.enums.AssetTypeEnum import AssetTypeEnum


class KnowledgeController(BaseController):
    def __init__(self, db_client=None):
        super().__init__()
        self.db_client = db_client
        self.classifier = MessageClassifier()
        self.router = KnowledgeRouter()
        self.pipeline = KnowledgeIngestionPipeline()
        self.validation = ValidationLayer()
        self.feedback_store = FeedbackLoopStore()
        self.ontology = AgricultureOntology()
        self.faq_dataset = FAQDataset()

    def classify_message(self, text: str, current_crop: Optional[str] = None) -> Dict:
        classification = self.classifier.classify(text=text, current_crop=current_crop)
        intent = self.router.detect_intent(query=text, message=classification)
        route = self.router.route(intent=intent)
        return {
            "classification": classification.model_dump(),
            "intent": intent.model_dump(),
            "route": route,
        }

    def get_seed_knowledge_assets(self) -> Dict:
        return {
            "ontology": self.ontology.to_dict(),
            "faq_dataset": self.faq_dataset.list_items(),
            "seed_count": len(get_seed_as_source_documents()),
        }

    def get_fertilization_plan_from_ontology(
        self, crop: str, area_feddan: float = 1.0
    ) -> Optional[Dict]:
        plan = get_fertilization_plan(crop_key=crop, area_feddan=area_feddan)
        return plan if plan.get("stages") else None

    async def ingest_sources(
        self,
        project_id: int,
        include_web: bool = False,
        include_files: bool = True,
        include_seed: bool = True,
        labels: Optional[List[str]] = None,
        max_pages: int = 2,
        
    ) -> Dict:
        if self.db_client is None:
            raise ValueError("db_client is required")

        source_documents: List[SourceDocument] = []

        # Seed knowledge — أول مصدر دايماً
        if include_seed:
            seed_docs = get_seed_as_source_documents()
            source_documents.extend(seed_docs)

        # ملفات مرفوعة
        if include_files:
            asset_model = await AssetModel.create_instance(db_client=self.db_client)
            process_controller = ProcessController(project_id=str(project_id))
            file_assets = await asset_model.get_all_project_assets(
                asset_project_id=project_id,
                asset_type=AssetTypeEnum.FILE.value,
            )
            for asset in file_assets:
                file_content = process_controller.get_file_content(file_id=asset.asset_name)
                if not file_content:
                    continue
                merged_text = "\n".join([r.page_content for r in file_content if r.page_content])
                if not merged_text.strip():
                    continue
                source_documents.append(SourceDocument(
                    source_name="uploaded-files",
                    source_type="directory",
                    language="ar",
                    title=asset.asset_name,
                    content=merged_text,
                    metadata={"entity_type": "crop", "topic": "general", "tags": ["uploaded"]},
                ))

        # FAO crawling (اختياري)
        if include_web:
            try:
                from .FAOCrawler import FAOCrawler
                fao_crawler = FAOCrawler()
                articles = await fao_crawler.fetch_all_sources(max_per_source=5)
                for post in articles:
                    source_documents.append(SourceDocument(
                        source_name=post.get("source_name", "fao-extension"),
                        source_type="article",
                        source_url=post.get("source_url"),
                        language=post.get("language", "en"),
                        title=post.get("title", ""),
                        author="FAO / Extension",
                        content=post.get("content", ""),
                        metadata={
                            "entity_type": "crop",
                            "topic": post.get("metadata", {}).get("topic", "general"),
                            "tags": post.get("metadata", {}).get("tags", []),
                            "source_type": "article",
                        },
                    ))
            except Exception as e:
                self.logger.warning(f"FAO crawl failed (non-fatal): {e}")

        stored_records = self.pipeline.run(source_documents=source_documents)
        knowledge_model = await KnowledgeModel.create_instance(db_client=self.db_client)
        db_records = []

        for item in stored_records:
            source_rec = await knowledge_model.upsert_source(
                project_id=project_id,
                source_name=item.get("source", "unknown"),
                source_type=item.get("metadata", {}).get("source_type", "knowledge_source"),
                source_url=item.get("metadata", {}).get("source_url"),
                source_country=item.get("country"),
                source_language=item.get("metadata", {}).get("language", "ar"),
                source_metadata=item.get("metadata", {}),
            )
            db_records.append({
                "record_project_id": project_id,
                "record_source_id": source_rec.source_id,
                "entity_type": item.get("entity_type", "crop"),
                "name": item.get("name", "general"),
                "topic": item.get("topic", "general"),
                "content": item.get("content", ""),
                "country": item.get("country"),
                "disease": item.get("disease"),
                "pest": item.get("pest"),
                "confidence": item.get("confidence", 0.7),
                "tags": item.get("tags", []),
                "normalized_facts": item.get("normalized_facts", []),
                "record_metadata": item.get("metadata", {}),
            })

        inserted_count = await knowledge_model.replace_project_records(
            project_id=project_id,
            records_payload=db_records,
        )
        return {
            "source_documents": len(source_documents),
            "inserted_records": inserted_count,
            "seed_included": include_seed,
            "web_included": include_web,
            "files_included": include_files,
        }

    async def answer_from_knowledge_store(
        self,
        project_id: int,
        query: str,
        current_crop: Optional[str] = None,
        limit: int = 5,
    ) -> Optional[Dict]:
        if self.db_client is None:
            return None

        flow = self.classify_message(text=query, current_crop=current_crop)
        message_type = flow["classification"]["message_type"]
        route = flow["route"]

        # ردود فورية بدون LLM
        if message_type in {"greeting", "small_talk", "out_of_scope"}:
            return {
                "answer": flow["classification"]["response_template"],
                "sources": [], "mode": "direct_response", "flow": flow,
            }

        # خطة تسميد من الـ ontology مباشرة
        if route == "fertilization_plan":
            crop = flow["classification"].get("detected_crop") or self._detect_crop_from_query(query)
            if crop:
                area = self._extract_area(query)
                plan = self.get_fertilization_plan_from_ontology(crop=crop, area_feddan=area)
                if plan:
                    ar_name = AGRI_ONTOLOGY.get(crop, {}).get("ar_names", [crop])[0]
                    answer_lines = [f"🌾 خطة تسميد {ar_name} لـ {area} فدان:\n"]
                    for stage in plan["stages"]:
                        answer_lines.append(
                            f"• {stage['stage']}: {stage['fertilizer']} — {stage['total_kg']} كجم"
                        )
                    answer_lines.append(
                        "\nملاحظة: الجرعات للتربة الطمية — التربة الرملية تحتاج زيادة 15-20%."
                    )
                    return {
                        "answer": "\n".join(answer_lines),
                        "sources": [{"name": crop, "topic": "fertilization", "confidence": 0.95}],
                        "mode": "ontology_plan",
                        "plan": plan,
                        "flow": flow,
                    }

        # general_rag يروح للـ RAG
        if route == "general_rag":
            return None

        # باقي الحالات — دور في الـ knowledge store
        crop = flow["classification"].get("detected_crop") or self._detect_crop_from_query(query) or current_crop
        topic = flow["intent"].get("topic", "general")

        knowledge_model = await KnowledgeModel.create_instance(db_client=self.db_client)

        # حاول بالـ crop + topic أول
        records = await knowledge_model.get_records(
            project_id=project_id, name=crop, topic=topic, limit=limit,
        )
        # لو مفيش، حاول بالـ topic بس
        if not records:
            records = await knowledge_model.get_records(
                project_id=project_id, topic=topic, limit=limit,
            )
        # لو مفيش خالص، اديه للـ RAG
        if not records:
            return None

        facts = [(rec.content or "")[:300] for rec in records if rec.content]
        sources = [
            {"record_id": rec.record_id, "name": rec.name,
             "topic": rec.topic, "confidence": rec.confidence}
            for rec in records
        ]

        context = "\n\n".join(facts[:4])
        return {
            "answer": context,
            "sources": sources,
            "mode": "knowledge_store_context",
            "flow": flow,
        }

    def _detect_crop_from_query(self, text: str) -> Optional[str]:
        text_lower = (text or "").lower()
        for crop_key, data in AGRI_ONTOLOGY.items():
            if crop_key in text_lower:
                return crop_key
            for ar_name in data.get("ar_names", []):
                if ar_name in text_lower:
                    return crop_key
        return None

    def _extract_area(self, text: str) -> float:
        import re
        match = re.search(r"(\d+(?:\.\d+)?)\s*فدان", text)
        if match:
            return float(match.group(1))
        return 1.0
    