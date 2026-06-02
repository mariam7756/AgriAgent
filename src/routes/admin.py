import logging

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from controllers.IndexController import IndexController
from models import ResponseSignal
from models.ProjectModel import ProjectModel
from routes.schemes.admin import SyncRequest

logger = logging.getLogger("uvicorn.error")

admin_router = APIRouter(
    prefix="/api/v1/admin",
    tags=["api_v1", "admin"],
)


@admin_router.post("/sources/sync/{project_id}")
async def sync_sources(request: Request, project_id: int, sync_request: SyncRequest):
    project_model = await ProjectModel.create_instance(
        db_client=request.app.db_client
    )

    project = await project_model.get_project_or_create_one(
        project_id=project_id
    )

    index_controller = IndexController(
        db_client=request.app.db_client,
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )

    try:
        stats = await index_controller.sync_sources(
            project=project,
            labels=sync_request.labels,
            max_pages=sync_request.max_pages,
            chunk_size=sync_request.chunk_size,
            overlap_size=sync_request.overlap_size,
        )
    except Exception as exc:
        logger.error(f"Sync failed: {exc}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseSignal.SYNC_SOURCES_ERROR.value,
                "error": str(exc),
            },
        )

    return JSONResponse(
        content={
            "signal": ResponseSignal.SYNC_SOURCES_SUCCESS.value,
            "stats": stats,
        }
    )


@admin_router.get("/sources/status/{project_id}")
async def sources_status(request: Request, project_id: int):
    project_model = await ProjectModel.create_instance(
        db_client=request.app.db_client
    )

    project = await project_model.get_project_or_create_one(
        project_id=project_id
    )

    index_controller = IndexController(
        db_client=request.app.db_client,
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )

    status_data = await index_controller.get_sources_status(project=project)

    return JSONResponse(
        content={
            "signal": ResponseSignal.SOURCES_STATUS_SUCCESS.value,
            "status": status_data,
        }
    )