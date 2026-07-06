"""
ConversationContext — الكيان الواحد اللي بيتمرر بين كل طبقات الـ pipeline.

قبل كده: كل طبقة كانت بترجع تجيب current_crop / collected_slots / recent_turns
من الذاكرة لوحدها (تكرار + عدم تناسق محتمل بين الطبقات).

دلوقتي: يتحمّل مرة واحدة في أول الـ request، وكل الطبقات (Policy Engine,
Planner, Knowledge Sources, Prompt Builder) بتستقبله كـ parameter واحد
وتقرا/تعدّل عليه، من غير ما ترجع تسأل الداتابيز.

active_entities عام (Domain-Agnostic) — في مشروع الزراعة بيشيل crop/governorate/
location/..، وفي مشروع طبي بكرة يشيل patient/condition، من غير ما الكلاس نفسه يتغير.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class ConversationContext:
    session_key: str
    project_id: int
    user_message: str

    # ── Active Entities (كانت اسمها current_crop + collected_slots متفرقين) ──
    active_entities: Dict[str, str] = field(default_factory=dict)

    # ── Memory ──────────────────────────────────────────────────────────────
    recent_turns: List[Dict] = field(default_factory=list)
    is_first_message: bool = True

    # ── هيتحدد أثناء الـ pipeline (مش من الداتابيز) ─────────────────────────
    classification: Optional[Any] = None      # MessageClassificationResult
    intent: Optional[Any] = None               # QueryIntentResult
    policy_decision: Optional[str] = None       # "llm_only" | "tool_ontology" | "knowledge_store" | "vector_rag" | "follow_up"
    needs_planning: bool = False
    sub_questions: List[str] = field(default_factory=list)

    # ── Domain — حقل مستقل بمعناه (مش مدسوس جوه active_entities كـ "_session_domain") ──
    active_domain: Optional[str] = None   # "agriculture" | "general" | "greeting" | None

    # ── Evidence / Reasoning ─────────────────────────────────────────────────
    evidence: List[str] = field(default_factory=list)   # ممكن يبقى فيه أكتر من مصدر لو الـ Planner فكك السؤال
    is_final_answer: bool = False                        # لو مصدر رقمي دقيق (ontology) مش محتاج LLM يصيغه
    final_answer_text: Optional[str] = None
    sources: List[Dict] = field(default_factory=list)
    flow_debug: Dict = field(default_factory=dict)

    # ── يتحدث بعد استخراج الكيانات من الرسالة الحالية ────────────────────────
    new_entities: Dict[str, str] = field(default_factory=dict)
    entity_changed: bool = False   # لو المستخدم غيّر الكيان الأساسي (مش هزرع نعناع هزرع ريحان)

    @property
    def current_crop(self) -> Optional[str]:
        """اسم مختصر للكيان الأساسي في الدومين الزراعي — الأسماء التقنية
        الداخلية (active_entities) عامة، لكن الكود اللي بيتكلم عن زراعة
        بيحتاج اسم واضح."""
        return self.active_entities.get("crop")

    @current_crop.setter
    def current_crop(self, value: Optional[str]):
        if value:
            self.active_entities["crop"] = value

    def known_facts_snapshot(self) -> Dict[str, str]:
        """نسخة نظيفة من الكيانات المعروفة — تُستخدم في الـ Prompt Builder."""
        return dict(self.active_entities)
