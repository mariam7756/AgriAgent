from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from controllers import KnowledgeController
from routes.schemes.knowledge import IngestionRequest, MessageClassificationRequest


knowledge_router = APIRouter(
    prefix="/api/v1/knowledge",
    tags=["api_v1", "knowledge"],
)


@knowledge_router.post("/message/classify")
async def classify_message(payload: MessageClassificationRequest):
    controller = KnowledgeController()
    result = controller.classify_message(text=payload.text, current_crop=payload.current_crop)
    return JSONResponse(
        content={
            "signal": "message_classification_success",
            "result": result,
        }
    )


@knowledge_router.get("/assets/seed")
async def get_seed_assets():
    controller = KnowledgeController()
    data = controller.get_seed_knowledge_assets()
    return JSONResponse(
        content={
            "signal": "knowledge_assets_seed_success",
            "result": data,
        }
    )


@knowledge_router.post("/ingest/{project_id}")
async def ingest_knowledge(request: Request, project_id: int, payload: IngestionRequest):
    controller = KnowledgeController(db_client=request.app.db_client)
    stats = await controller.ingest_sources(
        project_id=project_id,
        include_web=payload.include_web,
        include_files=payload.include_files,
        max_pages=payload.max_pages,
    )
    return JSONResponse(
        content={
            "signal": "knowledge_ingestion_success",
            "stats": stats,
        }
    )
