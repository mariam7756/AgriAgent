from fastapi import APIRouter, Depends, UploadFile, File, status
from fastapi.responses import JSONResponse
from helpers.config import get_settings, Settings
from controllers.DataController import DataController
from controllers.ProjectController import ProjectController
import aiofiles
from models import ResponseSignal
import logging

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
    file_path = data_controller.generate_unique_filename(
        orig_file_name=file.filename,
        project_path=project_dir_path
    )

    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await f.write(chunk)

    except Exception as e:
        logger.error(f"Error while uploading file: {e}")

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseSignal.FILE_UPLOAD_FAILED.value
            }
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseSignal.FILE_UPLOAD_SUCCESS.value
        }
    )