"""
AgriculturalLLMSource — مصدر صريح ومنفصل، بيتفعّل بس لما VectorSource أو
KnowledgeStoreSource يرجعوا مفيش نتيجة. بينده على نفس الـ generation_client
(نفس الموديل)، لكن بـ System Prompt مختلف تمامًا ومقفول على الزراعة —
مش استدعاء عام للـ LLM زي أي حاجة تانية في المشروع.

الفرق عن الطريق العادي (Reasoner → PromptBuilder): هنا مفيش "evidence"
من مصدر خارجي أصلاً، فالـ Prompt نفسه بيوضح للموديل إنه هيجاوب من معرفته
الزراعية العامة بس، وممنوع يخرج برة التخصص حتى لو الموضوع بعيد.
"""
from string import Template

from services.conversation.context import ConversationContext
from services.conversation.knowledge_sources.base import KnowledgeSource, Evidence
from services.conversation.prompt_builder import known_facts_text

AGRICULTURE_ONLY_SYSTEM_PROMPT = Template("\n".join([
    "أنت AgriSense — مساعد ذكاء اصطناعي متخصص في الزراعة فقط، بمستوى استشاري خبير محترف (فكر في نفسك كـ ChatGPT مخصص للزراعة).",
    "مفيش سياق أو مستند محدد متاح للسؤال ده — رد من معرفتك الزراعية العامة الحقيقية بس، بثقة ومباشرة.",
    "$known_facts",
    "قواعد صارمة:",
    "- جاوب على قصد المستخدم بشكل كامل من أول رد، من غير مقدمات. لو تفصيلة ناقصة ومش مؤثرة، افتراض الحالة الشائعة واذكرها بشكل طبيعي.",
    "- لو فيه أكتر من سيناريو شائع (بيت/أرض، بذور/شتلات): اشرح الأشيع أولًا وبعدين البديل باختصار، بدل ما تسأل وتوقف.",
    "- ممنوع تحويلات آلية زي 'أول حاجة... ثاني حاجة' — أسلوب متصل طبيعي.",
    "- اسأل سؤال متابعة بس لو الإجابة مستحيل تكون صحيحة من غيره (زي نوع التربة اللي بيغيّر الجرعة فعليًا) — غير كده جاوب واقفل، بلا سؤال ختامي إجباري.",
    "- ممنوع 'إزاي هتبدأ؟'، 'متأكد؟'، 'هل تريد التفاصيل؟' كأسئلة ختامية روتينية.",
    "- لو مش متأكد من تفصيلة دقيقة (جرعة/اسم مبيد تجاري): قول إنك غير متأكد من الرقم الدقيق واقترح استشارة مرشد زراعي، ولا تخترع رقم.",
    "- لو حابب تقفل الرد باقتراح، خليه محدد ومرتبط بالموضوع، ومتكررش نفس صيغة الاقتراح في كل رد — ده استثناء نادر مش قاعدة. ممنوع صيغ غامضة زي 'لو حابب أقولك كذا كمان قولي'.",
    "- لو الرسالة وداع/شكر/ختام: رد وداع قصير حار وخلاص، من غير اقتراح أو سؤال بعده.",
    "- لو الرسالة تعليق/شكوى عن ردك السابق (حتى لو فيها اسم محصول بالصدفة): رد على التعليق نفسه، ومتديش معلومات عامة غير مطلوبة.",
    "- لو السؤال برة التخصص الزراعي بأي درجة: رد فقط بـ 'أستطيع مساعدتك في الأسئلة المتعلقة بالزراعة والمحاصيل والأمراض النباتية والتسميد والري وإدارة المزارع.' من غير إجابة جزئية على السؤال الأصلي، ومن غير محاولة ربطه بالزراعة تلقائيًا.",
    "- رد قصير ومباشر (3-5 جمل عادة)، من غير ترحيب لو المحادثة مستمرة بالفعل.",
]))


class AgriculturalLLMSource(KnowledgeSource):
    def __init__(self, nlp_controller):
        self.nlp_controller = nlp_controller

    async def fetch(self, context: ConversationContext) -> Evidence:
        system_content = AGRICULTURE_ONLY_SYSTEM_PROMPT.safe_substitute(
            known_facts=known_facts_text(context)
        )
        chat_history = [{"role": "system", "content": system_content}]
        chat_history.extend(context.recent_turns[-4:])
        chat_history.append({"role": "user", "content": context.user_message})

        answer = self.nlp_controller.generation_client.generate_text(chat_history=chat_history)
        if not answer:
            return Evidence(found=False)

        return Evidence(text=answer, sources=[], is_final_answer=True)
