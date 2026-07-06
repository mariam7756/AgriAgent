"""
Conversation Memory — Postgres Backed
بيحل مشكلة _MEMORY_STORE = {} اللي بيتمسح مع كل server restart.
"""
import re
from typing import Dict, List, Optional
from sqlalchemy.future import select
from sqlalchemy import update, delete
from models.db_schemes.minirag.schemes.project import ConversationSession
from knowledge.entities import extract_name, extract_governorate


MAX_TURNS = 10
MAX_HISTORY_TO_MODEL = 6  # آخر 6 رسائل (3 دورات) بتتبعت فعليًا للـ LLM


# ── Slot extraction: قواعد بسيطة تستخرج تفاصيل ذكرها المستخدم عرضًا ──────────
_SLOT_PATTERNS = {
    "location": [
        (r"قدام (?:ال)?بيت", "قدام البيت"),
        (r"جنب (?:ال)?بيت", "جنب البيت"),
        (r"(?:في|فى) (?:ال)?جنينة", "في الجنينة"),          # ← كانت ناقصة (الكلمة العامية للحديقة)
        (r"(?:في|فى) (?:ال)?حديقة", "في الحديقة"),
        (r"(?:في|فى) (?:ال)?أرض|(?:في|فى) (?:ال)?ارض", "في الأرض المكشوفة"),
        (r"(?:في|فى) (?:ال)?شرفة|(?:في|فى) (?:ال)?بلكونة", "في الشرفة"),
        (r"(?:في|فى) (?:ال)?أصيص|(?:في|فى) (?:ال)?اصيص", "في أصيص"),
    ],
    "sun_exposure": [
        (r"مشمس", "مشمسة"),
        (r"شمس (?:طول|كل)? ?اليوم", "شمس طول اليوم"),
        (r"مفيهاش شمس|من غير شمس|ضل طول اليوم", "مفيهاش شمس كافية"),
    ],
    "watering_frequency": [
        (r"كل يوم|يوميًا|يوميا", "يومي"),
        (r"يوم بعد يوم|كل يومين", "كل يومين"),
        (r"مرتين? (?:في|فى) الأسبوع|مرتين (?:في|فى) الاسبوع", "مرتين أسبوعيًا"),
        (r"مرة (?:في|فى) الأسبوع|مرة (?:في|فى) الاسبوع", "مرة أسبوعيًا"),
    ],
    "soil_type": [
        (r"تربة رملية|رملي", "رملية"),
        (r"تربة طينية|طيني", "طينية"),
        (r"تربة صفراء", "صفراء"),
    ],
}


def extract_slots_from_text(text: str) -> Dict[str, str]:
    """بيدور على تفاصيل زي المكان/الشمس/الري/التربة/الاسم/المحافظة في كلام المستخدم
    العادي، من غير ما يحتاج المستخدم يجاوب على سؤال محدد بصيغة معينة."""
    text_lower = (text or "").lower()
    found: Dict[str, str] = {}
    for slot_name, patterns in _SLOT_PATTERNS.items():
        for pattern, normalized_value in patterns:
            if re.search(pattern, text_lower):
                found[slot_name] = normalized_value
                break

    name = extract_name(text)
    if name:
        found["user_name"] = name

    governorate = extract_governorate(text)
    if governorate:
        found["governorate"] = governorate

    return found


