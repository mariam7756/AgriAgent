from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from controllers import KnowledgeController
from models import ResponseSignal
from models.KnowledgeModel import KnowledgeModel
from routes.schemes.knowledge import (
    FeedbackRequest,
    FertilizationPlanRequest,
    IngestionRequest,
    MessageClassificationRequest,
)

knowledge_router = APIRouter(prefix="/api/v1/knowledge", tags=["api_v1", "knowledge"])


@knowledge_router.post("/message/classify")
async def classify_message(payload: MessageClassificationRequest):
    controller = KnowledgeController()
    result = controller.classify_message(text=payload.text, current_crop=payload.current_crop)
    return JSONResponse(content={"signal": "message_classification_success", "result": result})


@knowledge_router.get("/assets/seed")
async def get_seed_assets():
    controller = KnowledgeController()
    data = controller.get_seed_knowledge_assets()
    return JSONResponse(content={"signal": "knowledge_assets_seed_success", "result": data})


@knowledge_router.post("/ingest/{project_id}")
async def ingest_knowledge(request: Request, project_id: int, payload: IngestionRequest):
    controller = KnowledgeController(db_client=request.app.db_client)
    stats = await controller.ingest_sources(
        project_id=project_id,
        include_web=payload.include_web,
        include_files=payload.include_files,
        include_seed=payload.include_seed,
        max_pages=payload.max_pages,
    )
    return JSONResponse(content={"signal": "knowledge_ingestion_success", "stats": stats})


@knowledge_router.post("/plan/fertilization")
async def get_fertilization_plan(request: Request, payload: FertilizationPlanRequest):
    controller = KnowledgeController(db_client=request.app.db_client)
    plan = controller.get_fertilization_plan_from_ontology(
        crop=payload.crop, area_feddan=payload.area_feddan
    )
    if not plan:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"signal": "plan_not_found", "message": f"No plan for crop: {payload.crop}"},
        )
    return JSONResponse(content={"signal": "fertilization_plan_success", "plan": plan})


@knowledge_router.post("/feedback")
async def submit_feedback(request: Request, payload: FeedbackRequest):
    knowledge_model = await KnowledgeModel.create_instance(db_client=request.app.db_client)
    rec = await knowledge_model.append_feedback(
        project_id=payload.project_id,
        question=payload.question,
        answer=payload.answer,
        feedback=payload.feedback,
    )
    return JSONResponse(content={"signal": "feedback_submitted", "feedback_id": rec.feedback_id})


@knowledge_router.delete("/reset/{project_id}")
async def reset_knowledge(request: Request, project_id: int):
    """احذف كل الـ knowledge records لمشروع معين"""
    knowledge_model = await KnowledgeModel.create_instance(db_client=request.app.db_client)
    await knowledge_model.replace_project_records(project_id=project_id, records_payload=[])
    return JSONResponse(content={"signal": "knowledge_reset_success", "project_id": project_id})