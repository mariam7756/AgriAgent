"""
ConversationService — الـ Orchestrator الوحيد الحقيقي دلوقتي.

الفرق عن النسخة اللي فاتت: هنا مش بينده على NLPController.answer_rag_question
(اللي كانت بتعمل classify/prompt/generate/sanitize مكررة جوّاها) — بينده
على KnowledgeSource objects بس (VectorSource/OntologySource/KnowledgeStoreSource)،
وهو نفسه المسؤول الوحيد عن الـ prompt building والـ generation والـ validation.

كل الـ dependencies بتتحقن (Dependency Injection) بقيم افتراضية — سهل
تستبدل أي طبقة في الاختبار من غير ما تلمس الكلاس.
"""
from typing import Optional

from knowledge.classifier import MessageClassifier
from knowledge.router import KnowledgeRouter
from knowledge.conversation_memory import get_memory, extract_slots_from_text
from knowledge.entities import detect_crop_change
from knowledge.ontology import AGRI_ONTOLOGY

from services.conversation.context import ConversationContext
from services.conversation.policy_engine import PolicyEngine
from services.conversation.planner import Planner
from services.conversation.reasoner import Reasoner
from services.conversation.prompt_builder import PromptBuilder
from services.conversation.validators import InputValidator, OutputValidator
from services.conversation.domain_detector import DomainDetector
from services.conversation.knowledge_sources.vector_source import VectorSource
from services.conversation.knowledge_sources.ontology_source import OntologySource
from services.conversation.knowledge_sources.knowledge_store_source import KnowledgeStoreSource
from services.conversation.knowledge_sources.agricultural_llm_source import AgriculturalLLMSource

_OUT_OF_DOMAIN_REPLY = (
    "🌱 أنا متخصص في المساعدة الزراعية، فمش أقدر أقدّم إجابة دقيقة في الموضوع ده. "
    "لو عندك أي سؤال زراعي، أنا موجود."
)


