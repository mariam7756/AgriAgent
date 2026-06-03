from typing import Optional

from .schemas import MessageClassificationResult, MessageType


class MessageClassifier:
    GREETINGS = {"اهلا", "أهلا", "السلام عليكم", "مرحبا", "hi", "hello"}
    SMALL_TALK = {"كيف الحال", "عامل ايه", "عامل إيه", "شكرا", "شكراً"}
    AGRI_HINTS = {
        "زيتون", "قمح", "ذرة", "ارز", "أرز", "طماطم", "ري", "تسميد", "تقليم", "مرض", "حشرة",
    }
    PROBLEM_HINTS = {"اصفر", "أصفر", "مرض", "حشرة", "تبقع", "ذبول", "مشكلة"}

    def classify(self, text: str, current_crop: Optional[str] = None) -> MessageClassificationResult:
        normalized = (text or "").strip().lower()
        detected_crop = self._detect_crop(normalized)
        if not normalized:
            return MessageClassificationResult(
                message_type=MessageType.SMALL_TALK,
                confidence=0.55,
                response_template="ممكن توضح سؤالك الزراعي بشكل أكبر؟",
            )

        if any(token.lower() in normalized for token in self.GREETINGS):
            return MessageClassificationResult(
                message_type=MessageType.GREETING,
                confidence=0.95,
                response_template="أهلاً بك 🌱 كيف أستطيع مساعدتك في الزراعة اليوم؟",
            )

        if any(token.lower() in normalized for token in self.SMALL_TALK):
            return MessageClassificationResult(
                message_type=MessageType.SMALL_TALK,
                confidence=0.85,
                response_template="أنا هنا لمساعدتك في أي موضوع زراعي مثل الري والتسميد والأمراض.",
            )

        is_question = "?" in normalized or "؟" in normalized or normalized.startswith("كيف")
        has_agri_hint = any(token.lower() in normalized for token in self.AGRI_HINTS)

        if current_crop and ("اسقيه" in normalized or "اسمده" in normalized):
            return MessageClassificationResult(
                message_type=MessageType.FOLLOW_UP,
                confidence=0.88,
                detected_crop=current_crop,
                intent_hint="follow_up",
                response_template="مفهوم، سأكمل على نفس المحصول السابق.",
            )

        if has_agri_hint and any(token.lower() in normalized for token in self.PROBLEM_HINTS):
            return MessageClassificationResult(
                message_type=MessageType.AGRICULTURE_PROBLEM,
                confidence=0.9,
                detected_crop=detected_crop or current_crop,
                intent_hint="diagnosis",
                response_template="واضح أنها مشكلة زراعية، خلينا نبدأ بالتشخيص خطوة بخطوة.",
            )

        if has_agri_hint and is_question:
            return MessageClassificationResult(
                message_type=MessageType.AGRICULTURE_QUESTION,
                confidence=0.86,
                detected_crop=detected_crop or current_crop,
                intent_hint="qa",
                response_template="سأبحث لك في المعرفة الزراعية للإجابة الدقيقة.",
            )

        if has_agri_hint:
            return MessageClassificationResult(
                message_type=MessageType.AGRICULTURE_STATEMENT,
                confidence=0.8,
                detected_crop=detected_crop or current_crop,
                intent_hint="clarify",
                response_template="ممتاز. هل تريد نصائح زراعة أم حل مشكلة معينة؟",
            )

        return MessageClassificationResult(
            message_type=MessageType.OUT_OF_SCOPE,
            confidence=0.94,
            response_template=(
                "أنا مساعد زراعي متخصص، وأقدر أساعدك في المحاصيل والأمراض النباتية "
                "والري والتسميد والإرشاد الزراعي."
            ),
        )

    def _detect_crop(self, text: str) -> Optional[str]:
        if "زيتون" in text or "olive" in text:
            return "olive"
        if "قمح" in text or "wheat" in text:
            return "wheat"
        if "ذرة" in text or "corn" in text:
            return "corn"
        if "طماطم" in text or "tomato" in text:
            return "tomato"
        return None
