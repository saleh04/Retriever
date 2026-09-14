import asyncio
import codecs
import logging
import os

import aiofiles  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, Request, UploadFile, status
from fastapi.responses import JSONResponse

from controllers import DataController, NLPController, ProcessController
from helpers.config import Settings, get_settings
from models import AssetType, ResponseSignal
from models.AssetModel import AssetModel
from models.ChunkModel import chunkModel
from models.db_schemes import Asset, DataChunk
from models.ProjectModel import ProjectModel

from .schema.data import ProcessRequest

logger = logging.getLogger("uvicorn.error")

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["Data"] )

@data_router.post("/upload/{project_id}")
async def upload_file(request: Request, project_id: int, file: UploadFile,
                       app_settings: Settings = Depends(get_settings)):  # noqa: B008

    project_model = await ProjectModel.create_instance(
        db_client=request.app.state.db_client
    )

    project = await project_model.get_project_or_create_one(
        project_id=project_id
    )

    asset_model = await AssetModel.create_instance(
        db_client=request.app.state.db_client
    )

    datacontroller = DataController()

    header = await file.read(8)
    await file.seek(0)

    is_valid, response_message = datacontroller.validate_file(
        file=file,
        header=header,
    )

    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": response_message}
        )

    file_path = None

    try:
        file_path, file_id = datacontroller.generate_unique_filepath(
            original_filename=file.filename or "unnamed_file",
            project_id=str(project_id),
        )
        max_size = app_settings.FILE_ALLOWED_SIZES_MB * 1024 * 1024
        bytes_written = 0
        text_decoder = (
            codecs.getincrementaldecoder("utf-8")()
            if file.content_type == "text/plain"
            else None
        )

        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                bytes_written += len(chunk)
                if bytes_written > max_size:
                    raise ValueError(ResponseSignal.FILE_SIZE_EXCEEDED.value)

                if text_decoder is not None:
                    text_decoder.decode(chunk)

                await f.write(chunk)

            if text_decoder is not None:
                text_decoder.decode(b"", final=True)

        asset_resource = Asset(
            asset_project_id=project.project_id,
            asset_type=AssetType.FILE.value,
            asset_name=file_id,
            asset_size=bytes_written,
            asset_config={"content_type": file.content_type},
        )

        asset_record = await asset_model.create_asset(asset=asset_resource)
    except ValueError as e:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        if str(e) == ResponseSignal.FILE_SIZE_EXCEEDED.value:
            response_message = ResponseSignal.FILE_SIZE_EXCEEDED.value
        else:
            response_message = ResponseSignal.FILE_TYPE_NOT_SUPPORTED.value

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": response_message},
        )
    except Exception as e:  
        logger.exception("Error occurred while saving upload: %s", e)
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": ResponseSignal.FILE_UPLOAD_FAILED.value},
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": ResponseSignal.FILE_UPLOAD_SUCCESS.value,
                 "file_ID": asset_record.asset_id,
                 "file_name": asset_record.asset_name
                 }
    )

