from typing import Optional

from .schemas import MessageClassificationResult, MessageType
from knowledge.ontology import AGRI_ONTOLOGY


ALL_CROP_NAMES: set = set()
for _k, _v in AGRI_ONTOLOGY.items():
    ALL_CROP_NAMES.add(_k)
    ALL_CROP_NAMES.update(_v.get("ar_names", []))

# كلمات زراعية واضحة
AGRI_KEYWORDS = {
    "زراعة", "محصول", "تربة", "ري", "تسميد", "سماد", "مرض", "حشرة",
    "تقليم", "حصاد", "بذور", "شتل", "إنبات", "حقل", "مزرعة", "فدان",
    "نبات", "شجرة", "خضر", "خضروات", "فاكهة", "أعشاب", "بذرة", "شتلة",
    "تقاوي", "موسم", "مشتل", "رش", "مبيد", "سقي", "صرف",
    "crop", "irrigation", "fertilizer", "pest", "disease", "harvest",
    "plant", "soil", "farm", "tree", "vegetable", "herb",
} | ALL_CROP_NAMES

# خطة تسميد مطلوبة صراحة
FERTILIZATION_PLAN_HINTS = {
    "خطة تسميد", "برنامج تسميد", "جدول تسميد",
    "fertilization plan", "fertilizer schedule",
}




class MessageClassifier:
    """
    Classifier بسيط — 3 categories بس:
    1. agri_question   → knowledge store + RAG + LLM
    2. fertilization_plan → ontology مباشرة
    3. general_chat    → LLM مباشرة (greetings, small talk, out of scope)

    الـ LLM هو اللي يقرر شكل الرد في كل الحالات.
    الـ classifier بيقرر بس من فين تيجي المعلومة.
    """

    def classify(
        self,
        text: str,
        current_crop: Optional[str] = None,
    ) -> MessageClassificationResult:

        normalized = (text or "").strip()
        normalized_lower = normalized.lower()

        if not normalized:
            return MessageClassificationResult(
                message_type=MessageType.GENERAL_CHAT,
                confidence=0.9,
                detected_crop=None,
                intent_hint="empty",
            )

        detected_crop = self._detect_crop(normalized_lower) or current_crop
        

        # خطة تسميد مطلوبة صراحة → ontology
        if any(h in normalized_lower for h in FERTILIZATION_PLAN_HINTS):
            return MessageClassificationResult(
                message_type=MessageType.AGRICULTURE_QUESTION,
                confidence=0.97,
                detected_crop=detected_crop,
                intent_hint="fertilization_plan",
                
            )

        # سؤال زراعي واضح → knowledge + RAG
        if any(kw in normalized_lower for kw in AGRI_KEYWORDS):
            return MessageClassificationResult(
                message_type=MessageType.AGRICULTURE_QUESTION,
                confidence=0.88,
                detected_crop=detected_crop,
                intent_hint="qa",
                
            )

        # follow-up على محصول سابق → RAG
        if current_crop and any(
            w in normalized_lower for w in {
                "اسقيه", "اسمده", "اعالجه", "برش", "هرش",
                "كام مرة", "امتى", "بعد كام",
            }
        ):
            return MessageClassificationResult(
                message_type=MessageType.FOLLOW_UP,
                confidence=0.92,
                detected_crop=current_crop,
                intent_hint="follow_up",
            )

        # كل حاجة تانية → LLM مباشرة
        # (greetings, small talk, out of scope, أسئلة عامة)
        return MessageClassificationResult(
            message_type=MessageType.GENERAL_CHAT,
            confidence=0.85,
            detected_crop=detected_crop,
            intent_hint="chat",
        )

    def _detect_crop(self, text: str) -> Optional[str]:
        
        for crop_key, data in AGRI_ONTOLOGY.items():
            if crop_key in text:
                return crop_key
            for ar_name in data.get("ar_names", []):
                if ar_name in text:
                    return crop_key
        return None
    
