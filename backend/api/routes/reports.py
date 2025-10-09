from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from api.middleware.auth import get_current_user
from workers.report_worker import generate_report_task
from models.report import Report
from utils.logger import logger


router = APIRouter(prefix="/api/reports", tags=["reports"])


class ApiResponse(BaseModel):
	success: bool = True
	data: Optional[dict] = None
	error: Optional[dict] = None


class ReportGenerateRequest(BaseModel):
	analysis_id: str
	format: str = Field(..., regex=r"^(pdf|html|json)$")




def ok(data: dict) -> ApiResponse:
	return ApiResponse(success=True, data=data)




@router.post("/generate", response_model=ApiResponse)
async def generate_report(body: ReportGenerateRequest, user=Depends(get_current_user)):
	try:
		task = generate_report_task.delay(user_id=user.id, **body.dict())
		return ok({"task_id": task.id})
	except Exception:
		logger.exception("REPORT_GENERATE_FAILED")
		raise HTTPException(status_code=500, detail="Failed to generate report")




@router.get("/{report_id}", response_model=ApiResponse)
async def get_report(report_id: int, user=Depends(get_current_user)):
	try:
		report = await Report.get(report_id=report_id, user_id=user.id)
		if not report:
			raise HTTPException(status_code=404, detail="Report not found")
		return ok({"report": report.to_dict()})
	except HTTPException:
		raise
	except Exception:
		logger.exception("REPORT_GET_FAILED")
		raise HTTPException(status_code=500, detail="Failed to get report")




@router.get("/{report_id}/download")
async def download_report(report_id: int, user=Depends(get_current_user)):
	try:
		file_resp = await Report.stream_file(report_id=report_id, user_id=user.id)
		if not file_resp:
			raise HTTPException(status_code=404, detail="File not found")
		return file_resp # StreamingResponse/FileResponse from model/service
	except HTTPException:
		raise
	except Exception:
		logger.exception("REPORT_DOWNLOAD_FAILED")
		raise HTTPException(status_code=500, detail="Failed to download report")




@router.get("/projects/{project_id}", response_model=ApiResponse)
async def list_reports(project_id: int, user=Depends(get_current_user)):
	try:
		items = await Report.list_by_project(project_id=project_id, user_id=user.id)
		return ok({"reports": items})
	except Exception:
		logger.exception("REPORT_LIST_FAILED")
		raise HTTPException(status_code=500, detail="Failed to list reports")




@router.post("/{report_id}/flag", response_model=ApiResponse)
async def flag_report(report_id: int, user=Depends(get_current_user)):
	try:
		flagged = await Report.flag(report_id=report_id, user_id=user.id)
		if not flagged:
			raise HTTPException(status_code=404, detail="Report not found")
		return ok({"flagged": True, "report_id": report_id})
	except HTTPException:
		raise
	except Exception:
		logger.exception("REPORT_FLAG_FAILED")
		raise HTTPException(status_code=500, detail="Failed to flag report")