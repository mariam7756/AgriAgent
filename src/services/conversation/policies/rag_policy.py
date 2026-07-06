from services.conversation.policies.base import Policy
from services.conversation.context import ConversationContext


class RAGPolicy(Policy):
    """آخر حل — لو مفيش Policy تانية اتفعّلت. البحث في المستندات المرفوعة
    (Vector RAG)، ولو مفيش نتيجة ذات صلة، الموديل يجاوب من معرفته العامة."""
    priority = 99
    decision_name = "vector_rag"

    def matches(self, context: ConversationContext) -> bool:
        return True  # fallback دايمًا بيوافق
