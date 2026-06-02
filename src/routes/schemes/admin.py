from pydantic import BaseModel
from typing import List, Optional


class SyncRequest(BaseModel):
    labels: Optional[List[str]] = None
    max_pages: Optional[int] = 5
    chunk_size: Optional[int] = 1000
    overlap_size: Optional[int] = 100
    force_reindex: Optional[bool] = False