@data_router.post("/process/{project_id}")
async def process_endpoint(request: Request, project_id: int, process_request: ProcessRequest):

    chunk_size = process_request.chunk_size
    overlap = process_request.overlap
    do_reset = process_request.do_reset

    project_model = await ProjectModel.create_instance(
        db_client=request.app.state.db_client
    )

    project = await project_model.get_project_or_create_one(
        project_id=project_id
    )

    chunk_model = await chunkModel.create_instance(
        db_client=request.app.state.db_client
    )

    asset_model = await AssetModel.create_instance(
        db_client=request.app.state.db_client
    )
    
    nlp_controller = NLPController(vectordb_client=request.app.state.vectordb_client,
                                   generation_client=request.app.state.generation_client,
                                   embedding_client=request.app.state.embedding_client,
                                   template_parser=request.app.state.template_parser)

    project_files_ids = {}
    project_file_types = {}
    if process_request.file_id:
        record = None
        
        if str(process_request.file_id).isdigit():
            record = await asset_model.get_asset_by_id(
                asset_project_id=project.project_id,
                asset_id=process_request.file_id
            )
        else:
            record = await asset_model.get_asset_record(
                asset_project_id=project.project_id,
                asset_name=process_request.file_id
            )
            
        if record is None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": ResponseSignal.FILE_ID_ERROR.value}
            )
        project_files_ids = {record.asset_id: record.asset_name}
        project_file_types[record.asset_id] = (
            record.asset_config.get("content_type")
            if record.asset_config
            else None
        )
        
    else:
        project_files = await asset_model.get_all_project_assets(
            asset_project_id=project.project_id,
            asset_type=AssetType.FILE.value
        )
        project_files_ids = {
            record.asset_id : record.asset_name
            for record in project_files
        }
        project_file_types = {
            record.asset_id: (
                record.asset_config.get("content_type")
                if record.asset_config
                else None
            )
            for record in project_files
        }

    if len(project_files_ids) == 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": ResponseSignal.NO_FILE_ERROR.value}
            )

    process_controller = ProcessController(project_id=str(project_id))

    collection_name = nlp_controller.create_collection_name(
        project_id=str(project.project_id)
    )

    prepared_files = []
    failed_files = []
    skipped_files = []
    
    for asset_id, file_id in project_files_ids.items():
        existing_chunk_count = await chunk_model.get_chunk_count_by_asset_id(
                asset_id=asset_id
        )

        if existing_chunk_count > 0 and not do_reset:
            skipped_files.append({
                "file_id": asset_id,
                "file_name": file_id,
                "existing_chunks": existing_chunk_count,
            })
            continue
        
        try:
            file_content = await asyncio.to_thread(
                process_controller.get_file_content,
                file_id=file_id,
                content_type=project_file_types.get(asset_id),
            )

            if file_content is None:
                failed_files.append({
                    "file_id": asset_id,
                    "file_name": file_id,
                    "reason": ResponseSignal.FILE_UPLOAD_FAILED.value,
                    "existing_chunks": existing_chunk_count,
                })
                continue  
                
            file_chunks = process_controller.process_file_content(
                file_content=file_content,
                file_id=file_id,
                chunk_size=chunk_size,
                overlap=overlap,
            )

            if not file_chunks:
                failed_files.append({
                    "file_id": asset_id,
                    "file_name": file_id,
                })
                continue
            
            prepared_files.append((asset_id, file_id, file_chunks))
            
        except Exception as e:  
            logger.exception(f"Error while processing file: {file_id} - {e}")
            failed_files.append({
                "file_id": asset_id,
                "file_name": file_id,
            })
    
    if do_reset and failed_files:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "message": ResponseSignal.PROCESSING_FAILED.value,
                "failed_files": failed_files,
                "skipped_files": skipped_files,
            },
        )        
            
    if do_reset and process_request.file_id:
        asset_id = next(iter(project_files_ids))
        old_chunk_ids = await chunk_model.get_chunk_ids_by_asset_id(
            asset_id=asset_id
        )

        vectors_deleted = await request.app.state.vectordb_client.delete_by_record_ids(
            collection_name=collection_name,
            record_ids=old_chunk_ids,
        )
        if not vectors_deleted:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"message": ResponseSignal.VECTOR_DB_DELETION_ERROR.value}
            )

        await chunk_model.delete_chunks_by_asset_id(asset_id=asset_id)

    elif do_reset:
        
        vectors_deleted = await request.app.state.vectordb_client.delete_collection(
            collection_name=collection_name
        )
        await chunk_model.delete_chunks_by_project_id(
            project_id=project.project_id
        )
    
    no_records = 0
    no_files = 0
    
    for asset_id, file_id, file_chunks in prepared_files:
        file_chunks_records = [
            DataChunk(
                chunk_text=chunk.page_content,
                    chunk_metadata=chunk.metadata,
                    chunk_order=i+1,
                    chunk_project_id=project.project_id,
                    chunk_asset_id=asset_id
            )
            for i, chunk in enumerate(file_chunks)
        ]
        
        no_records += await chunk_model.insert_many_chunks(
            chunks=file_chunks_records,
            batch_size=100
        )
        no_files += 1
        
    if failed_files:
        message = ResponseSignal.PROCESSING_FAILED.value
    elif skipped_files and no_files == 0:
        message = ResponseSignal.ALREADY_PROCESSED.value
    else:
        message = ResponseSignal.PROCESSING_SUCCESS.value

    return JSONResponse(
        status_code=status.HTTP_200_OK if no_files > 0 or skipped_files else status.HTTP_400_BAD_REQUEST,
        content={
            'message' : message,
            'inserted_chunks' : no_records,
            'processed_files' : no_files,
            'skipped_files' : skipped_files,
            'failed_files' : failed_files
        }
    )