class PersistentConversationMemory:
    """
    Memory مرتبطة بـ Postgres — بتعيش بعد الـ restart.
    كل session_key (user_id أو project_session) ليها record مستقل.
    """

    def __init__(self, db_client, session_key: str, project_id: int):
        self.db_client = db_client
        self.session_key = session_key
        self.project_id = project_id
        self._record: Optional[ConversationSession] = None

    async def _load(self):
        """يجيب أو يعمل session record من الـ DB."""
        if self._record is not None:
            return
        async with self.db_client() as session:
            stmt = select(ConversationSession).where(
                ConversationSession.session_key == self.session_key,
                ConversationSession.project_id == self.project_id,
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()

            if not record:
                record = ConversationSession(
                    session_key=self.session_key,
                    project_id=self.project_id,
                    turns=[],
                    collected_slots={},
                )
                session.add(record)
                await session.commit()
                await session.refresh(record)

            self._record = record

    async def get_state(self) -> Dict:
        await self._load()
        turns = self._record.turns or []
        stored = self._record.collected_slots or {}
        return {
            "current_crop": self._record.current_crop,
            "growth_stage": self._record.growth_stage,
            "last_topic": self._record.last_topic,
            "last_problem": self._record.last_problem,
            "area_feddan": float(self._record.area_feddan or 1.0),
            # الحقل اللي كان ناقص وبيخلي البوت "ينسى" كل حاجة كل رسالة
            "recent_turns": turns[-MAX_HISTORY_TO_MODEL:],
            "is_first_message": len(turns) == 0,
            # entities الفعلية بس (مكان/شمس/اسم/محافظة..) — منفصلة عن الـ domain عمدًا
            "collected_slots": stored.get("entities", {}),
            "active_domain": stored.get("active_domain"),
        }

    async def get_current_crop(self) -> Optional[str]:
        await self._load()
        return self._record.current_crop

    async def get_recent_turns(self, n: int = MAX_HISTORY_TO_MODEL) -> List[Dict]:
        await self._load()
        turns = self._record.turns or []
        return turns[-n:]

    async def get_collected_slots(self) -> Dict:
        await self._load()
        stored = self._record.collected_slots or {}
        return dict(stored.get("entities", {}))

    async def resolve_crop_from_context(self, query: str) -> Optional[str]:
        """لو الـ query مش فيه محصول، يرجع المحصول من الـ memory."""
        FOLLOWUP_SIGNALS = {
            "اسقيه", "اسمده", "هرشه", "برشه", "هعالجه",
            "كام مرة", "امتى", "بعد كام", "المحصول", "النبات",
        }
        query_lower = (query or "").lower()
        if any(s in query_lower for s in FOLLOWUP_SIGNALS):
            return await self.get_current_crop()
        return None

    async def add_turn(
        self,
        role: str,
        content: str,
        crop: Optional[str] = None,
        topic: Optional[str] = None,
        problem: Optional[str] = None,
        new_slots: Optional[Dict[str, str]] = None,
        crop_changed: bool = False,
        active_domain: Optional[str] = None,
    ):
        await self._load()

        # حدث الـ turns
        turns = list(self._record.turns or [])
        turns.append({"role": role, "content": content[:500]})
        if len(turns) > MAX_TURNS:
            turns = turns[-MAX_TURNS:]

        stored = dict(self._record.collected_slots or {})
        entities = dict(stored.get("entities", {}))

        # لو المستخدم غيّر المحصول صراحة (مش هزرع X هزرع Y): نمسح تفاصيل خاصة
        # بالمحصول القديم (طور النمو، المشكلة) لكن نحافظ على معلومات المستخدم
        # العامة (الاسم، المحافظة) لأنها مش مرتبطة بمحصول معين.
        if crop_changed:
            entities.pop("growth_stage", None)
        if new_slots:
            entities.update({k: v for k, v in new_slots.items() if v})

        merged_slots = {
            "entities": entities,
            # active_domain حقل مستقل تمامًا عن الـ entities — ميتلخبطش معاهم
            # أبدًا حتى لو التخزين في نفس الـ JSONB column (مفيش migration جديدة).
            "active_domain": active_domain or stored.get("active_domain"),
        }

        new_growth_stage = None if crop_changed else self._record.growth_stage
        new_last_problem = None if crop_changed else (problem or self._record.last_problem)

        # حدث الـ state
        async with self.db_client() as session:
            stmt = (
                update(ConversationSession)
                .where(ConversationSession.session_key == self.session_key,
                       ConversationSession.project_id == self.project_id)
                .values(
                    turns=turns,
                    current_crop=crop or self._record.current_crop,
                    growth_stage=new_growth_stage,
                    last_topic=topic or self._record.last_topic,
                    last_problem=new_last_problem,
                    collected_slots=merged_slots,
                )
            )
            await session.execute(stmt)
            await session.commit()

        # حدث الـ cache
        self._record.turns = turns
        self._record.collected_slots = merged_slots
        self._record.growth_stage = new_growth_stage
        self._record.last_problem = new_last_problem
        if crop:
            self._record.current_crop = crop
        if topic:
            self._record.last_topic = topic

    async def to_dict(self) -> Dict:
        await self._load()
        return {
            "session_key": self.session_key,
            "state": await self.get_state(),
            "turns_count": len(self._record.turns or []),
        }


async def clear_session(db_client, session_key: str, project_id: int) -> bool:
    """يمسح جلسة محادثة بالكامل (المحصول المحفوظ، الـ entities، تاريخ الرسايل).
    مفيد قبل أي عرض/مناقشة عشان نضمن مفيش بيانات عالقة من تجربة سابقة
    (زي محصول قديم فضل محفوظ من اختبار مختلف تحت نفس session_key)."""
    async with db_client() as session:
        stmt = delete(ConversationSession).where(
            ConversationSession.session_key == session_key,
            ConversationSession.project_id == project_id,
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0


async def get_memory(
    db_client,
    session_key: str,
    project_id: int,
) -> PersistentConversationMemory:
    """Factory — يرجع memory object جاهز للاستخدام."""
    mem = PersistentConversationMemory(
        db_client=db_client,
        session_key=session_key,
        project_id=project_id,
    )
    await mem._load()
    return mem
