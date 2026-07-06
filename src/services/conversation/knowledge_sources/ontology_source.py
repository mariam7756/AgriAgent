import re
from typing import Optional

from services.conversation.context import ConversationContext
from services.conversation.knowledge_sources.base import KnowledgeSource, Evidence


class OntologySource(KnowledgeSource):
    """Tool حسابي دقيق (خطة تسميد) — بيستقبل crop جاهز من الـ Context،
    مفيش إعادة تصنيف جوّاه."""

    def __init__(self, knowledge_controller):
        self.knowledge_controller = knowledge_controller

    def _extract_area(self, text: str) -> float:
        match = re.search(r"(\d+(?:\.\d+)?)\s*فدان", text or "")
        return float(match.group(1)) if match else 1.0

    async def fetch(self, context: ConversationContext) -> Evidence:
        crop = context.current_crop
        if not crop:
            return Evidence(found=False)

        area = self._extract_area(context.user_message)
        result = self.knowledge_controller.build_fertilization_answer(crop=crop, area_feddan=area)
        if not result:
            return Evidence(found=False)

        return Evidence(
            text=result["answer"],
            sources=result.get("sources", []),
            is_final_answer=True,
        )
