from services.conversation.policies.base import Policy
from services.conversation.context import ConversationContext


class GreetingPolicy(Policy):
    """تحية أو كلام عادي أو سؤال برة الزراعة — يروح للـ LLM مباشرة من غير
    استرجاع، لأن مفيش معلومة محددة مطلوبة."""
    priority = 2
    decision_name = "llm_only"

    def matches(self, context: ConversationContext) -> bool:
        classification = context.classification
        return bool(classification) and classification.message_type == "general_chat"

