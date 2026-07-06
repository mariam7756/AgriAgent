"""
Policy Engine — بيشغّل كل Policy مسجّلة بترتيب الأولوية، وأول واحدة تطابق
هي اللي بتحدد القرار. إضافة مصدر معرفة جديد بكرة (Live Search مثلاً) =
ملف Policy جديد يتسجل هنا، من غير ما نلمس باقي القواعد.
"""
from typing import List

from services.conversation.context import ConversationContext
from services.conversation.policies.base import Policy
from services.conversation.policies.follow_up_policy import FollowUpPolicy
from services.conversation.policies.greeting_policy import GreetingPolicy
from services.conversation.policies.tool_policy import ToolPolicy
from services.conversation.policies.knowledge_store_policy import KnowledgeStorePolicy
from services.conversation.policies.rag_policy import RAGPolicy


class PolicyEngine:
    def __init__(self, policies: List[Policy] = None):
        self.policies = sorted(
            policies or [
                FollowUpPolicy(),
                GreetingPolicy(),
                ToolPolicy(),
                KnowledgeStorePolicy(),
                RAGPolicy(),
            ],
            key=lambda p: p.priority,
        )

    def decide(self, context: ConversationContext) -> str:
        for policy in self.policies:
            if policy.matches(context):
                context.policy_decision = policy.decision_name
                return policy.decision_name
        # هذا السطر نظريًا لا يوصله التنفيذ أبدًا (RAGPolicy بتوافق دايمًا)
        context.policy_decision = "vector_rag"
        return "vector_rag"
