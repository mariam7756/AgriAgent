from pydantic import BaseModel, Field, validator
from typing import Optional
from bson import ObjectId

# الـ Project هو Schema، لذا يجب أن يرث من BaseModel
class Project(BaseModel):
    # استخدام alias="_id" يحل مشكلة MongoDB تماماً
    id: Optional[ObjectId] = Field(None, alias="_id")
    project_id: str = Field(..., min_length=1)

    @validator('project_id')
    def validate_project_id(cls, value):
        if not value.isalnum():
            raise ValueError('project_id must be alphanumeric')
        return value

    class Config:  
        arbitrary_types_allowed = True
        # هذا السطر مهم جداً لكي يقبل Pydantic البيانات سواء كانت بـ id أو _id
        populate_by_name = True 
