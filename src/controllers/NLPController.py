from .BaseController import BaseController
from models.db_schemes import Project, DataChunk
from stores.llm.LLMEnums import DocumentTypeEnum
from stores.llm.LLMEnums import DocumentTypeEnum
from helpers.retrieval import rerank_documents, build_source_citation
from typing import List
import json



class NLPController(BaseController):
    RETRIEVAL_CANDIDATE_MULTIPLIER = 5
    MIN_CANDIDATE_POOL = 25

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
        
        
        collection_name = self.create_collection_name(project_id=project.project_id)

        
        texts = [ c.chunk_text for c in chunks ]
        metadata = [ c.chunk_metadata for c in  chunks]
        vectors = self.embedding_client.embed_text(
            text=texts,
            document_type=DocumentTypeEnum.DOCUMENT.value,
        )
        if not vectors:
            return False

        if isinstance(vectors[0], (int, float)):
            vectors = [vectors]

        if len(vectors) != len(chunks_ids):
            return False

        # step3: create collection if not exists
        _ = await self.vectordb_client.create_collection(
            collection_name=collection_name,
            embedding_size=self.embedding_client.embedding_size,
            do_reset=do_reset,
        )

        inserted = await self.vectordb_client.insert_many(
            collection_name=collection_name,
            texts=texts,
            metadata=metadata,
            vectors=vectors,
            record_ids=chunks_ids,
        )

        return bool(inserted)

    async def search_vector_db_collection(self, project: Project, text: str, limit: int = 10):
        
        
        collection_name = self.create_collection_name(project_id=project.project_id)

        
        
        vectors = self.embedding_client.embed_text(
            text=text,
            document_type=DocumentTypeEnum.QUERY.value,
        )

        if not vectors:
        
            return False
        

        if isinstance(vectors[0], (int, float)):
            query_vector = vectors
        elif isinstance(vectors, list) and len(vectors) > 0:
            query_vector = vectors[0]
        else:
            return False

        if not query_vector:
            return False

        candidate_limit = max(limit * self.RETRIEVAL_CANDIDATE_MULTIPLIER, self.MIN_CANDIDATE_POOL)
        
        
        results = await self.vectordb_client.search_by_vector(
            collection_name=collection_name,
            vector=query_vector,
            limit=candidate_limit,
        )

        if not results:
            return []

        seen = set()
        unique_docs = []
        for doc in results:
            dedupe_key = doc.text.strip()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            unique_docs.append(doc)
        return rerank_documents(
            documents=unique_docs,
            query=text,
            limit=limit,
        )
    
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
        answer, context_text, chat_history, sources = None, None, None, []

        retrieved_documents = await self.search_vector_db_collection(
            project=project,
            text=query,
            limit=limit,
            
        )
        
        if not retrieved_documents:
            return answer, context_text, chat_history, sources
        
        context_blocks = []
            
        for doc in retrieved_documents:
            citation = build_source_citation(doc.metadata)
            context_blocks.append(f"[{citation}]\n{doc.text}")
            sources.append({
                "title": (doc.metadata or {}).get("title"),
                "source_url": (doc.metadata or {}).get("source_url"),
                "category": (doc.metadata or {}).get("category"),
                "author": (doc.metadata or {}).get("author"),
                "score": doc.score,
                "vector_score": doc.vector_score,
                "metadata_score": doc.metadata_score,
            })
        context_text = "\n---\n".join(context_blocks)
        system_prompt = self.template_parser.get("rag", "system_prompt")
            
        chat_history = [
            {
                "role": "system", 
                "content": str(system_prompt) if system_prompt else "أنت مساعد خبير زراعي."
            },
            {
                "role": "user",
                "content": (
                    "استخدم المعلومات التالية فقط للإجابة. "
                    "اذكر اسم المصدر عندما يكون ذلك مفيداً.\n\n"
                    f"{context_text}\n\nالسؤال: {query}"
                )
            }
        ]
                
        answer = self.generation_client.generate_text(
            chat_history=chat_history
        )
        
        if answer:
            answer = (
                answer
                .replace("المستند رقم", "")
                .replace("بناءً على البيانات", "")
                .strip()
            )

        return answer, context_text, chat_history, sources
    