from services.conversation.policies.base import Policy
from services.conversation.context import ConversationContext


class FollowUpPolicy(Policy):
    """رد قصير (نفي/استكمال زي 'لا'، 'طب') — مايحتاجش مصدر معرفة جديد،
    يعتمد على الـ conversation history والكيانات المعروفة بس."""
    priority = 1
    decision_name = "follow_up"

    def matches(self, context: ConversationContext) -> bool:
        classification = context.classification
        return bool(classification) and classification.intent_hint == "negation_or_continuation"
