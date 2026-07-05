from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    GREETING = "greeting"
    SMALL_TALK = "small_talk"
    AGRICULTURE_QUESTION = "agriculture_question"
    AGRICULTURE_STATEMENT = "agriculture_statement"
    AGRICULTURE_PROBLEM = "agriculture_problem"
    FOLLOW_UP = "follow_up"
    OUT_OF_SCOPE = "out_of_scope"
    GENERAL_CHAT = "general_chat"


class SourceDocument(BaseModel):
    source_id: Optional[str] = None
    source_name: str
    source_type: str
    source_url: Optional[str] = None
    language: str = "ar"
    country: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    content: str
    metadata: Dict = Field(default_factory=dict)


class KnowledgeRecord(BaseModel):
    entity_type: str
    name: str
    topic: str
    content: str
    source: str
    country: Optional[str] = None
    disease: Optional[str] = None
    pest: Optional[str] = None
    confidence: float = 0.7
    tags: List[str] = Field(default_factory=list)
    normalized_facts: List[str] = Field(default_factory=list)
    metadata: Dict = Field(default_factory=dict)


class MessageClassificationResult(BaseModel):
    message_type: MessageType
    confidence: float
    detected_crop: Optional[str] = None
    intent_hint: Optional[str] = None
    response_template: Optional[str] = None


class QueryIntentResult(BaseModel):
    intent: str
    crop: Optional[str] = None
    disease: Optional[str] = None
    pest: Optional[str] = None
    topic: Optional[str] = None
    needs_memory: bool = False
    
    style: Optional[str] = None
    