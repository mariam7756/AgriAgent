"""
KnowledgeSource — Interface واحد لكل مصادر المعرفة. ConversationService
بيتعامل مع الواجهة دي بس، مش عارف أصلاً إن جواها KnowledgeController أو
NLPController أو أي حاجة تانية. ده اللي يسمح بإضافة مصدر جديد (LiveSearch
مثلاً) من غير ما ConversationService يتغيّر خالص.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from services.conversation.context import ConversationContext


@dataclass
class Evidence:
    text: Optional[str] = None
    sources: List[Dict] = field(default_factory=list)
    is_final_answer: bool = False
    found: bool = True   # False = "المصدر ده مالوش رد" (يفرق عن found=True بنص فاضي)


class KnowledgeSource(ABC):
    @abstractmethod
    async def fetch(self, context: ConversationContext) -> Evidence:
        """يرجع Evidence. لو مفيش معلومة، يرجع Evidence(found=False) —
        وده مختلف عن إرجاع نص فاضي."""
        raise NotImplementedError
