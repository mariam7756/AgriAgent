import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy import Index

from .minirag_base import SQLAlchemyBase


class KnowledgeSource(SQLAlchemyBase):
    __tablename__ = "knowledge_sources"

    source_id = Column(Integer, primary_key=True, autoincrement=True)
    source_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    source_project_id = Column(Integer, ForeignKey("projects.project_id"), nullable=False)
    source_name = Column(String, nullable=False)
    source_type = Column(String, nullable=False)
    source_url = Column(String, nullable=True)
    source_country = Column(String, nullable=True)
    source_language = Column(String, nullable=False, default="ar")
    source_metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    records = relationship("KnowledgeRecord", back_populates="source")

    __table_args__ = (
        Index("ix_knowledge_source_project_id", source_project_id),
        Index("ix_knowledge_source_name", source_name),
    )


class KnowledgeRecord(SQLAlchemyBase):
    __tablename__ = "knowledge_records"

    record_id = Column(Integer, primary_key=True, autoincrement=True)
    record_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    record_project_id = Column(Integer, ForeignKey("projects.project_id"), nullable=False)
    record_source_id = Column(Integer, ForeignKey("knowledge_sources.source_id"), nullable=False)
    entity_type = Column(String, nullable=False, default="crop")
    name = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    country = Column(String, nullable=True)
    disease = Column(String, nullable=True)
    pest = Column(String, nullable=True)
    confidence = Column(Float, nullable=False, default=0.7)
    tags = Column(JSONB, nullable=True)
    normalized_facts = Column(JSONB, nullable=True)
    record_metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    source = relationship("KnowledgeSource", back_populates="records")

    __table_args__ = (
        Index("ix_knowledge_record_project_id", record_project_id),
        Index("ix_knowledge_record_name", name),
        Index("ix_knowledge_record_topic", topic),
        Index("ix_knowledge_record_disease", disease),
        Index("ix_knowledge_record_pest", pest),
    )


class KnowledgeFeedback(SQLAlchemyBase):
    __tablename__ = "knowledge_feedback"

    feedback_id = Column(Integer, primary_key=True, autoincrement=True)
    feedback_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    feedback_project_id = Column(Integer, ForeignKey("projects.project_id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    feedback = Column(String, nullable=False, default="pending")
    feedback_metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_knowledge_feedback_project_id", feedback_project_id),
    )