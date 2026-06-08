from fastapi import FastAPI, APIRouter, status, Request
from fastapi.responses import JSONResponse
from routes.schemes.nlp import PushRequest, SearchRequest
from models.ProjectModel import ProjectModel
from models.ChunkModel import ChunkModel
from controllers import NLPController
from controllers import KnowledgeController
from models import ResponseSignal
from knowledge.conversation_memory import get_memory


import logging

logger = logging.getLogger('uvicorn.error')

nlp_router = APIRouter(
    prefix="/api/v1/nlp",
    tags=["api_v1", "nlp"],
)

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

@nlp_router.post("/index/answer/{project_id}")
async def answer_rag(request: Request, project_id: int, search_request: SearchRequest):

    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    # ── Persistent Conversation Memory ───────────────────────────────────
    from knowledge.conversation_memory import get_memory
    session_key = search_request.session_id or f"project_{project_id}_default"
    memory = await get_memory(
        db_client=request.app.db_client,
        session_key=session_key,
        project_id=project_id,
    )
    current_crop = (
        search_request.current_crop
        or await memory.get_current_crop()
        or await memory.resolve_crop_from_context(search_request.text)
    )
    memory_state = await memory.get_state()

    # ── Knowledge Store (ontology / fertilization / direct answers) ───────
    knowledge_controller = KnowledgeController(db_client=request.app.db_client)
    knowledge_answer = await knowledge_controller.answer_from_knowledge_store(
        project_id=project.project_id,
        query=search_request.text,
        current_crop=current_crop,
        limit=min(search_request.limit or 3, 3),
    )

    if knowledge_answer is not None:
        detected_crop = (
            knowledge_answer.get("flow", {})
            .get("classification", {})
            .get("detected_crop") or current_crop
        )
        await memory.add_turn(
            role="user",
            content=search_request.text,
            crop=detected_crop,
            topic=knowledge_answer.get("flow", {}).get("intent", {}).get("topic"),
        )
        await memory.add_turn(role="assistant", content=knowledge_answer["answer"])

        return JSONResponse(content={
            "signal": ResponseSignal.RAG_ANSWER_SUCCESS.value,
            "answer": knowledge_answer["answer"],
            "sources": knowledge_answer.get("sources", []),
            "flow": knowledge_answer.get("flow", {}),
            "answer_mode": knowledge_answer.get("mode", "knowledge_store"),
            "full_prompt": None,
            "chat_history": [],
            "session_state": await memory.to_dict(),
        })

    # ── RAG ───────────────────────────────────────────────────────────────
    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )

    answer, full_prompt, chat_history, sources = await nlp_controller.answer_rag_question(
        project=project,
        query=search_request.text,
        limit=min(search_request.limit or 3, 3),
        current_crop=current_crop,
        memory_state=memory_state,
    )

    if not answer:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseSignal.RAG_ANSWER_ERROR.value},
        )

    await memory.add_turn(
        role="user",
        content=search_request.text,
        crop=current_crop,
    )
    await memory.add_turn(role="assistant", content=answer)

    return JSONResponse(content={
        "signal": ResponseSignal.RAG_ANSWER_SUCCESS.value,
        "answer": answer,
        "sources": sources,
        "answer_mode": "rag",
        "full_prompt": full_prompt,
        "chat_history": chat_history,
        "session_state": await memory.to_dict(),
    })