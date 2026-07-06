"""
Reasoner — بيجمّع الـ Evidence (نتيجة Retriever واحد أو أكتر لو الـ Planner
فكك السؤال) في نص واحد منظم، قبل ما يوصل للـ Prompt Builder. الترتيب مهم:
Retriever → Evidence → Reasoner → Prompt Builder (الـ Prompt يتبني من نتيجة
التفكير، مش قبله).
"""
from services.conversation.context import ConversationContext


class Reasoner:
    def reason(self, context: ConversationContext) -> str:
        if not context.evidence:
            return "لا يوجد سياق محدد — أجب من خبرتك الزراعية العامة."

        if len(context.evidence) == 1:
            return context.evidence[0]

        # أكتر من مصدر (سؤال معقد فككه الـ Planner) — نظم الأدلة مع بعض
        combined = []
        for i, piece in enumerate(context.evidence, start=1):
            combined.append(f"[جزء {i}]\n{piece}")
        return "\n\n".join(combined)
