import re
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
from models.ChunkModel import ChunkModel
from models.KnowledgeModel import KnowledgeModel
from models.db_schemes import Asset, DataChunk
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

    
    # Classification & Routing
    
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

    
    # helpers
    

    async def _get_or_create_asset(
        self,
        asset_model: AssetModel,
        project_id: int,
        asset_name: str,
        asset_size: int,
        asset_config: dict,
        asset_type: str = AssetTypeEnum.FILE.value,
    ) -> Asset:
        
        existing = await asset_model.get_all_project_assets(
            asset_project_id=project_id,
            asset_type=asset_type,
        )
        found = next((a for a in existing if a.asset_name == asset_name), None)
        if found:
            return found

        async with self.db_client() as session:
            new_asset = Asset(
                asset_project_id=project_id,
                asset_type=asset_type,
                asset_name=asset_name,
                asset_size=asset_size,
                asset_config=asset_config,
            )
            session.add(new_asset)
            await session.commit()
            await session.refresh(new_asset)
        return new_asset

    def _build_data_chunks(
        self,
        records: List[Dict],
        project_id: int,
        asset_id: int,
        start_order: int = 1,
    ) -> List[DataChunk]:
        
        chunks = []
        for i, item in enumerate(records):
            content = (item.get("content") or "").strip()
            if not content or len(content) < 50:
                continue
            chunks.append(DataChunk(
                chunk_project_id=project_id,
                chunk_asset_id=asset_id,
                chunk_order=start_order + i,
                chunk_text=content,
                chunk_metadata={
                    "title": item.get("name", "unknown"),
                    "source_url": item.get("metadata", {}).get("source_url", ""),
                    "category": item.get("topic", "general"),
                    "author": item.get("metadata", {}).get("author", "AgriAssistant Egypt"),
                },
            ))
        return chunks

    
    async def ingest_sources(
        self,
        project_id: int,
        include_seed: bool = True,
        include_files: bool = False,
        include_web: bool = False,
        
        labels: Optional[List[str]] = None,
        
        max_pages: int = 2,
        
    ) -> Dict:
        if self.db_client is None:
            raise ValueError("db_client is required")

        asset_model = await AssetModel.create_instance(db_client=self.db_client)
        chunk_model = await ChunkModel.create_instance(db_client=self.db_client)
        knowledge_model = await KnowledgeModel.create_instance(db_client=self.db_client)

        all_source_documents: List[SourceDocument] = []
        stats = {
            "seed_docs": 0,
            "file_docs": 0,
            "web_docs": 0,
            "inserted_records": 0,
            "inserted_chunks": 0,
        }

        #SEED 
        if include_seed:
            seed_docs = get_seed_as_source_documents()
            all_source_documents.extend(seed_docs)
            stats["seed_docs"] = len(seed_docs)

        # FILES
        if include_files:
            
            process_controller = ProcessController(project_id=str(project_id))
            file_assets = await asset_model.get_all_project_assets(
                asset_project_id=project_id,
                asset_type=AssetTypeEnum.FILE.value,
            )
            
            file_assets = [a for a in file_assets if a.asset_name != "seed-knowledge-eg"]

            for asset in file_assets:
                file_content = process_controller.get_file_content(file_id=asset.asset_name)
                if not file_content:
                    continue
                merged_text = "\n".join([r.page_content for r in file_content if r.page_content])
                if not merged_text.strip():
                    continue
                all_source_documents.append(SourceDocument(
                    source_name="uploaded-files",
                    source_type="directory",
                    language="ar",
                    title=asset.asset_name,
                    content=merged_text,
                    metadata={
                        "entity_type": "crop",
                        "topic": "general",
                        "tags": ["uploaded"],
                        "asset_id": asset.asset_id,
                    },
                ))
                stats["file_docs"] += 1

        #  WEB (FAO) 
        if include_web:
            try:
                from .FAOCrawler import FAOCrawler
                fao_crawler = FAOCrawler()
                articles = await fao_crawler.fetch_all_sources(max_per_source=5)
                for post in articles:
                    all_source_documents.append(SourceDocument(
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
                            "source_url": post.get("source_url", ""),
                        },
                    ))
                stats["web_docs"] = len(articles)
            except Exception as e:
                self.logger.warning(f"Web crawl failed (non-fatal): {e}")

        # pipeline: extract → clean → normalize → tag → store 
        stored_records = self.pipeline.run(source_documents=all_source_documents)

        #knowledge_records 
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

        stats["inserted_records"] = await knowledge_model.replace_project_records(
            project_id=project_id,
            records_payload=db_records,
        )

        
        seed_asset = await self._get_or_create_asset(
            asset_model=asset_model,
            project_id=project_id,
            asset_name="seed-knowledge-eg",
            asset_size=sum(len((r.get("content") or "").encode()) for r in stored_records),
            asset_config={"source": "seed+web", "version": "1.0"},
        )

        
        await chunk_model.delete_chunks_by_asset_id(asset_id=seed_asset.asset_id)

        
        non_file_records = [
            r for r in stored_records
            if not (r.get("metadata") or {}).get("asset_id")
        ]
        data_chunks = self._build_data_chunks(
            records=non_file_records,
            project_id=project_id,
            asset_id=seed_asset.asset_id,
        )

        
        file_records = [
            r for r in stored_records
            if (r.get("metadata") or {}).get("asset_id")
        ]
        for item in file_records:
            file_asset_id = item["metadata"]["asset_id"]
            await chunk_model.delete_chunks_by_asset_id(asset_id=file_asset_id)
            file_chunks = self._build_data_chunks(
                records=[item],
                project_id=project_id,
                asset_id=file_asset_id,
            )
            data_chunks.extend(file_chunks)

        if data_chunks:
            await chunk_model.insert_many_chunks(chunks=data_chunks)

        stats["inserted_chunks"] = len(data_chunks)

        return {
            "source_documents": len(all_source_documents),
            "stats": stats,
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

        # general_chat → مش بنرد هنا، بنبعته للـ LLM في nlp.py
        # الـ LLM هيرد بشكل طبيعي على التحية أو الكلام العادي
        if message_type == "general_chat":
            return None

        # خطة تسميد من الـ ontology مباشرة
        if route == "fertilization_plan":
            crop = (
                flow["classification"].get("detected_crop")
                or self._detect_crop_from_query(query)
            )
            if crop:
                area = self._extract_area(query)
                plan = self.get_fertilization_plan_from_ontology(crop=crop, area_feddan=area)
                if plan:
                    ar_name = AGRI_ONTOLOGY.get(crop, {}).get("ar_names", [crop])[0]
                    lines = [f"🌾 خطة تسميد {ar_name} لـ {area} فدان:\n"]
                    for stage in plan["stages"]:
                        lines.append(
                            f"• {stage['stage']}: {stage['fertilizer']} — {stage['total_kg']} كجم"
                        )
                    lines.append(
                        "\nملاحظة: الجرعات للتربة الطمية — التربة الرملية تحتاج زيادة 15-20%."
                    )
                    
                    return {
                        "answer": "\n".join(lines),
                        "sources": [{"name": crop, "topic": "fertilization", "confidence": 0.95}],
                        "mode": "ontology_plan",
                        "plan": plan,
                        "flow": flow,
                    }

        # general_rag → اديه للـ RAG
        if route == "general_rag":
            return None

        # دور في الـ knowledge store
        crop = (
            flow["classification"].get("detected_crop")
            or self._detect_crop_from_query(query)
            or current_crop
        )
        topic = flow["intent"].get("topic", "general")
        
        knowledge_model = await KnowledgeModel.create_instance(db_client=self.db_client)
        

        records = await knowledge_model.get_records(
            project_id=project_id, name=crop, topic=topic, limit=limit,
        )
        
        if not records:
            records = await knowledge_model.get_records(
                project_id=project_id, topic=topic, limit=limit,
            )
            
        if not records:
            return None

        # نظف المحتوى — شيل الـ "سؤال: ... إجابة: ..." prefix
        def clean_content(text: str) -> str:
            if "إجابة:" in text:
                return text.split("إجابة:")[-1].strip()
            if "سؤال:" in text:
                parts = text.split("سؤال:")
                return parts[-1].strip() if len(parts) > 1 else text
            return text

        facts = [clean_content(rec.content or "")[:400] for rec in records if rec.content]
        sources = [
            {
                "record_id": rec.record_id,
                "name": rec.name,
                "topic": rec.topic,
                "confidence": rec.confidence,
            }
            for rec in records
        ]
        

        return {
            "answer": "\n\n".join(facts[:3]),
            "sources": sources,
            "mode": "knowledge_store_context",
            "flow": flow,
        }

    
    # Private helpers
    
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
        match = re.search(r"(\d+(?:\.\d+)?)\s*فدان", text or "")
        return float(match.group(1)) if match else 1.0