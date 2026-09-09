import logging
import os

import aiofiles  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, Request, UploadFile, status
from fastapi.responses import JSONResponse

from controllers import DataController, ProcessController
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

    is_valid, response_message = datacontroller.validate_file(file=file)

    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": response_message}
        )

    file_path, file_id = datacontroller.generate_unique_filepath(
        original_filename=file.filename or "unnamed_file", project_id=project_id)

    try:
        async with aiofiles.open(file_path, 'wb') as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await f.write(chunk)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error occurred while saving the file: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": ResponseSignal.FILE_UPLOAD_FAILED.value}
        )

    asset_resource = Asset(
        asset_project_id = project.project_id,
        asset_type = AssetType.FILE.value,
        asset_name = file_id,
        asset_size = os.path.getsize(file_path)
    )

    asset_record = await asset_model.create_asset(asset=asset_resource)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": ResponseSignal.FILE_UPLOAD_SUCCESS.value,
                 "file_ID": str(asset_record.asset_id),
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

    project_files_ids = {}
    if process_request.file_id:
        record = await asset_model.get_asset_record(
            asset_project_id=project.project_id,
            asset_name=process_request.file_id
        )
        if record is None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": ResponseSignal.FILE_ID_ERROR.value}
            )
        project_files_ids = {record.asset_project_id : record.asset_name}
    else:
        project_files = await asset_model.get_all_project_assets(
            asset_project_id=project.project_id,
            asset_type=AssetType.FILE.value
        )
        project_files_ids = {
            record.asset_id : record.asset_name
            for record in project_files
        }

    if len(project_files_ids) == 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": ResponseSignal.NO_FILE_ERROR.value}
            )

    process_controller = ProcessController(project_id=project_id)

    if do_reset:
        _= await chunk_model.delete_chunks_by_project_id(project_id=project.project_id)

    no_records = 0
    no_files = 0
    
    for asset_id, file_id in project_files_ids.items():

        file_content = process_controller.get_file_content(file_id=file_id)

        if file_content is None:
            logger.error(f"Error While processing file: {file_id}")
            continue

        file_chunks = process_controller.process_file_content(
            file_content=file_content,
            file_id=file_id,
            chunk_size=chunk_size,
            overlap=overlap,
        )

        if file_chunks is None or len(file_chunks) == 0:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": ResponseSignal.PROCESSING_FAILED.value}
            )

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

        no_records += await chunk_model.insert_many_chunks(chunks=file_chunks_records, batch_size=100)
        no_files += 1

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            'message' : ResponseSignal.PROCESSING_SUCCESS.value,
            'inserted_chunks' : no_records,
            'processed_files' : no_files
        }
    )