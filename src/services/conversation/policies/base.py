"""
Policy Interface — كل قاعدة قرار بتاعة "مين يجاوب على السؤال ده" لازم تنفذها.
كل Policy مستقلة، تقدر تتضاف/تتشال/تتعدل من غير ما تلمس Policies تانية
(Open/Closed Principle) — عكس if/elif طويلة في function واحدة.
"""
from abc import ABC, abstractmethod
from typing import Optional

from services.conversation.context import ConversationContext


class Policy(ABC):
    # رقم أقل = أولوية أعلى (يتفحص الأول)
    priority: int = 100
    decision_name: str = "unknown"

    @abstractmethod
    def matches(self, context: ConversationContext) -> bool:
        """هل القاعدة دي بتنطبق على الرسالة الحالية؟"""
        raise NotImplementedError
