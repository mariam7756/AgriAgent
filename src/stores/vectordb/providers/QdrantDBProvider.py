from qdrant_client import QdrantClient, models
from qdrant_client.models import PointStruct
from ..VectorDBInterface import VectorDBInterface
from ..VectorDBEnums import DistanceMethodEnums

from models.db_schemes import RetrievedDocument
from typing import List
import logging


class QdrantDBProvider(VectorDBInterface):

    def __init__(self, db_client, default_vector_size: int = 786,
                       distance_method: str = None, index_threshold: int=100):

        self.client = None
        self.db_client = db_client
        self.distance_method = None
        self.default_vector_size = default_vector_size
        

        self.distance_method = models.Distance.COSINE

        if distance_method == DistanceMethodEnums.DOT.value:
            self.distance_method = models.Distance.DOT


        self.logger = logging.getLogger("uvicorn")

    
    # CONNECT
    

    async def connect(self):
        
        self.client = QdrantClient(path=self.db_client)


    async def disconnect(self):
        self.client = None

    
    # COLLECTION
    

    async def is_collection_existed(self, collection_name: str) -> bool:
        return self.client.collection_exists(collection_name)

    async def list_all_collections(self):
        return self.client.get_collections()

    async def get_collection_info(self, collection_name: str):
        try:
            return self.client.get_collection(collection_name)

        except Exception as e:
            self.logger.error(f"Collection info error: {e}")
            return None

    async def delete_collection(self, collection_name: str):

        if await self.is_collection_existed(collection_name):
            self.client.delete_collection(collection_name)
            return True

        return False

    async def create_collection(
        self,
        collection_name: str,
        embedding_size: int,
        do_reset: bool = False
    ):

        if do_reset:
            await self.delete_collection(collection_name)

        if not await self.is_collection_existed(collection_name):
            self.logger.info(f"Creating new Qdrant collection: {collection_name}")
            


            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=embedding_size,
                    distance=self.distance_method
                )
            )


            return True

        return False

    
    # INSERT ONE
    
    async def insert_one(
        self,
        collection_name: str,
        text: str,
        vector: list,
        metadata: dict = None,
        record_id: str = None
    ):

        try:
            self.client.upsert(
                collection_name=collection_name,
                points=[
                    PointStruct(
                        id=int(record_id),
                        vector=vector,
                        payload={
                            "text": text,
                            "metadata": metadata
                        }
                    )
                ]
            )

            return True

        except Exception as e:
            self.logger.error(f"Insert one error: {e}")
            return False

    
    # INSERT MANY
    
    async def insert_many(
        self,
        collection_name: str,
        texts: list,
        vectors: list,
        metadata: list = None,
        record_ids: list = None,
        batch_size: int = 50
    ):

        if metadata is None:
            metadata = [None] * len(texts)

        if record_ids is None:
            record_ids = list(range(len(texts)))

        for i in range(0, len(texts), batch_size):

            points = [
                PointStruct(
                    id=int(record_ids[x]),
                    vector=vectors[i:i+batch_size][x],
                    payload={
                        "text": texts[i:i+batch_size][x],
                        "metadata": metadata[i:i+batch_size][x]
                    }
                )
                for x in range(len(texts[i:i+batch_size]))
            ]

            try:
                
                self.client.upsert(
                    collection_name=collection_name,
                    points=points
                )



            except Exception as e:
                self.logger.error(f"Insert error: {e}")
                return False

        return True


    # SEARCH
    
    async def search_by_vector(
        self,
        collection_name: str,
        vector: list,
        limit: int = 5
    ):

        try:
            
            results = self.client.query_points(
                collection_name=collection_name,
                query=vector,
                limit=limit,
                with_payload=True
            )
            
            points = results.points

            if not points:
                
                return []
            retrieved_docs = []
            for p in points:
                if isinstance(p, tuple):
                    point = p[1]
                else:
                    point = p
                    

                retrieved_docs.append(
                    RetrievedDocument(
                        score=getattr(point, "score", 0.0),
                        text=point.payload.get("text", ""),
                        metadata=point.payload.get("metadata", {}),
                        vector_score=getattr(point, "score", 0.0),
                    )
                )
                        
            return retrieved_docs
        except Exception as e:
            self.logger.error(f"Search error: {e}")
            return []
            
