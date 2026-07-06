from services.conversation.policies.base import Policy
from services.conversation.context import ConversationContext


class KnowledgeStorePolicy(Policy):
    """سؤال زراعي عام (زراعة/ري/تسميد/حصاد/تربة) — يتفحص الأول في
    knowledge_records المنظمة (Facts)، وده أرخص وأدق من البحث في المستندات."""
    priority = 4
    decision_name = "knowledge_store"

    def matches(self, context: ConversationContext) -> bool:
        classification = context.classification
        return bool(classification) and classification.message_type == "agriculture_question"
