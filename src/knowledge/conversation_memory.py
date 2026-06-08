"""
Conversation Memory — Postgres Backed
بيحل مشكلة _MEMORY_STORE = {} اللي بيتمسح مع كل server restart.
"""
from typing import Dict, List, Optional
from sqlalchemy.future import select
from sqlalchemy import update
from models.db_schemes.minirag.schemes.project import ConversationSession


MAX_TURNS = 10


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
                )
                session.add(record)
                await session.commit()
                await session.refresh(record)

            self._record = record

    async def get_state(self) -> Dict:
        await self._load()
        return {
            "current_crop": self._record.current_crop,
            "growth_stage": self._record.growth_stage,
            "last_topic": self._record.last_topic,
            "last_problem": self._record.last_problem,
            "area_feddan": float(self._record.area_feddan or 1.0),
        }

    async def get_current_crop(self) -> Optional[str]:
        await self._load()
        return self._record.current_crop

    async def get_recent_turns(self, n: int = 4) -> List[Dict]:
        await self._load()
        turns = self._record.turns or []
        return turns[-n:]

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
    ):
        await self._load()

        # حدث الـ turns
        turns = list(self._record.turns or [])
        turns.append({"role": role, "content": content[:500]})
        if len(turns) > MAX_TURNS:
            turns = turns[-MAX_TURNS:]

        # حدث الـ state
        async with self.db_client() as session:
            stmt = (
                update(ConversationSession)
                .where(ConversationSession.session_key == self.session_key,
                       ConversationSession.project_id == self.project_id)
                .values(
                    turns=turns,
                    current_crop=crop or self._record.current_crop,
                    last_topic=topic or self._record.last_topic,
                    last_problem=problem or self._record.last_problem,
                )
            )
            await session.execute(stmt)
            await session.commit()

        # حدث الـ cache
        self._record.turns = turns
        if crop:
            self._record.current_crop = crop
        if topic:
            self._record.last_topic = topic
        if problem:
            self._record.last_problem = problem

    async def to_dict(self) -> Dict:
        await self._load()
        return {
            "session_key": self.session_key,
            "state": await self.get_state(),
            "turns_count": len(self._record.turns or []),
        }


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