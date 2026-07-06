from services.conversation.policies.base import Policy
from services.conversation.context import ConversationContext


class ToolPolicy(Policy):
    """سؤال محتاج أداة حسابية دقيقة (زي خطة التسميد) — مش نص معرفة عام.
    ده فعليًا Calculator Tool، بس كان مسمى 'ontology_plan' في الكود القديم
    من غير ما يُعترف بيه كـ Tool صراحة."""
    priority = 3
    decision_name = "tool_ontology"

    def matches(self, context: ConversationContext) -> bool:
        classification = context.classification
        return bool(classification) and classification.intent_hint == "fertilization_plan"
