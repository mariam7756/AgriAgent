"""
VectorSource — بيستخدم methods الاسترجاع الخام بس من NLPController
(search_vector_db_collection + _is_context_relevant)، وأبدًا answer_rag_question
(اللي فيها classify/prompt/generate/sanitize مكررة). ده الاستخراج الحقيقي
اللي كان المفروض يحصل من الأول.
"""
from typing import Optional

from services.conversation.context import ConversationContext
from services.conversation.knowledge_sources.base import KnowledgeSource, Evidence

_NOISE = {"تنزيل الكتاب", "تحميل الكتاب", "download", "اضغط هنا", "-----"}


class VectorSource(KnowledgeSource):
    def __init__(self, nlp_controller, project, limit: int = 3):
        self.nlp_controller = nlp_controller
        self.project = project
        self.limit = limit

    async def fetch(self, context: ConversationContext) -> Evidence:
        retrieved_documents = await self.nlp_controller.search_vector_db_collection(
            project=self.project,
            text=context.user_message,
            limit=self.limit,
            current_crop=context.current_crop,
        )

        context_blocks = []
        sources = []
        for doc in (retrieved_documents or []):
            text = doc.text or ""
            if len(text.strip()) < 60 or any(n in text for n in _NOISE):
                continue
            context_blocks.append(text)
            sources.append({
                "title": (doc.metadata or {}).get("title"),
                "source_url": (doc.metadata or {}).get("source_url"),
                "category": (doc.metadata or {}).get("category"),
                "score": doc.score,
            })

        if not context_blocks:
            return Evidence(found=False)

        if not self.nlp_controller._is_context_relevant(
            context.user_message, retrieved_documents or [], current_crop=context.current_crop
        ):
            return Evidence(found=False)

        return Evidence(text="\n---\n".join(context_blocks), sources=sources, is_final_answer=False)
