from qdrant_client import QdrantClient, models
from qdrant_client.models import PointStruct
from ..VectorDBInterface import VectorDBInterface
from ..VectorDBEnums import DistanceMethodEnums

from models.db_schemes import RetrievedDocument
from typing import List
import logging


class QdrantDBProvider(VectorDBInterface):

    def __init__(self, db_path: str, distance_method: str):

        self.client = None
        self.db_path = db_path
        

        if distance_method == DistanceMethodEnums.COSINE.value:
            self.distance_method = models.Distance.COSINE
        elif distance_method == DistanceMethodEnums.DOT.value:
            self.distance_method = models.Distance.DOT
        else:
            self.distance_method = models.Distance.COSINE

        self.logger = logging.getLogger(__name__)

    # CONNECT
    def connect(self):
        print(" Connecting to Qdrant...")
        self.client = QdrantClient(path=self.db_path)
        print(" Connected")

    def disconnect(self):
        self.client = None

    #  COLLECTION 
    def is_collection_existed(self, collection_name: str) -> bool:
        return self.client.collection_exists(collection_name)

    def list_all_collections(self) -> List:
        return self.client.get_collections()

    def get_collection_info(self, collection_name: str):
        try:
            return self.client.get_collection(collection_name)
        except Exception as e:
            self.logger.error(f"Get collection error: {e}")
            return None

    def delete_collection(self, collection_name: str):
        if self.is_collection_existed(collection_name):
            self.client.delete_collection(collection_name)
            return True
        return False

    def create_collection(self, collection_name: str, embedding_size: int, do_reset: bool = False):

        if do_reset:
            self.delete_collection(collection_name)

        if not self.is_collection_existed(collection_name):
            print(f"Creating collection: {collection_name}")

            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=embedding_size,
                    distance=self.distance_method
                )
            )

            print(" Collection created")
            return True

        return False

    
    def insert_one(self, collection_name: str, text: str,
                   vector: list, metadata: dict = None,
                   record_id: str = None):

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

    #  INSERT MANY 
    def insert_many(self, collection_name: str,
                    texts: list,
                    vectors: list,
                    metadata: list = None,
                    record_ids: list = None,
                    batch_size: int = 50):

        if not self.is_collection_existed(collection_name):
            print(" Collection not found")
            return False

        if metadata is None:
            metadata = [None] * len(texts)

        if record_ids is None:
            record_ids = list(range(len(texts)))

        total = len(texts)
        print(f"INSERTING {total} ITEMS INTO {collection_name}")

        for i in range(0, total, batch_size):

            batch_texts = texts[i:i + batch_size]
            batch_vectors = vectors[i:i + batch_size]
            batch_metadata = metadata[i:i + batch_size]
            batch_ids = record_ids[i:i + batch_size]

            points = []

            for x in range(len(batch_texts)):
                points.append(
                    PointStruct(
                        id=int(batch_ids[x]),
                        vector=batch_vectors[x],
                        payload={
                            "text": batch_texts[x],
                            "metadata": batch_metadata[x]
                        }
                    )
                )
                

            try:
                print(f" Upload batch {i} -> {i + len(points)}")

                self.client.upsert(
                    collection_name=collection_name,
                    points=points
                )

                print("Batch success")

            except Exception as e:
                self.logger.error(f"Insert error: {e}")
                return False

        return True

    # SEARCH 
    def search_by_vector(self, collection_name: str,
                         vector: list,
                         limit: int = 5):

        try:
            print("🔎 Searching...")

            results = self.client.query_points(
                collection_name=collection_name,
                query=vector,
                limit=limit,
                with_payload=True
            )

            points = results.points

            if not points:
                print(" NO RESULTS")
                return []

            return [
                RetrievedDocument(
                    score=p.score,
                    text=p.payload.get("text")
                )
                for p in points
            ]

        except Exception as e:
            self.logger.error(f"Search error: {e}")
            return []
        