from pydantic import BaseModel
from typing import Optional




class MessageClassificationRequest(BaseModel):
    text: str
    current_crop: Optional[str] = None


class IngestionRequest(BaseModel):
    include_web: Optional[bool] = False
    include_files: Optional[bool] = True
    include_seed: Optional[bool] = True
    max_pages: Optional[int] = 2


class FertilizationPlanRequest(BaseModel):
    project_id: int = 1
    crop: str
    area_feddan: Optional[float] = 1.0


class FeedbackRequest(BaseModel):
    project_id: int = 1
    question: str
    answer: str
    feedback: Optional[str] = "positive"