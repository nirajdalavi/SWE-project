from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any, Dict, Optional
import os
import json
import uuid
from datetime import datetime
from main import job_manager  # Import job_manager from main

router = APIRouter(prefix="/webhooks/elevenlabs", tags=["webhooks"])

SERVER_TOOL_BEARER = os.getenv("SERVER_TOOL_BEARER", "change-me")

class RunUIFlowPayload(BaseModel):
    intent: str
    dom_snapshot: Dict[str, Any]
    screenshot: str
    page_url: str
    code_map: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    tool_invocation_id: Optional[str] = None
    ts: Optional[str] = None

@router.post("/run_ui_flow")
async def run_ui_flow(request: Request):
    # Skip authentication for now - allow all requests
    print(f"[Webhook] ⚠️ Authentication disabled for testing - allowing all requests")
    
    try:
        # Get raw body first to check if it's empty
        raw_body = await request.body()
        print(f"[Webhook] Raw body length: {len(raw_body)}")
        
        if len(raw_body) == 0:
            print(f"[Webhook] ⚠️ Empty request body, creating default payload")
            body = {
                "intent": "test",
                "dom_snapshot": {"inputs": []},
                "screenshot": "",
                "page_url": "https://example.com",
                "code_map": None,
                "session_id": "default_session",
                "user_id": "default_user",
                "tool_invocation_id": str(uuid.uuid4()),
                "ts": datetime.now().isoformat() + "Z"
            }
        else:
            body = await request.json()
            print(f"[Webhook] Request body: {json.dumps(body, indent=2)}")
    except Exception as e:
        print(f"[Webhook] ❌ Failed to parse JSON body: {e}")
        # Create a default payload if JSON parsing fails
        body = {
            "intent": "test",
            "dom_snapshot": {"inputs": []},
            "screenshot": "",
            "page_url": "https://example.com",
            "code_map": None,
            "session_id": "default_session",
            "user_id": "default_user",
            "tool_invocation_id": str(uuid.uuid4()),
            "ts": datetime.now().isoformat() + "Z"
        }
        print(f"[Webhook] Using default payload due to parsing error")
    
    try:
        payload = RunUIFlowPayload(**body)
        print(f"[Webhook] ✅ Payload validated successfully")
    except Exception as e:
        print(f"[Webhook] ❌ Payload validation failed: {e}")
        raise HTTPException(status_code=422, detail=f"invalid payload: {e}")
    
    # Ensure idempotency field
    if not payload.tool_invocation_id:
        body["tool_invocation_id"] = str(uuid.uuid4())
        print(f"[Webhook] Generated tool_invocation_id: {body['tool_invocation_id']}")
    
    job_id = job_manager.enqueue_job("run_ui_flow", body)
    print(f"[Webhook] ✅ Job enqueued with ID: {job_id}")
    
    # Respond fast; ElevenLabs can store this via Dynamic Variable Assignment
    return JSONResponse(status_code=202, content={
        "status": "accepted",
        "job_id": job_id,
        "message": "UI flow enqueued"
    })
