from typing import Optional

from pydantic import BaseModel


class MessageClassificationRequest(BaseModel):
    text: str
    current_crop: Optional[str] = None


class IngestionRequest(BaseModel):
    include_web: Optional[bool] = True
    include_files: Optional[bool] = True
    max_pages: Optional[int] = 2
