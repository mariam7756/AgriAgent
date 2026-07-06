
from typing import List, Optional


class ActiveEntityScope:
    def __init__(self, entity_value: Optional[str]):
        self.entity_value = entity_value

    def is_scoped(self) -> bool:
        return bool(self.entity_value)

    def matches(self, texts: List[str]) -> bool:
        """لو مفيش entity نشط، مفيش تقييد (True دايمًا). لو فيه، لازم
        اسمه يظهر صراحة في النصوص المسترجعة، غير كده نرفضها بالكامل."""
        if not self.is_scoped():
            return True
        joined = " ".join(t or "" for t in texts).lower()
        return self.entity_value.lower() in joined
