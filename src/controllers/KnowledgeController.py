from typing import Dict, List, Optional

from .BaseController import BaseController
from .AgroLibCrawler import AgroLibCrawler
from .ProcessController import ProcessController
from knowledge.classifier import MessageClassifier
from knowledge.schemas import SourceDocument
from knowledge.ontology import AgricultureOntology, FAQDataset
from knowledge.pipeline import KnowledgeIngestionPipeline
from knowledge.router import KnowledgeRouter
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
        }

    async def ingest_sources(
        self,
        project_id: int,
        include_web: bool = True,
        labels: Optional[List[str]] = None,
        max_pages: int = 2,
        include_files: bool = True,
    ) -> Dict:
        if self.db_client is None:
            raise ValueError("db_client is required for ingestion")

        source_documents: List[SourceDocument] = []

        if include_web:
            crawler = AgroLibCrawler()
            posts = await crawler.crawl_labels(labels=labels, max_pages=max_pages)
            for post in posts:
                source_documents.append(
                    SourceDocument(
                        source_name=post.get("source_name", "agro-lib"),
                        source_type="knowledge_source",
                        source_url=post.get("source_url"),
                        language=post.get("language", "ar"),
                        country=post.get("country"),
                        title=post.get("title"),
                        author=post.get("author"),
                        content=post.get("content", ""),
                        metadata={
                            "entity_type": "crop",
                            "topic": post.get("category", "general"),
                            "tags": [post.get("category", "general")],
                        },
                    )
                )

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
                merged_text = "\n".join([rec.page_content for rec in file_content if rec.page_content])
                if not merged_text.strip():
                    continue
                source_documents.append(
                    SourceDocument(
                        source_name="uploaded-files",
                        source_type="directory",
                        source_url=None,
                        language="ar",
                        country=None,
                        title=asset.asset_name,
                        author=None,
                        content=merged_text,
                        metadata={
                            "entity_type": "crop",
                            "topic": "general",
                            "tags": ["uploaded", "directory"],
                        },
                    )
                )

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
            db_records.append(
                {
                    "record_project_id": project_id,
                    "record_source_id": source_rec.source_id,
                    "entity_type": item.get("entity_type", "crop"),
                    "name": item.get("name", "unknown"),
                    "topic": item.get("topic", "general"),
                    "content": item.get("content", ""),
                    "country": item.get("country"),
                    "disease": item.get("disease"),
                    "pest": item.get("pest"),
                    "confidence": item.get("confidence", 0.7),
                    "tags": item.get("tags", []),
                    "normalized_facts": item.get("normalized_facts", []),
                    "record_metadata": item.get("metadata", {}),
                }
            )

        inserted_count = await knowledge_model.replace_project_records(
            project_id=project_id,
            records_payload=db_records,
        )
        return {
            "source_documents": len(source_documents),
            "inserted_records": inserted_count,
        }

    async def answer_from_knowledge_store(
        self,
        project_id: int,
        query: str,
        current_crop: Optional[str] = None,
        limit: int = 3,
    ) -> Optional[Dict]:
        if self.db_client is None:
            return None

        flow = self.classify_message(text=query, current_crop=current_crop)
        message_type = flow["classification"]["message_type"]

        if message_type in {"greeting", "small_talk", "out_of_scope", "agriculture_statement"}:
            return {
                "answer": flow["classification"]["response_template"],
                "sources": [],
                "mode": "message_layer",
                "flow": flow,
            }

        intent = flow["intent"]["intent"]
        route = flow["route"]
        if route == "general_rag":
            return None

        crop = flow["classification"].get("detected_crop") or self._detect_crop(query) or current_crop
        topic = self._topic_from_intent(intent)

        knowledge_model = await KnowledgeModel.create_instance(db_client=self.db_client)
        records = await knowledge_model.get_records(
            project_id=project_id,
            name=crop,
            topic=topic,
            limit=limit,
        )
        if not records:
            records = await knowledge_model.get_records(
                project_id=project_id,
                topic=topic,
                limit=limit,
            )
        if not records:
            return None

        facts = []
        sources = []
        for rec in records:
            snippet = (rec.content or "")[:220]
            if snippet:
                facts.append(snippet)
            sources.append(
                {
                    "record_id": rec.record_id,
                    "name": rec.name,
                    "topic": rec.topic,
                    "confidence": rec.confidence,
                }
            )

        answer = "بناءً على قاعدة المعرفة الزراعية المنظمة:\n- " + "\n- ".join(facts[:3])
        return {
            "answer": answer,
            "sources": sources,
            "mode": "knowledge_store",
            "flow": flow,
        }

    def _detect_crop(self, text: str) -> Optional[str]:
        value = (text or "").lower()
        if "زيتون" in value or "olive" in value:
            return "olive"
        if "قمح" in value or "wheat" in value:
            return "wheat"
        if "طماطم" in value or "tomato" in value:
            return "tomato"
        return None

    def _topic_from_intent(self, intent: str) -> str:
        mapping = {
            "cultivation": "cultivation",
            "irrigation": "irrigation",
            "fertilization": "fertilization",
            "diagnosis": "disease_management",
            "follow_up": "general",
        }
        return mapping.get(intent, "general")
