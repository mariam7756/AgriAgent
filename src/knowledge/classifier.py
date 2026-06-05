from typing import Optional

from .schemas import MessageClassificationResult, MessageType
from knowledge.ontology import AGRI_ONTOLOGY

# بناء قائمة المحاصيل تلقائياً من الـ ontology
ALL_CROP_NAMES: set = set()
for _crop_key, _crop_data in AGRI_ONTOLOGY.items():
    ALL_CROP_NAMES.add(_crop_key)
    ALL_CROP_NAMES.update(_crop_data.get("ar_names", []))

GREETINGS = {
    "اهلا", "أهلا", "أهلًا", "السلام عليكم", "مرحبا", "مرحباً",
    "صباح الخير", "مساء الخير", "هاي", "hi", "hello", "hey",
}
SMALL_TALK = {
    "كيف الحال", "عامل ايه", "عامل إيه", "شكرا", "شكراً", "تمام",
    "ممتاز", "عظيم", "how are you",
}
AGRI_HINTS = {
    "زراعة", "محصول", "تربة", "ري", "تسميد", "سماد", "مرض", "حشرة",
    "تقليم", "حصاد", "بذور", "شتل", "إنبات", "حقل", "مزرعة", "فدان",
    "crop", "irrigation", "fertilizer", "pest", "disease", "harvest",
} | ALL_CROP_NAMES

PROBLEM_HINTS = {
    "اصفر", "أصفر", "مرض", "حشرة", "تبقع", "ذبول", "مشكلة",
    "تعفن", "عفن", "يموت", "بتموت", "يتساقط", "ضعيف", "تلف",
    "yellow", "wilt", "rot", "pest", "disease", "dying",
}

FERTILIZATION_HINTS = {
    "خطة تسميد", "برنامج تسميد", "جدول تسميد", "تسميد",
    "fertilization plan", "fertilizer schedule",
}

PLAN_HINTS = {
    "خطة", "برنامج", "جدول", "plan", "schedule", "program",
}


class MessageClassifier:
    

    def classify(self, text: str, current_crop: Optional[str] = None) -> MessageClassificationResult:
        normalized = (text or "").strip()
        normalized_lower = normalized.lower()

        if not normalized:
            return MessageClassificationResult(
                message_type=MessageType.SMALL_TALK,
                confidence=0.55,
                response_template="ممكن توضح سؤالك الزراعي؟",
            )

        # Greeting
        if any(g in normalized_lower for g in GREETINGS):
            return MessageClassificationResult(
                message_type=MessageType.GREETING,
                confidence=0.95,
                response_template="أهلاً وسهلاً 🌱 أنا خضر، مساعدك الزراعي. كيف أقدر أساعدك النهارده؟",
            )

        # Small talk
        if any(s in normalized_lower for s in SMALL_TALK):
            return MessageClassificationResult(
                message_type=MessageType.SMALL_TALK,
                confidence=0.85,
                response_template="أنا بخير، جاهز أساعدك في أي سؤال زراعي — ري، تسميد، أمراض، أو زراعة.",
            )

        detected_crop = self._detect_crop(normalized_lower) or current_crop
        has_agri = any(h in normalized_lower for h in AGRI_HINTS)

        # Follow-up على محصول سابق
        if current_crop and any(
            w in normalized_lower for w in {"اسقيه", "اسمده", "اعالجه", "أسقيه", "أسمده", "برش", "هرش"}
        ):
            return MessageClassificationResult(
                message_type=MessageType.FOLLOW_UP,
                confidence=0.9,
                detected_crop=current_crop,
                intent_hint="follow_up",
                response_template=f"تمام، هكمل على محصول {current_crop}.",
            )

        # خطة تسميد مطلوبة صراحة
        if any(h in normalized_lower for h in FERTILIZATION_HINTS):
            return MessageClassificationResult(
                message_type=MessageType.AGRICULTURE_QUESTION,
                confidence=0.95,
                detected_crop=detected_crop,
                intent_hint="fertilization_plan",
                response_template="هجيبلك خطة التسميد كاملة.",
            )

        # مشكلة زراعية (تشخيص)
        if has_agri and any(p in normalized_lower for p in PROBLEM_HINTS):
            return MessageClassificationResult(
                message_type=MessageType.AGRICULTURE_PROBLEM,
                confidence=0.92,
                detected_crop=detected_crop,
                intent_hint="diagnosis",
                response_template="واضح إنها مشكلة زراعية، خليني أساعدك في التشخيص.",
            )

        # سؤال زراعي
        is_question = any(c in normalized for c in {"?", "؟"}) or any(
            normalized_lower.startswith(w) for w in {"كيف", "ازاي", "إزاي", "امتى", "إمتى", "ما", "هل", "what", "when", "how"}
        )
        if has_agri and is_question:
            return MessageClassificationResult(
                message_type=MessageType.AGRICULTURE_QUESTION,
                confidence=0.88,
                detected_crop=detected_crop,
                intent_hint="qa",
                response_template="سأبحث في المعرفة الزراعية للإجابة الدقيقة.",
            )

        # جملة زراعية (مش سؤال)
        if has_agri:
            return MessageClassificationResult(
                message_type=MessageType.AGRICULTURE_STATEMENT,
                confidence=0.8,
                detected_crop=detected_crop,
                intent_hint="clarify",
                response_template="ممتاز. هل عندك سؤال معين أو مشكلة محددة؟",
            )

        # خارج النطاق
        return MessageClassificationResult(
            message_type=MessageType.OUT_OF_SCOPE,
            confidence=0.94,
            response_template=(
                "أنا خضر، مساعد زراعي متخصص. أقدر أساعدك في المحاصيل والأمراض النباتية "
                "والري والتسميد والإرشاد الزراعي فقط."
            ),
        )

    def _detect_crop(self, text: str) -> Optional[str]:
        # ابحث في الـ ontology كاملاً
        for crop_key, data in AGRI_ONTOLOGY.items():
            if crop_key in text:
                return crop_key
            for ar_name in data.get("ar_names", []):
                if ar_name in text:
                    return crop_key
        return None
    