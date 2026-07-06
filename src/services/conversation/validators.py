"""
Input Validator + Output Validator.

OutputValidator دلوقتي Chain of Responsibility حقيقي: قائمة كائنات
مستقلة (كل واحد مسؤوليته حاجة واحدة)، بتتشغل بالترتيب — إضافة/إزالة فحص
بتتم بتعديل القائمة، مش بتعديل الكلاس نفسه.
"""
import re
from typing import List, Optional, Protocol


class InputValidator:
    """بينضّف رسالة المستخدم قبل ما تدخل الـ pipeline."""

    MAX_LENGTH = 800

    def clean(self, text: str) -> str:
        if not text:
            return ""
        cleaned = text.strip()
        cleaned = re.sub(r"\s{3,}", " ", cleaned)
        return cleaned[: self.MAX_LENGTH]


class ResponseCheck(Protocol):
    def apply(self, text: str) -> str: ...


class NoisePhraseCheck:
    _NOISE_PHRASES = [
        "المستند رقم", "بناءً على البيانات", "بناءً على المستندات",
        "وفقاً للسياق", "بالطبع،",
    ]

    def apply(self, text: str) -> str:
        for phrase in self._NOISE_PHRASES:
            text = text.replace(phrase, "")
        return text.strip()


class ForeignScriptCheck:
    _PATTERN = re.compile(
        r"[^\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF"
        r"\u0020-\u007E"
        r"\u2000-\u206F"
        r"\U0001F300-\U0001FAFF"
        r"]"
    )

    def apply(self, text: str) -> str:
        cleaned = self._PATTERN.sub("", text)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        return cleaned or text


class BoilerplateClosingCheck:
    """فحص دفاعي (مش بس تعليمة في البرومبت) — بيشيل الجملة الكليشيه اللي
    ظهرت متكررة في الاختبار الفعلي ('لو حابب أقولك كذا كمان قولي' وأشباهها)،
    عشان الحماية متعتمدش على التزام الموديل بالبرومبت لوحده."""

    _PATTERNS = [
        r"لو\s+حابب\s+أقولك\s+كذا\s+كمان\s+قولي[.،]?",
        r"لو\s+عايز[ةه]?\s+أقولك\s+كذا[.،]?",
    ]

    def apply(self, text: str) -> str:
        for pattern in self._PATTERNS:
            text = re.sub(pattern, "", text)
        return re.sub(r"\s{2,}", " ", text).strip()


class OutputValidator:
    def __init__(self, checks: Optional[List[ResponseCheck]] = None):
        self.checks: List[ResponseCheck] = checks or [
            NoisePhraseCheck(),
            ForeignScriptCheck(),
            BoilerplateClosingCheck(),
        ]

    def validate(self, answer: Optional[str]) -> Optional[str]:
        if not answer:
            return answer
        for check in self.checks:
            answer = check.apply(answer)
        return answer
