from .BaseDataModel import BaseDataModel
from .db_schemes.data_chunk import DataChunk
from .enums.DataBaseEnum import DataBaseEnum
from bson import ObjectId

class ChunkModel(BaseDataModel):
    def __init__(self, db_client: object):
        super().__init__(db_client=db_client)
        self.collection = self.db_client[DataBaseEnum.COLLECTION_CHUNK_NAME.value]

    @classmethod
    async def create_instance(cls, db_client: object):
        instance = cls(db_client)
        await instance.init_collection()
        return instance

    async def init_collection(self):
        all_collections = await self.db_client.list_collection_names()
        if DataBaseEnum.COLLECTION_CHUNK_NAME.value not in all_collections:
            self.collection = self.db_client[DataBaseEnum.COLLECTION_CHUNK_NAME.value]
            indexes = DataChunk.get_indexes()
            for index in indexes:
                await self.collection.create_index(index["key"], name=index["name"], unique=index["unique"])

    async def insert_many_chunks(self, chunks: list[DataChunk]):
        if not chunks: return 0
        chunks_data = [chunk.dict(by_alias=True, exclude_unset=True) for chunk in chunks]
        result = await self.collection.insert_many(chunks_data)
        return len(result.inserted_ids)

    async def delete_chunks_by_project_id(self, project_id: ObjectId):
        result = await self.collection.delete_many({"chunk_project_id": project_id})
        return result.deleted_count
