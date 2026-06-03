from sqlalchemy import delete
from sqlalchemy.future import select

from .BaseDataModel import BaseDataModel
from .db_schemes import KnowledgeFeedback, KnowledgeRecord, KnowledgeSource


class KnowledgeModel(BaseDataModel):
    def __init__(self, db_client: object):
        super().__init__(db_client=db_client)
        self.collection = db_client

    @classmethod
    async def create_instance(cls, db_client: object):
        return cls(db_client)

    async def upsert_source(
        self,
        project_id: int,
        source_name: str,
        source_type: str,
        source_url: str = None,
        source_country: str = None,
        source_language: str = "ar",
        source_metadata: dict = None,
    ) -> KnowledgeSource:
        async with self.collection() as session:
            stmt = select(KnowledgeSource).where(
                KnowledgeSource.source_project_id == project_id,
                KnowledgeSource.source_name == source_name,
                KnowledgeSource.source_url == source_url,
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            if record:
                record.source_type = source_type
                record.source_country = source_country
                record.source_language = source_language
                record.source_metadata = source_metadata or {}
            else:
                record = KnowledgeSource(
                    source_project_id=project_id,
                    source_name=source_name,
                    source_type=source_type,
                    source_url=source_url,
                    source_country=source_country,
                    source_language=source_language,
                    source_metadata=source_metadata or {},
                )
                session.add(record)
            await session.commit()
            await session.refresh(record)
        return record

    async def replace_project_records(self, project_id: int, records_payload: list):
        async with self.collection() as session:
            await session.execute(
                delete(KnowledgeRecord).where(KnowledgeRecord.record_project_id == project_id)
            )
            for payload in records_payload:
                session.add(KnowledgeRecord(**payload))
            await session.commit()
        return len(records_payload)

    async def get_records(
        self,
        project_id: int,
        name: str = None,
        topic: str = None,
        limit: int = 10,
    ):
        async with self.collection() as session:
            stmt = select(KnowledgeRecord).where(KnowledgeRecord.record_project_id == project_id)
            if name:
                stmt = stmt.where(KnowledgeRecord.name == name)
            if topic:
                stmt = stmt.where(KnowledgeRecord.topic == topic)
            stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def append_feedback(
        self,
        project_id: int,
        question: str,
        answer: str,
        feedback: str = "pending",
        feedback_metadata: dict = None,
    ):
        rec = KnowledgeFeedback(
            feedback_project_id=project_id,
            question=question,
            answer=answer,
            feedback=feedback,
            feedback_metadata=feedback_metadata or {},
        )
        async with self.collection() as session:
            session.add(rec)
            await session.commit()
            await session.refresh(rec)
        return rec
    