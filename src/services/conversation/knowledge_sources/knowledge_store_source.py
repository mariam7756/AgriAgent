from typing import Optional

from services.conversation.context import ConversationContext
from services.conversation.knowledge_sources.base import KnowledgeSource, Evidence


class KnowledgeStoreSource(KnowledgeSource):
    """معرفة منظمة (Facts) — بتستقبل crop/topic جاهزين من الـ Context،
    مفيش إعادة تصنيف جوّاه."""

    def __init__(self, knowledge_controller, project_id: int, limit: int = 3):
        self.knowledge_controller = knowledge_controller
        self.project_id = project_id
        self.limit = limit

    async def fetch(self, context: ConversationContext) -> Evidence:
        topic = getattr(context.intent, "topic", None) or "general"
        result = await self.knowledge_controller.fetch_knowledge_records_answer(
            project_id=self.project_id,
            crop=context.current_crop,
            topic=topic,
            limit=self.limit,
        )
        if not result:
            return Evidence(found=False)

        return Evidence(text=result["answer"], sources=result.get("sources", []), is_final_answer=False)
