from typing import Optional

from .schemas import MessageClassificationResult, MessageType, QueryIntentResult


INTENT_MAP = {
    frozenset({"مرض", "حشرة", "تبقع", "أصفر", "اصفر", "ذبول", "تعفن", "يموت", "ضعيف"}): ("diagnosis", "disease_management"),
    frozenset({"ازرع", "إزاي أزرع", "زراعة", "ميعاد زراعة", "كيف أزرع"}): ("cultivation", "cultivation"),
    frozenset({"ري", "اسقي", "سقي", "مياه", "جدول ري"}): ("irrigation", "irrigation"),
    frozenset({"سماد", "تسميد", "خطة تسميد", "يوريا", "فوسفات", "بوتاسيوم"}): ("fertilization", "fertilization"),
    frozenset({"حصاد", "قطاف", "جني"}): ("harvest", "harvest"),
    frozenset({"تربة", "تحليل تربة", "خصوبة"}): ("soil", "soil_management"),
}

# "إزاي أزرع نعناع" → عايز خطوات عملية
HOW_TO_SIGNALS = {"إزاي", "ازاي", "كيف", "طريقة", "خطوات", "عايز اعرف ازاي", "عاوزة اعرف ازاي"}
# "عايز أعرف عن النعناع" → عايز معلومة عامة عن المحصول نفسه
INFO_SIGNALS = {"إيه هو", "ايه هو", "يعني إيه", "يعني ايه", "معلومات عن", "عايز اعرف عن", "عاوزة اعرف عن", "احكيلي عن"}


class KnowledgeRouter:

    def _detect_style(self, text: str) -> Optional[str]:
        if any(s in text for s in HOW_TO_SIGNALS):
            return "how_to"
        if any(s in text for s in INFO_SIGNALS):
            return "informational"
        return None

    def detect_intent(self, query: str, message: MessageClassificationResult) -> QueryIntentResult:
        text = (query or "").lower()
        style = self._detect_style(text)

        if message.message_type == MessageType.FOLLOW_UP:
            return QueryIntentResult(
                intent="follow_up", crop=message.detected_crop, needs_memory=True, style=style
            )

        if message.intent_hint == "fertilization_plan":
            return QueryIntentResult(intent="fertilization", topic="fertilization", crop=message.detected_crop, style=style)

        if message.intent_hint == "diagnosis":
            return QueryIntentResult(intent="diagnosis", topic="disease_management", crop=message.detected_crop, style=style)

        for keywords, (intent, topic) in INTENT_MAP.items():
            if any(kw in text for kw in keywords):
                return QueryIntentResult(intent=intent, topic=topic, crop=message.detected_crop, style=style)

        return QueryIntentResult(intent="general_rag", topic="general", crop=message.detected_crop, style=style)

    def route(self, intent: QueryIntentResult) -> str:
        routing = {
            "cultivation":   "crop_knowledge",
            "irrigation":    "crop_knowledge",
            "fertilization": "fertilization_plan",
            "harvest":       "crop_knowledge",
            "soil":          "crop_knowledge",
            "diagnosis":     "disease_knowledge",
            "follow_up":     "memory_augmented_qa",
        }
        return routing.get(intent.intent, "general_rag")
    