"""
Prompt Builder — مسؤولية واحدة: يبني chat_history جاهز للـ LLM من
ConversationContext + الـ Evidence بعد التفكير. قبل كده الجزء ده كان
inline جوه NLPController.answer_rag_question (مسؤولية إضافية فوق
الـ retrieval والـ generation).
"""
from typing import List, Dict
from services.conversation.context import ConversationContext

LABEL_MAP = {
    "user_name": "اسم المستخدم",
    "governorate": "المحافظة",
    "location": "مكان الزراعة",
    "sun_exposure": "التعرض للشمس",
    "watering_frequency": "تكرار الري",
    "soil_type": "نوع التربة",
}


def known_facts_text(context: ConversationContext) -> str:
    """Helper مشترك (مش method جوه PromptBuilder) — بيستخدمه PromptBuilder
    و AgriculturalLLMSource كمان من غير ما يكرروا نفس المنطق."""
    entities = context.known_facts_snapshot()
    if not entities:
        return "لسه مفيش معلومات معروفة عن المستخدم — دي أول حاجة هتعرفها منه."

    parts = []
    if entities.get("user_name"):
        parts.append(f"اسم المستخدم: {entities['user_name']}")
    if entities.get("crop"):
        parts.append(f"المحصول: {entities['crop']}")
    for key, label in LABEL_MAP.items():
        if key == "user_name" or key not in entities:
            continue
        parts.append(f"{label}: {entities[key]}")

    if not parts:
        return "لسه مفيش معلومات معروفة عن المستخدم — دي أول حاجة هتعرفها منه."

    return "معلومات معروفة بالفعل عن المستخدم (متسألش عنها تاني): " + "، ".join(parts) + "."


class PromptBuilder:

    def _greeting_rule(self, context: ConversationContext) -> str:
        if context.is_first_message:
            return "دي أول رسالة في المحادثة — رحب بالمستخدم بجملة ودّية قصيرة مرة واحدة دلوقتي."
        return "المحادثة مستمرة بالفعل — ممنوع تقول 'أهلاً بيك' أو أي ترحيب تاني، ادخل في الموضوع على طول."

    def _style_instruction(self, context: ConversationContext) -> str:
        style = getattr(context.intent, "style", None) if context.intent else None
        if style == "how_to":
            return "المستخدم عايز خطوات عملية (إزاي يعمل الحاجة) — جاوب بخطوات مباشرة، متشرحش عن المحصول نفسه الأول."
        if style == "informational":
            return "المستخدم عايز يعرف معلومة عامة عن المحصول — نبذة مختصرة تكفي."
        return ""

    def build(
        self,
        context: ConversationContext,
        evidence_text: str,
        system_prompt_template,
    ) -> List[Dict]:
        if hasattr(system_prompt_template, "safe_substitute"):
            system_content = system_prompt_template.safe_substitute(
                greeting_rule=self._greeting_rule(context),
                known_facts=known_facts_text(context),
            )
        else:
            system_content = str(system_prompt_template) if system_prompt_template else "أنت AgriSense — مهندس زراعي مصري خبير."

        chat_history = [{"role": "system", "content": system_content}]
        chat_history.extend(context.recent_turns[-4:])

        user_parts = [f"المعلومات المتاحة:\n{evidence_text}"]

        style_instruction = self._style_instruction(context)
        if style_instruction:
            user_parts.append(style_instruction)

        if context.needs_planning and context.sub_questions:
            user_parts.append(
                "السؤال ده فيه أكتر من جزء (أصلي + فرضية 'لو') — رد على الجزء الأصلي "
                "الأول بوضوح، وبعدها اتعامل مع الفرضية بشكل منفصل ومختصر."
            )

        user_parts.append(f"---\nرسالة المستخدم: {context.user_message}\n\nرد بشكل طبيعي كخبير زراعي مصري.")
        chat_history.append({"role": "user", "content": "\n\n".join(user_parts)})

        return chat_history
