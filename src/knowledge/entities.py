"""
Entity Extractor — استخراج كيانات من كلام المستخدم:
- الاسم
- المحافظة
- تغيير المحصول (المستخدم غيّر رأيه من محصول لمحصول تاني)

الملف ده منفصل عن extract_slots_from_text (اللي بيستخرج تفاصيل مكانية/بيئية)
عشان نفصل مسؤولية كل نوع كيان — Single Responsibility.
"""
import re
from typing import Optional, Tuple

EGYPT_GOVERNORATES = [
    "القاهرة", "الجيزة", "الإسكندرية", "الاسكندرية", "الدقهلية", "المنيا",
    "كفر الشيخ", "أسيوط", "اسيوط", "سوهاج", "قنا", "أسوان", "اسوان",
    "البحيرة", "الشرقية", "الغربية", "المنوفية", "بورسعيد", "دمياط",
    "بني سويف", "الفيوم", "الوادي الجديد", "مطروح", "شمال سيناء",
    "جنوب سيناء", "الإسماعيلية", "الاسماعيلية", "السويس", "القليوبية",
    "الأقصر", "الاقصر",
]

_NAME_PATTERNS = [
    r"اسمي\s+([\u0600-\u06FF]{2,15})",
    r"انا\s+اسمي\s+([\u0600-\u06FF]{2,15})",
    r"أنا\s+اسمي\s+([\u0600-\u06FF]{2,15})",
    r"انا\s+([\u0600-\u06FF]{2,15})\s*$",  # "انا مريم" في آخر الجملة
]

# كلمات لو ظهرت بعد "انا" مش اسم (تجنب false positive زي "أنا هنا"، "أنا كويس")
_NAME_STOPWORDS = {"هنا", "كويس", "كويسة", "تمام", "بخير", "زعلانة", "زعلان", "مبسوط", "مبسوطة"}


def extract_name(text: str) -> Optional[str]:
    for pattern in _NAME_PATTERNS:
        match = re.search(pattern, text or "")
        if match:
            candidate = match.group(1).strip()
            if candidate and candidate not in _NAME_STOPWORDS:
                return candidate
    return None


def extract_governorate(text: str) -> Optional[str]:
    text_norm = (text or "")
    for gov in EGYPT_GOVERNORATES:
        if gov in text_norm:
            return gov
    return None


def detect_crop_change(text: str, current_crop: Optional[str], all_crop_names: dict) -> Optional[Tuple[str, str]]:
    """
    بيكتشف لو المستخدم غيّر رأيه من محصول لمحصول تاني في نفس الجملة، زي:
    "مش هزرع نعناع خلاص هزرع ريحان" → (نعناع, ريحان)

    all_crop_names: dict بشكل {crop_key: [الأسماء العربية]} من الـ ontology،
    بنمررها من بره عشان الملف ده يفضل مستقل من ontology.py.
    """
    text_norm = (text or "").lower()
    negation_signals = ["مش هزرع", "مش عايز أزرع", "بلاش", "خلاص مش", "غيرت رأيي"]

    if not any(sig in text_norm for sig in negation_signals):
        return None

    mentioned_crops = []
    for crop_key, ar_names in all_crop_names.items():
        if any(name.lower() in text_norm for name in ar_names):
            # نرجع crop_key (المفتاح الإنجليزي الداخلي زي 'mint')، مش الاسم
            # العربي — لأن الـ Ontology و OntologySource و ActiveEntityScope
            # لازم يستخدموا نفس المعرّف الموحّد لأي محصول، غير كده خطة
            # التسميد هتفشل بعد أي تغيير محصول لأنها بتدور بـ crop_key.
            mentioned_crops.append((crop_key, crop_key))

    if len(mentioned_crops) < 2:
        return None

    # أول محصول اتكتب هو القديم اللي بيرفضه، وآخر واحد هو الجديد
    old_crop = mentioned_crops[0][1]
    new_crop = mentioned_crops[-1][1]
    if old_crop == new_crop:
        return None
    return old_crop, new_crop
