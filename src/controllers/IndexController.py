import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from controllers.FAOCrawler import  FAOCrawler
from controllers.NLPController import NLPController
from controllers.ProcessController import ProcessController
from models.AssetModel import AssetModel
from models.ChunkModel import ChunkModel
from models.db_schemes import Asset, DataChunk
from models.enums.AssetTypeEnum import AssetTypeEnum

from .BaseController import BaseController

logger = logging.getLogger("uvicorn.error")


class IndexController(BaseController):

    def __init__(
        self,
        db_client,
        vectordb_client,
        generation_client,
        embedding_client,
        template_parser,
    ):
        super().__init__()
        self.db_client = db_client
        self.nlp_controller = NLPController(
            vectordb_client=vectordb_client,
            generation_client=generation_client,
            embedding_client=embedding_client,
            template_parser=template_parser,
        )

    def _asset_name_from_url(self, source_url: str) -> str:
        digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()
        return f"web_{digest[:16]}"

    def _build_asset_config(self, post: Dict, chunk_count: int) -> dict:
        return {
            "source_url": post["source_url"],
            "title": post["title"],
            "category": post["category"],
            "author": post.get("author"),
            "published_at": post.get("published_at"),
            "content_hash": post["content_hash"],
            "language": post.get("language", "ar"),
            "source_type": post.get("source_type", "web"),
            "source_name": post.get("source_name", "agro-lib"),
            "last_crawled_at": datetime.now(timezone.utc).isoformat(),
            "chunk_count": chunk_count,
        }

    def _build_chunk_metadata(self, post: Dict) -> dict:
        return {
            "source_url": post["source_url"],
            "title": post["title"],
            "category": post["category"],
            "author": post.get("author"),
            "published_at": post.get("published_at"),
            "language": post.get("language", "ar"),
            "source_type": post.get("source_type", "web"),
            "source_name": post.get("source_name", "agro-lib"),
        }

    def _chunk_post(
        self,
        project_id: int,
        post: Dict,
        chunk_size: int = 1000,
        overlap_size: int = 100,
    ):
        process_controller = ProcessController(project_id=str(project_id))
        chunk_metadata = self._build_chunk_metadata(post)
        document = type("Doc", (), {
            "page_content": post["content"],
            "metadata": chunk_metadata,
        })()

        chunks = process_controller.process_file_content(
            file_content=[document],
            file_id=post["source_url"],
            chunk_size=chunk_size,
            overlap_size=overlap_size,
        )

        if not chunks:
            return []

        enriched_chunks = []
        for chunk in chunks:
            enriched_chunks.append(type("Doc", (), {
                "page_content": f"[{post['title']}]\n{chunk.page_content}",
                "metadata": {
                    **chunk_metadata,
                },
            })())

        return enriched_chunks

    async def _index_chunks(self, project, chunks: List[DataChunk]):
        if not chunks:
            return False

        chunk_ids = [chunk.chunk_id for chunk in chunks]
        return await self.nlp_controller.index_into_vector_db(
            project=project,
            chunks=chunks,
            chunks_ids=chunk_ids,
            do_reset=False,
        )

    async def _remove_asset_vectors(self, project, asset_id: int, chunk_model: ChunkModel):
        existing_chunks = await chunk_model.get_chunks_by_asset_id(asset_id=asset_id)
        if not existing_chunks:
            return

        chunk_ids = [chunk.chunk_id for chunk in existing_chunks]
        collection_name = self.nlp_controller.create_collection_name(
            project_id=project.project_id
        )
        await self.nlp_controller.vectordb_client.delete_by_chunk_ids(
            collection_name=collection_name,
            chunk_ids=chunk_ids,
        )

    async def sync_sources(
        self,
        project,
        labels: Optional[List[str]] = None,
        max_pages: int = 2,
        chunk_size: int = 1000,
        overlap_size: int = 100,
        force_reindex: bool = False,
    ) -> Dict:
        crawler = FAOCrawler()
        asset_model = await AssetModel.create_instance(db_client=self.db_client)
        chunk_model = await ChunkModel.create_instance(db_client=self.db_client)

        posts = await crawler.crawl_labels(labels=labels, max_pages=max_pages)

        stats = {
            "crawled": len(posts),
            "new": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "indexed_chunks": 0,
        }

        for post in posts:
            try:
                existing_asset = await asset_model.get_web_asset_by_source_url(
                    asset_project_id=project.project_id,
                    source_url=post["source_url"],
                )

                if existing_asset and not force_reindex:
                    old_hash = (existing_asset.asset_config or {}).get("content_hash")
                    if old_hash == post["content_hash"]:
                        stats["skipped"] += 1
                        continue

                if existing_asset:
                    await self._remove_asset_vectors(
                        project=project,
                        asset_id=existing_asset.asset_id,
                        chunk_model=chunk_model,
                    )
                    await chunk_model.delete_chunks_by_asset_id(
                        asset_id=existing_asset.asset_id
                    )
                    asset_id = existing_asset.asset_id
                    stats["updated"] += 1
                else:
                    asset = Asset(
                        asset_project_id=project.project_id,
                        asset_type=AssetTypeEnum.WEB.value,
                        asset_name=self._asset_name_from_url(post["source_url"]),
                        asset_size=len(post["content"].encode("utf-8")),
                        asset_config={},
                    )
                    
                    stats["new"] += 1

                raw_chunks = self._chunk_post(
                    project_id=project.project_id,
                    post=post,
                    chunk_size=chunk_size,
                    overlap_size=overlap_size,
                )

                if not raw_chunks:
                    stats["errors"] += 1
                    continue

                chunk_records = [
                    DataChunk(
                        chunk_text=chunk.page_content,
                        chunk_metadata=chunk.metadata,
                        chunk_order=i + 1,
                        chunk_project_id=project.project_id,
                        chunk_asset_id=asset_id,
                    )
                    for i, chunk in enumerate(raw_chunks)
                ]

                await chunk_model.insert_many_chunks(chunks=chunk_records)
                chunk_records = await chunk_model.get_chunks_by_asset_id(asset_id)

                indexed = await self._index_chunks(project=project, chunks=chunk_records)
                if not indexed:
                    stats["errors"] += 1
                    continue

                await asset_model.update_asset_config(
                    asset_id=asset_id,
                    asset_size=len(post["content"].encode("utf-8")),
                    asset_config=self._build_asset_config(
                        post=post,
                        chunk_count=len(chunk_records),
                    ),
                )
               
                stats["indexed_chunks"] += len(chunk_records)

            except Exception as exc:
                logger.error(f"Failed to sync post {post.get('source_url')}: {exc}")
                stats["errors"] += 1

        return stats

    async def get_sources_status(self, project) -> Dict:
        asset_model = await AssetModel.create_instance(db_client=self.db_client)
        chunk_model = await ChunkModel.create_instance(db_client=self.db_client)

        web_assets = await asset_model.get_all_project_assets(
            asset_project_id=project.project_id,
            asset_type=AssetTypeEnum.WEB.value,
        )

        last_crawled_at = None
        categories = {}

        for asset in web_assets:
            config = asset.asset_config or {}
            category = config.get("category", "unknown")
            categories[category] = categories.get(category, 0) + 1

            crawled_at = config.get("last_crawled_at")
            if crawled_at and (last_crawled_at is None or crawled_at > last_crawled_at):
                last_crawled_at = crawled_at

        collection_info = await self.nlp_controller.get_vector_db_collection_info(project=project)
        vector_count = 0
        if collection_info:
            vector_count = collection_info.get("record_count", 0)

        total_chunks = await chunk_model.get_total_chunks_count(project_id=project.project_id)

        return {
            "total_web_assets": len(web_assets),
            "total_chunks": total_chunks,
            "vector_count": vector_count,
            "last_sync_at": last_crawled_at,
            "categories": categories,
        }
