from .schemas import MessageClassificationResult, MessageType, QueryIntentResult


class KnowledgeRouter:
    def detect_intent(self, query: str, message: MessageClassificationResult) -> QueryIntentResult:
        text = (query or "").lower()
        if message.message_type == MessageType.FOLLOW_UP:
            return QueryIntentResult(intent="follow_up", crop=message.detected_crop, needs_memory=True)

        if any(token in text for token in {"مرض", "حشرة", "تبقع", "أصفر", "اصفر", "ذبول"}):
            return QueryIntentResult(intent="diagnosis", topic="disease_management")

        if any(token in text for token in {"ازرع", "زراعة", "زرع"}):
            return QueryIntentResult(intent="cultivation", topic="cultivation")

        if any(token in text for token in {"ري", "اسقي", "سقي"}):
            return QueryIntentResult(intent="irrigation", topic="irrigation")

        if any(token in text for token in {"سماد", "تسميد"}):
            return QueryIntentResult(intent="fertilization", topic="fertilization")

        return QueryIntentResult(intent="general_rag", topic="general")

    def route(self, intent: QueryIntentResult) -> str:
        if intent.intent in {"cultivation", "irrigation", "fertilization"}:
            return "crop_knowledge"
        if intent.intent == "diagnosis":
            return "disease_knowledge"
        if intent.intent == "follow_up":
            return "memory_augmented_qa"
        return "general_rag"
