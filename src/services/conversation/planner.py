"""
Planner — بيتفعّل بس لو الرسالة معقدة (فيها فرضية "لو" أو أكتر من كيان
في نفس الجملة). لغير كده، الـ pipeline بيتجاوزه تمامًا (زي ما اتفقنا:
مش كل رسالة محتاجة تحليل).

مثال بيتفعّل معاه: "عندي نعناع، ازرعه امتى؟ ولو عندي فطر؟"
مثال ميتفعّلش معاه: "ازرع نعناع امتى؟" (سؤال بسيط، مباشر لمصدر واحد)

النطاق الحالي (MVP وواضح حدوده): بيكتشف وجود فرضية ويجهّز تعليمة توضيحية
للـ LLM إنه يرد على الجزئين، بدل عمل retrieval منفصل لكل جزء (ده تطوير
لاحق لو ظهرت حاجة حقيقية له في الاختبار).
"""
import re
from typing import List

from services.conversation.context import ConversationContext

_HYPOTHETICAL_MARKERS = [r"\bو?لو\b", r"وإذا", r"وإزا"]


class Planner:
    def needs_planning(self, context: ConversationContext) -> bool:
        text = context.user_message or ""
        has_hypothetical = any(re.search(m, text) for m in _HYPOTHETICAL_MARKERS)
        return has_hypothetical

    def plan(self, context: ConversationContext) -> None:
        """يحلل الرسالة ويحدد لو محتاجة رد بجزئين، ويجهّز تعليمة للـ Prompt
        Builder — مش بيعمل retrieval بنفسه، هو بس بيحدد الشكل المطلوب."""
        context.needs_planning = True
        context.sub_questions = self._split_hypothetical(context.user_message)

    def _split_hypothetical(self, text: str) -> List[str]:
        parts = re.split(r"\bلو\b", text)
        return [p.strip() for p in parts if p.strip()]
