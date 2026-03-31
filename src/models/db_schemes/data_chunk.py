from pydantic import BaseModel, Field, validator
from typing import Optional
from bson import ObjectId 

class DataChunk(BaseModel):
   
    id: Optional[ObjectId] = Field(None, alias="_id")
    chunk_text: str = Field(..., min_length=1)
    chunk_metadata: Optional[dict] = Field(default_factory=dict) 
    chunk_order: int = Field(1, ge=0) 
    chunk_project_id: Optional[ObjectId] = None 
    chunk_asset_id: Optional[ObjectId] = None 

    class Config:
        arbitrary_types_allowed = True
        populate_by_name = True 

    @classmethod
    def get_indexes(cls):
        return [
            {
                "key": [
                    ("chunk_project_id", 1)
                ],
                "name": "chunk_project_id_index_1",
                "unique": False
            }
        ]