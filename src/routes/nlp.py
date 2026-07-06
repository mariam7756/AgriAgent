from fastapi import FastAPI, APIRouter, status, Request
from fastapi.responses import JSONResponse
from routes.schemes.nlp import PushRequest, SearchRequest
from models.ProjectModel import ProjectModel
from models.ChunkModel import ChunkModel
from controllers import NLPController
from controllers import KnowledgeController
from models import ResponseSignal
from knowledge.conversation_memory import get_memory, clear_session
from services.conversation.conversation_service import ConversationService


import logging

logger = logging.getLogger('uvicorn.error')

nlp_router = APIRouter(
    prefix="/api/v1/nlp",
    tags=["api_v1", "nlp"],
)

@nlp_router.post("/index/reset/{project_id}")
async def reset_project_index(request: Request, project_id: int):
    """
    يعمل cleanup كامل وآمن:
    1. يحذف الـ vector collection
    2. يمسح جدول chunks في Postgres
    المكافئ الآمن لـ TRUNCATE اليدوي — استخدمه قبل إعادة الـ push.
    """
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    chunk_model   = await ChunkModel.create_instance(db_client=request.app.db_client)

    project = await project_model.get_project_or_create_one(project_id=project_id)
    if not project:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.PROJECT_NOT_FOUND_ERROR.value},
        )

    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )

    # 1) احذف الـ vector collection
    await nlp_controller.reset_vector_db_collection(project=project)

    # 2) احذف الـ chunks من Postgres
    deleted_count = await chunk_model.delete_chunks_by_project_id(
        project_id=project_id
    )

    logger.info(f"Reset project {project_id}: deleted {deleted_count} chunks + vector collection.")

    return JSONResponse(content={
        "signal": "INDEX_RESET_SUCCESS",
        "deleted_chunks": deleted_count,
        "message": f"تم مسح {deleted_count} chunk والـ vector collection. جاهز لـ push جديد.",
    })


@nlp_router.post("/index/push/{project_id}")
async def index_project(request: Request, project_id: int, push_request: PushRequest):

    project_model = await ProjectModel.create_instance(
        db_client=request.app.db_client
    )

    chunk_model = await ChunkModel.create_instance(
        db_client=request.app.db_client
    )

    project = await project_model.get_project_or_create_one(
        project_id=project_id
    )

    if not project:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseSignal.PROJECT_NOT_FOUND_ERROR.value
            }
        )
    
    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser
    )

    has_records = True
    page_no = 1
    inserted_items_count = 0
    

    while has_records:
        page_chunks = await chunk_model.get_poject_chunks(project_id=project.project_id, page_no=page_no)
        if len(page_chunks):
            page_no += 1
        
        if not page_chunks or len(page_chunks) == 0:
            has_records = False
            break

        chunks_ids = [c.chunk_id for c in page_chunks]
        
        
        # Only reset on the first page
        current_do_reset = bool(push_request.do_reset) and page_no == 1
        is_inserted = await nlp_controller.index_into_vector_db(
            project=project,
            chunks=page_chunks,
            do_reset=current_do_reset,
            chunks_ids=chunks_ids,
        )

        if not is_inserted:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "signal": ResponseSignal.INSERT_INTO_VECTORDB_ERROR.value
                }
            )
        
        inserted_items_count += len(page_chunks)
        
    return JSONResponse(
        content={
            "signal": ResponseSignal.INSERT_INTO_VECTORDB_SUCCESS.value,
            "inserted_items_count": inserted_items_count
        }
    )

@nlp_router.get("/index/info/{project_id}")
async def get_project_index_info(request: Request, project_id: int):
    
    project_model = await ProjectModel.create_instance(
        db_client=request.app.db_client
    )

    project = await project_model.get_project_or_create_one(
        project_id=project_id
    )

    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser
    )

    collection_info = await nlp_controller.get_vector_db_collection_info(project=project)

    return JSONResponse(
        content={
            "signal": ResponseSignal.VECTORDB_COLLECTION_RETRIEVED.value,
            "collection_info": collection_info
        }
    )

@nlp_router.post("/index/search/{project_id}")
async def search_index(request: Request, project_id: int, search_request: SearchRequest):
    
    project_model = await ProjectModel.create_instance(
        db_client=request.app.db_client
    )

    project = await project_model.get_project_or_create_one(
        project_id=project_id
    )

    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )

    results = await nlp_controller.search_vector_db_collection(
        project=project, text=search_request.text, limit=search_request.limit
    )

    if not results:
        return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "signal": ResponseSignal.VECTORDB_SEARCH_ERROR.value
                }
            )
    
    return JSONResponse(
        content={
            "signal": ResponseSignal.VECTORDB_SEARCH_SUCCESS.value,
            "results": [ result.dict()  for result in results ]
        }
    )

@nlp_router.post("/index/reset-session/{project_id}")
async def reset_conversation_session(request: Request, project_id: int, search_request: SearchRequest):
    """
    يمسح جلسة محادثة محددة بالكامل (المحصول المحفوظ + الـ entities + التاريخ).
    مهم قبل أي عرض/مناقشة: لو نفس session_id (أو الافتراضي project_{id}_default
    لو الفرونت إند مبعتش session_id لسه) استُخدم في تجارب سابقة، محصول قديم
    (زي "قمح") ممكن يفضل عالق ويظهر غلط في سؤال عن محصول تاني تمامًا.
    body: {"text": "", "session_id": "<نفس الـ session المستخدمة في التطبيق>"}
    """
    session_key = search_request.session_id or f"project_{project_id}_default"
    deleted = await clear_session(
        db_client=request.app.db_client, session_key=session_key, project_id=project_id
    )
    return JSONResponse(content={"cleared": deleted, "session_key": session_key})

@nlp_router.post("/index/answer/{project_id}")
async def answer_rag(request: Request, project_id: int, search_request: SearchRequest):

    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    knowledge_controller = KnowledgeController(db_client=request.app.db_client)
    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )

    conversation_service = ConversationService(
        db_client=request.app.db_client,
        knowledge_controller=knowledge_controller,
        nlp_controller=nlp_controller,
        template_parser=request.app.template_parser,
    )

    result = await conversation_service.handle_message(
        project=project,
        project_id=project_id,
        session_id=search_request.session_id,
        text=search_request.text,
        current_crop_hint=search_request.current_crop,
    )

    if not result.get("answer"):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.RAG_ANSWER_ERROR.value},
        )
        


    return JSONResponse(content={
        "signal": ResponseSignal.RAG_ANSWER_SUCCESS.value,
        "answer": result["answer"],
        "sources": result.get("sources", []),
        "answer_mode": result.get("policy_decision"),
        "session_state": result.get("session_state"),
    })
    