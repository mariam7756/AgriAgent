from .minirag_base import SQLAlchemyBase
from sqlalchemy import Column, Integer, DateTime, String, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid


class Project(SQLAlchemyBase):

    __tablename__ = "projects"

    project_id = Column(Integer, primary_key=True, autoincrement=True)
    project_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    chunks = relationship("DataChunk", back_populates="project")
    assets = relationship("Asset", back_populates="project")
    sessions = relationship("ConversationSession", back_populates="project")


class ConversationSession(SQLAlchemyBase):
    """
    Persistent conversation memory — بديل الـ _MEMORY_STORE = {} في RAM.
    بيتخزن في Postgres عشان يعيش بعد الـ server restart.
    """
    __tablename__ = "conversation_sessions"

    session_id = Column(Integer, primary_key=True, autoincrement=True)
    session_uuid = Column(
        UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False
    )
    session_key = Column(String, nullable=False, index=True)  # user_id أو project_id
    project_id = Column(
        Integer, ForeignKey("projects.project_id"), nullable=False
    )

    
    current_crop = Column(String, nullable=True)
    growth_stage = Column(String, nullable=True)
    last_topic = Column(String, nullable=True)
    last_problem = Column(String, nullable=True)
    area_feddan = Column(String, nullable=True, default="1.0")

    
    turns = Column(JSONB, nullable=True, default=list)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    project = relationship("Project", back_populates="sessions")