class ConversationService:
    def __init__(
        self,
        db_client,
        knowledge_controller,
        nlp_controller,
        template_parser,
        classifier: Optional[MessageClassifier] = None,
        router: Optional[KnowledgeRouter] = None,
        policy_engine: Optional[PolicyEngine] = None,
        planner: Optional[Planner] = None,
        reasoner: Optional[Reasoner] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        input_validator: Optional[InputValidator] = None,
        output_validator: Optional[OutputValidator] = None,
        domain_detector: Optional[DomainDetector] = None,
    ):
        self.db_client = db_client
        self.knowledge_controller = knowledge_controller
        self.nlp_controller = nlp_controller
        self.template_parser = template_parser

        # Dependency Injection حقيقي — كل حاجة قابلة للاستبدال من بره
        self.classifier = classifier or MessageClassifier()
        self.router = router or KnowledgeRouter()
        self.policy_engine = policy_engine or PolicyEngine()
        self.planner = planner or Planner()
        self.reasoner = reasoner or Reasoner()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.input_validator = input_validator or InputValidator()
        self.output_validator = output_validator or OutputValidator()
        self.domain_detector = domain_detector or DomainDetector()

    async def _load_context(self, project_id, session_id, raw_text, current_crop_hint):
        session_key = session_id or f"project_{project_id}_default"
        memory = await get_memory(db_client=self.db_client, session_key=session_key, project_id=project_id)

        clean_text = self.input_validator.clean(raw_text)
        current_crop = (
            current_crop_hint
            or await memory.get_current_crop()
            or await memory.resolve_crop_from_context(clean_text)
        )
        state = await memory.get_state()

        context = ConversationContext(
            session_key=session_key,
            project_id=project_id,
            user_message=clean_text,
            active_entities=dict(state.get("collected_slots", {})),
            recent_turns=state.get("recent_turns", []),
            is_first_message=state.get("is_first_message", True),
            active_domain=state.get("active_domain"),
        )
        if current_crop:
            context.current_crop = current_crop
        return context, memory

    def _extract_entities(self, context: ConversationContext) -> None:
        context.new_entities = extract_slots_from_text(context.user_message)
        all_crop_names = {k: v.get("ar_names", []) for k, v in AGRI_ONTOLOGY.items()}
        crop_change = detect_crop_change(context.user_message, context.current_crop, all_crop_names)
        if crop_change:
            _, new_crop = crop_change
            context.current_crop = new_crop
            context.entity_changed = True

    def _classify_and_route(self, context: ConversationContext) -> None:
        # لو تغيير المحصول اتحدد بالفعل هذه الرسالة عن طريق صيغة نفي واضحة
        # ("مش هزرع نعناع هزرع ريحان") في _extract_entities، متلمسيهوش تاني هنا —
        # التحقق البسيط تحت (كشف أول اسم محصول في النص) ممكن يرجع محصول غلط
        # لو الجملة فيها اسمين محاصيل مع بعض (زي المثال ده بالظبط).
        if not context.entity_changed:
            explicit_crop = self.classifier.detect_explicit_crop(context.user_message)
            if explicit_crop and explicit_crop != context.current_crop:
                context.current_crop = explicit_crop
                context.entity_changed = True

        context.classification = self.classifier.classify(text=context.user_message, current_crop=context.current_crop)
        context.intent = self.router.detect_intent(query=context.user_message, message=context.classification)

        # لو مفيش محصول محفوظ قبل كده، والـ classification لقى اسم محصول
        # في الرسالة الحالية (أول ذكر ليه) — لازم يتسجل كـ current_crop فورًا،
        # غير كده هيفضل None طول الرسالة دي كلها (Ontology/Scope/Memory كلهم
        # هيتعاملوا معاه كإنه مفيش محصول أصلاً).
        if not context.current_crop and context.classification.detected_crop:
            context.current_crop = context.classification.detected_crop

    def _select_knowledge_source(self, decision: str, project, project_id: int):
        """بديل الـ if/elif — mapping من قرار الـ Policy Engine لكائن
        KnowledgeSource. إضافة مصدر جديد = سطر واحد هنا + كلاس جديد."""
        mapping = {
            "tool_ontology": OntologySource(self.knowledge_controller),
            "knowledge_store": KnowledgeStoreSource(self.knowledge_controller, project_id),
            "vector_rag": VectorSource(self.nlp_controller, project),
            "follow_up": VectorSource(self.nlp_controller, project),
        }
        return mapping.get(decision)

    async def handle_message(self, project, project_id: int, session_id: Optional[str], text: str, current_crop_hint: Optional[str] = None) -> dict:
        context, memory = await self._load_context(project_id, session_id, text, current_crop_hint)

        # [1] Entity Extraction
        self._extract_entities(context)

        # [2] Intent + Classification
        self._classify_and_route(context)

        # [3] Domain Detector — بيحدد المجال بناءً على الـ session كله، مش الرسالة لوحدها
        domain = self.domain_detector.detect(context, context.active_domain)
        if domain == "agriculture":
            context.active_domain = "agriculture"

        if domain == "general":
            final_text = self.output_validator.validate(_OUT_OF_DOMAIN_REPLY)
            await memory.add_turn(role="user", content=context.user_message, new_slots=context.new_entities)
            await memory.add_turn(role="assistant", content=final_text)
            return {"answer": final_text, "sources": [], "policy_decision": "out_of_domain",
                    "session_state": await memory.to_dict()}

        # [4] Policy Engine
        self.policy_engine.decide(context)

        # [5] Planner — لو الرسالة معقدة بس
        if self.planner.needs_planning(context):
            self.planner.plan(context)

        # [6] Knowledge Source (Interface — مش Controller مباشر)
        source = self._select_knowledge_source(context.policy_decision, project, project_id)
        if source:
            evidence = await source.fetch(context)
            if evidence.found and evidence.text:
                context.evidence.append(evidence.text)
                context.sources = evidence.sources
                if evidence.is_final_answer:
                    context.is_final_answer = True
                    context.final_answer_text = evidence.text

        # ── Fallback الصريح: لو المصدر الأساسي (RAG/Knowledge Store/Ontology)
        # مالقاش حاجة، نروح لـ AgriculturalLLMSource (زراعي مقفول)، مش أي مصدر
        # عام. ده Layer منفصل بالاسم والـ Prompt، مش استدعاء مموّه لموديل عام. ──
        if not context.is_final_answer and not context.evidence and context.policy_decision in (
            "knowledge_store", "tool_ontology", "vector_rag", "follow_up"
        ):
            fallback = AgriculturalLLMSource(self.nlp_controller)
            evidence = await fallback.fetch(context)
            if evidence.found and evidence.text:
                context.is_final_answer = True
                context.final_answer_text = evidence.text

        # [7-8] Reasoner + Prompt Builder + LLM (لو مفيش رد نهائي جاهز من Tool)
        if context.is_final_answer:
            final_text = context.final_answer_text
        else:
            evidence_text = self.reasoner.reason(context)
            system_prompt_template = self.template_parser.get("rag", "system_prompt")
            chat_history = self.prompt_builder.build(context, evidence_text, system_prompt_template)
            final_text = self.nlp_controller.generation_client.generate_text(chat_history=chat_history)

        # [9] Output Validator (Chain of Responsibility)
        final_text = self.output_validator.validate(final_text)

        # حفظ الذاكرة
        await memory.add_turn(
            role="user", content=context.user_message, crop=context.current_crop,
            new_slots=context.new_entities,
            crop_changed=context.entity_changed,
            active_domain=context.active_domain,
        )
        if final_text:
            await memory.add_turn(role="assistant", content=final_text)

        return {
            "answer": final_text,
            "sources": context.sources,
            "policy_decision": context.policy_decision,
            "needs_planning": context.needs_planning,
            "session_state": await memory.to_dict(),
        }
        