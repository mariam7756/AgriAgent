from fastapi import APIRouter, Depends, UploadFile, File, status
from fastapi.responses import JSONResponse
from helpers.config import get_settings, Settings
from controllers.DataController import DataController
from controllers.ProjectController import ProjectController
from controllers.ProcessController import ProcessController
import aiofiles
from models import ResponseSignal
import logging
import os
from .schemes.data import ProcessRequest
 
logger = logging.getLogger("uvicorn.error")

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1"],
)


@data_router.post("/upload/{project_id}")
async def upload_data(
    project_id: str,
    file: UploadFile = File(...),
    app_settings: Settings = Depends(get_settings),
):
    data_controller = DataController()
    project_controller = ProjectController()

    # Validate file
    is_valid, signal = data_controller.validate_uploaded_file(file=file)

    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": signal}
        )

    # Get project path
    project_dir_path = project_controller.get_project_path(
        project_id=project_id
    )
      # Generate unique file path
    file_path, file_id = data_controller.generate_unique_filePath(
    orig_file_name=file.filename,
    project_path=project_dir_path
    )

  
    # Define file_id using the generated file name
    file_id = os.path.basename(file_path)

    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await f.write(chunk)

    except Exception as e:
        logger.error(f"Error while uploading file: {e}")

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseSignal.FILE_UPLOAD_FAILED.value,
                "file_id":file_id
            }
        )

    # Success response
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseSignal.FILE_UPLOAD_SUCCESS.value,
            "file_id": file_id
        }
    )
@data_router.post("/process/{project_id}")
async def process_endpoint(project_id:str,process_request:ProcessRequest):
   
   
   
   
    file_id = process_request.file_id
    chunk_size=process_request.chunk_size
    overlap_size =process_request.overlap_size

    process_controller=ProcessController(project_id=project_id)
    
    file_content=process_controller.get_file_content(file_id=file_id)
    file_chunks =process_controller.process_file_content(
        file_content=file_content,
        file_id=file_id,
        chunk_size=chunk_size,
        overlap_size=overlap_size
    )
    if file_chunks is None or len(file_chunks) ==0:
        return JSONResponse(
             status_code=status.HTTP_400_BAD_REQUEST,
             content={
                 "signal":ResponseSignal.PROCESSING_FAILED.value

             }
            
        )
    return file_chunks

