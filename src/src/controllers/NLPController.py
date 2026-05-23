from .BaseController import BaseController
from models.db_schemes import Project, DataChunk
from stores.llm.LLMEnums import DocumentTypeEnum
from typing import List
import json

class NLPController(BaseController):
    def __init__(self, vectordb_client, generation_client, embedding_client, template_parser):
        super().__init__()
        self.vectordb_client = vectordb_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser

    def create_collection_name(self, project_id: str):
        return f'collection_{self.vectordb_client.default_vector_size}_{project_id}'.strip()
        
    async def reset_vector_db_collection(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        return await self.vectordb_client.delete_collection(collection_name=collection_name)
    
    async def get_vector_db_collection_info(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        collection_info = await self.vectordb_client.get_collection_info(collection_name=collection_name)
        return json.loads(json.dumps(collection_info, default=lambda x: x.__dict__))
    
    async def index_into_vector_db(self, project: Project, chunks: List[DataChunk], chunks_ids: List[int], do_reset: bool = False):
        collection_name = self.create_collection_name(project_id=project.project_id)
        texts = [c.chunk_text for c in chunks]
        metadata = [c.chunk_metadata for c in chunks]
        vectors = self.embedding_client.embed_text(text=texts, document_type=DocumentTypeEnum.DOCUMENT.value)
        _ = await self.vectordb_client.create_collection(collection_name=collection_name, embedding_size=self.embedding_client.embedding_size, do_reset=do_reset)
        _ = await self.vectordb_client.insert_many(collection_name=collection_name, texts=texts, metadata=metadata, vectors=vectors, record_ids=chunks_ids)
        return True

    async def search_vector_db_collection(self, project: Project, text: str, limit: int = 10):
        query_vector = None
        collection_name = self.create_collection_name(project_id=project.project_id)
        vectors = self.embedding_client.embed_text(text=text, document_type=DocumentTypeEnum.QUERY.value)
        if not vectors or len(vectors) == 0: return False
        if isinstance(vectors, list) and len(vectors) > 0: query_vector = vectors[0]
        if not query_vector: return False 
        results = await self.vectordb_client.search_by_vector(collection_name=collection_name, vector=query_vector, limit=limit)
        return results if results else []
    
    async def answer_rag_question(self, project: Project, query: str, limit: int = 10):
        answer, context_text, chat_history = None, None, None
        retrieved_documents = await self.search_vector_db_collection(project=project, text=query, limit=limit)
        if not retrieved_documents: return answer, context_text, chat_history
        seen = set()
        unique_docs = []
        for doc in retrieved_documents:
            if doc.text not in seen:
                unique_docs.append(doc)
                seen.add(doc.text)
        retrieved_documents = unique_docs
        context_text = '\n---\n'.join([f'[مصدر زراعي]: {doc.text}' for doc in retrieved_documents])
        system_prompt = self.template_parser.get('rag', 'system_prompt')
        chat_history = [
            {'role': 'system', 'content': str(system_prompt) if system_prompt else 'أنت مساعد خبير زراعي.'},
            {'role': 'user', 'content': f'المعلومات المتاحة:\n{context_text}\n\nالسؤال: {query}'}
        ]
        answer = self.generation_client.generate_text(chat_history=chat_history)
        if answer:
            answer = answer.replace('المستند رقم', '').replace('بناءً على البيانات', '').strip()
        return answer, context_text, chat_history
