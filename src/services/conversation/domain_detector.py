"""
Domain Detector — بيحدد هل الرسالة زراعية ولا عامة، **مش بناءً على الرسالة
الحالية بس** — بناءً على domain الـ Session كله + الرسالة الحالية.

بيحل مشكلة: "طب أعمل إيه؟" (مفيهاش كلمة زراعية) بعد "هزرع نعناع" — من غير
الطبقة دي، أي follow-up مالوش كلمة زراعية صريحة كان بيضيع الـ context.

3 حالات:
- "greeting"    → تحية/كلام عادي، مايأثرش على domain الـ session
- "agriculture" → صريح أو موروث من الـ session
- "general"     → صريح إنه خارج التخصص (حساب، أخبار، سياسة، إيميل...)
"""
import re
from typing import Optional

from services.conversation.context import ConversationContext

# كلمات لو موجودة، السؤال خارج التخصص صراحة (بغض النظر عن الـ session)
_OUT_OF_DOMAIN_SIGNALS = [
    r"\bاحسب\w*\b", r"\bرئيس\b", r"\bوزير\b", r"\bانتخابات\b",
    r"\bايميل\b", r"\bإيميل\b", r"\bكود\b", r"\bبرمجة\b",
    r"\bفيلم\b", r"\bمباراة\b", r"\bأسهم\b", r"\bعملة\b",
]

_GREETING_ONLY = {"السلام عليكم", "اهلا", "أهلا", "هاي", "هلا", "مرحبا"}


class DomainDetector:
    def detect(self, context: ConversationContext, session_domain: Optional[str]) -> str:
        text = context.user_message.strip()

        # أولوية قصوى: كلمة خارج التخصص صراحة (حتى لو الرسالة قصيرة زي التحية)
        if any(re.search(pat, text) for pat in _OUT_OF_DOMAIN_SIGNALS):
            return "general"

        # تحية/small talk خالص — ما تأثرش على domain الـ session المحفوظ
        if text in _GREETING_ONLY or (
            context.classification
            and context.classification.message_type == "general_chat"
            and len(text.split()) <= 3
        ):
            return "greeting"

        # سؤال زراعي صريح (فيه كيان/كلمة زراعية) → agriculture + يحفظ في الـ session
        if context.classification and context.classification.message_type in (
            "agriculture_question", "follow_up",
        ):
            return "agriculture"

        # مفيش دليل صريح في الرسالة الحالية — لو الـ session أصلاً زراعي، فضل زراعي
        # (ده جوهر "Domain-Aware Fallback": مش كل رسالة لوحدها)
        if session_domain == "agriculture":
            return "agriculture"

        return "general"
