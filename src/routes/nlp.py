import logging

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from tqdm.auto import tqdm

from controllers import NLPController
from models import ResponseSignal
from models.ChunkModel import chunkModel
from models.ProjectModel import ProjectModel

from .schema.nlp import PushRequest, SearchRequest

logger = logging.getLogger("uvicorn.error")

nlp_router = APIRouter(
    prefix="/api/v1/nlp",
    tags=["NLP"],
)

@nlp_router.post("/index/push/{project_id}")
async def index_project(request: Request, project_id: int, push_request: PushRequest):

    project_model = await ProjectModel.create_instance(
        db_client=request.app.state.db_client
    )

    project = await project_model.get_project_or_create_one(
        project_id=project_id
    )

    chunk_model = await chunkModel.create_instance(
        db_client=request.app.state.db_client
    )

    if not project:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message" : ResponseSignal.PROJECT_NOT_FOUND_ERROR.value}
        )

    nlp_controller = NLPController(vectordb_client=request.app.state.vectordb_client,
                                   generation_client=request.app.state.generation_client,
                                   embedding_client=request.app.state.embedding_client,
                                   template_parser=request.app.state.template_parser)

    has_records = True
    page_no = 1
    inserted_items_count = 0
    first_iteration = True

    collection_name = nlp_controller.create_collection_name(project_id=str(project.project_id))
    
    _ = await request.app.state.vectordb_client.create_collection(collection_name=collection_name,
                                                                embedding_size=request.app.state.embedding_client.embedding_size,
                                                                )
    
    total_chunks_count = await chunk_model.get_total_chunks_count(project_id=project.project_id)
    pbar = tqdm(total=total_chunks_count, desc="Vector Indexing Progress", position=0)

    while has_records:
        page_chunks = await chunk_model.get_chunks_by_project_id(project_id=project.project_id, page_no=page_no,)
        if len(page_chunks):
            page_no += 1

        if not page_chunks or len(page_chunks) == 0:
            has_records = False
            break 
        
        chunks_ids = [c.chunk_id for c in page_chunks]
        
        is_inserted = await nlp_controller.index_into_vector_db(
            project=project,
            chunks=page_chunks,
            chunks_ids=chunks_ids,
            do_reset=push_request.do_reset and first_iteration
        )

        if not is_inserted:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"message" : ResponseSignal.VECTOR_DB_INSERTION_ERROR.value}
            )

        pbar.update(len(page_chunks))
        inserted_items_count += len(page_chunks)
        first_iteration = False

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message" : ResponseSignal.VECTOR_DB_INSERTION_SUCCESS.value,
                 "inserted_items_count" : inserted_items_count}
    )

@nlp_router.get("/index/info/{project_id}")
async def get_project_index_info(request: Request, project_id: int):
    
    project_model = await ProjectModel.create_instance(
        db_client=request.app.state.db_client
    )

    project = await project_model.get_project_or_create_one(
        project_id=project_id
    )

    nlp_controller = NLPController(vectordb_client=request.app.state.vectordb_client,
                                   generation_client=request.app.state.generation_client,
                                   embedding_client=request.app.state.embedding_client,
                                   template_parser=request.app.state.template_parser)

    if not project:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message" : ResponseSignal.PROJECT_NOT_FOUND_ERROR.value}
        )

    collection_info = await nlp_controller.get_vector_db_collection_info(project=project)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message" : ResponseSignal.COLLECTION_INFO_SUCCESS.value,
                 "collection_info" : collection_info}
    )

@nlp_router.post("/index/search/{project_id}")
async def search_project_index(request: Request, project_id: int, search_request: SearchRequest):
    
    project_model = await ProjectModel.create_instance(
        db_client=request.app.state.db_client
    )

    project = await project_model.get_project_or_create_one(
        project_id=project_id
    )

    nlp_controller = NLPController(vectordb_client=request.app.state.vectordb_client,
                                   generation_client=request.app.state.generation_client,
                                   embedding_client=request.app.state.embedding_client,
                                   template_parser=request.app.state.template_parser)

    if not project:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message" : ResponseSignal.PROJECT_NOT_FOUND_ERROR.value}
        )

    search_results = await nlp_controller.search_in_vector_db(
        project=project,
        query=search_request.query,
        limit=search_request.limit
    )

    if not search_results:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message" : ResponseSignal.SEARCH_RESULTS_ERROR.value}
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message" : ResponseSignal.SEARCH_RESULTS_SUCCESS.value,
                 "search_results" : [result.dict() for result in search_results]
        }
    )

@nlp_router.post("/index/answer/{project_id}")
async def answer_rag_question(request: Request, project_id: int, search_request: SearchRequest):
    
    project_model = await ProjectModel.create_instance(
        db_client=request.app.state.db_client
    )

    project = await project_model.get_project_or_create_one(
        project_id=project_id
    )

    nlp_controller = NLPController(vectordb_client=request.app.state.vectordb_client,
                                   generation_client=request.app.state.generation_client,
                                   embedding_client=request.app.state.embedding_client,
                                   template_parser=request.app.state.template_parser)

    if not project:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message" : ResponseSignal.PROJECT_NOT_FOUND_ERROR.value}
        )

    answer, full_prompt, chat_history = await nlp_controller.answer_rag_question(
        project=project,
        query=search_request.query,
        limit=search_request.limit
    )

    if not answer:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message" : ResponseSignal.RAG_ANSWER_ERROR.value}
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message" : ResponseSignal.RAG_ANSWER_SUCCESS.value,
            "answer" : answer,
            "full_prompt" : full_prompt,
            "chat_history" : chat_history
        }
    )