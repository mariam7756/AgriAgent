from .BaseController import BaseController
from models.db_schemes import Project, DataChunk
from stores.llm.LLMEnums import DocumentTypeEnum
from typing import List
import json



class NLPController(BaseController):

    def __init__(self, vectordb_client, generation_client, 
                 embedding_client, template_parser):
        super().__init__()

        self.vectordb_client = vectordb_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser

    def create_collection_name(self, project_id: str):
        return f"collection_{self.vectordb_client.default_vector_size}_{project_id}".strip()
        
    
    async def reset_vector_db_collection(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        return await self.vectordb_client.delete_collection(collection_name=collection_name)
    
    async def get_vector_db_collection_info(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        collection_info = await self.vectordb_client.get_collection_info(collection_name=collection_name)

        return json.loads(
            json.dumps(collection_info, default=lambda x: x.__dict__)
        )
    
    async def index_into_vector_db(self, project: Project, chunks: List[DataChunk],
                                   chunks_ids: List[int], 
                                   do_reset: bool = False):
        
        # step1: get collection name
        collection_name = self.create_collection_name(project_id=project.project_id)

        # step2: manage items
        texts = [ c.chunk_text for c in chunks ]
        metadata = [ c.chunk_metadata for c in  chunks]
        vectors = self.embedding_client.embed_text(text=texts, 
                                                  document_type=DocumentTypeEnum.DOCUMENT.value)

        # step3: create collection if not exists
        _ = await self.vectordb_client.create_collection(
            collection_name=collection_name,
            embedding_size=self.embedding_client.embedding_size,
            do_reset=do_reset,
        )

        # step4: insert into vector db
        _ = await  self.vectordb_client.insert_many(
            collection_name=collection_name,
            texts=texts,
            metadata=metadata,
            vectors=vectors,
            record_ids=chunks_ids,
        )

        return True

    async def search_vector_db_collection(self, project: Project, text: str, limit: int = 10):
        query_vector = None

        # step1: get collection name
        collection_name = self.create_collection_name(project_id=project.project_id)

        # step2: get text embedding vector
        
        vectors = self.embedding_client.embed_text(text=text, 
                                                 document_type=DocumentTypeEnum.QUERY.value)

        if not vectors or len(vectors) == 0:
            return False
        

        if isinstance(vectors[0], (int, float)):
            query_vector = vectors
        else:
            query_vector = vectors[0]

        if not query_vector:
            return False

        # step3: do semantic search
        results = await self.vectordb_client.search_by_vector(
            collection_name=collection_name,
            vector=query_vector,
            limit=limit
        )

        if not results:
            return []

        return results
    
    def _is_context_relevant(self, query: str, docs: list, min_score: float = 0.35) -> bool:
        if not docs:
            return False
        top_score = max((getattr(d, "score", 0) or 0) for d in docs)
        if top_score < min_score:
            return False
        query_tokens = [w.strip() for w in query.replace("؟", "").split() if len(w.strip()) > 2]
        if not query_tokens:
            return top_score >= min_score
        joined_context = " ".join((d.text or "") for d in docs).lower()
        hits = sum(1 for t in query_tokens if t.lower() in joined_context)
        return hits > 0 or top_score >= 0.55
    
    async def answer_rag_question(self, project: Project, query: str, limit: int = 3):
        answer, context_text, chat_history, follow_up = None, None, None, None
        retrieved_documents = await self.search_vector_db_collection(
            project=project,
            text=query,
            limit=limit,
        )
        
        if not retrieved_documents:
            answer = (
                "مش لاقي في ملفات مشروعك معلومة كافية عن الموضوع ده 🌱\n"
                "ارفعي ملف فيه التفاصيل، أو صفّيلي أكتر: إيه المحصول وإيه اللي ملاحظاه بالظبط؟"
            )
            follow_up = "تحبي نركّز على نوع المحصول ولا على نوع التربة عندك؟"
            return answer, None, None, follow_up
        seen = set()
        unique_docs = []
        for doc in retrieved_documents:
            if doc.text not in seen:
                unique_docs.append(doc)
                seen.add(doc.text)
        retrieved_documents = unique_docs[:limit]
        is_relevant = self._is_context_relevant(query=query, docs=retrieved_documents)
        max_chunk_chars = 350
        context_parts = []
        for i, doc in enumerate(retrieved_documents, start=1):
            snippet = (doc.text or "")[:max_chunk_chars]
            score = round(getattr(doc, "score", 0) or 0, 3)
            context_parts.append(f"[مصدر {i} | score={score}]: {snippet}")
        context_text = "\n---\n".join(context_parts)
        system_prompt = self.template_parser.get("rag", "system_prompt")
        if not is_relevant:
            user_content = "\n".join([
                f"سؤال المزارع: {query}",
                "",
                "ملاحظة: المقاطع المسترجعة من الملفات غير مرتبطة مباشرة بالسؤال.",
                "ممنوع اختراع معلومات أو استخدام أمثلة جاهزة (مثل نقص النيتروجين).",
                "اكتبي ردًا قصيرًا بشريًا:",
                "1) قولي بصراحة إن الملف الحالي مش فيه إجابة مباشرة.",
                "2) اطلبي من المزارع تفصيلة واحدة عملية (محصول/موقع/ملاحظة).",
                "3) اقترحي خطوة بسيطة يعملها دلوقتي.",
            ])
        else:
            user_content = "\n".join([
                "السياق الزراعي (من ملفات المشروع فقط):",
                context_text,
                "",
                f"سؤال المزارع: {query}",
                "",
                "قواعد الرد:",
                "- اعتمدي فقط على السياق.",
                "- ممنوع ذكر نيتروجين إلا إذا كان مذكورًا في السياق.",
                "- اكتبي 3-5 جمل عملية بالعربية.",
                "- في آخر الرد: سطر يبدأ بـ FOLLOW_UP: وسؤال متابعة واحد قصير وم relacion بالسؤال.",
            ])
        chat_history = [
            {
                "role": "system",
                "content": str(system_prompt) if system_prompt else "أنت خبير زراعي.",
            },
            {"role": "user", "content": user_content},
        ]
        raw_answer = self.generation_client.generate_text(
            prompt=None,
            chat_history=chat_history,
        )
        if not raw_answer:
            return None, context_text, chat_history, None
        follow_up = None
        answer = raw_answer.strip()
        if "FOLLOW_UP:" in answer:
            parts = answer.split("FOLLOW_UP:", 1)
            answer = parts[0].strip()
            follow_up = parts[1].strip()
        for bad in ["بناءً على", "المستند", "بالطبع"]:
            answer = answer.replace(bad, "")
        answer = answer.strip()
        if not follow_up and is_relevant:
            follow_up = "تحبي أقولك خطوة عملية تناسب نوع تربتك عندك؟"
        return answer, context_text, chat_history, follow_up