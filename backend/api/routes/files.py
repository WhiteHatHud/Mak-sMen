from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from api.middleware.auth import get_current_user
from services.storage.file_handler import (
    save_project_files,
    list_project_files,
    get_file_meta,
    delete_file,
    stream_file_preview,
)
from utils.logger import logger


ALLOWED_EXT = {"pdf", "csv", "json", "parquet"}


router = APIRouter(tags=["files"]) # mixed prefixes per spec


class ApiResponse(BaseModel):
	success: bool = True
	data: Optional[dict] = None
	error: Optional[dict] = None


class FileMeta(BaseModel):
	id: int
	project_id: int
	filename: str
	content_type: Optional[str]
	size_bytes: int
	created_at: str


class FileList(BaseModel):
	items: List[FileMeta]




def ok(data: dict) -> ApiResponse:
	return ApiResponse(success=True, data=data)




@router.post("/api/projects/{project_id}/files", response_model=ApiResponse)
async def upload_files(project_id: int, files: List[UploadFile] = File(...), user=Depends(get_current_user)):
	# Validate extensions
	for f in files:
		ext = (f.filename.rsplit(".", 1)[-1] or "").lower()
		if ext not in ALLOWED_EXT:
			raise HTTPException(status_code=400, detail=f"Unsupported file extension: {ext}")
	try:
		saved = await save_project_files(project_id=project_id, files=files, user_id=user.id)
		return ok({"files": [FileMeta(**m).dict() for m in saved]})
	except HTTPException:
		raise
	except Exception:
		logger.exception("FILE_UPLOAD_FAILED")
		raise HTTPException(status_code=500, detail="Failed to upload files")




@router.get("/api/projects/{project_id}/files", response_model=ApiResponse)
async def list_files(project_id: int, user=Depends(get_current_user)):
	try:
		items = await list_project_files(project_id=project_id, user_id=user.id)
		return ok({"files": [FileMeta(**m).dict() for m in items]})
	except Exception:
		logger.exception("FILE_LIST_FAILED")
		raise HTTPException(status_code=500, detail="Failed to list files")




@router.get("/api/files/{file_id}", response_model=ApiResponse)
async def get_file(file_id: int, user=Depends(get_current_user)):
	try:
		meta = await get_file_meta(file_id=file_id, user_id=user.id)
		if not meta:
			raise HTTPException(status_code=404, detail="File not found")
		return ok({"file": FileMeta(**meta).dict()})
	except HTTPException:
		raise
	except Exception:
		logger.exception("FILE_GET_FAILED")
		raise HTTPException(status_code=500, detail="Failed to get file")




@router.delete("/api/files/{file_id}", response_model=ApiResponse)
async def remove_file(file_id: int, user=Depends(get_current_user)):
	try:
		deleted = await delete_file(file_id=file_id, user_id=user.id)
		if not deleted:
			raise HTTPException(status_code=404, detail="File not found")
		return ok({"deleted": True, "file_id": file_id})
	except HTTPException:
		raise
	except Exception:
		logger.exception("FILE_DELETE_FAILED")
		raise HTTPException(status_code=500, detail="Failed to delete file")




@router.get("/api/files/{file_id}/preview", response_model=ApiResponse)
async def preview_file(file_id: int, rows: int = Query(100, ge=1, le=1000), user=Depends(get_current_user)):
	try:
		preview = await stream_file_preview(file_id=file_id, user_id=user.id, limit=rows)
		return ok({"preview": preview})
	except HTTPException:
		raise
	except Exception:
		logger.exception("FILE_PREVIEW_FAILED")
		raise HTTPException(status_code=500, detail="Failed to preview file")