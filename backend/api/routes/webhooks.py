from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, AnyHttpUrl
from api.middleware.auth import get_current_user
from models.webhook import Webhook
from utils.logger import logger


router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


class ApiResponse(BaseModel):
	success: bool = True
	data: Optional[dict] = None
	error: Optional[dict] = None


class WebhookCreate(BaseModel):
	url: AnyHttpUrl
	secret: Optional[str] = Field(default=None, description="HMAC secret for signing")
	event: str = Field(..., description="event key, e.g. analysis.completed")
	active: bool = True


class WebhookUpdate(BaseModel):
	url: Optional[AnyHttpUrl] = None
	secret: Optional[str] = None
	event: Optional[str] = None
	active: Optional[bool] = None




def ok(data: dict) -> ApiResponse:
	return ApiResponse(success=True, data=data)




@router.post("", response_model=ApiResponse)
async def register_webhook(body: WebhookCreate, user=Depends(get_current_user)):
	try:
		wh = await Webhook.create(user_id=user.id, **body.dict())
		return ok({"webhook": wh.to_dict()})
	except Exception:
		logger.exception("WEBHOOK_CREATE_FAILED")
		raise HTTPException(status_code=500, detail="Failed to register webhook")




@router.get("", response_model=ApiResponse)
async def list_webhooks(user=Depends(get_current_user)):
	try:
		items = await Webhook.list(user_id=user.id)
		return ok({"webhooks": items})
	except Exception:
		logger.exception("WEBHOOK_LIST_FAILED")
		raise HTTPException(status_code=500, detail="Failed to list webhooks")




@router.put("/{webhook_id}", response_model=ApiResponse)
async def update_webhook(webhook_id: int, body: WebhookUpdate, user=Depends(get_current_user)):
	try:
		wh = await Webhook.update(webhook_id=webhook_id, user_id=user.id, **body.dict(exclude_unset=True))
		if not wh:
			raise HTTPException(status_code=404, detail="Webhook not found")
		return ok({"webhook": wh.to_dict()})
	except HTTPException:
		raise
	except Exception:
		logger.exception("WEBHOOK_UPDATE_FAILED")
		raise HTTPException(status_code=500, detail="Failed to update webhook")




@router.delete("/{webhook_id}", response_model=ApiResponse)
async def delete_webhook(webhook_id: int, user=Depends(get_current_user)):
	try:
		deleted = await Webhook.delete(webhook_id=webhook_id, user_id=user.id)
		if not deleted:
			raise HTTPException(status_code=404, detail="Webhook not found")
		return ok({"deleted": True, "webhook_id": webhook_id})
	except HTTPException:
		raise
	except Exception:
		logger.exception("WEBHOOK_DELETE_FAILED")
		raise HTTPException(status_code=500, detail="Failed to delete webhook")




@router.post("/{webhook_id}/test", response_model=ApiResponse)
async def test_webhook(webhook_id: int, user=Depends(get_current_user)):
	try:
		result = await Webhook.test_fire(webhook_id=webhook_id, user_id=user.id)
		if not result:
			raise HTTPException(status_code=404, detail="Webhook not found or inactive")
		return ok({"delivered": True, "response": result})
	except HTTPException:
		raise
	except Exception:
		logger.exception("WEBHOOK_TEST_FAILED")
		raise HTTPException(status_code=500, detail="Failed to test webhook")