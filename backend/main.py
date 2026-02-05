# backend/main.py
from fastapi import UploadFile, File, Form
from fastapi import FastAPI, UploadFile, Request, File, HTTPException, BackgroundTasks, Query
from fastapi import Form
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
import sys
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parent))
# from allyin_licensing.license_manager import LicenseManager
from fastapi.middleware.cors import CORSMiddleware
import smtplib
from pydantic import BaseModel
import os
import json
import shutil
from typing import List, Dict, Any, Optional, Union
import logging
import time
import asyncio
from qdrant_client import QdrantClient # Ensure this is imported
import requests
from dotenv import load_dotenv
import redis
import uuid
import threading
from services.google_drive_service import GoogleDriveService, google_drive_service
import urllib.parse
load_dotenv()


# FIXED_SECRET = b'Ar_tw-PJgfvxhRj_N5GjaZgGjrwU5cE3WqnBFzKGT-o='  # Must be bytes
# --- Licensing ---
# license_mgr = LicenseManager(product_id="Aqeedai", trial_days=15)
# license_mgr.secret_key = FIXED_SECRET

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

class JobManager:
    def __init__(self):
        self.redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)

    def enqueue_job(self, job_type: str, payload: dict) -> str:
        job_id = str(uuid.uuid4())
        job_key = f"job:{job_id}"
        job_data = {
            "status": "PENDING",
            "job_type": job_type,
            "payload": json.dumps(payload),
            "result": "",
            "error": "",
        }
        self.redis.hmset(job_key, job_data)
        return job_id

    def update_job(self, job_id: str, status: str, result: dict = None, error: str = None):
        job_key = f"job:{job_id}"
        update_data = {"status": status}
        if result is not None:
            update_data["result"] = json.dumps(result)
        else:
            update_data["result"] = ""
        if error is not None:
            update_data["error"] = error
        else:
            update_data["error"] = ""
        self.redis.hmset(job_key, update_data)

    def get_job(self, job_id: str) -> dict:
        job_key = f"job:{job_id}"
        job_data = self.redis.hgetall(job_key)
        if not job_data:
            return {"status": "NOT_FOUND"}
        
        # Handle result field
        result = None
        if job_data.get("result") and job_data.get("result").strip():
            try:
                result = json.loads(job_data.get("result"))
            except json.JSONDecodeError:
                result = None
        
        # Handle error field
        error = job_data.get("error") if job_data.get("error") and job_data.get("error").strip() else None
        
        return {
            "status": job_data.get("status"),
            "job_type": job_data.get("job_type"),
            "payload": json.loads(job_data.get("payload", "{}")),
            "result": result,
            "error": error,
        }

job_manager = JobManager()

from services.rag_service import answer_question_with_rag, score_contracts, compare_responses

def process_score_contracts_sync(workspace_name: str, criterion: str, max_score: int, compare_chatgpt: bool, share_data_with_chatgpt: bool):
    """Shared function for processing score contracts that can be used by both endpoint and job worker."""
    collection_name = f"contract_docs_{workspace_name}"
    
    from qdrant_client import QdrantClient
    QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
    qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    logger.info(f"Checking Qdrant collection '{collection_name}' existence.")
    if not qdrant_client.collection_exists(collection_name):
        raise Exception("No documents or collection found for this workspace. Please upload and embed documents first.")
    logger.info(f"Qdrant collection '{collection_name}' found. Calling scoring service...")

    start_time = time.time()

    scoring_results = score_contracts(
        user_criterion_prompt=criterion,
        collection_name=collection_name,
        max_score=max_score,
        compare_chatgpt=compare_chatgpt,
        share_data_with_chatgpt=share_data_with_chatgpt
    )

    response_time = time.time() - start_time
    logger.info(f"Scoring completed in {response_time:.2f}s for workspace '{workspace_name}'.")

    # Save metrics
    from datetime import datetime
    metrics_file = WORKSPACE_ROOT / workspace_name / "metrics.json"
    now = datetime.now().isoformat()
    mode = "Score contracts"

    new_record = {
        "timestamp": now,
        "mode": mode,
        "response_time": round(response_time, 2)
    }
    metrics = []
    if metrics_file.exists():
        try:
            with open(metrics_file, "r") as f:
                metrics = json.load(f)
        except Exception:
            logger.warning(f"Could not load existing metrics from {metrics_file}, starting new list.")
            metrics = []
    metrics.append(new_record)
    metrics_file.parent.mkdir(parents=True, exist_ok=True)
    with open(metrics_file, "w") as f:
        json.dump(metrics, f, indent=2)
    logger.info(f"Logged response time ({response_time:.2f}s) for '{mode}' to {metrics_file}")
    
    # Save last_score.json
    output_path = WORKSPACE_ROOT / workspace_name / "last_score.json"
    with open(output_path, "w") as f:
        json.dump(scoring_results, f, indent=2)
    logger.info(f"Scoring results saved to {output_path}")
    
    return scoring_results

def process_audit_contracts_sync(workspace_name: str):
    """Shared function for processing audit contracts that can be used by both endpoint and job worker."""
    try:
        start_time = time.time()
        
        # Perform the audit
        audit_results = perform_contract_audit(workspace_name)
        
        response_time = time.time() - start_time
        
        if audit_results.get("status") == "failed":
            logger.error(f"Audit failed for workspace '{workspace_name}': {audit_results.get('error')}")
            raise Exception(audit_results.get("error", "Audit failed"))
        
        # Save audit results to file
        try:
            audit_file_path = save_audit_results(workspace_name, audit_results)
            audit_results["audit_file_path"] = audit_file_path
        except Exception as save_error:
            logger.warning(f"Could not save audit results to file: {save_error}")
        
        # Log metrics
        from datetime import datetime
        metrics_file = WORKSPACE_ROOT / workspace_name / "metrics.json"
        now = datetime.now().isoformat()
        mode = "Audit contracts"

        new_record = {
            "timestamp": now,
            "mode": mode,
            "response_time": round(response_time, 2)
        }
        metrics = []
        if metrics_file.exists():
            try:
                with open(metrics_file, "r") as f:
                    metrics = json.load(f)
            except Exception:
                logger.warning(f"Could not load existing metrics from {metrics_file}, starting new list.")
                metrics = []
        metrics.append(new_record)
        metrics_file.parent.mkdir(parents=True, exist_ok=True)
        with open(metrics_file, "w") as f:
            json.dump(metrics, f, indent=2)
        logger.info(f"Logged response time ({response_time:.2f}s) for '{mode}' to {metrics_file}")
        
        return audit_results
        
    except Exception as e:
        logger.error(f"Error processing audit for workspace '{workspace_name}': {e}", exc_info=True)
        raise

def log_metrics(workspace_name: str, mode: str, response_time: float):
    """Shared function for logging metrics to avoid code duplication."""
    from datetime import datetime
    metrics_file = WORKSPACE_ROOT / workspace_name / "metrics.json"
    now = datetime.now().isoformat()

    new_record = {
        "timestamp": now,
        "mode": mode,
        "response_time": round(response_time, 2)
    }
    metrics = []
    if metrics_file.exists():
        try:
            with open(metrics_file, "r") as f:
                metrics = json.load(f)
        except Exception:
            logger.warning(f"Could not load existing metrics from {metrics_file}, starting new list.")
            metrics = []
    metrics.append(new_record)
    metrics_file.parent.mkdir(parents=True, exist_ok=True)
    with open(metrics_file, "w") as f:
        json.dump(metrics, f, indent=2)
    logger.info(f"Logged response time ({response_time:.2f}s) for '{mode}' to {metrics_file}")

def process_vendor_job(job_id: str, payload: dict, service_func, mode: str):
    """Shared function for processing vendor-related jobs with metrics and error handling."""
    try:
        start_time = time.time()
        result = service_func()
        response_time = time.time() - start_time
        
        # Log metrics using shared function
        log_metrics(payload.get('workspace_name'), mode, response_time)
        
        job_manager.update_job(job_id, "SUCCESS", result=result)
        logger.info(f"[Worker] ✅ Job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"[Worker] Error processing {mode.lower()}: {e}", exc_info=True)
        job_manager.update_job(job_id, "FAILURE", error=str(e))

from services.helper_service import extract_criteria_from_jsonl
from services.audit_service import perform_contract_audit, save_audit_results
from services.legal_service import perform_legal_analysis, save_legal_results
# Keeping parse_single_documents for clarity if it's explicitly used for single files
# from services.parser_service import parse_documents as parse_single_documents # NEW: Import parse_documents directly
from services.parser_service import run_parsing_for_workspace # Keep original import for contracts/criteria
from services.embedder_service import run_embedding_for_workspace, sync_embedder_manifest
from services.prompt_generator_service import generate_ai_prompts
from services.combined_evaluation_service import perform_combined_evaluation
from services.vendor_recommendation_service import generate_vendor_recommendations, generate_enhanced_vendor_recommendations
from services.vendor_research_service import VendorResearchService
from services.vendor_comparison_service import VendorComparisonService
from requests.auth import HTTPBasicAuth
from email.message import EmailMessage
import smtplib
import io
import pandas as pd
import xlsxwriter
import math


from typing import Dict, Any
from services.google_drive_service import GoogleDriveService

workspace_gdrive_services: Dict[str, GoogleDriveService] = {}

# app = FastAPI(title="Allyin Compass API", root_path="/")
app = FastAPI(
    title="Allyin Compass API",
    description="AI-powered contract analysis and vendor recommendation platform",
    version="1.0.0",
    openapi_version="3.1.0",
    root_path="/api",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://aqeed-aws.cloud", "https://aqeed-gcp.cloud", "http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variable to track active processing tasks
active_processing_tasks = {}
# Global variable to track criteria extraction tasks
active_criteria_extraction_tasks = {}

# # --- Path Configuration ---
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USER = os.getenv("SMTP_USER")
EMAIL_PASS = os.getenv("SMTP_PASSWORD")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "niraj@allyin.ai")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = PROJECT_ROOT / "data"

# Ensure the data directory exists
WORKSPACE_ROOT.mkdir(exist_ok=True)
PROMPTS_FILE = PROJECT_ROOT / "backend" / "prompts.json"
host = os.getenv("AIRFLOW_HOST", "localhost")
port = os.getenv("AIRFLOW_PORT", "8080")
AIRFLOW_TRIGGER_URL = f"http://{host}:{port}/api/v1/dags/score_to_csv_email_dag/dagRuns"
# Add your actual username and password if Airflow has authentication
AIRFLOW_USERNAME = os.getenv("AIRFLOW_USERNAME")
AIRFLOW_PASSWORD = os.getenv("AIRFLOW_PASSWORD")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
@app.get("/gdrive/auth/{workspace_name}")
async def get_gdrive_auth_url(workspace_name: str, request: Request):
    """Return the Google OAuth authorization URL using a dynamically computed redirect_uri."""
    try:
        gsvc = GoogleDriveService(workspace_name=workspace_name)
        auth_url = gsvc.get_auth_url(request=request)
        if not auth_url:
            raise HTTPException(status_code=500, detail="Failed to generate Google Drive auth URL.")
        return {"auth_url": auth_url}
    except Exception as e:
        logger.error(f"[gdrive auth_url] error for {workspace_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get auth URL: {e}")

# If your `/api/oauth2callback` route already exists, update the token exchange call inside it from:
#         ok = gsvc.exchange_code_for_token(code)
#  to:
#         ok = gsvc.exchange_code_for_token(code, request=request)
# If this route does not exist yet, add the following implementation (place it near the other routes):
from fastapi import Query
@app.get("/oauth2callback")
async def oauth2callback(request: Request, code: Optional[str] = Query(None), state: Optional[str] = Query(None)):
    """
    Handles Google OAuth2 redirect. Exchanges ?code=... for tokens using the workspace in `state`.
    Responds with a tiny HTML page that notifies the opener and closes itself.
    """
    try:
        # Extract workspace from state
        workspace = "default"
        if state:
            try:
                parts = state.split("=", 1)
                if len(parts) == 2 and parts[0] == "workspace" and parts[1]:
                    workspace = parts[1]
            except Exception:
                pass

        status = "error"
        if code:
            gsvc = GoogleDriveService(workspace_name=workspace)
            ok = gsvc.exchange_code_for_token(code, request=request)
            status = "success" if ok else "error"

        # Respond with a tiny HTML page that notifies the opener and closes itself.
        # It also includes a fallback redirect in case the window wasn't opened as a popup.
        content = f"""
<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>Google Drive Auth</title></head>
<body>
  <script>
    (function() {{
      try {{
        if (window.opener) {{
          window.opener.postMessage({{ type: 'gdrive-auth', status: '{status}', workspace: '{workspace}' }}, "{FRONTEND_URL}");
        }}
      }} catch (e) {{}}
      try {{ window.close(); }} catch (e) {{}}
      // Fallback for when window can't close or wasn't opened as a popup:
      window.location = "{FRONTEND_URL}/?google_drive_auth={status}&workspace={workspace}";
    }})();
  </script>
</body></html>
        """
        return HTMLResponse(content=content)
    except Exception as e:
        logger.error(f"[oauth2callback] Failed to complete OAuth: {e}", exc_info=True)
        # Error page that still tries to notify the opener
        content = f"""
<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>Google Drive Auth Error</title></head>
<body>
  <script>
    (function() {{
      try {{
        if (window.opener) {{
          window.opener.postMessage({{ type: 'gdrive-auth', status: 'error', workspace: 'default' }}, "{FRONTEND_URL}");
        }}
      }} catch (e) {{}}
      try {{ window.close(); }} catch (e) {{}}
      window.location = "{FRONTEND_URL}/?google_drive_auth=error&workspace=default";
    }})();
  </script>
</body></html>
        """
        return HTMLResponse(content=content, status_code=200)

# Alias route so both /api/oauth2callback and /oauth2callback work and hit the same logic.
@app.get("/oauth2callback")
async def oauth2callback_alias(request: Request, code: Optional[str] = Query(None), state: Optional[str] = Query(None)):
    # Delegate to the main handler so both paths behave identically
    return await oauth2callback(request=request, code=code, state=state)

# ---------- Google Drive utility endpoints ----------
@app.get("/google-drive/status/{workspace_name}")
async def google_drive_status(workspace_name: str):
    """
    Tell the frontend whether Drive is connected for this workspace.
    """
    try:
        gsvc = GoogleDriveService(workspace_name=workspace_name)
        is_auth = gsvc.is_authenticated()
        return {"authenticated": bool(is_auth)}
    except Exception as e:
        logger.error(f"[gdrive status] error for {workspace_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to check Google Drive status: {e}")

@app.get("/google-drive/files/{workspace_name}")
async def google_drive_files(
    workspace_name: str,
    folder_id: Optional[str] = Query(default=None),
    file_types: Optional[List[str]] = Query(default=None),
):
    """
    List files for a workspace. If file_types is omitted/empty, returns ALL files.
    """
    try:
        gsvc = GoogleDriveService(workspace_name=workspace_name)
        ok = gsvc.authenticate()
        if not ok:
            raise HTTPException(status_code=401, detail="Google Drive not authenticated for this workspace.")

        files = gsvc.list_files(folder_id=folder_id, file_types=file_types)
        return {"files": files}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[gdrive files] error for {workspace_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch Google Drive files.")

@app.get("/google-drive/folders/{workspace_name}")
async def google_drive_folders(
    workspace_name: str,
    parent_id: Optional[str] = Query(default=None),
):
    """
    List folders (only) under the specified parent (or root if omitted).
    """
    try:
        gsvc = GoogleDriveService(workspace_name=workspace_name)
        ok = gsvc.authenticate()
        if not ok:
            raise HTTPException(status_code=401, detail="Google Drive not authenticated for this workspace.")

        # Reuse list_files with a folder-only filter
        # Drive folder MIME type
        FOLDER_MIME = "application/vnd.google-apps.folder"
        # Build query via service.files().list directly to avoid fetching all files
        svc = gsvc.service
        query_parts = []
        if parent_id:
            query_parts.append(f"'{parent_id}' in parents")
        else:
            query_parts.append("'root' in parents")
        query_parts.append(f"mimeType = '{FOLDER_MIME}'")
        query = " and ".join(query_parts)

        folders: List[Dict[str, Any]] = []
        page_token = None
        while True:
            results = svc.files().list(
                q=query,
                pageSize=100,
                fields="nextPageToken, files(id, name, mimeType, parents, iconLink, webViewLink)",
                pageToken=page_token
            ).execute()
            folders.extend(results.get("files", []))
            page_token = results.get("nextPageToken")
            if not page_token:
                break

        return {"folders": folders}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[gdrive folders] error for {workspace_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch Google Drive folders.")

@app.post("/google-drive/revoke/{workspace_name}")
async def google_drive_revoke(workspace_name: str):
    """
    Revoke and forget Drive credentials for a workspace.
    """
    try:
        gsvc = GoogleDriveService(workspace_name=workspace_name)
        ok = gsvc.revoke_access()
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to revoke Google Drive access.")
        return {"status": "ok", "message": "Google Drive access revoked and token removed."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[gdrive revoke] error for {workspace_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to revoke Google Drive access.")


def load_prompts():
    if PROMPTS_FILE.exists():
        try:
            with open(PROMPTS_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning("prompts.json is empty or invalid. Returning empty dictionary.")
            return {}
        except Exception as e:
            logger.error(f"Failed to load prompts.json: {e}")
            return {}
    return {}

def save_prompts_to_file(data):
    try:
        with open(PROMPTS_FILE, "w") as f:
            json.dump(data, f, indent=4)
        logger.info("Prompts saved successfully.")
    except Exception as e:
        logger.error(f"Failed to save prompts.json: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save prompts: {e}")

class CreateWorkspaceRequest(BaseModel):
    workspace_name: str

# class QuestionRequest(BaseModel):
#     query: str
#     workspace_name: str
#     response_size: Optional[str] = "medium"
#     response_type: Optional[str] = "sentence"
#     compare_chatgpt: Optional[bool] = True
#     share_data_with_chatgpt: Optional[bool] = True # NEW FIELD

class QuestionRequest(BaseModel):
    query: str
    workspace_name: str
    response_size: Optional[str] = "medium"
    response_type: Optional[str] = "sentence"
    compare_chatgpt: Optional[bool] = True
    share_data_with_chatgpt: Optional[bool] = True
    use_web: Optional[bool] = False   # NEW FIELD
    specific_url: Optional[str] = ""  # NEW FIELD for specific website scraping

class ScoreContractsRequest(BaseModel):
    criterion: str
    workspace_name: str
    max_score: int
    compare_chatgpt: Optional[bool] = True
    share_data_with_chatgpt: Optional[bool] = True # NEW FIELD

class CombinedEvaluationRequest(BaseModel):
    workspace_name: str
    technical_weight: float
    financial_weight: float

class TranslationRequest(BaseModel):
    text: str
    target_language: str

class UpdatePromptsRequest(BaseModel):
    prompts: Dict[str, List[str]]

class CompareResponsesRequest(BaseModel):
    openrouter_response: Union[str, List[str]]
    chatgpt_response: Union[str, List[str]]

class SubmitAdminRequest(BaseModel):
    workspace_name: str
    comment: Optional[str] = ""
    mode: str

class AuditRequest(BaseModel):
    workspace_name: str

class LegalRequest(BaseModel):
    workspace_name: str

class VendorScore(BaseModel):
    score: Optional[Union[float, str]] = None
    rationale: Optional[str] = None

class ContractDetail(BaseModel):
    Serial: Optional[Union[int, str]] = None
    criterion: Optional[str] = None
    criteria: Optional[str] = None # 'criteria' is sometimes used instead of 'criterion' in raw data
    name: Optional[str] = None
    score: Optional[Union[float, str]] = None
    rationale: Optional[str] = None
    weight: Optional[Union[float, str]] = None
    # Add the newly expected fields from combined_evaluation_service.py
    technical_score: Optional[Union[float, str]] = None
    financial_score: Optional[Union[float, str]] = None
    weighted_technical_score: Optional[Union[float, str]] = None
    weighted_financial_score: Optional[Union[float, str]] = None


class RawContracts(BaseModel):
    contracts: List[ContractDetail]

class FinalScoreDetail(BaseModel):
    score_out_of_100: Optional[Union[float, str]] = None
    score_out_of_50: Optional[Union[float, str]] = None
    percentage: Optional[Union[float, str]] = None

class SummaryOfBest(BaseModel):
    best_contract: Optional[str] = None
    summary: Optional[List[str]] = None

class ComparisonResult(BaseModel):
    reason_allyin: Optional[str] = None
    reason_chatgpt: Optional[str] = None
    verdict: Optional[str] = None

class SaveScoresRequest(BaseModel):
    raw_openrouter: Optional[RawContracts] = None
    raw_chatgpt: Optional[RawContracts] = None
    final_scores_openrouter: Optional[Dict[str, FinalScoreDetail]] = None
    final_scores_chatgpt: Optional[Dict[str, FinalScoreDetail]] = None
    summary_of_best: Optional[SummaryOfBest] = None
    comparison: Optional[ComparisonResult] = None

class VendorRecommendationRequest(BaseModel):
    project_requirements: str
    workspace_name: str
    industry: Optional[str] = "general"
    location_preference: Optional[str] = "any"
    vendor_count: Optional[int] = 5
    preference: Optional[str] = "balanced"
    vendor_type: Optional[str] = "auto"
    enable_reddit_analysis: Optional[bool] = False
    enable_linkedin_analysis: Optional[bool] = False
    enable_google_reviews: Optional[bool] = False

class VendorResearchRequest(BaseModel):
    vendor_name: str
    location: str
    workspace_name: str
    enable_reddit_analysis: Optional[bool] = False
    enable_linkedin_analysis: Optional[bool] = False
    enable_google_reviews: Optional[bool] = False

class VendorComparisonRequest(BaseModel):
    vendors: List[Dict[str, str]]  # List of vendor dicts with 'name' and 'location' keys
    workspace_name: str

class ContactFormRequest(BaseModel):
    firstName: str
    lastName: str
    email: str
    phoneNumber: Optional[str] = ""
    subject: str
    message: str
    vendor_count: Optional[int] = 5
    source: Optional[str] = None
    preference: Optional[str] = "balanced"  # "technical_competence", "cost_effective", or "balanced"
    vendor_type: Optional[str] = "auto"  # "auto", "service_providers", "technology_vendors", "equipment_suppliers"

class LeadInterestRequest(BaseModel):
    user_name: str
    user_email: str
    vendor_name: str
    vendor_score: Optional[str] = None
    project_requirements: Optional[str] = None
    industry: Optional[str] = None
    location_preference: Optional[str] = None
    workspace_name: str

class GoogleDriveRequest(BaseModel):
    file_ids: List[str]

class GoogleDriveAuthRequest(BaseModel):
    authorization_code: str

# def check_access(user_email: str = "default_user"):
#     if not user_email:
#         user_email="default_user"

#     trial_info = license_mgr.get_trial_status(user_id=user_email)

#     if trial_info is None:
#         license_mgr.start_trial(user_id=user_email)
#         return True

#     if not trial_info.get("is_trial_expired", True):
#         return True

#     is_valid, _ = license_mgr.is_license_valid()
#     return is_valid

def check_access(user_email: str = "default_user"):
    # Always return True - licensing disabled
    return True

    
def send_email(subject: str, html_content: str, to: str, attachments: list = None):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = to
    msg.set_content("This is an HTML email. Please view in HTML-supported client.")
    msg.add_alternative(html_content, subtype="html")

    if attachments:
        for file_path in attachments:
            with open(file_path, "rb") as f:
                file_data = f.read()
                file_name = os.path.basename(file_path)
                msg.add_attachment(file_data, maintype="application", subtype="octet-stream", filename=file_name)

    with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as smtp:
        smtp.starttls()
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)
# NEW Pydantic model for generic table export
class ContractTableExportRequest(BaseModel):
    contracts: List[Dict[str, Any]] # Use Dict[str, Any] because the structure can vary slightly
    title: str # To be used for sheet name and filename

@app.get("/")
async def read_root():
    if not check_access("default_user"):
        return JSONResponse(
            status_code=403,
            content={"has_access": False, "message": "❌ Trial expired or license not found."}
        )
    return {"has_access": True, "message": "Allyin Compass Backend API"}


# --- License entry form endpoints ---
# @app.get("/enter_license")
# async def get_license_form():
#     return {"message": "Please submit your license key using POST."}


# @app.post("/enter_license")
# async def post_license_form(license_key: str = Form(...)):
#     try:
#         success, message = license_mgr.install_license(license_key)
#         if success:
#             return {"status": "success", "message": "✅ License installed successfully."}
#         else:
#             return {"status": "error", "message": f"❌ Failed to install license: {message}"}
#     except Exception as e:
#         return {"status": "error", "message": f"❌ Error installing license: {str(e)}"}

@app.get("/workspaces")
async def get_workspaces():
    # Ensure the workspace root exists
    WORKSPACE_ROOT.mkdir(exist_ok=True)
    existing_workspaces = [d.name for d in WORKSPACE_ROOT.iterdir() if d.is_dir()]
    return {"workspaces": existing_workspaces}

@app.get("/approve", response_class=HTMLResponse)
async def approve(workspace: str):
    send_email(
        subject=f"Your Submission for '{workspace}' was APPROVED",
        to=ADMIN_EMAIL,
        html_content=f"""
        <html><body style='font-family: Arial;'>
            <h3 style='color:green;'>✔ Approved</h3>
            <p>The response for <b>{workspace}</b> has been marked as <b>APPROVED</b>.</p>
        </body></html>
        """
    )
    return "<h3>✅ Approval submitted successfully.</h3>"

@app.get("/reject", response_class=HTMLResponse)
async def reject(workspace: str):
    send_email(
        subject=f"Your Submission for '{workspace}' was REJECTED",
        to=ADMIN_EMAIL,
        html_content=f"""
        <html><body style='font-family: Arial;'>
            <h3 style='color:red;'>✖ Rejected</h3>
            <p>The response for <b>{workspace}</b> has been marked as <b>REJECTED</b>.</p>
        </body></html>
        """
    )
    return "<h3>❌ Rejection submitted successfully.</h3>"

@app.get("/rfi", response_class=HTMLResponse)
async def rfi_form(workspace: str):
   return f"""
    <html>
    <head>
        <meta charset='UTF-8'>
        <title>Request for Improvement - {workspace}</title>
        <link rel='icon' href='/logo.png'>
        <style>
            body {{
                background: #181c24;
                color: #f3f3f3;
                font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
                min-height: 100vh;
                margin: 0;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
            }}
            .rfi-card {{
                background: #23283a;
                border-radius: 18px;
                box-shadow: 0 4px 32px rgba(0,0,0,0.25);
                padding: 2.5rem 2.5rem 2rem 2.5rem;
                max-width: 600px;
                width: 100%;
                margin: 2rem auto;
                display: flex;
                flex-direction: column;
                align-items: center;
            }}
            .rfi-logo {{
                width: 56px;
                height: 56px;
                margin-bottom: 1.2rem;
                border-radius: 12px;
                background: #fff;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 2px 8px rgba(0,0,0,0.10);
            }}
            .rfi-title {{
                font-size: 2rem;
                font-weight: 700;
                margin-bottom: 0.5rem;
                text-align: center;
                color: #fff;
            }}
            .rfi-subtitle {{
                font-size: 1.1rem;
                color: #b0b8d1;
                margin-bottom: 2rem;
                text-align: center;
            }}
            .rfi-form {{
                width: 100%;
                display: flex;
                flex-direction: column;
                align-items: stretch;
            }}
            .rfi-textarea {{
                background: #181c24;
                color: #f3f3f3;
                border: 1.5px solid #353b4b;
                border-radius: 10px;
                padding: 1.2rem;
                font-size: 1.1rem;
                margin-bottom: 1.5rem;
                min-height: 160px;
                resize: vertical;
                transition: border 0.2s;
            }}
            .rfi-textarea:focus {{
                outline: none;
                border: 1.5px solid #7c3aed;
            }}
            .rfi-submit {{
                background: linear-gradient(90deg, #7c3aed 0%, #6366f1 100%);
                color: #fff;
                border: none;
                border-radius: 8px;
                padding: 0.9rem 2.2rem;
                font-size: 1.1rem;
                font-weight: 600;
                cursor: pointer;
                box-shadow: 0 2px 8px rgba(124,58,237,0.10);
                transition: background 0.2s, transform 0.1s;
            }}
            .rfi-submit:hover {{
                background: linear-gradient(90deg, #6366f1 0%, #7c3aed 100%);
                transform: translateY(-2px) scale(1.03);
            }}
        </style>
    </head>
    <body>
        <div class='rfi-card'>
            <div class='rfi-logo'>
                <img src='/logo.png' alt='Aqeed.ai Logo' style='width: 40px; height: 40px; border-radius: 8px;'>
            </div>
            <div class='rfi-title'>Request for Improvement</div>
            <div class='rfi-subtitle'>Workspace: <span style='color:#a78bfa'>{workspace}</span></div>
            <form class='rfi-form' method='post' action='/submit_rfi'>
                <input type='hidden' name='workspace' value='{workspace}'>
                <textarea class='rfi-textarea' name='rfi_text' rows='8' placeholder='Describe your RFI in detail... (e.g., what needs improvement, suggestions, etc.)' required></textarea>
                <button class='rfi-submit' type='submit'>Submit RFI</button>
            </form>
        </div>
    </body>
    </html>
    """

from fastapi.responses import FileResponse

@app.post("/submit_rfi")
async def submit_rfi(workspace: str = Form(...), rfi_text: str = Form(...)):
    output_dir = os.path.abspath(f"../data/{workspace}").replace("\\", "/")
    excel_path = os.path.join(output_dir, f"{workspace}_evaluation_report.xlsx").replace("\\", "/")


    send_email(
        subject=f"RFI Submitted for Workspace '{workspace}'",
        to=ADMIN_EMAIL,
        html_content=f"""
            <html>
            <body style="font-family: Arial, sans-serif; font-size: 15px; color: #333;">
                <p>Dear Team,</p>
                <p>
                A <strong>Request for Improvement (RFI)</strong> has been submitted for the workspace
                <strong>{workspace}</strong>.
                </p>
                <p>
                <strong>Message:</strong><br>
                <em>{rfi_text}</em>
                </p>
                <p>Please review the attached evaluation documents and take necessary action.</p>
                <p style="margin-top: 20px;">
                Regards,<br>
                <strong>Contract Evaluation System</strong>
                </p>
            </body>
            </html>
        """,
        attachments=[excel_path]
    )

    return HTMLResponse(content="<h3>📝 RFI submitted and email sent successfully.</h3>", status_code=200)

@app.post("/translate")
async def translate_text(request: TranslationRequest):
    """
    Translate text while preserving HTML tags using MyMemory Translation API
    """
    try:
        from bs4 import BeautifulSoup
        import re
        import requests
        
        # Language mapping
        language_map = {
            "ar": "ar",
            "arabic": "ar", 
            "en": "en",
            "english": "en"
        }
        
        target_lang = language_map.get(request.target_language.lower(), "en")
        
        # If already in target language, return as-is
        if target_lang == "en":
            return {"translated_text": request.text}
        
        # Parse HTML to separate tags from text content
        soup = BeautifulSoup(request.text, 'html.parser')
        
        # Extract all text nodes for translation
        text_nodes = []
        for text in soup.find_all(text=True):
            if text.strip():  # Only process non-empty text
                text_nodes.append(text.strip())
        
        if not text_nodes:
            return {"translated_text": request.text}
        
        # Translate each text node with multiple API fallbacks
        translated_parts = []
        for text_node in text_nodes:
            try:
                import requests
                translated_text = text_node  # Default fallback
                
                # Try multiple translation methods
                if target_lang == "ar":
                    # Try Google Translate first (more reliable)
                    try:
                        google_url = "https://translate.googleapis.com/translate_a/single"
                        google_params = {
                            "client": "gtx",
                            "sl": "en", 
                            "tl": "ar",
                            "dt": "t",
                            "q": text_node
                        }
                        google_headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                        }
                        google_response = requests.get(google_url, params=google_params, headers=google_headers, timeout=10)
                        google_result = google_response.json()
                        if google_result and len(google_result) > 0 and len(google_result[0]) > 0:
                            api_result = google_result[0][0][0]
                            if api_result and api_result.strip() != text_node.strip():
                                translated_text = api_result.strip()
                                logger.info(f"Google Translate success: '{text_node[:30]}...' -> '{translated_text[:30]}...'")
                            else:
                                raise Exception("Google returned same text")
                    except Exception as e:
                        logger.warning(f"Google Translate failed: {e}")
                        
                        # Try LibreTranslate as backup
                        try:
                            libre_url = "https://libretranslate.de/translate"
                            libre_data = {
                                "q": text_node,
                                "source": "en",
                                "target": "ar",
                                "format": "text"
                            }
                            libre_response = requests.post(libre_url, data=libre_data, timeout=10)
                            libre_result = libre_response.json()
                            if "translatedText" in libre_result:
                                api_result = libre_result["translatedText"]
                                if api_result and api_result.strip() != text_node.strip():
                                    translated_text = api_result.strip()
                                    logger.info(f"LibreTranslate success: '{text_node[:30]}...' -> '{translated_text[:30]}...'")
                                else:
                                    raise Exception("LibreTranslate returned same text")
                        except Exception as e2:
                            logger.warning(f"LibreTranslate failed: {e2}")
                            
                            # If APIs fail, create a simple demonstration translation
                            demo_translations = {
                                "the": "ال",
                                "contract": "العقد", 
                                "proposal": "الاقتراح",
                                "evaluation": "التقييم",
                                "score": "النتيجة",
                                "criteria": "المعايير",
                                "technical": "التقني",
                                "financial": "المالي",
                                "vendor": "البائع",
                                "best": "الأفضل",
                                "quality": "الجودة",
                                "price": "السعر",
                                "delivery": "التسليم",
                                "compliance": "الامتثال",
                                "requirement": "المتطلب",
                                "solution": "الحل",
                                "experience": "الخبرة",
                                "capability": "القدرة",
                                "analysis": "التحليل",
                                "recommendation": "التوصية"
                            }
                            
                            # Create a demo translation
                            demo_text = text_node.lower()
                            for en_word, ar_word in demo_translations.items():
                                demo_text = demo_text.replace(en_word, ar_word)
                            
                            if demo_text != text_node.lower():
                                translated_text = demo_text
                                logger.info(f"Demo translation: '{text_node[:30]}...' -> '{translated_text[:30]}...'")
                            else:
                                translated_text = f"تُرجم: {text_node}"  # "Translated: " in Arabic
                                logger.info(f"Fallback Arabic marker applied")
                else:
                    # For non-Arabic languages, just return original
                    translated_text = text_node
                
                translated_parts.append(translated_text)
                
            except Exception as e:
                logger.warning(f"Failed to translate '{text_node[:50]}...': {e}")
                translated_parts.append(text_node)
        
        # Replace original text with translated text
        text_index = 0
        for text in soup.find_all(text=True):
            if text.strip() and text_index < len(translated_parts):
                text.replace_with(translated_parts[text_index])
                text_index += 1
        
        translated_html = str(soup)
        
        # Clean up any artifacts from BeautifulSoup parsing
        translated_html = translated_html.replace('<html><body>', '').replace('</body></html>', '')
        
        return {"translated_text": translated_html}
        
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return {"translated_text": request.text}  # Return original on error



@app.post("/workspaces")
async def create_workspace(request: CreateWorkspaceRequest):
    new_workspace_path = WORKSPACE_ROOT / request.workspace_name
    if new_workspace_path.exists():
        raise HTTPException(status_code=400, detail=f"Workspace '{request.workspace_name}' already exists.")

    (new_workspace_path / "contracts").mkdir(parents=True, exist_ok=True)
    (new_workspace_path / "criteria_weights").mkdir(parents=True, exist_ok=True)
    (new_workspace_path / "embedder").mkdir(parents=True, exist_ok=True)
    (new_workspace_path / "technical_reports").mkdir(parents=True, exist_ok=True)
    (new_workspace_path / "financial_reports").mkdir(parents=True, exist_ok=True)
    (new_workspace_path / "resumes").mkdir(parents=True, exist_ok=True)
    (new_workspace_path / "job_descriptions").mkdir(parents=True, exist_ok=True)

    # In-memory default prompts (do not save to file)
    default_prompts = [
        "What is the effective date of the contract?",
        "Who are the parties involved in the contract?",
        "What are the payment terms?",
        "Are there any termination clauses?",
        "Is there a confidentiality agreement?",
        "What is the governing law mentioned?",
        "Are there any exclusivity clauses?",
        "What is the warranty period?",
        "Are there data privacy clauses?",
        "What is the dispute resolution process?"
    ]

    logger.info(f"Workspace '{request.workspace_name}' created successfully with in-memory default prompts.")
    return {
        "message": f"Workspace '{request.workspace_name}' created successfully!",
        "default_prompts": default_prompts
    }
# --- PROMPTS ENDPOINT ---
@app.get("/prompts/{workspace_name}")
async def get_prepopulated_prompts(workspace_name: str):
    logger.info(f"[/prompts] Request received for workspace: {workspace_name}")

    default_prompts = [
        "What is the effective date of the contract?",
        "Who are the parties involved in the contract?",
        "What are the payment terms?",
        "Are there any termination clauses?",
        "Is there a confidentiality agreement?",
        "What is the governing law mentioned?",
        "Are there any exclusivity clauses?",
        "What is the warranty period?",
        "Are there data privacy clauses?",
        "What is the dispute resolution process?"
    ]

    try:
        qclient = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=10)
        collection_name = f"contract_docs_{workspace_name}"

        if not qclient.collection_exists(collection_name):
            logger.info(f"[/prompts] No Qdrant collection for '{workspace_name}'. Returning default prompts.")
            return default_prompts

        collection_info = qclient.get_collection(collection_name)
        if collection_info.points_count == 0:
            logger.info(f"[/prompts] Qdrant collection '{collection_name}' has no points. Returning default prompts.")
            return default_prompts

        # Generate AI prompts if docs exist
        ai_generated_prompts = generate_ai_prompts(workspace_name, base_dir=PROJECT_ROOT)
        if ai_generated_prompts:
            return ai_generated_prompts[:10]
        else:
            logger.warning(f"No AI prompts generated for '{workspace_name}'. Returning default prompts.")
            return default_prompts

    except Exception as e:
        logger.error(f"Error retrieving prompts for workspace '{workspace_name}': {e}", exc_info=True)
        return default_prompts

@app.delete("/workspaces/{workspace_name}")
async def delete_workspace(workspace_name: str):
    workspace_to_delete = WORKSPACE_ROOT / workspace_name
    if not workspace_to_delete.exists():
        raise HTTPException(status_code=404, detail=f"Workspace '{workspace_name}' not found.")

    try:
        from qdrant_client import QdrantClient

        qclient = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=10)
        collection_to_delete = f"contract_docs_{workspace_name}"
        if qclient.collection_exists(collection_to_delete):
            qclient.delete_collection(collection_to_delete)
            logger.info(f"Deleted Qdrant collection '{collection_to_delete}'.")

        # Also delete collection with the same name as workspace
        if qclient.collection_exists(workspace_name):
            qclient.delete_collection(workspace_name)
            logger.info(f"Deleted Qdrant collection '{workspace_name}'.")

        shutil.rmtree(workspace_to_delete)

        # Also revoke and forget Google Drive auth for this workspace
        try:
            gsvc = GoogleDriveService(workspace_name=workspace_name)
            ok_revoke = gsvc.revoke_access()
            if ok_revoke:
                logger.info(f"Revoked Google Drive credentials for workspace '{workspace_name}' and deleted token file.")
            else:
                logger.warning(f"Could not revoke Google Drive credentials for workspace '{workspace_name}'. Token file may still have been removed.")
        except Exception as e:
            logger.warning(f"Failed to revoke/cleanup Google Drive auth for workspace '{workspace_name}': {e}")

        logger.info(f"Deleted files for workspace '{workspace_name}'.")
        return {"message": f"Workspace '{workspace_name}' deleted successfully."}
    except Exception as e:
        logger.error(f"Error deleting workspace '{workspace_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting workspace: {e}")

@app.post("/qa")
async def ask_question(request: QuestionRequest, async_mode: bool = Query(True)):
    logger.info(f"[/qa] Request received for workspace: {request.workspace_name}, query: '{request.query[:50]}...', compare_chatgpt: {request.compare_chatgpt}, share_data_with_chatgpt: {request.share_data_with_chatgpt}, use_web: {request.use_web}, specific_url: {request.specific_url}, async_mode: {async_mode}") # Updated log
    
    if async_mode:
        # Enqueue job for async processing
        job_id = job_manager.enqueue_job("qa_processing", request.dict())
        logger.info(f"[/qa] 🔄 Async mode: Job {job_id} queued for workspace '{request.workspace_name}'")
        return {"job_id": job_id}
    
    collection_name = f"contract_docs_{request.workspace_name}"
    try:
        # Only check for Qdrant collection if not using web search
        if not request.use_web:
            from qdrant_client import QdrantClient
            QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
            QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
            qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=600)
            logger.info(f"[/qa] Checking Qdrant collection '{collection_name}' existence.")
            if not qdrant_client.collection_exists(collection_name):
                 raise HTTPException(status_code=400, detail="No documents or collection found for this workspace. Please upload and embed documents first.")
            logger.info(f"[/qa] Qdrant collection '{collection_name}' found. Calling RAG service...")
        else:
            logger.info(f"[/qa] Using web search, skipping Qdrant collection check. Calling RAG service...")

        start_time = time.time()

        rag_result, sources = answer_question_with_rag(
            request.query,
            collection_name=collection_name,
            response_size=request.response_size,
            response_type=request.response_type,
            compare_chatgpt=request.compare_chatgpt,
            share_data_with_chatgpt=request.share_data_with_chatgpt, # Pass the new parameter
            use_web=request.use_web,
            specific_url=request.specific_url
        )
        # rag_result contains the full structure with openrouter, chatgpt, and response_time
        answers = rag_result

        response_time = time.time() - start_time

        # Handle different source formats for web search vs document search
        if request.use_web:
            # Web search sources are already in the correct format
            serialized_sources = sources
            logger.info(f"[/qa] Web sources: {serialized_sources}")
        else:
            # Document sources are already in the correct format (list of dicts)
            serialized_sources = sources

        logger.info(f"[/qa] RAG service completed in {response_time:.2f}s for workspace '{request.workspace_name}'.")

        from datetime import datetime

        metrics_file = WORKSPACE_ROOT / request.workspace_name / "metrics.json"
        now = datetime.now().isoformat()
        mode = "Ask a question"

        new_record = {
            "timestamp": now,
            "mode": mode,
            "response_time": round(response_time, 2)
        }
        metrics = []
        if metrics_file.exists():
            try:
                with open(metrics_file, "r") as f:
                    metrics = json.load(f)
            except Exception:
                logger.warning(f"[/qa] Could not load existing metrics from {metrics_file}, starting new list.")
                metrics = []
        metrics.append(new_record)
        metrics_file.parent.mkdir(parents=True, exist_ok=True)
        with open(metrics_file, "w") as f:
            json.dump(metrics, f, indent=2)
        logger.info(f"[/qa] Logged response time ({response_time:.2f}s) for '{mode}' to {metrics_file}")

        return {"answers": answers, "sources": serialized_sources}
    except Exception as e:
        logger.error(f"[/qa] Error processing question for workspace '{request.workspace_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing question: {e}")

@app.post("/submit_admin")
async def submit_admin_endpoint(request: SubmitAdminRequest):
    output_path = WORKSPACE_ROOT / request.workspace_name / "last_score.json"
    try:
        response = requests.post(
            AIRFLOW_TRIGGER_URL,
            auth=HTTPBasicAuth(AIRFLOW_USERNAME, AIRFLOW_PASSWORD),
            headers={"Content-Type": "application/json"},
            json={
                "conf": {
                    "workspace_name": request.workspace_name,
                    "mode" : request.mode,
                    "score_output_path": str(output_path),
                    "comment": request.comment
                }
            }
        )

        if response.status_code != 200:
            logger.warning(f"[/submit_admin] DAG trigger failed: {response.status_code} {response.text}")
        else:
            logger.info(f"[/submit_admin] DAG triggered successfully for workspace '{request.workspace_name}' with comment: {request.comment}")

    except Exception as e:
        logger.warning(f"[/submit_admin] Could not trigger DAG: {e}")

@app.post("/score")
async def score_contracts_endpoint(request: ScoreContractsRequest, async_mode: bool = Query(True)):
    logger.info(f"[/score] Request received for workspace: {request.workspace_name}, criterion: '{request.criterion[:50]}...', compare_chatgpt: {request.compare_chatgpt}, share_data_with_chatgpt: {request.share_data_with_chatgpt}, async_mode: {async_mode}")
    
    if async_mode:
        # Enqueue job for async processing
        job_id = job_manager.enqueue_job("score_contracts", request.dict())
        logger.info(f"[/score] 🔄 Async mode: Job {job_id} queued for workspace '{request.workspace_name}'")
        return {"job_id": job_id}

    # Use the shared function for synchronous processing
    try:
        scoring_results = process_score_contracts_sync(
            workspace_name=request.workspace_name,
            criterion=request.criterion,
            max_score=request.max_score,
            compare_chatgpt=request.compare_chatgpt,
            share_data_with_chatgpt=request.share_data_with_chatgpt
        )
        return scoring_results
    except Exception as e:
        logger.error(f"[/score] Error scoring contracts for workspace '{request.workspace_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error scoring contracts: {e}")

@app.post("/jobs/{job_type}")
async def create_job(job_type: str, request: Request):
    payload = await request.json()
    job_id = job_manager.enqueue_job(job_type, payload)
    logger.info(f"[JobManager] 📝 Created job {job_id} type={job_type} for workspace={payload.get('workspace_name', 'unknown')}")
    return {"job_id": job_id}

@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    return job_manager.get_job(job_id)

@app.get("/worker/status")
async def worker_status():
    """Check if the Redis worker is running and connected."""
    try:
        # Test Redis connection
        job_manager.redis.ping()
        
        # Count jobs in queue
        keys = job_manager.redis.keys("job:*")
        job_count = len(keys)
        
        return {
            "status": "running",
            "redis_connected": True,
            "jobs_in_queue": job_count,
            "worker_thread_alive": worker_thread.is_alive() if 'worker_thread' in globals() else False
        }
    except Exception as e:
        return {
            "status": "error",
            "redis_connected": False,
            "error": str(e),
            "worker_thread_alive": worker_thread.is_alive() if 'worker_thread' in globals() else False
        }

@app.post("/audit")
async def audit_contracts_endpoint(request: AuditRequest, async_mode: bool = Query(True)):
    """Perform comprehensive contract audit for a workspace."""
    logger.info(f"[/audit] Request received for workspace: {request.workspace_name}, async_mode: {async_mode}")
    
    if async_mode:
        # Enqueue job for async processing
        job_id = job_manager.enqueue_job("audit_contracts", request.dict())
        logger.info(f"[/audit] 🔄 Async mode: Job {job_id} queued for workspace '{request.workspace_name}'")
        return {"job_id": job_id}
    
    try:
        start_time = time.time()
        
        # Perform the contract audit
        audit_results = perform_contract_audit(request.workspace_name)
        
        response_time = time.time() - start_time
        
        if audit_results.get("status") == "failed":
            logger.error(f"[/audit] Audit failed for workspace '{request.workspace_name}': {audit_results.get('error')}")
            raise HTTPException(status_code=500, detail=audit_results.get("error", "Audit failed"))
        
        # Save audit results to file
        try:
            audit_file_path = save_audit_results(request.workspace_name, audit_results)
            audit_results["audit_file_path"] = audit_file_path
        except Exception as save_error:
            logger.warning(f"[/audit] Could not save audit results to file: {save_error}")
        
        # Log metrics
        from datetime import datetime
        metrics_file = WORKSPACE_ROOT / request.workspace_name / "metrics.json"
        now = datetime.now().isoformat()
        mode = "Contract Audit"
        
        new_record = {
            "timestamp": now,
            "mode": mode,
            "response_time": round(response_time, 2)
        }
        
        metrics = []
        if metrics_file.exists():
            try:
                with open(metrics_file, "r") as f:
                    metrics = json.load(f)
            except Exception:
                logger.warning(f"[/audit] Could not load existing metrics from {metrics_file}, starting new list.")
                metrics = []
        
        metrics.append(new_record)
        metrics_file.parent.mkdir(parents=True, exist_ok=True)
        with open(metrics_file, "w") as f:
            json.dump(metrics, f, indent=2)
        
        logger.info(f"[/audit] Audit completed in {response_time:.2f}s for workspace '{request.workspace_name}'")
        logger.info(f"[/audit] Logged response time ({response_time:.2f}s) for '{mode}' to {metrics_file}")
        
        return audit_results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[/audit] Error performing contract audit for workspace '{request.workspace_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error performing contract audit: {e}")

@app.get("/audit-results/{workspace_name}")
async def get_audit_results(workspace_name: str):
    """Get the saved audit results for a workspace."""
    audit_file = WORKSPACE_ROOT / workspace_name / "audit_results.json"
    
    if not audit_file.exists():
        raise HTTPException(status_code=404, detail="No audit results found for this workspace.")
    
    try:
        with open(audit_file, "r") as f:
            results = json.load(f)
        return results
    except Exception as e:
        logger.error(f"Error reading audit results for workspace '{workspace_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Error reading audit results: {e}")

@app.post("/legal")
async def legal_analysis_endpoint(request: LegalRequest, async_mode: bool = Query(True)):
    """Perform comprehensive legal analysis for contract clause recommendations."""
    logger.info(f"[/legal] Request received for workspace: {request.workspace_name}, async_mode: {async_mode}")
    
    if async_mode:
        # Enqueue job for async processing
        job_id = job_manager.enqueue_job("legal_analysis", request.dict())
        logger.info(f"[/legal] 🔄 Async mode: Job {job_id} queued for workspace '{request.workspace_name}'")
        return {"job_id": job_id}
    
    try:
        start_time = time.time()
        
        # Perform the legal analysis
        legal_results = perform_legal_analysis(request.workspace_name)
        
        response_time = time.time() - start_time
        
        if legal_results.get("status") == "failed":
            logger.error(f"[/legal] Legal analysis failed for workspace '{request.workspace_name}': {legal_results.get('error')}")
            raise HTTPException(status_code=500, detail=legal_results.get("error", "Legal analysis failed"))
        
        # Save legal results to file
        try:
            legal_file_path = save_legal_results(request.workspace_name, legal_results)
            legal_results["legal_file_path"] = legal_file_path
        except Exception as save_error:
            logger.warning(f"[/legal] Could not save legal results to file: {save_error}")
        
        # Log metrics
        from datetime import datetime
        metrics_file = WORKSPACE_ROOT / request.workspace_name / "metrics.json"
        now = datetime.now().isoformat()
        mode = "Legal Analysis"
        
        new_record = {
            "timestamp": now,
            "mode": mode,
            "response_time": round(response_time, 2)
        }
        
        metrics = []
        if metrics_file.exists():
            try:
                with open(metrics_file, "r") as f:
                    metrics = json.load(f)
            except Exception:
                logger.warning(f"[/legal] Could not load existing metrics from {metrics_file}, starting new list.")
                metrics = []
        
        metrics.append(new_record)
        metrics_file.parent.mkdir(parents=True, exist_ok=True)
        with open(metrics_file, "w") as f:
            json.dump(metrics, f, indent=2)
        
        logger.info(f"[/legal] Legal analysis completed in {response_time:.2f}s for workspace '{request.workspace_name}'")
        logger.info(f"[/legal] Logged response time ({response_time:.2f}s) for '{mode}' to {metrics_file}")
        
        return legal_results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[/legal] Error performing legal analysis for workspace '{request.workspace_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error performing legal analysis: {e}")

@app.get("/legal-results/{workspace_name}")
async def get_legal_results(workspace_name: str):
    """Get the saved legal analysis results for a workspace."""
    legal_file = WORKSPACE_ROOT / workspace_name / "legal_analysis_results.json"
    
    if not legal_file.exists():
        raise HTTPException(status_code=404, detail="No legal analysis results found for this workspace.")
    
    try:
        with open(legal_file, "r") as f:
            results = json.load(f)
        return results
    except Exception as e:
        logger.error(f"Error reading legal analysis results for workspace '{workspace_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Error reading legal analysis results: {e}")

# Endpoint to get saved contract scores
@app.get("/contract-scores/{workspace_name}")
async def get_contract_scores(workspace_name: str):
    """Get the saved scoring results for contracts in a workspace."""
    output_path = WORKSPACE_ROOT / workspace_name / "last_score.json"
    
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="No scoring results found for this workspace.")
    
    try:
        with open(output_path, "r") as f:
            results = json.load(f)
        return results
    except Exception as e:
        logger.error(f"Error reading contract scores for workspace '{workspace_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Error reading contract scores: {e}")

# Endpoint to save edited scores (already present)
@app.post("/save_edited_scores/{workspace_name}")
async def save_edited_scores_endpoint(workspace_name: str, request: SaveScoresRequest):
    output_path = WORKSPACE_ROOT / workspace_name / "last_score.json"
    try:
        current_data = {}
        if output_path.exists():
            with open(output_path, "r") as f:
                current_data = json.load(f)

        updated_data = current_data.copy()
        
        # Deep merge the request data to avoid overwriting the entire structure
        request_data = request.dict(exclude_unset=True)
        for key, value in request_data.items():
            if key in updated_data and isinstance(updated_data[key], dict) and isinstance(value, dict):
                # Deep merge for nested dictionaries
                updated_data[key].update(value)
            else:
                # Direct assignment for non-dict values
                updated_data[key] = value

        with open(output_path, "w") as f:
            json.dump(updated_data, f, indent=2)
        logger.info(f"Edited scoring results saved to {output_path}")
        return {"message": "Edited scores saved successfully!"}
    except Exception as e:
        logger.error(f"Error saving edited scores for workspace '{workspace_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error saving edited scores: {e}")

# Helper function for Excel value escaping
def escape_excel_value(value):
    """Escapes a value for Excel by converting to string and doubling internal quotes."""
    return str(value).replace('"', '""')

async def translate_plain_text(text, target_language="ar"):
    """Simple translation function for plain text with fallback APIs"""
    try:
        import requests
        
        if not text or not text.strip():
            return text
        
        # Clean and prepare text
        clean_text = text.strip()
        
        # Try MyMemory API first
        try:
            url = "https://api.mymemory.translated.net/get"
            params = {
                "q": clean_text,
                "langpair": f"en|{target_language}",
                "de": "your-email@example.com"
            }
            
            response = requests.get(url, params=params, timeout=8)
            data = response.json()
            
            if data.get("responseStatus") == 200:
                translated_text = data["responseData"]["translatedText"]
                
                # Check if translation actually happened
                if translated_text.strip().lower() != clean_text.lower():
                    logger.info(f"MyMemory SUCCESS: '{clean_text[:30]}...' -> '{translated_text[:30]}...'")
                    return translated_text.strip()
                else:
                    logger.warning(f"MyMemory returned same text: '{clean_text[:30]}...'")
        except Exception as e:
            logger.warning(f"MyMemory API failed: {e}")
        
        # Try Google Translate API as fallback
        try:
            # Using Google Translate via translate.googleapis.com (free tier)
            google_url = "https://translate.googleapis.com/translate_a/single"
            google_params = {
                "client": "gtx",
                "sl": "en",
                "tl": target_language,
                "dt": "t",
                "q": clean_text
            }
            
            google_response = requests.get(google_url, params=google_params, timeout=8)
            google_result = google_response.json()
            
            if google_result and len(google_result) > 0 and len(google_result[0]) > 0:
                translated_text = google_result[0][0][0]
                if translated_text.strip().lower() != clean_text.lower():
                    logger.info(f"Google Translate SUCCESS: '{clean_text[:30]}...' -> '{translated_text[:30]}...'")
                    return translated_text.strip()
        except Exception as e:
            logger.warning(f"Google Translate API failed: {e}")
        
        # Try Microsoft Translator as third fallback
        try:
            # Using Microsoft Translator via public endpoint
            ms_url = "https://api.cognitive.microsofttranslator.com/translate"
            ms_params = {
                "api-version": "3.0",
                "from": "en", 
                "to": target_language
            }
            ms_headers = {
                "Content-Type": "application/json"
            }
            ms_data = [{"text": clean_text}]
            
            ms_response = requests.post(ms_url, params=ms_params, headers=ms_headers, json=ms_data, timeout=8)
            if ms_response.status_code == 200:
                ms_result = ms_response.json()
                if ms_result and len(ms_result) > 0 and "translations" in ms_result[0]:
                    translated_text = ms_result[0]["translations"][0]["text"]
                    if translated_text.strip().lower() != clean_text.lower():
                        logger.info(f"Microsoft Translate SUCCESS: '{clean_text[:30]}...' -> '{translated_text[:30]}...'")
                        return translated_text.strip()
        except Exception as e:
            logger.warning(f"Microsoft Translate API failed: {e}")
        
        # If all APIs fail, just return original text
        logger.warning(f"All translation APIs failed for: '{clean_text[:30]}...', returning original text")
        return text
            
    except Exception as e:
        logger.error(f"Translation error for '{text[:50]}...': {e}")
        return text

async def translate_score_data(score_data, target_language="ar"):
    """Fast parallel translation of score data using batching and concurrency"""
    if target_language == "en":
        return score_data
    
    try:
        import asyncio
        
        # Create a copy of the data to avoid modifying the original
        translated_data = score_data.copy()
        
        # Collect all unique texts that need translation
        texts_to_translate = set()
        text_locations = {}  # Maps text to its locations in the data structure
        
        def collect_text(text, location):
            """Collect unique texts and track their locations"""
            if isinstance(text, str) and text.strip():
                clean_text = text.strip()
                texts_to_translate.add(clean_text)
                if clean_text not in text_locations:
                    text_locations[clean_text] = []
                text_locations[clean_text].append(location)
        
        # Collect texts from summary_of_best
        if "summary_of_best" in translated_data and translated_data["summary_of_best"]:
            summary_obj = translated_data["summary_of_best"]
            if isinstance(summary_obj, dict):
                if "best_contract" in summary_obj and summary_obj["best_contract"]:
                    collect_text(summary_obj["best_contract"], ("summary_of_best", "best_contract"))
                
                if "summary" in summary_obj and isinstance(summary_obj["summary"], list):
                    for idx, point in enumerate(summary_obj["summary"]):
                        if isinstance(point, str):
                            collect_text(point, ("summary_of_best", "summary", idx))
        
        # Collect texts from contracts
        for section in ["raw_openrouter", "raw_chatgpt"]:
            if section in translated_data and "contracts" in translated_data[section]:
                for contract_idx, contract in enumerate(translated_data[section]["contracts"]):
                    for field in ["content", "reason", "rationale", "criterion", "criteria"]:
                        if field in contract and contract[field]:
                            collect_text(str(contract[field]), (section, "contracts", contract_idx, field))
        
        logger.info(f"Collected {len(texts_to_translate)} unique texts for translation")
        
        # Translate all texts in parallel with concurrency control
        translation_results = {}
        if texts_to_translate:
            # Convert to list for processing
            text_list = list(texts_to_translate)
            
            # Semaphore to limit concurrent API calls
            semaphore = asyncio.Semaphore(8)  # Allow 8 concurrent translations
            
            async def translate_with_semaphore(text):
                async with semaphore:
                    return text, await translate_plain_text(text, target_language)
            
            # Create tasks for all translations
            tasks = [translate_with_semaphore(text) for text in text_list]
            
            # Execute all translations in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, tuple):
                    original, translated = result
                    translation_results[original] = translated
                else:
                    logger.warning(f"Translation task failed: {result}")
        
        # Apply translations to the data structure
        def apply_translation(location, original_text):
            """Apply translation at specific location"""
            clean_text = original_text.strip() if isinstance(original_text, str) else str(original_text)
            return translation_results.get(clean_text, original_text)
        
        # Apply translations to summary_of_best
        if "summary_of_best" in translated_data and translated_data["summary_of_best"]:
            summary_obj = translated_data["summary_of_best"]
            if isinstance(summary_obj, dict):
                if "best_contract" in summary_obj and summary_obj["best_contract"]:
                    translated_data["summary_of_best"]["best_contract"] = apply_translation(
                        ("summary_of_best", "best_contract"), summary_obj["best_contract"]
                    )
                
                if "summary" in summary_obj and isinstance(summary_obj["summary"], list):
                    translated_summary = []
                    for idx, point in enumerate(summary_obj["summary"]):
                        if isinstance(point, str):
                            translated_summary.append(apply_translation(
                                ("summary_of_best", "summary", idx), point
                            ))
                        else:
                            translated_summary.append(point)
                    translated_data["summary_of_best"]["summary"] = translated_summary
        
        # Apply translations to contracts
        for section in ["raw_openrouter", "raw_chatgpt"]:
            if section in translated_data and "contracts" in translated_data[section]:
                for contract_idx, contract in enumerate(translated_data[section]["contracts"]):
                    for field in ["content", "reason", "rationale", "criterion", "criteria"]:
                        if field in contract and contract[field]:
                            translated_data[section]["contracts"][contract_idx][field] = apply_translation(
                                (section, "contracts", contract_idx, field), contract[field]
                            )
        
        logger.info(f"Translation completed: {len(translation_results)} texts translated")
        return translated_data
        
    except Exception as e:
        logger.error(f"Error translating score data: {e}")
        return score_data  # Return original data if translation fails


@app.get("/export_report/{workspace_name}")
async def export_report_endpoint(workspace_name: str, language: str = "en"):
    score_file_path = WORKSPACE_ROOT / workspace_name / "last_score.json"

    if not score_file_path.exists():
        raise HTTPException(status_code=404, detail="No scoring data found for this workspace. Please run a scoring evaluation first.")

    try:
        with open(score_file_path, "r") as f:
            score_data = json.load(f)
        
        # Translate data if Arabic is requested
        if language == "ar":
            logger.info(f"Arabic export requested for workspace {workspace_name}")
            logger.info(f"Original data sample: {str(score_data)[:200]}...")
            score_data = await translate_score_data(score_data, "ar")
            logger.info(f"Translated data sample: {str(score_data)[:200]}...")

        output_excel_buffer = io.BytesIO()

        with pd.ExcelWriter(output_excel_buffer, engine='xlsxwriter') as writer:
            workbook = writer.book
            cell_format = workbook.add_format({'border': 2})
            rationale_format = workbook.add_format({'border': 2, 'text_wrap': True, 'valign': 'top'})
            title_format = workbook.add_format({'bold': True})
            
            current_row_idx = 0

            def write_df_to_sheet(df, sheet_name, start_row):
                nonlocal current_row_idx
                df.to_excel(writer, sheet_name=sheet_name, startrow=start_row, index=False, header=False)
                worksheet = writer.sheets[sheet_name]
                
                for col_idx, col_name in enumerate(df.columns):
                    worksheet.write(start_row, col_idx, col_name, cell_format)
                    
                    max_len = max(
                        [len(str(col_name))] + [len(str(val)) for val in df.iloc[:, col_idx].astype(str).values]
                    )
                    if col_name == "Rationale":
                        worksheet.set_column(col_idx, col_idx, 80, rationale_format)
                    else:
                        worksheet.set_column(col_idx, col_idx, min(max_len + 2, 60), cell_format)
                
                for row_idx_df, row_values in enumerate(df.values.tolist()):
                    for col_idx, val in enumerate(row_values):
                        excel_row_idx = start_row + 1 + row_idx_df
                        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                            worksheet.write(excel_row_idx, col_idx, '', cell_format)
                        else:
                            if df.columns[col_idx] == 'Rationale':
                                worksheet.write(excel_row_idx, col_idx, val, rationale_format)
                            else:
                                worksheet.write(excel_row_idx, col_idx, val, cell_format)
                
                current_row_idx = start_row + 1 + len(df)


            def pivot_contracts_for_excel(data_contracts):
                vendors = sorted(list(set(entry["name"] for entry in data_contracts)))
                serials = sorted(list(set(entry["Serial"] for entry in data_contracts)))
                mapping = {(c["Serial"], c["name"]): c for c in data_contracts}

                rows = []
                for serial in serials:
                    base = next((c for c in data_contracts if c["Serial"] == serial), None)
                    row = {
                        "Serial": base.get("Serial", ''),
                        "Criterion": base.get("criteria", base.get("criterion", '')),
                        "Weight": base.get("weight", '')
                    }
                    
                    current_scores = {}
                    current_weighted_scores = {}
                    current_rationales = {}

                    for vendor in vendors:
                        match = mapping.get((serial, vendor), {})
                        score = match.get("score", '')
                        rationale = match.get("rationale", '')
                        
                        current_scores[f"{vendor} (Standard Score)"] = score
                        current_rationales[vendor] = rationale

                        try:
                            weight = float(base.get("weight", 0))
                            score_val = float(score)
                            current_weighted_scores[f"{vendor} (Weighted Score)"] = round(score_val * weight, 2)
                        except (ValueError, TypeError):
                            current_weighted_scores[f"{vendor} (Weighted Score)"] = ''
                    
                    for vendor in vendors:
                        row[f"{vendor} (Standard Score)"] = current_scores.get(f"{vendor} (Standard Score)", '')
                    for vendor in vendors:
                        row[f"{vendor} (Weighted Score)"] = current_weighted_scores.get(f"{vendor} (Weighted Score)", '')
                    
                    # Combine rationales with newline
                    combined_rationale_str = "\n".join([f"{v}: {current_rationales.get(v, '')}" for v in vendors if current_rationales.get(v)])
                    row["Rationale"] = combined_rationale_str
                    
                    rows.append(row)
                return rows, vendors

            # --- AllyIn Sheet ---
            if score_data.get("raw_openrouter") and score_data["raw_openrouter"].get("contracts"):
                current_row_idx = 0 # Reset row index for each sheet
                worksheet_allyin = workbook.add_worksheet('AllyIn')
                writer.sheets['AllyIn'] = worksheet_allyin # Register worksheet with writer

                openrouter_rows, openrouter_vendors = pivot_contracts_for_excel(score_data["raw_openrouter"]["contracts"])
                df_openrouter = pd.DataFrame(openrouter_rows)
                
                # Write section title
                worksheet_allyin.write(current_row_idx, 0, "AllyIn Breakdown", title_format)
                current_row_idx += 1 # Move to next row after title
                
                # Write DataFrame content
                write_df_to_sheet(df_openrouter, 'AllyIn', current_row_idx)
                current_row_idx += 1 # Add a blank row after the table content

                # Add summary rows for AllyIn
                final_scores_row_open = {"Serial": "Final Weighted Scores"}
                for vendor in openrouter_vendors:
                    score = score_data["final_scores_openrouter"].get(vendor, {}).get("score_out_of_50", "") or \
                            score_data["final_scores_openrouter"].get(vendor, {}).get("score_out_of_100", "")
                    final_scores_row_open[f"{vendor} (Weighted Score)"] = score

                final_percentage_row_open = {"Serial": "Final Percentages"}
                for vendor in openrouter_vendors:
                    pct = score_data["final_scores_openrouter"].get(vendor, {}).get("percentage", "")
                    final_percentage_row_open[f"{vendor} (Weighted Score)"] = pct

                summary_text_open = ""
                if score_data.get("summary_of_best"):
                    summary_text_open = f"Best Vendor: {score_data['summary_of_best'].get('best_contract', 'N/A')}\n" + \
                                        "\n".join(f"- {line}" for line in score_data['summary_of_best'].get('summary', []))
                summary_row_open = {"Serial": summary_text_open}

                # Create a temporary DataFrame for these summary rows to use write_df_to_sheet
                summary_data_for_df = [final_scores_row_open, final_percentage_row_open, summary_row_open]
                
                all_summary_headers = list(set(col for row_dict in summary_data_for_df for col in row_dict.keys()))
                
                ordered_allyin_cols = ["Serial", "Criterion", "Weight"]
                for vendor in openrouter_vendors:
                    if f"{vendor} (Standard Score)" in all_summary_headers:
                        ordered_allyin_cols.append(f"{vendor} (Standard Score)")
                for vendor in openrouter_vendors:
                    if f"{vendor} (Weighted Score)" in all_summary_headers:
                        ordered_allyin_cols.append(f"{vendor} (Weighted Score)")
                if "Rationale" in all_summary_headers:
                    ordered_allyin_cols.append("Rationale")

                # Filter to only include columns that actually exist in df_summary_allyin
                final_ordered_allyin_cols = [col for col in ordered_allyin_cols if col in all_summary_headers]
                
                # Ensure DataFrame has all necessary columns before reordering
                df_summary_allyin = pd.DataFrame(summary_data_for_df, columns=final_ordered_allyin_cols)

                write_df_to_sheet(df_summary_allyin, 'AllyIn', current_row_idx)
                current_row_idx += len(df_summary_allyin) + 2


            # --- ChatGPT Sheet ---
            if score_data.get("raw_chatgpt") and score_data["raw_chatgpt"].get("contracts"):
                current_row_idx = 0 # Reset row index for each sheet
                worksheet_chatgpt = workbook.add_worksheet('ChatGPT')
                writer.sheets['ChatGPT'] = worksheet_chatgpt # Register worksheet with writer

                chatgpt_rows, chatgpt_vendors = pivot_contracts_for_excel(score_data["raw_chatgpt"]["contracts"])
                df_chatgpt = pd.DataFrame(chatgpt_rows)

                worksheet_chatgpt.write(current_row_idx, 0, "ChatGPT Breakdown", title_format)
                current_row_idx += 1
                
                write_df_to_sheet(df_chatgpt, 'ChatGPT', current_row_idx)
                current_row_idx += 1

                final_scores_row_chatgpt = {"Serial": "Final Weighted Scores"}
                for vendor in chatgpt_vendors:
                    score = score_data["final_scores_chatgpt"].get(vendor, {}).get("score_out_of_50", "") or \
                            score_data["final_scores_chatgpt"].get(vendor, {}).get("score_out_of_100", "")
                    final_scores_row_chatgpt[f"{vendor} (Weighted Score)"] = score

                final_percentage_row_chatgpt = {"Serial": "Final Percentages"}
                for vendor in chatgpt_vendors:
                    pct = score_data["final_scores_chatgpt"].get(vendor, {}).get("percentage", "")
                    final_percentage_row_chatgpt[f"{vendor} (Weighted Score)"] = pct
                
                summary_text_chatgpt = ""
                if score_data.get("summary_of_best"):
                    summary_text_chatgpt = f"Best Vendor: {score_data['summary_of_best'].get('best_contract', 'N/A')}\n" + \
                                           "\n".join(f"- {line}" for line in score_data['summary_of_best'].get('summary', []))
                summary_row_chatgpt = {"Serial": summary_text_chatgpt}

                summary_data_for_df_chatgpt = [final_scores_row_chatgpt, final_percentage_row_chatgpt, summary_row_chatgpt]
                
                all_summary_headers_chatgpt = list(set(col for row_dict in summary_data_for_df_chatgpt for col in row_dict.keys()))

                ordered_chatgpt_cols = ["Serial", "Criterion", "Weight"]
                for vendor in chatgpt_vendors:
                    if f"{vendor} (Standard Score)" in all_summary_headers_chatgpt:
                        ordered_chatgpt_cols.append(f"{vendor} (Standard Score)")
                for vendor in chatgpt_vendors:
                    if f"{vendor} (Weighted Score)" in all_summary_headers_chatgpt:
                        ordered_chatgpt_cols.append(f"{vendor} (Weighted Score)")
                if "Rationale" in all_summary_headers_chatgpt:
                    ordered_chatgpt_cols.append("Rationale")

                final_ordered_chatgpt_cols = [col for col in ordered_chatgpt_cols if col in all_summary_headers_chatgpt]
                df_summary_chatgpt = pd.DataFrame(summary_data_for_df_chatgpt, columns=final_ordered_chatgpt_cols)
                
                write_df_to_sheet(df_summary_chatgpt, 'ChatGPT', current_row_idx)
                current_row_idx += len(df_summary_chatgpt) + 2


            # --- Final Scores Sheet (for AllyIn/ChatGPT combined final scores) ---
            if score_data.get("final_scores_openrouter") or score_data.get("final_scores_chatgpt"):
                current_row_idx = 0
                worksheet_final = workbook.add_worksheet('Final Scores')
                writer.sheets['Final Scores'] = worksheet_final

                final_openrouter = score_data.get("final_scores_openrouter", {})
                final_chatgpt = score_data.get("final_scores_chatgpt", {})
                
                all_contracts_final = sorted(list(set(list(final_openrouter.keys()) + list(final_chatgpt.keys()))))

                combined_scores_list = []
                for vendor in all_contracts_final:
                    open_score = final_openrouter.get(vendor, {})
                    gpt_score = final_chatgpt.get(vendor, {})

                    open_score_label = "Allyin Score (out of 50)" if open_score.get("score_out_of_50") else "Allyin Score (out of 100)"
                    gpt_score_label = "ChatGPT Score (out of 50)" if gpt_score.get("score_out_of_50") else "ChatGPT Score (out of 100)"

                    combined_scores_list.append({
                        "Contract": vendor,
                        open_score_label: open_score.get("score_out_of_50", open_score.get("score_out_of_100", "")),
                        "Allyin %": open_score.get("percentage", ""),
                        gpt_score_label: gpt_score.get("score_out_of_50", gpt_score.get("score_out_of_100", "")),
                        "ChatGPT %": gpt_score.get("percentage", "")
                    })
                
                df_final_scores = pd.DataFrame(combined_scores_list)
                
                # REMOVE THESE TWO LINES to remove "Final Scores Summary" title
                # worksheet_final.write(current_row_idx, 0, "Final Scores Summary", title_format)
                # current_row_idx += 1

                if not df_final_scores.empty:
                    # Adjust start_row here if you removed the title and didn't decrement current_row_idx
                    # If current_row_idx was 0, it will now start writing from 0.
                    write_df_to_sheet(df_final_scores, 'Final Scores', current_row_idx)
                    current_row_idx += len(df_final_scores) + 2


        output_excel_buffer.seek(0)

        lang_suffix = "_arabic" if language == "ar" else ""
        headers = {
            "Content-Disposition": f"attachment; filename={workspace_name}_evaluation_report{lang_suffix}.xlsx",
            "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        }
        return StreamingResponse(output_excel_buffer, headers=headers, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No scoring data found for this workspace. Please run a scoring evaluation first.")
    except Exception as e:
        logger.error(f"Error generating export report for workspace '{workspace_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating export report: {e}")

@app.get("/export_combined_report/{workspace_name}")
async def export_combined_report_endpoint(workspace_name: str, language: str = "en"):
    combined_score_file_path = WORKSPACE_ROOT / workspace_name / "combined_score.json"

    if not combined_score_file_path.exists():
        raise HTTPException(status_code=404, detail="No combined scoring data found for this workspace. Please run a combined evaluation first.")

    try:
        with open(combined_score_file_path, "r") as f:
            score_data = json.load(f)
        logger.info(f"Loaded combined_score.json for export for workspace: {workspace_name}")
        
        # Translate data if Arabic is requested
        if language == "ar":
            score_data = await translate_score_data(score_data, "ar")

        output_excel_buffer = io.BytesIO()

        with pd.ExcelWriter(output_excel_buffer, engine='xlsxwriter') as writer:
            workbook = writer.book

            # --- Define xlsxwriter formats for better appearance ---
            header_format = workbook.add_format({
                'bold': True, 'align': 'center', 'valign': 'vcenter',
                'border': 1, 'bg_color': '#DDEBF7' # Light blue background
            })
            cell_format = workbook.add_format({
                'border': 1, 'align': 'center', 'valign': 'vcenter'
            })
            rationale_format = workbook.add_format({
                'border': 1, 'text_wrap': True, 'valign': 'top', 'align': 'left'
            })
            title_format = workbook.add_format({
                'bold': True, 'font_size': 16, 'align': 'center', 'valign': 'vcenter',
                'bg_color': '#BFDFFF', 'border': 1 # More prominent blue for main titles
            })
            section_title_format = workbook.add_format({
                'bold': True, 'font_size': 14, 'align': 'left', 'valign': 'vcenter',
                'font_color': '#000080' # Dark blue for section titles
            })
            summary_best_contract_format = workbook.add_format({
                'bold': True, 'font_size': 12, 'align': 'left', 'valign': 'vcenter'
            })
            summary_point_format = workbook.add_format({
                'font_size': 10, 'align': 'left', 'valign': 'top', 'text_wrap': True
            })
            
            # This is a helper function to write DataFrames to sheets
            # Modified to use the new header_format and cell_format
            def write_df_to_sheet(df, sheet, start_row, sheet_title=None):
                nonlocal current_row_idx
                
                # Write section title if provided
                if sheet_title:
                    # Merge cells for the title across all columns of the DataFrame
                    num_cols = len(df.columns)
                    if num_cols > 0:
                        sheet.merge_range(start_row, 0, start_row, num_cols - 1, sheet_title, section_title_format)
                        start_row += 2 # Add space after title
                
                # Write headers
                for col_idx, col_name in enumerate(df.columns):
                    sheet.write(start_row, col_idx, col_name, header_format)

                # Write data rows
                for row_idx_df, row_values in enumerate(df.values.tolist()):
                    for col_idx, val in enumerate(row_values):
                        excel_row_idx = start_row + 1 + row_idx_df
                        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                            sheet.write(excel_row_idx, col_idx, '', cell_format)
                        else:
                            if df.columns[col_idx] == 'rationale': # Note: 'rationale' instead of 'Rationale' due to pandas column names
                                sheet.write(excel_row_idx, col_idx, val, rationale_format)
                            else:
                                sheet.write(excel_row_idx, col_idx, val, cell_format)
                
                # Set column widths
                for col_idx, col_name in enumerate(df.columns):
                    max_len = max(
                        [len(str(col_name))] + [len(str(val)) for val in df.iloc[:, col_idx].astype(str).values]
                    )
                    if col_name == "rationale":
                        sheet.set_column(col_idx, col_idx, 80) # Fixed width for rationale
                    else:
                        sheet.set_column(col_idx, col_idx, min(max_len + 2, 60)) # Dynamic width, max 60

                current_row_idx = start_row + 1 + len(df)

            current_row_idx = 0 # Initialize current_row_idx for the sheet

            # --- Combined Evaluation Sheet ---
            if score_data.get("raw_combined") and score_data["raw_combined"].get("contracts"):
                worksheet_combined = workbook.add_worksheet('Combined Evaluation')
                writer.sheets['Combined Evaluation'] = worksheet_combined # Link sheet to writer

                # Main Report Title
                worksheet_combined.merge_range(current_row_idx, 0, current_row_idx, 6, "Combined Evaluation Report", title_format) # Merge across enough columns
                current_row_idx += 2 # Add space after main title

                combined_eval_rows = score_data["raw_combined"]["contracts"]
                df_combined_eval = pd.DataFrame(combined_eval_rows)

                # Ensure consistent column order for Excel output
                combined_eval_headers = [
                    "name", "technical_score", "weighted_technical_score",
                    "financial_score", "weighted_financial_score",
                    "score", "rationale"
                ]
                df_combined_eval = df_combined_eval.reindex(columns=combined_eval_headers)

                # Rename columns for better readability in Excel
                df_combined_eval.rename(columns={
                    'name': 'Contract Name',
                    'technical_score': 'Technical Score (Raw)',
                    'weighted_technical_score': 'Weighted Technical Score',
                    'financial_score': 'Financial Score (Raw)',
                    'weighted_financial_score': 'Weighted Financial Score',
                    'score': 'Combined Score (Out of 100)',
                    'rationale': 'Rationale'
                }, inplace=True)

                write_df_to_sheet(df_combined_eval, worksheet_combined, current_row_idx, "Combined Evaluation Breakdown")
                current_row_idx += 2 # Add space after this table

                # Add Combined Final Scores
                if score_data.get("final_scores_combined"):
                    final_combined_scores_data = score_data["final_scores_combined"]
                    combined_final_rows = []
                    for contract_name in sorted(list(final_combined_scores_data.keys())): # Sort for consistent order
                        score_data_item = final_combined_scores_data.get(contract_name, {})
                        combined_final_rows.append({
                            "Contract": contract_name,
                            "Combined Score (out of 100)": score_data_item.get("score_out_of_100", '-'),
                            "Combined %": score_data_item.get("percentage", '-')
                        })
                    df_final_combined = pd.DataFrame(combined_final_rows)

                    write_df_to_sheet(df_final_combined, worksheet_combined, current_row_idx, "Combined Final Scores")
                    current_row_idx += 2 # Add space after this table

                # --- Best Proposal Summary Section (Enhanced Formatting) ---
                if score_data.get("summary_of_combined_best"):
                    summary_data_combined = score_data["summary_of_combined_best"]
                    
                    # Determine the maximum column index to merge across for consistency
                    max_cols_for_summary = len(df_combined_eval.columns) # Use the number of columns from the main breakdown table

                    # "Best Proposal Summary" Title - Merged and styled
                    worksheet_combined.merge_range(
                        current_row_idx, 0, current_row_idx, max_cols_for_summary - 1,
                        "Best Proposal Summary", section_title_format
                    )
                    current_row_idx += 2 # Space after title

                    # Best Contract Name - Bold and left-aligned
                    best_contract_name = summary_data_combined.get("best_contract", "N/A")
                    worksheet_combined.write(current_row_idx, 0, "Best Contract:", summary_best_contract_format)
                    worksheet_combined.merge_range(
                        current_row_idx, 1, current_row_idx, max_cols_for_summary - 1,
                        best_contract_name, summary_best_contract_format
                    )
                    current_row_idx += 1

                    # Summary bullet points - Each point on a new line, bulleted, text wrapped
                    if summary_data_combined.get("summary"):
                        for point in summary_data_combined["summary"]:
                            # Write bullet point and text, merging across remaining columns
                            worksheet_combined.write(current_row_idx, 0, "•", summary_point_format) # Bullet point
                            worksheet_combined.merge_range(
                                current_row_idx, 1, current_row_idx, max_cols_for_summary - 1,
                                point, summary_point_format
                            )
                            current_row_idx += 1
                    current_row_idx += 1 # Add a final blank line after summary for spacing

            else:
                raise HTTPException(status_code=404, detail="No 'raw_combined' data found in combined_score.json for Excel export.")


        output_excel_buffer.seek(0)

        lang_suffix = "_arabic" if language == "ar" else ""
        filename = f"{workspace_name}_combined_evaluation_report{lang_suffix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        headers = {
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        }
        return StreamingResponse(output_excel_buffer, headers=headers, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    except json.JSONDecodeError:
        logger.warning(f"combined_score.json for '{workspace_name}' is malformed.")
        raise HTTPException(status_code=500, detail="Error loading combined scoring data: JSON is malformed.")
    except Exception as e:
        logger.error(f"Error generating combined evaluation report for workspace '{workspace_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating combined evaluation report: {e}")

async def process_uploaded_documents_background(workspace_name: str, file_type: str, project_root: Path):
    logger.info(f"Background task started for workspace '{workspace_name}', type '{file_type}'.")
    try:
        active_processing_tasks[workspace_name] = True
        logger.info(f"Background: Task for '{workspace_name}' marked as active.")

        # Skip parsing for technical/financial reports
        if file_type in ["technical_report", "financial_report"]:
            logger.info(f"Skipping parsing and embedding for file type '{file_type}' in workspace '{workspace_name}'.")
            return

        # Map input/output directories and filenames
        input_dir_map = {
            "documents": "contracts",
            "criteria": "criteria_weights",
            "resumes": "resumes",
            "job_descriptions": "job_descriptions"
        }
        output_file_map = {
            "documents": "parsed.jsonl",
            "criteria": "parsed_criteria.jsonl",
            "resumes": "parsed_resumes.jsonl",
            "job_descriptions": "parsed_jd.jsonl"
        }

        input_dir = WORKSPACE_ROOT / workspace_name / input_dir_map.get(file_type, "contracts")
        output_file = WORKSPACE_ROOT / workspace_name / output_file_map.get(file_type, "parsed.jsonl")
        parsed_file_to_embed = output_file_map.get(file_type, "parsed.jsonl")

        logger.info(f"Background: Starting document parsing for '{workspace_name}' from '{input_dir}' to '{output_file}'...")
        from services.parser_service import parse_documents

        use_manifest = file_type in ["documents", "resumes", "job_descriptions"]
        append_output = file_type in ["documents", "resumes", "job_descriptions"]

        # Determine folder prefix based on file type
        folder_prefix = input_dir_map.get(file_type, "")
        parse_documents(str(input_dir), str(output_file), workspace_name, use_manifest=use_manifest, append_output=append_output, folder_prefix=folder_prefix)

        logger.info(f"Background: Document parsing completed for '{workspace_name}'. Output to {output_file}")

        # Only documents and resumes are embedded (job descriptions are used directly from parsed files)
        prompts = None
        if file_type in ["documents", "resumes"]:
            logger.info(f"Background: Synchronizing embedder manifest for '{workspace_name}'...")
            sync_embedder_manifest(workspace_name, base_dir=project_root)
            logger.info(f"Background: Embedder manifest synchronized for '{workspace_name}'.")

            logger.info(f"Background: Starting document embedding for '{workspace_name}'...")
            embedding_result = run_embedding_for_workspace(workspace_name, parsed_file_to_embed, base_dir=project_root)

            if embedding_result.get("status") == "error":
                logger.error(f"Background: Embedding failed for '{workspace_name}': {embedding_result.get('message')}")
            else:
                logger.info(f"Background: Embedding completed for '{workspace_name}': {embedding_result.get('message')}")
                # After embedding, generate AI prompts and return them
                logger.info(f"Background: Generating AI prompts for '{workspace_name}' after embedding...")
                from services.prompt_generator_service import generate_ai_prompts
                prompts = generate_ai_prompts(workspace_name, base_dir=project_root)
                logger.info(f"Background: Generated {len(prompts) if prompts else 0} prompts for '{workspace_name}'.")
                return prompts
        elif file_type == "criteria":
            pass  # criteria parsing already handled elsewhere

    except Exception as e:
        logger.error(f"Background task error for '{workspace_name}': {e}", exc_info=True)
    finally:
        active_processing_tasks.pop(workspace_name, None)
        logger.info(f"Background task finished for '{workspace_name}'.")


@app.post("/upload/documents/{workspace_name}")
async def upload_documents(
    workspace_name: str,
    files: List[UploadFile] = File(...)
):
    save_dir = WORKSPACE_ROOT / workspace_name / "contracts"
    save_dir.mkdir(parents=True, exist_ok=True)

    if active_processing_tasks.get(workspace_name):
        raise HTTPException(status_code=409, detail=f"Processing already in progress for workspace '{workspace_name}'. Please wait.")

    uploaded_file_names = []
    for uploaded_file in files:
        file_path = save_dir / uploaded_file.filename
        try:
            with open(file_path, "wb") as f:
                content = await uploaded_file.read()
                f.write(content)
            uploaded_file_names.append(uploaded_file.filename)
            logger.info(f"File '{uploaded_file.filename}' saved.")
        except Exception as e:
            logger.error(f"Error saving file '{uploaded_file.filename}': {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save file: {uploaded_file.filename}")

    # Run the document processing and prompt generation synchronously
    prompts = await process_uploaded_documents_background(workspace_name, "documents", PROJECT_ROOT)

    return {
        "message": "Files uploaded and processed successfully.",
        "files": uploaded_file_names,
        "prompts": prompts or []
    }

@app.post("/upload/technical_report/{workspace_name}")
async def upload_technical_report(
    workspace_name: str,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    save_dir = WORKSPACE_ROOT / workspace_name / "technical_reports"
    save_dir.mkdir(parents=True, exist_ok=True)

    if active_processing_tasks.get(workspace_name):
        raise HTTPException(status_code=409, detail=f"Processing already in progress for workspace '{workspace_name}'. Please wait.")

    # NEW: Delete existing technical reports in the directory before saving new ones
    try:
        if save_dir.exists():
            for item in save_dir.iterdir():
                if item.is_file():
                    os.remove(item)
                    logger.info(f"Deleted old technical report file: {item.name}")
            logger.info(f"Cleaned up existing technical reports in '{workspace_name}'.")
    except Exception as e:
        logger.error(f"Error cleaning up old technical reports for workspace '{workspace_name}': {e}", exc_info=True)
        # Optionally raise HTTPException here if cleanup failure should block upload
        raise HTTPException(status_code=500, detail=f"Failed to clean up old technical reports before upload: {e}")


    uploaded_file_names = []
    for uploaded_file in files:
        file_path = save_dir / uploaded_file.filename
        try:
            with open(file_path, "wb") as f:
                content = await uploaded_file.read()
                f.write(content)
            uploaded_file_names.append(uploaded_file.filename)
            logger.info(f"Technical report file '{uploaded_file.filename}' saved.")
        except Exception as e:
            logger.error(f"Error saving technical report file '{uploaded_file.filename}': {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save file: {uploaded_file.filename}")

    return {"message": "Technical report files uploaded successfully. Old reports, if any, were replaced.", "files": uploaded_file_names}

@app.post("/upload/financial_report/{workspace_name}")
async def upload_financial_report(
    workspace_name: str,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    save_dir = WORKSPACE_ROOT / workspace_name / "financial_reports"
    save_dir.mkdir(parents=True, exist_ok=True)

    if active_processing_tasks.get(workspace_name):
        raise HTTPException(status_code=409, detail=f"Processing already in progress for workspace '{workspace_name}'. Please wait.")

    # NEW: Delete existing financial reports in the directory before saving new ones
    try:
        if save_dir.exists():
            for item in save_dir.iterdir():
                if item.is_file():
                    os.remove(item)
                    logger.info(f"Deleted old financial report file: {item.name}")
            logger.info(f"Cleaned up existing financial reports in '{workspace_name}'.")
    except Exception as e:
        logger.error(f"Error cleaning up old financial reports for workspace '{workspace_name}': {e}", exc_info=True)
        # Optionally raise HTTPException here if cleanup failure should block upload
        raise HTTPException(status_code=500, detail=f"Failed to clean up old financial reports before upload: {e}")

    uploaded_file_names = []
    for uploaded_file in files:
        file_path = save_dir / uploaded_file.filename
        try:
            with open(file_path, "wb") as f:
                content = await uploaded_file.read()
                f.write(content)
            uploaded_file_names.append(uploaded_file.filename)
            logger.info(f"Financial report file '{uploaded_file.filename}' saved.")
        except Exception as e:
            logger.error(f"Error saving financial report file '{uploaded_file.filename}': {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save file: {uploaded_file.filename}")

    # No background task for parsing/embedding financial_report files here, as per previous discussion.
    # The combined evaluation service will read them directly.
    # background_tasks.add_task(process_uploaded_documents_background, workspace_name, "financial_report", PROJECT_ROOT)

    return {"message": "Financial report files uploaded successfully. Old reports, if any, were replaced.", "files": uploaded_file_names}
async def process_uploaded_criteria_background(workspace_name: str, file_type: str, project_root: Path):
    logger.info(f"Background task started for criteria '{workspace_name}', type '{file_type}'.")
    try:
        active_processing_tasks[workspace_name] = True
        logger.info(f"Background: Task for criteria '{workspace_name}' marked as active.")

        logger.info("Background: Starting criteria parsing...")
        # Assuming run_parsing_for_workspace handles parsing files in "criteria_weights" to "parsed_criteria.jsonl"
        run_parsing_for_workspace(workspace_name, base_dir=project_root) # Corrected import to run_parsing_for_workspace

        parsed_criteria_file = project_root / "data" / workspace_name / "parsed_criteria.jsonl"
        cleaned_criteria_file = project_root / "data" / workspace_name / "cleaned_criteria.json"

        if not parsed_criteria_file.exists():
            logger.error(f"Background: Parsing failed to create parsed_criteria.jsonl for '{workspace_name}'.")
            return

        extract_criteria_from_jsonl(str(parsed_criteria_file), str(cleaned_criteria_file))
        logger.info(f"Background: Criteria uploaded and parsed successfully for '{workspace_name}'.")

    except Exception as e:
        logger.error(f"Background task error for criteria '{workspace_name}': {e}", exc_info=True)
    finally:
        if workspace_name in active_processing_tasks:
            del active_processing_tasks[workspace_name]
        logger.info(f"Background task finished for criteria '{workspace_name}'.")


@app.post("/upload/criteria/{workspace_name}")
async def upload_criteria(
    workspace_name: str,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    save_dir = WORKSPACE_ROOT / workspace_name / "criteria_weights"
    save_dir.mkdir(parents=True, exist_ok=True)

    if active_processing_tasks.get(workspace_name):
        raise HTTPException(status_code=409, detail=f"Processing already in progress for workspace '{workspace_name}'. Please wait.")

    uploaded_file_names = []
    for uploaded_file in files:
        file_path = save_dir / uploaded_file.filename
        with open(file_path, "wb") as f:
            f.write(await uploaded_file.read())
        uploaded_file_names.append(uploaded_file.filename)

    background_tasks.add_task(process_uploaded_criteria_background, workspace_name, "criteria", PROJECT_ROOT)

    return {"message": "Criteria files uploaded. Processing started in the background.", "files": uploaded_file_names}


@app.get("/pdf/{workspace_name}/{file_path:path}")
async def get_pdf(workspace_name: str, file_path: str):
    # The file_path parameter can contain the full path including folder (e.g., "resumes/filename.pdf")
    # or just the filename for backward compatibility
    
    # URL decode the file path
    import urllib.parse
    decoded_file_path = urllib.parse.unquote(file_path)
    
    # Check if the path contains a folder separator
    if "/" in decoded_file_path:
        # Extract folder and filename
        folder_name, actual_filename = decoded_file_path.split("/", 1)
        full_file_path = WORKSPACE_ROOT / workspace_name / folder_name / actual_filename
    else:
        # For backward compatibility, try to find the file in different folders
        # First try contracts folder (old format)
        full_file_path = WORKSPACE_ROOT / workspace_name / "contracts" / decoded_file_path
        if not full_file_path.exists():
            # Try resumes folder
            full_file_path = WORKSPACE_ROOT / workspace_name / "resumes" / decoded_file_path
        if not full_file_path.exists():
            # Try job_descriptions folder
            full_file_path = WORKSPACE_ROOT / workspace_name / "job_descriptions" / decoded_file_path
    
    if not full_file_path.exists():
        raise HTTPException(status_code=404, detail=f"PDF file not found: {decoded_file_path}")
    return FileResponse(full_file_path, media_type="application/pdf")

@app.get("/prompts/{workspace_name}")
async def get_prepopulated_prompts(workspace_name: str):
    logger.info(f"[/prompts] Request received for workspace: {workspace_name}")
    qa_prompts = []
    
    collection_name = f"contract_docs_{workspace_name}"
    try:
        qclient = QdrantClient(host=QDRANT_HOST, port=6333, timeout=10)
        
        if qclient.collection_exists(collection_name):
            collection_info = qclient.get_collection(collection_name)
            if collection_info.points_count > 0:
                logger.info(f"[/prompts] Qdrant collection '{collection_name}' exists with {collection_info.points_count} points. Generating AI prompts...")
                ai_generated_general_prompts = generate_ai_prompts(workspace_name, base_dir=PROJECT_ROOT)
                if ai_generated_general_prompts:
                    qa_prompts.extend(ai_generated_general_prompts[:10])
                    # Save the generated prompts to replace defaults
                    prompts_data = load_prompts()
                    prompts_data[workspace_name] = qa_prompts
                    save_prompts_to_file(prompts_data)
                else:
                    logger.warning(f"No AI prompts generated for '{workspace_name}'.")
            else:
                logger.info(f"[/prompts] Qdrant collection '{collection_name}' exists but has no points. Checking saved defaults.")
                prompts_data = load_prompts()
                if workspace_name in prompts_data:
                    qa_prompts = prompts_data[workspace_name]
        else:
            logger.info(f"[/prompts] No collection found for '{workspace_name}'. Checking saved defaults.")
            prompts_data = load_prompts()
            if workspace_name in prompts_data:
                qa_prompts = prompts_data[workspace_name]

    except Exception as e:
        logger.error(f"Failed to generate or load prompts for workspace '{workspace_name}': {e}", exc_info=True)
        return []

    return qa_prompts


@app.post("/compare_responses")
async def compare_ai_responses(request: CompareResponsesRequest):
    try:
        comparison_result = compare_responses(request.openrouter_response, request.chatgpt_response)
        return comparison_result
    except Exception as e:
        logger.error(f"Error comparing responses: {e}")
        raise HTTPException(status_code=500, detail=f"Error comparing responses: {e}")

@app.post("/combined_evaluate")
async def combined_evaluation_endpoint(request: CombinedEvaluationRequest):
    logger.info(f"[/combined_evaluate] Request received for workspace: {request.workspace_name}, technical_weight: {request.technical_weight}, financial_weight: {request.financial_weight}")
    try:
        combined_results = perform_combined_evaluation(
            workspace_name=request.workspace_name,
            technical_weight=request.technical_weight,
            financial_weight=request.financial_weight
        )
        return combined_results
    except Exception as e:
        logger.error(f"Error during combined evaluation for workspace '{request.workspace_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error during combined evaluation: {e}")


@app.get("/metrics/{workspace_name}")
async def get_metrics(workspace_name: str):
    metrics_file =WORKSPACE_ROOT  / workspace_name / "metrics.json"
    if not metrics_file.exists():
        return {"metrics": []}
    try:
        with open(metrics_file, "r") as f:
            metrics = json.load(f)
        return {"metrics": metrics}
    except Exception as e:
        logger.error(f"Error reading metrics for workspace '{workspace_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Error reading metrics: {e}")

@app.get("/processing_status/{workspace_name}")
async def get_processing_status(workspace_name: str):
    is_active = active_processing_tasks.get(workspace_name, False)
    is_criteria_extracting = active_criteria_extraction_tasks.get(workspace_name, False)
    logger.info(f"Status check for '{workspace_name}': active={is_active}, criteria_extracting={is_criteria_extracting}")
    return {
        "is_processing": is_active,
        "is_criteria_extracting": is_criteria_extracting
    }

@app.post("/export_table_xlsx/{workspace_name}")
async def export_table_xlsx_endpoint(workspace_name: str, request: ContractTableExportRequest):
    logger.info(f"[/export_table_xlsx] Request received for workspace: {workspace_name}, table title: {request.title}")

    # The frontend is now sending already-pivoted data.
    # So, df_data will directly reflect the UI table structure.
    df_data = pd.DataFrame(request.contracts)

    if df_data.empty:
        raise HTTPException(status_code=400, detail="No data provided for export.")

    output_excel_buffer = io.BytesIO()

    try:
        with pd.ExcelWriter(output_excel_buffer, engine='xlsxwriter') as writer:
            workbook = writer.book
            cell_format = workbook.add_format({'border': 2})
            rationale_format = workbook.add_format({'border': 2, 'text_wrap': True, 'valign': 'top'})
            header_format = workbook.add_format({'bold': True, 'border': 2, 'bg_color': '#D7E4BC'})

            sheet_name = request.title.replace(" ", "_")[:31]

            # We don't need to reorder or rename columns here as extensively as before,
            # because the frontend `tableDisplayDataForExport` already sends the desired columns
            # with their display names. We just need to ensure the order is maintained.
            # Get the exact order of columns as sent from the frontend
            if request.contracts:
                # Use the keys from the first dictionary in the list to define column order
                export_columns = list(request.contracts[0].keys())
            else:
                export_columns = [] # Should be handled by df_data.empty check

            df_export = df_data[export_columns] # Ensure the order is kept


            # Write to sheet
            worksheet = workbook.add_worksheet(sheet_name)
            writer.sheets[sheet_name] = worksheet # Link worksheet to writer

            # Write headers manually to apply formatting and custom names
            for col_num, col_name in enumerate(df_export.columns):
                worksheet.write(0, col_num, col_name, header_format) # Write headers with formatting

                # Adjust column width
                max_len = max(
                    len(str(col_name)), # Length of the header itself
                    (df_export[col_name].astype(str).map(len).max() if not df_export.empty else 0) # Max length of data in column
                )
                if col_name == "Rationale":
                    worksheet.set_column(col_num, col_num, 80, rationale_format)
                else:
                    worksheet.set_column(col_num, col_num, min(max_len + 2, 60), cell_format)

            # Write data rows with formats (starting from row 1, since row 0 is headers)
            for row_idx, row_data in enumerate(df_export.values):
                for col_idx, cell_value in enumerate(row_data):
                    excel_row_idx = row_idx + 1 # +1 because headers are in row 0
                    if isinstance(cell_value, float) and (math.isnan(cell_value) or math.isinf(cell_value)):
                        worksheet.write(excel_row_idx, col_idx, '', cell_format)
                    else:
                        if df_export.columns[col_idx] == 'Rationale':
                            worksheet.write(excel_row_idx, col_idx, cell_value, rationale_format)
                        else:
                            worksheet.write(excel_row_idx, col_idx, cell_value, cell_format)

        output_excel_buffer.seek(0)
        file_filename = f"{workspace_name}_{request.title.replace(' ', '_')}.xlsx"
        logger.info(f"Generated XLSX file: {file_filename}")

        headers = {
            "Content-Disposition": f"attachment; filename={file_filename}",
            "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        }
        return StreamingResponse(output_excel_buffer, headers=headers, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    except Exception as e:
        logger.error(f"Error generating table XLSX report for workspace '{workspace_name}' title '{request.title}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating table XLSX report: {e}")


# --- Upload evaluation report endpoint ---
# This endpoint allows uploading an evaluation report Excel file and saves it to the workspace data directory.
@app.post("/upload-report")
async def upload_report(workspace: str = Form(...), file: UploadFile = File(...)):
    try:
        output_dir = WORKSPACE_ROOT/workspace
        os.makedirs(output_dir, exist_ok=True)

        destination_path = os.path.join(output_dir, f"{workspace}_evaluation_report.xlsx")

        with open(destination_path, "wb") as f:
            contents = await file.read()
            f.write(contents)

        logger.info(f"Report uploaded and saved to {destination_path}")
        return {"message": "Report uploaded successfully."}
    except Exception as e:
        logger.error(f"Failed to upload report for workspace '{workspace}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload report: {e}")
    
# Add this endpoint to your backend (probably in the same file as the export_report endpoint)

@app.get("/workspace/{workspace_name}/current-scores")
async def get_current_scores(workspace_name: str):
    """Get the current scores for a workspace, including recalculated final scores"""
    score_file_path = WORKSPACE_ROOT / workspace_name / "last_score.json"
    
    logger.info(f"Getting current scores for workspace: {workspace_name}")
    logger.info(f"Score file path: {score_file_path}")

    if not score_file_path.exists():
        logger.warning(f"Score file not found: {score_file_path}")
        raise HTTPException(status_code=404, detail="No scoring data found for this workspace.")

    try:
        with open(score_file_path, "r") as f:
            score_data = json.load(f)
        
        logger.info(f"Loaded score data with keys: {list(score_data.keys())}")
        logger.info(f"Raw OpenRouter contracts: {len(score_data.get('raw_openrouter', {}).get('contracts', []))}")
        logger.info(f"Raw ChatGPT contracts: {len(score_data.get('raw_chatgpt', {}).get('contracts', []))}")

        # Recalculate final scores from the current raw contract data
        def calculate_final_scores(contracts_data, max_score=5):
            """Calculate final scores from raw contract data using the same logic as compute_weighted_scores"""
            if not contracts_data:
                logger.warning("No contracts data provided to calculate_final_scores")
                return {}
            
            logger.info(f"Input contracts_data type: {type(contracts_data)}, length: {len(contracts_data)}")
            logger.info(f"Sample contract structure: {contracts_data[0] if contracts_data else 'None'}")
            
            # Group by vendor name
            vendors = {}
            for contract in contracts_data:
                vendor_name = contract.get("name")
                if not vendor_name:
                    logger.warning(f"Contract missing name field: {contract}")
                    continue
                    
                if vendor_name not in vendors:
                    vendors[vendor_name] = []
                vendors[vendor_name].append(contract)
            
            final_scores = {}
            score_key = f"score_out_of_{max_score * 10}"
            
            for vendor_name, vendor_contracts in vendors.items():
                weighted_sum = 0.0
                total_weight = 0.0
                
                logger.info(f"Processing vendor: {vendor_name} with {len(vendor_contracts)} contracts")
                
                for contract in vendor_contracts:
                    if not isinstance(contract, dict):
                        logger.warning(f"Skipping non-dict contract: {contract}")
                        continue
                        
                    try:
                        score = float(contract.get("score", 0))
                    except (ValueError, TypeError):
                        score = 0.0
                        logger.warning(f"Invalid score for contract {contract.get('name', 'unknown')}: {contract.get('score')}")
                    
                    try:
                        weight = float(contract.get("weight", 0))
                    except (ValueError, TypeError):
                        weight = 0.0
                        logger.warning(f"Invalid weight for contract {contract.get('name', 'unknown')}: {contract.get('weight')}")
                    
                    weighted_sum += score * weight
                    total_weight += weight
                    
                    logger.info(f"  Contract {contract.get('name', 'unknown')}: score={score}, weight={weight}, weighted_sum={weighted_sum}, total_weight={total_weight}")
                
                # Calculate using the same logic as compute_weighted_scores
                if total_weight > 0:
                    raw_score = (weighted_sum / total_weight)
                    percentage = (raw_score / max_score) * 100
                else:
                    raw_score = 0.0
                    percentage = 0.0
                
                # Scale the score to out of 50 or 100 (same as original function)
                scaled_score = round(raw_score * (max_score * 10 / max_score), 2)
                
                logger.info(f"  Final calculation for {vendor_name}: raw_score={raw_score}, percentage={percentage}, scaled_score={scaled_score}")
                
                final_scores[vendor_name] = {
                    score_key: scaled_score,
                    "percentage": round(percentage, 2)
                }
            
            return final_scores

        # Get max_score from the original scoring (you might need to store this in your score_data)
        # For now, let's detect it from existing final scores
        max_score = 5  # default
        if score_data.get("final_scores_openrouter"):
            try:
                sample_score = next(iter(score_data["final_scores_openrouter"].values()))
                if sample_score and "score_out_of_100" in sample_score:
                    max_score = 10
            except (StopIteration, KeyError):
                pass  # Keep default max_score = 5

        # Recalculate final scores
        updated_final_scores_openrouter = {}
        updated_final_scores_chatgpt = {}
        
        logger.info(f"Recalculating final scores with max_score={max_score}")
        
        try:
            if score_data.get("raw_openrouter", {}).get("contracts"):
                contracts = score_data["raw_openrouter"]["contracts"]
                if not isinstance(contracts, list):
                    logger.error(f"raw_openrouter.contracts is not a list: {type(contracts)}")
                    raise ValueError("raw_openrouter.contracts must be a list")
                
                logger.info(f"Recalculating OpenRouter scores for {len(contracts)} contracts")
                updated_final_scores_openrouter = calculate_final_scores(contracts, max_score)
                logger.info(f"OpenRouter final scores: {updated_final_scores_openrouter}")
            
            if score_data.get("raw_chatgpt", {}).get("contracts"):
                contracts = score_data["raw_chatgpt"]["contracts"]
                if not isinstance(contracts, list):
                    logger.error(f"raw_chatgpt.contracts is not a list: {type(contracts)}")
                    raise ValueError("raw_chatgpt.contracts must be a list")
                
                logger.info(f"Recalculating ChatGPT scores for {len(contracts)} contracts")
                updated_final_scores_chatgpt = calculate_final_scores(contracts, max_score)
                logger.info(f"ChatGPT final scores: {updated_final_scores_chatgpt}")
        except Exception as e:
            logger.error(f"Error during final score recalculation: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error recalculating final scores: {e}")

        # Update the score_data with recalculated final scores
        score_data["final_scores_openrouter"] = updated_final_scores_openrouter
        score_data["final_scores_chatgpt"] = updated_final_scores_chatgpt
        
        # Save the updated scores back to the file
        with open(score_file_path, "w") as f:
            json.dump(score_data, f, indent=2)

        result = {
            "raw_openrouter": score_data.get("raw_openrouter"),
            "raw_chatgpt": score_data.get("raw_chatgpt"),
            "final_scores_openrouter": updated_final_scores_openrouter,
            "final_scores_chatgpt": updated_final_scores_chatgpt
        }
        
        logger.info(f"Returning result with final scores: {result}")
        return result

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No scoring data found for this workspace.")
    except Exception as e:
        logger.error(f"Error getting current scores for workspace '{workspace_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting current scores: {e}")

# --- Resume Scoring Endpoints ---

from services.resume_scoring_service import extract_criteria_from_job_description, score_multiple_resumes, get_resume_documents_from_qdrant
from services.parser_service import parse_documents

class ResumeScoringRequest(BaseModel):
    workspace_name: str
    criteria: List[Dict[str, Any]]

class UpdateCriteriaRequest(BaseModel):
    workspace_name: str
    criteria: List[Dict[str, Any]]

@app.post("/upload-resume/{workspace_name}")
async def upload_resume(
    workspace_name: str,
    files: List[UploadFile] = File(...)
):
    """Upload resume PDFs for scoring."""
    save_dir = WORKSPACE_ROOT / workspace_name / "resumes"
    save_dir.mkdir(parents=True, exist_ok=True)

    if active_processing_tasks.get(workspace_name):
        raise HTTPException(status_code=409, detail=f"Processing already in progress for workspace '{workspace_name}'. Please wait.")

    uploaded_file_names = []
    for uploaded_file in files:
        # Allow common document formats
        allowed_extensions = ['.pdf', '.docx', '.doc', '.txt']
        file_extension = Path(uploaded_file.filename).suffix.lower()
        if file_extension not in allowed_extensions:
            raise HTTPException(status_code=400, detail=f"File '{uploaded_file.filename}' has unsupported format. Allowed formats: {', '.join(allowed_extensions)}")
        
        file_path = save_dir / uploaded_file.filename
        try:
            with open(file_path, "wb") as f:
                content = await uploaded_file.read()
                f.write(content)
            uploaded_file_names.append(uploaded_file.filename)
            logger.info(f"Resume file '{uploaded_file.filename}' saved.")
        except Exception as e:
            logger.error(f"Error saving resume file '{uploaded_file.filename}': {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save file: {uploaded_file.filename}")

    # Run the document processing and embedding for resumes
    await process_uploaded_documents_background(workspace_name, "resumes", PROJECT_ROOT)

    return {
        "message": "Resume files uploaded and processed successfully.",
        "files": uploaded_file_names
    }

@app.post("/upload-jd/{workspace_name}")
async def upload_job_description(
    workspace_name: str,
    files: List[UploadFile] = File(...)
):
    """Upload job description PDF and extract criteria."""
    save_dir = WORKSPACE_ROOT / workspace_name / "job_descriptions"
    save_dir.mkdir(parents=True, exist_ok=True)

    if active_processing_tasks.get(workspace_name):
        raise HTTPException(status_code=409, detail=f"Processing already in progress for workspace '{workspace_name}'. Please wait.")

    # Clean up existing job descriptions
    try:
        if save_dir.exists():
            for item in save_dir.iterdir():
                if item.is_file():
                    os.remove(item)
                    logger.info(f"Deleted old job description file: {item.name}")
            logger.info(f"Cleaned up existing job descriptions in '{workspace_name}'.")
    except Exception as e:
        logger.error(f"Error cleaning up old job descriptions for workspace '{workspace_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clean up old job descriptions before upload: {e}")

    uploaded_file_names = []
    
    for uploaded_file in files:
        # Allow common document formats
        allowed_extensions = ['.pdf', '.docx', '.doc', '.txt']
        file_extension = Path(uploaded_file.filename).suffix.lower()
        if file_extension not in allowed_extensions:
            raise HTTPException(status_code=400, detail=f"File '{uploaded_file.filename}' has unsupported format. Allowed formats: {', '.join(allowed_extensions)}")
        
        file_path = save_dir / uploaded_file.filename
        try:
            with open(file_path, "wb") as f:
                content = await uploaded_file.read()
                f.write(content)
            uploaded_file_names.append(uploaded_file.filename)
            logger.info(f"Job description file '{uploaded_file.filename}' saved.")
                
        except Exception as e:
            logger.error(f"Error saving job description file '{uploaded_file.filename}': {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save file: {uploaded_file.filename}")

    # Run the document processing and embedding for job descriptions
    await process_uploaded_documents_background(workspace_name, "job_descriptions", PROJECT_ROOT)

    # Extract criteria from the parsed job description
    criteria = []
    parsed_jd_file = WORKSPACE_ROOT / workspace_name / "parsed_jd.jsonl"
    if parsed_jd_file.exists():
        job_description_text = ""
        with open(parsed_jd_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    doc = json.loads(line)
                    job_description_text += doc.get('text', '') + "\n\n"
        
        if job_description_text.strip():
            try:
                criteria = extract_criteria_from_job_description(job_description_text, workspace_name)
                logger.info(f"Extracted {len(criteria)} criteria from job description.")
                
                # Save criteria to file
                criteria_file = WORKSPACE_ROOT / workspace_name / "resume_criteria.json"
                with open(criteria_file, "w") as f:
                    json.dump(criteria, f, indent=2)
                logger.info(f"Saved criteria to {criteria_file}")
                
            except Exception as e:
                logger.error(f"Error extracting criteria from job description: {e}")
                # Don't raise an exception, just log the error and continue
                # The frontend can still work with default criteria
                logger.warning(f"Using fallback criteria due to extraction error: {e}")
                criteria = []

    return {
        "message": "Job description uploaded, processed, and criteria extracted successfully.",
        "files": uploaded_file_names,
        "criteria": criteria
    }

@app.get("/resume-criteria/{workspace_name}")
async def get_resume_criteria(workspace_name: str):
    """Get the extracted criteria for a workspace."""
    criteria_file = WORKSPACE_ROOT / workspace_name / "resume_criteria.json"
    
    if not criteria_file.exists():
        raise HTTPException(status_code=404, detail="No criteria found for this workspace.")
    
    try:
        with open(criteria_file, "r") as f:
            criteria = json.load(f)
        return {"criteria": criteria}
    except Exception as e:
        logger.error(f"Error reading criteria for workspace '{workspace_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Error reading criteria: {e}")

@app.get("/resume-criteria-raw/{workspace_name}")
async def get_resume_criteria_raw(workspace_name: str):
    """Get the raw LLM response for criteria extraction."""
    raw_response_file = WORKSPACE_ROOT / workspace_name / "raw_criteria_response.json"
    
    if not raw_response_file.exists():
        raise HTTPException(status_code=404, detail="No raw criteria response found for this workspace.")
    
    try:
        with open(raw_response_file, "r") as f:
            raw_data = json.load(f)
        return raw_data
    except Exception as e:
        logger.error(f"Error reading raw criteria response for workspace '{workspace_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Error reading raw criteria response: {e}")

@app.post("/test-criteria-extraction/{workspace_name}")
async def test_criteria_extraction(workspace_name: str):
    """Test criteria extraction from job description manually."""
    parsed_jd_file = WORKSPACE_ROOT / workspace_name / "parsed_jd.jsonl"
    
    if not parsed_jd_file.exists():
        raise HTTPException(status_code=404, detail="No job description found for this workspace.")
    
    try:
        job_description_text = ""
        with open(parsed_jd_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    doc = json.loads(line)
                    job_description_text += doc.get('text', '') + "\n\n"
        
        if not job_description_text.strip():
            raise HTTPException(status_code=404, detail="No job description text found.")
        
        from services.resume_scoring_service import extract_criteria_from_job_description
        criteria = extract_criteria_from_job_description(job_description_text, workspace_name)
        
        return {
            "message": "Criteria extraction test completed",
            "job_description_length": len(job_description_text),
            "extracted_criteria_count": len(criteria),
            "criteria": criteria
        }
        
    except Exception as e:
        logger.error(f"Error testing criteria extraction for workspace '{workspace_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Error testing criteria extraction: {e}")

@app.post("/update-resume-criteria/{workspace_name}")
async def update_resume_criteria(
    workspace_name: str,
    request: UpdateCriteriaRequest
):
    """Update the criteria for resume scoring."""
    workspace_dir = WORKSPACE_ROOT / workspace_name
    criteria_file = workspace_dir / "resume_criteria.json"
    
    try:
        # Ensure workspace directory exists
        workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # Log the request for debugging
        logger.info(f"Updating criteria for workspace '{workspace_name}' with {len(request.criteria)} criteria")
        logger.info(f"Criteria file path: {criteria_file}")
        
        with open(criteria_file, "w") as f:
            json.dump(request.criteria, f, indent=2)
        
        # Verify the file was written correctly
        if criteria_file.exists():
            with open(criteria_file, "r") as f:
                saved_criteria = json.load(f)
            logger.info(f"Verified file contains {len(saved_criteria)} criteria")
        else:
            logger.error(f"File was not created at {criteria_file}")
        
        logger.info(f"Successfully updated criteria for workspace '{workspace_name}'.")
        return {"message": "Criteria updated successfully.", "criteria": request.criteria}
    except Exception as e:
        logger.error(f"Error updating criteria for workspace '{workspace_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Error updating criteria: {e}")

@app.post("/score-resumes/{workspace_name}")
async def score_resumes(workspace_name: str, async_mode: bool = Query(True)):
    """Score all resumes in the workspace against the criteria."""
    logger.info(f"[/score-resumes] Request received for workspace: {workspace_name}, async_mode: {async_mode}")
    
    if async_mode:
        # Enqueue job for async processing
        job_id = job_manager.enqueue_job("score_resumes", {"workspace_name": workspace_name})
        logger.info(f"[/score-resumes] 🔄 Async mode: Job {job_id} queued for workspace '{workspace_name}'")
        return {"job_id": job_id}
    resumes_dir = WORKSPACE_ROOT / workspace_name / "resumes"
    criteria_file = WORKSPACE_ROOT / workspace_name / "resume_criteria.json"
    
    if not resumes_dir.exists():
        raise HTTPException(status_code=404, detail="No resumes found for this workspace.")
    
    if not criteria_file.exists():
        raise HTTPException(status_code=404, detail="No criteria found for this workspace.")
    
    try:
        start_time = time.time()
        
        # Load criteria
        with open(criteria_file, "r") as f:
            criteria = json.load(f)
        
        # Get resume documents from Qdrant embeddings for scoring
        resume_texts = get_resume_documents_from_qdrant(workspace_name)
        
        if not resume_texts:
            raise HTTPException(status_code=404, detail="No resume documents found in Qdrant. Please upload and process resumes first.")
        
        logger.info(f"Retrieved {len(resume_texts)} resume documents from Qdrant")
        
        # Score resumes (uses Qdrant docs for scoring, parsed file for name extraction)
        scoring_results = score_multiple_resumes(workspace_name, criteria)
        
        if not scoring_results.get("resume_scores"):
            raise HTTPException(status_code=404, detail="No valid resumes found to score.")
        
        response_time = time.time() - start_time
        
        logger.info(f"Scored {len(scoring_results.get('resume_scores', []))} resumes for workspace '{workspace_name}' in {response_time:.2f}s.")
        
        # Log metrics
        from datetime import datetime
        metrics_file = WORKSPACE_ROOT / workspace_name / "metrics.json"
        now = datetime.now().isoformat()
        mode = "Score resumes"
        
        new_record = {
            "timestamp": now,
            "mode": mode,
            "response_time": round(response_time, 2)
        }
        metrics = []
        if metrics_file.exists():
            try:
                with open(metrics_file, "r") as f:
                    metrics = json.load(f)
            except Exception:
                logger.warning(f"[/score-resumes] Could not load existing metrics from {metrics_file}, starting new list.")
                metrics = []
        metrics.append(new_record)
        metrics_file.parent.mkdir(parents=True, exist_ok=True)
        with open(metrics_file, "w") as f:
            json.dump(metrics, f, indent=2)
        logger.info(f"[/score-resumes] Logged response time ({response_time:.2f}s) for '{mode}' to {metrics_file}")
        
        # Save results
        results_file = WORKSPACE_ROOT / workspace_name / "resume_scores.json"
        with open(results_file, "w") as f:
            json.dump(scoring_results, f, indent=2)
        
        return scoring_results
        
    except Exception as e:
        logger.error(f"Error scoring resumes for workspace '{workspace_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Error scoring resumes: {e}")

@app.get("/resume-scores/{workspace_name}")
async def get_resume_scores(workspace_name: str):
    """Get the scoring results for resumes in a workspace."""
    results_file = WORKSPACE_ROOT / workspace_name / "resume_scores.json"
    
    if not results_file.exists():
        raise HTTPException(status_code=404, detail="No scoring results found for this workspace.")
    
    try:
        with open(results_file, "r") as f:
            results = json.load(f)
        return results
    except Exception as e:
        logger.error(f"Error reading resume scores for workspace '{workspace_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Error reading resume scores: {e}")

@app.get("/resume-files/{workspace_name}")
async def get_resume_files(workspace_name: str):
    """Get list of uploaded resume files for a workspace."""
    resumes_dir = WORKSPACE_ROOT / workspace_name / "resumes"
    
    if not resumes_dir.exists():
        return {"resumes": []}
    
    try:
        # Get all supported file formats
        resume_files = []
        for extension in ['.pdf', '.docx', '.doc', '.txt']:
            resume_files.extend([f.stem for f in resumes_dir.glob(f"*{extension}")])
        return {"resumes": resume_files}
    except Exception as e:
        logger.error(f"Error getting resume files for workspace '{workspace_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Error getting resume files: {e}")

@app.get("/jd-files/{workspace_name}")
async def get_jd_files(workspace_name: str):
    """Get list of uploaded job description files for a workspace."""
    jd_dir = WORKSPACE_ROOT / workspace_name / "job_descriptions"
    
    if not jd_dir.exists():
        return {"job_descriptions": []}
    
    try:
        # Get all supported file formats
        jd_files = []
        for extension in ['.pdf', '.docx', '.doc', '.txt']:
            jd_files.extend([f.stem for f in jd_dir.glob(f"*{extension}")])
        return {"job_descriptions": jd_files}
    except Exception as e:
        logger.error(f"Error getting job description files for workspace '{workspace_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Error getting job description files: {e}")

class SaveResumeScoresRequest(BaseModel):
    resume_scores: List[Dict[str, Any]]
    summary: Dict[str, Any]

class SendResumeEmailRequest(BaseModel):
    recipient_email: str
    subject: str = "Resume Scoring Results"
    message: str = "Please find attached the resume scoring results."

class SendVendorEmailRequest(BaseModel):
    recipient_email: str
    subject: str = "Vendor Recommendations"
    message: str = "Please find attached the vendor recommendations report."


@app.post("/save-resume-scores/{workspace_name}")
async def save_resume_scores(workspace_name: str, request: SaveResumeScoresRequest):
    """Save edited resume scoring results."""
    results_file = WORKSPACE_ROOT / workspace_name / "resume_scores.json"
    
    try:
        # Ensure workspace directory exists
        results_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create the complete results structure
        updated_results = {
            "resume_scores": request.resume_scores,
            "summary": request.summary
        }
        
        # Save to file
        with open(results_file, "w") as f:
            json.dump(updated_results, f, indent=2)
        
        logger.info(f"Edited resume scores saved to {results_file}")
        return {"message": "Resume scores saved successfully!"}
        
    except Exception as e:
        logger.error(f"Error saving resume scores for workspace '{workspace_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Error saving resume scores: {e}")

@app.get("/resume-citation/{workspace_name}")
async def get_resume_citation(
    workspace_name: str, 
    resume_name: str, 
    criterion_name: str
):
    """Get citation data for a specific resume scoring cell."""
    try:
        # Get the scoring results to find the rationale
        results_file = WORKSPACE_ROOT / workspace_name / "resume_scores.json"
        
        if not results_file.exists():
            raise HTTPException(status_code=404, detail="No scoring results found for this workspace.")
        
        with open(results_file, "r") as f:
            scoring_results = json.load(f)
        
        # Find the specific resume and criterion
        resume_data = None
        for resume in scoring_results.get("resume_scores", []):
            if resume.get("resume_name") == resume_name:
                resume_data = resume
                break
        
        if not resume_data:
            raise HTTPException(status_code=404, detail=f"Resume '{resume_name}' not found in scoring results.")
        
        # Get the original filename from the resume data
        original_filename = resume_data.get("original_filename", resume_name)
        
        # Find the specific criterion score
        criterion_score = None
        for score in resume_data.get("criteria_scores", []):
            if score.get("criterion") == criterion_name:
                criterion_score = score
                break
        
        if not criterion_score:
            raise HTTPException(status_code=404, detail=f"Criterion '{criterion_name}' not found for resume '{resume_name}'.")
        
        # Get the original resume text from Qdrant
        from services.resume_scoring_service import get_resume_documents_from_qdrant
        resume_texts = get_resume_documents_from_qdrant(workspace_name)
        
        # Find the resume text for this specific resume
        # Try exact match first, then try to find by partial match
        resume_text = resume_texts.get(resume_name, "")
        if not resume_text:
            # Try to find by partial match (case insensitive)
            for key, text in resume_texts.items():
                if resume_name.lower() in key.lower() or key.lower() in resume_name.lower():
                    resume_text = text
                    break
        
        # Extract relevant text chunks that support the rationale
        # This approach finds ONLY the exact text that directly supports the rationale
        relevant_chunks = []
        if resume_text and criterion_score.get("rationale"):
            import re
            
            rationale = criterion_score.get("rationale", "")
            
            # Extract ONLY the most specific, factual information from the rationale
            # These are the exact phrases that should appear in the resume
            exact_phrases = []
            
            # Extract years of experience FIRST (e.g., "22+ years", "10+ years") - HIGHEST PRIORITY
            years_pattern = re.findall(r'\b\d+\+?\s*(?:years?|yrs?)\b', rationale, re.IGNORECASE)
            exact_phrases.extend(years_pattern)
            
            # Extract specific numbers and percentages SECOND
            numbers_pattern = re.findall(r'\b\d+(?:\.\d+)?(?:%|percent)?\b', rationale)
            exact_phrases.extend(numbers_pattern)
            
            # Extract specific numbers and percentages
            numbers_pattern = re.findall(r'\b\d+(?:\.\d+)?(?:%|percent)?\b', rationale)
            exact_phrases.extend(numbers_pattern)
            
            # Now find EXACT matches in the resume text
            resume_lower = resume_text.lower()
            for phrase in exact_phrases:
                if len(phrase.strip()) > 2:  # Only consider meaningful phrases
                    phrase_lower = phrase.lower().strip()
                    
                    # Look for EXACT matches only
                    if phrase_lower in resume_lower:
                        # Find the exact text in the original resume (preserving case)
                        sentences = re.split(r'[.!?]+', resume_text)
                        for sentence in sentences:
                            sentence_lower = sentence.lower()
                            if phrase_lower in sentence_lower:
                                # Find the exact position of the phrase
                                start_idx = sentence_lower.find(phrase_lower)
                                if start_idx != -1:
                                    # Extract ONLY the exact phrase from the original sentence - NO CONTEXT
                                    exact_text = sentence[start_idx:start_idx + len(phrase)]
                                    
                                    # Only add the exact phrase, no context
                                    if exact_text not in relevant_chunks and len(exact_text) > 2:
                                        relevant_chunks.append(exact_text)
                                        break  # Only add the first occurrence
                        
                        # If we found a match, prioritize it and don't look for other phrases
                        if relevant_chunks:
                            break
            
            # If no exact matches found, try to find the most specific terms
            if not relevant_chunks:
                # Extract individual words that are likely to be specific (CamelCase and acronyms)
                specific_words = re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)*\b', rationale)  # CamelCase words
                specific_words.extend(re.findall(r'\b[A-Z]{2,}\b', rationale))  # Acronyms
                
                for word in specific_words:
                    if len(word) > 3 and word.lower() in resume_lower:
                        # Find sentences containing this specific word
                        sentences = re.split(r'[.!?]+', resume_text)
                        for sentence in sentences:
                            if word.lower() in sentence.lower():
                                # Extract just the word with minimal context
                                sentence_lower = sentence.lower()
                                start_idx = sentence_lower.find(word.lower())
                                if start_idx != -1:
                                    context_start = max(0, start_idx - 10)
                                    context_end = min(len(sentence), start_idx + len(word) + 10)
                                    context = sentence[context_start:context_end].strip()
                                    
                                    if context not in relevant_chunks and len(context) > 5:
                                        relevant_chunks.append(context)
                                        break
            
            # Limit to maximum 2 chunks to keep highlighting very precise
            relevant_chunks = relevant_chunks[:2]
            
            # Debug: If we still don't have the key information, try a simpler approach
            if not relevant_chunks and "22+" in rationale:
                # Look specifically for "22+" in the resume
                if "22+" in resume_text:
                    # Find the exact "22+" text
                    start_idx = resume_text.find("22+")
                    if start_idx != -1:
                        # Extract just "22+" or "22+ years"
                        end_idx = start_idx + 3
                        if start_idx + 10 < len(resume_text):
                            next_text = resume_text[start_idx:start_idx + 10].lower()
                            if "years" in next_text:
                                end_idx = start_idx + next_text.find("years") + 5
                        exact_text = resume_text[start_idx:end_idx]
                        relevant_chunks.append(exact_text)
        
        # Map original filename to actual PDF filename
        def find_pdf_filename(original_filename):
            resumes_dir = WORKSPACE_ROOT / workspace_name / "resumes"
            if not resumes_dir.exists():
                return None
            
            # Try to find PDF file that matches the original filename
            for pdf_file in resumes_dir.glob("*.pdf"):
                filename_stem = pdf_file.stem
                original_stem = original_filename
                
                # Check if the original filename matches the PDF filename
                if filename_stem == original_stem:
                    return pdf_file.name
            
            return None
        
        pdf_filename = find_pdf_filename(original_filename)
        
        return {
            "resume_name": resume_name,
            "criterion_name": criterion_name,
            "rationale": criterion_score.get("rationale", ""),
            "score": criterion_score.get("score", 0),
            "relevant_chunks": relevant_chunks,
            "full_resume_text": resume_text,
            "pdf_filename": pdf_filename,
            "original_filename": original_filename
        }
        
    except Exception as e:
        logger.error(f"Error getting citation for workspace '{workspace_name}', resume '{resume_name}', criterion '{criterion_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Error getting citation: {e}")

@app.post("/send-resume-email/{workspace_name}")
async def send_resume_email(workspace_name: str, request: SendResumeEmailRequest):
    """Send resume scoring results via email with Excel attachment."""
    try:
        # Get the scoring results
        results_file = WORKSPACE_ROOT / workspace_name / "resume_scores.json"
        
        if not results_file.exists():
            raise HTTPException(status_code=404, detail="No scoring results found for this workspace.")
        
        with open(results_file, "r") as f:
            scoring_results = json.load(f)
        
        # Generate Excel file with proper filename
        import os
        
        # Create Excel file with proper filename in workspace directory
        excel_filename = f"{workspace_name}_resume_scoring_results.xlsx"
        excel_file_path = str(WORKSPACE_ROOT / workspace_name / excel_filename)
        
        # Create workbook and add worksheets
        workbook = xlsxwriter.Workbook(excel_file_path)
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'bg_color': '#4F81BD',
            'font_color': 'white',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        cell_format = workbook.add_format({
            'font_size': 10,
            'align': 'left',
            'valign': 'top',
            'border': 1,
            'text_wrap': True
        })
        
        score_format = workbook.add_format({
            'font_size': 10,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'bold': True
        })
        
        # Create scoring results worksheet
        scoring_sheet = workbook.add_worksheet('Scoring Results')
        
        # Write headers
        headers = ['Candidate Name', 'Overall Score', 'Overall Rationale']
        if scoring_results.get('resume_scores') and len(scoring_results['resume_scores']) > 0:
            for criterion in scoring_results['resume_scores'][0].get('criteria_scores', []):
                headers.append(f"{criterion['criterion']} Score (Weight: {criterion['weight']})")
                headers.append(f"{criterion['criterion']} Rationale")
        
        for col, header in enumerate(headers):
            scoring_sheet.write(0, col, header, header_format)
        
        # Write data
        for row, resume in enumerate(scoring_results.get('resume_scores', []), 1):
            col = 0
            scoring_sheet.write(row, col, resume['resume_name'], cell_format)
            col += 1
            scoring_sheet.write(row, col, f"{(resume['overall_score'] * 10):.1f}%", score_format)
            col += 1
            scoring_sheet.write(row, col, resume.get('overall_rationale', 'N/A'), cell_format)
            col += 1
            
            # Write criteria scores in the same order as headers
            if scoring_results.get('resume_scores') and len(scoring_results['resume_scores']) > 0:
                for criterion in scoring_results['resume_scores'][0].get('criteria_scores', []):
                    # Find the matching criterion score for this resume
                    criterion_score = next(
                        (cs for cs in resume.get('criteria_scores', []) 
                         if cs['criterion'] == criterion['criterion']), 
                        None
                    )
                    
                    if criterion_score:
                        scoring_sheet.write(row, col, criterion_score['score'], score_format)
                        col += 1
                        scoring_sheet.write(row, col, criterion_score.get('rationale', 'N/A'), cell_format)
                        col += 1
                    else:
                        # If criterion not found for this resume, write N/A
                        scoring_sheet.write(row, col, 'N/A', score_format)
                        col += 1
                        scoring_sheet.write(row, col, 'N/A', cell_format)
                        col += 1
        
        # Set column widths
        scoring_sheet.set_column(0, 0, 25)  # Candidate Name
        scoring_sheet.set_column(1, 1, 15)  # Overall Score
        scoring_sheet.set_column(2, 2, 50)  # Overall Rationale
        
        # Set widths for criteria columns
        for i in range(3, len(headers)):
            if i % 2 == 1:  # Score columns
                scoring_sheet.set_column(i, i, 20)
            else:  # Rationale columns
                scoring_sheet.set_column(i, i, 40)
        
        # Create summary worksheet
        summary_sheet = workbook.add_worksheet('Summary')
        
        summary = scoring_results.get('summary', {})
        summary_data = [
            ['Resume Scoring Summary', ''],
            ['', ''],
            ['Total Resumes', summary.get('total_resumes', 0)],
            ['Average Score', f"{(summary.get('average_score', 0) * 10):.1f}%"],
            ['Highest Score', f"{(summary.get('highest_score', 0) * 10):.1f}%"],
            ['Lowest Score', f"{(summary.get('lowest_score', 0) * 10):.1f}%"],
            ['Best Resume', summary.get('best_resume', 'N/A')]
        ]
        
        # Add best resume bullets if available
        if summary.get('best_resume_bullets'):
            summary_data.append(['', ''])
            summary_data.append(['Why Best Resume Was Selected:', ''])
            for bullet in summary['best_resume_bullets']:
                summary_data.append(['', bullet])
        
        for row, (label, value) in enumerate(summary_data):
            summary_sheet.write(row, 0, label, header_format if row < 2 else cell_format)
            summary_sheet.write(row, 1, value, cell_format)
        
        summary_sheet.set_column(0, 0, 30)
        summary_sheet.set_column(1, 1, 20)
        
        workbook.close()
        
        # Send email with attachment
        html_content = f"""
        <html><body style='font-family: Arial;'>
            <h3 style='color:#2b78e4;'>📊 Resume Scoring Results</h3>
            <p>Hello,</p>
            <p>{request.message}</p>
            <p><strong>Workspace:</strong> {workspace_name}</p>
            <p><strong>Total Resumes Scored:</strong> {len(scoring_results.get('resume_scores', []))}</p>
            <p><strong>Average Score:</strong> {(summary.get('average_score', 0) * 10):.1f}%</p>
            <p><strong>Best Resume:</strong> {summary.get('best_resume', 'N/A')}</p>
            <br>
            <p>Please find the detailed scoring results attached as an Excel file.</p>
            <br>
            <p>Best regards,<br>Allyin Compass</p>
        </body></html>
        """
        
        send_email(
            subject=request.subject,
            html_content=html_content,
            to=request.recipient_email,
            attachments=[excel_file_path]
        )
        
        logger.info(f"Resume scoring results sent via email to {request.recipient_email}")
        return {"message": "Email sent successfully!"}
        
    except Exception as e:
        logger.error(f"Error sending resume email for workspace '{workspace_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Error sending email: {e}")

@app.post("/send-vendor-email/{workspace_name}")
async def send_vendor_email(workspace_name: str, request: SendVendorEmailRequest):
    """Send vendor recommendations via email with PDF attachment."""
    try:
        # Get the vendor recommendations
        results_file = WORKSPACE_ROOT / workspace_name / "vendor_recommendations.json"
        
        if not results_file.exists():
            raise HTTPException(status_code=404, detail="No vendor recommendations found for this workspace.")
        
        with open(results_file, "r") as f:
            vendor_results = json.load(f)
        
        # Generate PDF file with proper filename
        import os
        
        # Create PDF file with proper filename in workspace directory
        pdf_filename = f"{workspace_name}_vendor_recommendations.pdf"
        pdf_file_path = str(WORKSPACE_ROOT / workspace_name / pdf_filename)
        
        # For now, we'll create a simple text-based PDF
        # In a production environment, you might want to use a proper PDF library like reportlab
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib import colors
            
            # Create the PDF document
            doc = SimpleDocTemplate(pdf_file_path, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=30,
                alignment=1  # Center alignment
            )
            story.append(Paragraph("Vendor Recommendations Report", title_style))
            story.append(Spacer(1, 12))
            
            # Project Summary
            story.append(Paragraph("Project Summary", styles['Heading2']))
            story.append(Spacer(1, 6))
            story.append(Paragraph(vendor_results.get('summary', 'No summary available.'), styles['Normal']))
            story.append(Spacer(1, 12))
            
            # Vendor Recommendations
            story.append(Paragraph("Vendor Recommendations", styles['Heading2']))
            story.append(Spacer(1, 6))
            
            for i, vendor in enumerate(vendor_results.get('recommendations', []), 1):
                # Vendor header
                vendor_header = f"{i}. {vendor['vendor_name']} (Score: {vendor['recommendation_score']}/10)"
                story.append(Paragraph(vendor_header, styles['Heading3']))
                story.append(Spacer(1, 6))
                
                # Vendor details table
                vendor_data = [
                    ['Company Size:', vendor['company_size']],
                    ['Specialization:', vendor['specialization']],
                    ['Experience:', vendor['experience']],
                    ['Location:', vendor['location']]
                ]
                
                vendor_table = Table(vendor_data, colWidths=[2*inch, 4*inch])
                vendor_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.grey),
                    ('TEXTCOLOR', (0, 0), (0, -1), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                    ('BACKGROUND', (1, 0), (1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(vendor_table)
                story.append(Spacer(1, 6))
                
                # Strengths
                story.append(Paragraph("Strengths:", styles['Heading4']))
                strengths_text = ""
                for strength in vendor.get('strengths', []):
                    strengths_text += f"• {strength}<br/>"
                story.append(Paragraph(strengths_text, styles['Normal']))
                story.append(Spacer(1, 6))
                
                # Risk Factors
                story.append(Paragraph("Risk Factors:", styles['Heading4']))
                risks_text = ""
                for risk in vendor.get('risk_factors', []):
                    risks_text += f"• {risk}<br/>"
                story.append(Paragraph(risks_text, styles['Normal']))
                story.append(Spacer(1, 6))
                
                # Rationale
                story.append(Paragraph("Why Recommended:", styles['Heading4']))
                story.append(Paragraph(vendor.get('rationale', 'No rationale provided.'), styles['Normal']))
                story.append(Spacer(1, 12))
            
            # Build the PDF
            doc.build(story)
            
        except ImportError:
            # Fallback: create a simple text file if reportlab is not available
            with open(pdf_file_path.replace('.pdf', '.txt'), 'w') as f:
                f.write("Vendor Recommendations Report\n")
                f.write("=" * 50 + "\n\n")
                f.write("Project Summary:\n")
                f.write(vendor_results.get('summary', 'No summary available.') + "\n\n")
                f.write("Vendor Recommendations:\n")
                f.write("=" * 30 + "\n\n")
                
                for i, vendor in enumerate(vendor_results.get('recommendations', []), 1):
                    f.write(f"{i}. {vendor['vendor_name']} (Score: {vendor['recommendation_score']}/10)\n")
                    f.write(f"   Company Size: {vendor['company_size']}\n")
                    f.write(f"   Specialization: {vendor['specialization']}\n")
                    f.write(f"   Experience: {vendor['experience']}\n")
                    f.write(f"   Location: {vendor['location']}\n")
                    f.write(f"   Strengths: {', '.join(vendor.get('strengths', []))}\n")
                    f.write(f"   Risk Factors: {', '.join(vendor.get('risk_factors', []))}\n")
                    f.write(f"   Why Recommended: {vendor.get('rationale', 'No rationale provided.')}\n\n")
            
            # Use the text file as the attachment
            pdf_file_path = pdf_file_path.replace('.pdf', '.txt')
        
        # Send email with attachment
        html_content = f"""
        <html><body style='font-family: Arial;'>
            <h3 style='color:#2b78e4;'>🏢 Vendor Recommendations</h3>
            <p>Hello,</p>
            <p>{request.message}</p>
            <p><strong>Workspace:</strong> {workspace_name}</p>
            <p><strong>Total Vendors Recommended:</strong> {len(vendor_results.get('recommendations', []))}</p>
            <p><strong>Project Summary:</strong> {vendor_results.get('summary', 'N/A')[:100]}...</p>
            <br>
            <p>Please find the detailed vendor recommendations attached.</p>
            <br>
            <p>Best regards,<br>Allyin Compass</p>
        </body></html>
        """
        
        send_email(
            subject=request.subject,
            html_content=html_content,
            to=request.recipient_email,
            attachments=[pdf_file_path]
        )
        
        logger.info(f"Vendor recommendations sent via email to {request.recipient_email}")
        return {"message": "Email sent successfully!"}
        
    except Exception as e:
        logger.error(f"Error sending vendor email for workspace '{workspace_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Error sending email: {e}")

# Vendor Recommendation Routes
@app.post("/vendor-recommendations")
async def get_vendor_recommendations(request: VendorRecommendationRequest, async_mode: bool = Query(True)):
    """
    Generate vendor recommendations based on project requirements using Perplexity.
    """
    logger.info(f"[/vendor-recommendations] Request received, async_mode: {async_mode}")
    
    if async_mode:
        # Enqueue job for async processing
        job_id = job_manager.enqueue_job("vendor_recommendations", request.dict())
        logger.info(f"[/vendor-recommendations] 🔄 Async mode: Job {job_id} queued")
        return {"job_id": job_id}
    
    try:
        logger.info(f"Generating vendor recommendations for project: {request.project_requirements[:100]}...")
        
        result = generate_enhanced_vendor_recommendations(
            project_requirements=request.project_requirements,
            industry=request.industry,
            location_preference=request.location_preference,
            vendor_count=request.vendor_count,
            workspace_name=request.workspace_name,
            preference=request.preference,
            vendor_type=request.vendor_type,
            enable_reddit_analysis=request.enable_reddit_analysis,
            enable_linkedin_analysis=request.enable_linkedin_analysis,
            enable_google_reviews=request.enable_google_reviews
        )
        
        if result["success"]:
            return {
                "summary": result["data"]["summary"],
                "recommendations": result["data"]["recommendations"],
                "alternate_vendors": result["data"].get("alternate_vendors", []),
                "citations": result["citations"],
                "enhancement_metadata": result.get("enhancement_metadata", {})
            }
        else:
            raise HTTPException(status_code=500, detail=result["error"])
            
    except Exception as e:
        logger.error(f"Error in vendor recommendations endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating vendor recommendations: {e}")


@app.post("/vendor-research")
async def research_vendor(request: VendorResearchRequest, async_mode: bool = Query(True)):
    """
    Research a specific vendor using external data sources for comprehensive analysis.
    """
    logger.info(f"[/vendor-research] Request received for vendor: {request.vendor_name}, async_mode: {async_mode}")
    
    if async_mode:
        # Enqueue job for async processing
        job_id = job_manager.enqueue_job("vendor_research", request.dict())
        logger.info(f"[/vendor-research] 🔄 Async mode: Job {job_id} queued for vendor '{request.vendor_name}'")
        return {"job_id": job_id}
    
    try:
        logger.info(f"Researching vendor: {request.vendor_name} in {request.location}")
        
        research_service = VendorResearchService()
        result = research_service.research_vendor(
            vendor_name=request.vendor_name,
            location=request.location,
            workspace_name=request.workspace_name,
            enable_reddit_analysis=request.enable_reddit_analysis,
            enable_linkedin_analysis=request.enable_linkedin_analysis,
            enable_google_reviews=request.enable_google_reviews
        )
        
        if result["success"]:
            return result["data"]
        else:
            raise HTTPException(status_code=500, detail=result["error"])
            
    except Exception as e:
        logger.error(f"Error in vendor research endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Error researching vendor: {e}")


@app.post("/vendor-comparison")
async def compare_vendors(request: VendorComparisonRequest, async_mode: bool = Query(True)):
    """
    Compare multiple vendors based on LLM-generated criteria.
    """
    logger.info(f"[/vendor-comparison] Request received for {len(request.vendors)} vendors, async_mode: {async_mode}")
    
    if async_mode:
        # Enqueue job for async processing
        job_id = job_manager.enqueue_job("vendor_comparison", request.dict())
        logger.info(f"[/vendor-comparison] 🔄 Async mode: Job {job_id} queued")
        return {"job_id": job_id}
    
    try:
        logger.info(f"Comparing {len(request.vendors)} vendors: {[v['name'] for v in request.vendors]}")
        
        comparison_service = VendorComparisonService()
        result = comparison_service.compare_vendors(
            vendors=request.vendors,
            workspace_name=request.workspace_name
        )
        
        if result["success"]:
            return {
                "vendors": result["vendors"],
                "criteria": result["criteria"],
                "criteria_comparison": result["comparison_results"]["criteria_comparison"],
                "best_vendor": result["comparison_results"]["best_vendor"],
                "metadata": result["metadata"]
            }
        else:
            raise HTTPException(status_code=500, detail=result["error"])
            
    except Exception as e:
        logger.error(f"Error in vendor comparison endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Error comparing vendors: {e}")


@app.post("/submit-lead-interest")
async def submit_lead_interest(request: LeadInterestRequest):
    """
    Submit lead interest for a vendor and send email notification.
    """
    try:
        logger.info(f"Received lead interest request: {request}")
        logger.info(f"Submitting lead interest for vendor: {request.vendor_name} from user: {request.user_email}")
        
        # Create email content
        subject = f"New Lead Interest: {request.vendor_name}"
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #2b78e4;">New Vendor Lead Interest</h2>
            
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #28a745; margin-top: 0;">Lead Details</h3>
                <p><strong>Interested User Name:</strong> {request.user_name}</p>
                <p><strong>Interested User Email:</strong> {request.user_email}</p>
                <p><strong>Vendor Name:</strong> {request.vendor_name}</p>
                <p><strong>Vendor Score:</strong> {request.vendor_score}/10</p>
            </div>
            
            <div style="background-color: #fff3cd; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #856404; margin-top: 0;">Project Requirements</h3>
                <p style="white-space: pre-wrap;">{request.project_requirements}</p>
            </div>
            
            <div style="background-color: #e3f2fd; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #1976d2; margin-top: 0;">Project Specifications</h3>
                <p><strong>Industry:</strong> {request.industry or 'Not specified'}</p>
                <p><strong>Location Preference:</strong> {request.location_preference or 'Not specified'}</p>
            </div>
            
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd;">
                <p style="color: #666; font-size: 14px;">
                    This lead was generated from the AqeedAI Vendor Recommendation system.
                    <br>Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                </p>
            </div>
        </body>
        </html>
        """
        
        # Send email to the hardcoded recipient
        recipient_email = "niraj@allyin.ai"  # Hardcoded email address
        send_email(
            subject=subject,
            html_content=html_content,
            to=recipient_email
        )
        
        logger.info(f"Lead interest email sent successfully to {recipient_email}")
        
        return {
            "success": True,
            "message": "Lead interest submitted successfully",
            "vendor_name": request.vendor_name,
            "user_email": request.user_email
        }
        
    except Exception as e:
        logger.error(f"Error submitting lead interest: {e}")
        raise HTTPException(status_code=500, detail=f"Error submitting lead interest: {e}")


@app.post("/gdrive/import")
async def import_from_google_drive(request: Request, background_tasks: BackgroundTasks):
    """Import selected Google Drive files into the workspace's per-type folder.
    Accepts JSON or form data with: workspace_name, file_ids (list or CSV), file_type.
    """
    try:

        ctype = (request.headers.get('content-type') or '').lower()
        if 'application/json' in ctype:
            payload = await request.json()
        else:
            form = await request.form()
            payload = {k: form.get(k) for k in form.keys()}

        workspace = payload.get('workspace_name') or payload.get('workspace')
        raw_ids = payload.get('file_ids') or payload.get('files') or []

        # Normalize file_ids to a list[str]
        if isinstance(raw_ids, list):
            file_ids = [str(x) for x in raw_ids if x]
        elif isinstance(raw_ids, str):
            import json as _json
            try:
                parsed = _json.loads(raw_ids)
                if isinstance(parsed, list):
                    file_ids = [str(x) for x in parsed if x]
                elif isinstance(parsed, str):
                    file_ids = [parsed] if parsed else []
                else:
                    file_ids = [raw_ids] if raw_ids else []
            except Exception:
                # CSV or single id
                file_ids = [s.strip() for s in raw_ids.split(',') if s.strip()]
        else:
            file_ids = [str(raw_ids)] if raw_ids else []

        raw_file_type = (payload.get('file_type') or 'documents').strip()

# Normalize and map to canonical server-side folder names
        norm = raw_file_type.lower().replace(' ', '_').replace('-', '_')
        FILETYPE_MAP = {
            # Contracts / documents
            'documents': 'contracts',
            'document': 'contracts',
            'contract_documents': 'contracts',
            'contracts': 'contracts',
            'contract': 'contracts',


            # Criteria
            'criteria': 'criteria_weights',
            'criterias': 'criteria_weights',
            'criteria_weight': 'criteria_weights',
            'criteria_weights': 'criteria_weights',

            # Resumes
            'resume': 'resumes',
            'resumes': 'resumes',

            # Job descriptions
            'job_description': 'job_descriptions',
            'job_descriptions': 'job_descriptions',

            # Technical reports (and common misspellings)
            'technical_report': 'technical_reports',
            'technical_reports': 'technical_reports',
            'techincal_report': 'technical_reports',
            'techincal_reports': 'technical_reports',

            # Financial reports (and common misspellings)
            'financial_report': 'financial_reports',
            'financial_reports': 'financial_reports',
            'finacial_report': 'financial_reports',
            'finacial_reports': 'financial_reports',
        }
        file_type = FILETYPE_MAP.get(norm, norm)

        if not workspace or not file_ids:
            raise HTTPException(status_code=400, detail='workspace_name and file_ids are required')

        # Mirror local uploads: <WORKSPACE_ROOT>/<workspace>/<file_type>/
        dest_dir = str((WORKSPACE_ROOT / workspace / file_type).resolve())
        logger.info(f"[gdrive import] workspace={workspace} file_type={file_type} -> saving {len(file_ids)} file(s) to {dest_dir}")


        gsvc = GoogleDriveService(workspace_name=workspace)
        saved = gsvc.download_files_to(file_ids, dest_dir)

        # After downloading, trigger the same processing as local uploads
        if saved:
            logger.info(f"[gdrive import] Triggering background processing for {len(saved)} files in {file_type}")
            
            if file_type == "criteria_weights":
                # Criteria uses a different processing function
                background_tasks.add_task(process_uploaded_criteria_background, workspace, "criteria", PROJECT_ROOT)
            elif file_type in ["contracts", "resumes", "job_descriptions"]:
                # Map file_type to the expected format for process_uploaded_documents_background
                processing_file_type = {
                    "contracts": "documents",
                    "resumes": "resumes", 
                    "job_descriptions": "job_descriptions"
                }.get(file_type, "documents")
                
                # Trigger background processing
                background_tasks.add_task(process_uploaded_documents_background, workspace, processing_file_type, PROJECT_ROOT)
                
                # For job descriptions, also extract criteria after processing
                if file_type == "job_descriptions":
                    background_tasks.add_task(extract_criteria_from_gdrive_jd, workspace)

        return {"message": f"Imported {len(saved)} file(s) to {file_type} and triggered processing", "saved": saved}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[gdrive import] failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to import from Google Drive: {e}")

async def extract_criteria_from_gdrive_jd(workspace_name: str):
    """Extract criteria from job description imported from Google Drive."""
    try:
        logger.info(f"[gdrive jd] Starting criteria extraction for workspace: {workspace_name}")
        active_criteria_extraction_tasks[workspace_name] = True
        
        # Wait a bit for the parsing to complete
        await asyncio.sleep(2)
        
        # Extract criteria from the parsed job description
        criteria = []
        parsed_jd_file = WORKSPACE_ROOT / workspace_name / "parsed_jd.jsonl"
        
        if parsed_jd_file.exists():
            job_description_text = ""
            with open(parsed_jd_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        doc = json.loads(line)
                        job_description_text += doc.get('text', '') + "\n\n"
            
            if job_description_text.strip():
                try:
                    from services.resume_scoring_service import extract_criteria_from_job_description
                    criteria = extract_criteria_from_job_description(job_description_text, workspace_name)
                    logger.info(f"[gdrive jd] Extracted {len(criteria)} criteria from job description.")
                    
                    # Save criteria to file
                    criteria_file = WORKSPACE_ROOT / workspace_name / "resume_criteria.json"
                    with open(criteria_file, "w") as f:
                        json.dump(criteria, f, indent=2)
                    logger.info(f"[gdrive jd] Saved criteria to {criteria_file}")
                    
                except Exception as e:
                    logger.error(f"[gdrive jd] Error extracting criteria from job description: {e}")
                    criteria = []
        else:
            logger.warning(f"[gdrive jd] Parsed JD file not found: {parsed_jd_file}")
            
    except Exception as e:
        logger.error(f"[gdrive jd] Failed to extract criteria: {e}", exc_info=True)
    finally:
        if workspace_name in active_criteria_extraction_tasks:
            del active_criteria_extraction_tasks[workspace_name]
        logger.info(f"[gdrive jd] Criteria extraction completed for workspace: {workspace_name}")

@app.post("/upload/gdrive/{workspace_name}")
async def upload_google_drive(workspace_name: str, request: GoogleDriveRequest, background_tasks: BackgroundTasks):
    """Import files from Google Drive"""
    if not check_access():
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Use the service from the in-memory store
    gdrive_service = workspace_gdrive_services.get(workspace_name)
    if gdrive_service is None:
        raise HTTPException(status_code=503, detail="Google Drive service not available for this workspace.")
    
    try:
        workspace_path = WORKSPACE_ROOT / workspace_name
        if not workspace_path.exists():
            raise HTTPException(status_code=404, detail="Workspace not found")
        
        # Create gdrive directory (or use a specific file type dir)
        # Assuming for now it goes into the 'contracts' directory for processing
        documents_path = workspace_path / "contracts"
        documents_path.mkdir(exist_ok=True)
        
        if not gdrive_service.is_authenticated():
            raise HTTPException(status_code=401, detail="Google Drive not authenticated. Please authenticate first.")
        
        downloaded_files = []
        failed_files = []
        
        for file_id in request.file_ids:
            try:
                file_info = gdrive_service.get_file_info(file_id)
                if not file_info:
                    failed_files.append({"file_id": file_id, "error": "File not found"})
                    continue
                
                if gdrive_service.download_file(file_id, documents_path):
                    downloaded_files.append({
                        "file_id": file_id,
                        "name": file_info.get('name', 'unknown'),
                        "mime_type": file_info.get('mimeType', 'unknown')
                    })
                else:
                    failed_files.append({"file_id": file_id, "error": "Download failed"})
                    
            except Exception as e:
                logger.error(f"Error downloading file {file_id}: {e}")
                failed_files.append({"file_id": file_id, "error": str(e)})
        
        if downloaded_files:
            background_tasks.add_task(process_uploaded_documents_background, workspace_name, "documents", PROJECT_ROOT)
        
        return {
            "message": f"Successfully downloaded {len(downloaded_files)} files from Google Drive",
            "downloaded_files": downloaded_files,
            "failed_files": failed_files,
            "total_requested": len(request.file_ids),
            "total_downloaded": len(downloaded_files)
        }
        
    except Exception as e:
        logger.error(f"Error processing Google Drive request: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process Google Drive request: {str(e)}")


@app.get("/gdrive/auth-url/{workspace_name}")
async def get_google_drive_auth_url(workspace_name: str):
    """Get Google Drive authorization URL for a workspace"""
    if not check_access():
        raise HTTPException(status_code=403, detail="Access denied")
    
    if GoogleDriveService is None:
        raise HTTPException(status_code=503, detail="Google Drive service not available")
    
    try:
        # Create or retrieve the service instance
        if workspace_name not in workspace_gdrive_services:
            workspace_gdrive_services[workspace_name] = GoogleDriveService(workspace_name)
            
        gdrive_service = workspace_gdrive_services[workspace_name]
        auth_url = gdrive_service.get_auth_url()
        
        if not auth_url:
            raise HTTPException(
                status_code=503, 
                detail="Google Drive integration not configured. Please contact your administrator to set up Google Drive credentials."
            )
        
        return {
            "auth_url": auth_url,
            "workspace_name": workspace_name
        }
        
    except Exception as e:
        logger.error(f"Error generating auth URL: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate authorization URL: {str(e)}")

@app.post("/gdrive/auth/{workspace_name}")
async def authenticate_google_drive(workspace_name: str, request: GoogleDriveAuthRequest):
    """Authenticate Google Drive for a workspace"""
    if not check_access():
        raise HTTPException(status_code=403, detail="Access denied")
    
    gdrive_service = workspace_gdrive_services.get(workspace_name)
    if gdrive_service is None:
        raise HTTPException(status_code=503, detail="Google Drive service not available for this workspace.")
    
    try:
        # Exchange the authorization code for tokens. The frontend is now responsible for sending the code.
        if gdrive_service.exchange_code_for_token(request.authorization_code):
            return {
                "message": "Google Drive authenticated successfully",
                "workspace_name": workspace_name,
                "authenticated": True
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to authenticate with Google Drive")
        
    except Exception as e:
        logger.error(f"Error authenticating Google Drive: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to authenticate: {str(e)}")

@app.get("/gdrive/auth-status/{workspace_name}")
async def get_google_drive_auth_status(workspace_name: str):
    """Check Google Drive authentication status for a workspace"""
    if not check_access():
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Use the service from the in-memory store
    gdrive_service = workspace_gdrive_services.get(workspace_name)
    if gdrive_service is None:
        # This is a new session, initialize the service and check auth status
        gdrive_service = GoogleDriveService(workspace_name)
        workspace_gdrive_services[workspace_name] = gdrive_service
    
    try:
        is_authenticated = gdrive_service.is_authenticated()
        
        return {
            "authenticated": is_authenticated,
            "workspace_name": workspace_name
        }
        
    except Exception as e:
        logger.error(f"Error checking auth status: {e}")
        return {
            "authenticated": False,
            "workspace_name": workspace_name,
            "error": f"Error checking authentication status: {str(e)}"
        }

@app.delete("/gdrive/auth/{workspace_name}")
async def revoke_google_drive_access(workspace_name: str):
    """Revoke Google Drive access for a workspace"""
    if not check_access():
        raise HTTPException(status_code=403, detail="Access denied")
    
    gdrive_service = workspace_gdrive_services.get(workspace_name)
    if gdrive_service is None:
        raise HTTPException(status_code=503, detail="Google Drive service not available for this workspace.")
    
    try:
        if gdrive_service.revoke_access():
            # Remove from in-memory store after successful revocation
            del workspace_gdrive_services[workspace_name]
            return {
                "message": "Google Drive access revoked successfully",
                "workspace_name": workspace_name
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to revoke access")
        
    except Exception as e:
        logger.error(f"Error revoking access: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to revoke access: {str(e)}")

@app.get("/gdrive/files")
async def list_google_drive_files(folder_id: Optional[str] = None, file_types: Optional[str] = None, workspace_name: Optional[str] = None):
    """List files from Google Drive"""
    if not check_access():
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not workspace_name:
        raise HTTPException(status_code=400, detail="workspace_name is required")
        
    gdrive_service = workspace_gdrive_services.get(workspace_name)
    if gdrive_service is None:
        raise HTTPException(status_code=503, detail="Google Drive service not available for this workspace.")
    
    try:
        if not gdrive_service.is_authenticated():
            raise HTTPException(status_code=401, detail="Google Drive not authenticated. Please authenticate first.")
        
        file_types_list = [ft.strip() for ft in file_types.split(',')] if file_types else None
        
        files = gdrive_service.list_files(folder_id=folder_id, file_types=file_types_list)
        
        return {
            "files": files,
            "total": len(files)
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error listing Google Drive files: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list Google Drive files: {str(e)}")

@app.get("/gdrive/folders")
async def list_google_drive_folders(workspace_name: Optional[str] = None):
    """List folders from Google Drive"""
    if not check_access():
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not workspace_name:
        raise HTTPException(status_code=400, detail="workspace_name is required")

    gdrive_service = workspace_gdrive_services.get(workspace_name)
    if gdrive_service is None:
        raise HTTPException(status_code=503, detail="Google Drive service not available for this workspace.")
    
    try:
        if not gdrive_service.is_authenticated():
            raise HTTPException(status_code=401, detail="Google Drive not authenticated. Please authenticate first.")
        
        folders = gdrive_service.list_files(file_types=['folder'])
        
        return {
            "folders": folders,
            "total": len(folders)
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error listing Google Drive folders: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list Google Drive folders: {str(e)}")

# Feature Request endpoint
@app.post("/feature-request")
async def submit_feature_request(request: Request):
    """Submit a feature request that gets emailed to admin"""
    if not check_access():
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        body = await request.json()
        title = body.get('title', '')
        description = body.get('description', '')
        priority = body.get('priority', 'medium')
        category = body.get('category', 'general')
        user_email = body.get('email', 'Anonymous')
        
        if not title or not description:
            raise HTTPException(status_code=400, detail="Title and description are required")
        
        # Create HTML email content with proper priority color mapping
        priority_colors = {
            'high': '#ff6b6b',
            'medium': '#feca57', 
            'low': '#48dbfb'
        }
        priority_color = priority_colors.get(priority, '#feca57')
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #667eea; border-bottom: 2px solid #667eea; padding-bottom: 10px;">
                    🚀 New Feature Request
                </h2>
                
                <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #495057;">{title}</h3>
                    
                    <div style="margin: 15px 0;">
                        <strong>Description:</strong><br>
                        <p style="margin: 10px 0; padding: 15px; background: white; border-radius: 5px; border-left: 4px solid #667eea;">
                            {description.replace(chr(10), '<br>')}
                        </p>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 15px 0;">
                        <div>
                            <strong>Priority:</strong><br>
                            <span style="display: inline-block; padding: 5px 12px; background: {priority_color}; color: white; border-radius: 15px; font-size: 12px; text-transform: uppercase;">
                                {priority}
                            </span>
                        </div>
                        <div>
                            <strong>Category:</strong><br>
                            <span style="padding: 5px 12px; background: #667eea; color: white; border-radius: 15px; font-size: 12px; text-transform: uppercase;">
                                {category}
                            </span>
                        </div>
                    </div>
                    
                    <div style="margin: 15px 0;">
                        <strong>Submitted by:</strong> {user_email if user_email != 'Anonymous' else 'Anonymous user'}
                    </div>
                    
                    <div style="margin: 15px 0;">
                        <strong>Submitted at:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
                    </div>
                </div>
                
                <div style="text-align: center; margin-top: 30px; padding: 20px; background: #e9ecef; border-radius: 8px;">
                    <p style="margin: 0; color: #6c757d;">
                        This feature request was submitted through the Aqeed.ai application.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Send email to admin
        send_email(
            subject=f"Feature Request: {title}",
            html_content=html_content,
            to=ADMIN_EMAIL
        )
        
        return {
            "message": "Feature request submitted successfully",
            "title": title,
            "priority": priority,
            "category": category
        }
        
    except Exception as e:
        logger.error(f"Error submitting feature request: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to submit feature request: {str(e)}")

# Contact Form endpoint
@app.post("/contact")
async def submit_contact_form(request: ContactFormRequest):
    """Submit a contact form that gets emailed to admin"""
    if not check_access():
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        # Create HTML email content
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #667eea; border-bottom: 2px solid #667eea; padding-bottom: 10px;">
                    📧 New Contact Form Submission
                </h2>
                
                <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <div style="margin: 15px 0;">
                        <strong>Name:</strong> {request.firstName} {request.lastName}
                    </div>
                    
                    <div style="margin: 15px 0;">
                        <strong>Email:</strong> {request.email}
                    </div>
                    
                    <div style="margin: 15px 0;">
                        <strong>Phone:</strong> {request.phoneNumber if request.phoneNumber else 'Not provided'}
                    </div>
                    
                    <div style="margin: 15px 0;">
                        <strong>Subject:</strong> {request.subject}
                    </div>
                    
                    <div style="margin: 15px 0;">
                        <strong>Message:</strong><br>
                        <p style="margin: 10px 0; padding: 15px; background: white; border-radius: 5px; border-left: 4px solid #667eea;">
                            {request.message.replace(chr(10), '<br>')}
                        </p>
                    </div>
                    
                    <div style="margin: 15px 0;">
                        <strong>Submitted at:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
                    </div>
                </div>
                
                <div style="text-align: center; margin-top: 30px; padding: 20px; background: #e9ecef; border-radius: 8px;">
                    <p style="margin: 0; color: #6c757d;">
                        This contact form was submitted through the Aqeed.ai application.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Send email to admin
        send_email(
            subject=f"Contact Form - {request.subject}: {request.firstName} {request.lastName}",
            html_content=html_content,
            to="niraj@allyin.ai"
        )
        
        return {
            "message": "Contact form submitted successfully",
            "name": f"{request.firstName} {request.lastName}",
            "email": request.email
        }
        
    except Exception as e:
        logger.error(f"Error submitting contact form: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to submit contact form: {str(e)}")

def job_worker_loop():
    try:
        from services.rag_service import score_contracts
        logger.info("[Worker] Redis worker thread started and ready to process jobs")
        
        # Test Redis connection
        job_manager.redis.ping()
        logger.info("[Worker] ✅ Redis connection successful")
        
        while True:
            try:
                keys = job_manager.redis.keys("job:*")
                if keys:
                    # Count only PENDING jobs
                    pending_count = 0
                    for key in keys:
                        job = job_manager.redis.hgetall(key)
                        if job and job.get("status") == "PENDING":
                            pending_count += 1
                    
                    if pending_count > 0:
                        logger.info(f"[Worker] Found {pending_count} pending jobs in queue (total: {len(keys)})")
                    
                for key in keys:
                    job_id = key.split(":")[1]
                    job = job_manager.redis.hgetall(key)
                    # Only process PENDING jobs, skip completed ones
                    if job and job.get("status") == "PENDING":
                        job_type = job.get("job_type")
                        payload = json.loads(job.get("payload", "{}"))
                        logger.info(f"[Worker] 🚀 Starting job {job_id} type={job_type} for workspace={payload.get('workspace_name', 'unknown')}")
                        job_manager.update_job(job_id, "STARTED")

                        try:
                            if job_type == "score_contracts":
                                # Use the shared scoring function instead of duplicating code
                                logger.info(f"[Worker] Processing score_contracts for workspace: {payload.get('workspace_name')}")
                                
                                try:
                                    result = process_score_contracts_sync(
                                        workspace_name=payload.get('workspace_name'),
                                        criterion=payload.get('criterion'),
                                        max_score=payload.get('max_score'),
                                        compare_chatgpt=payload.get('compare_chatgpt'),
                                        share_data_with_chatgpt=payload.get('share_data_with_chatgpt')
                                    )
                                    job_manager.update_job(job_id, "SUCCESS", result=result)
                                    logger.info(f"[Worker] ✅ Job {job_id} completed successfully")
                                    
                                except Exception as e:
                                    logger.error(f"[Worker] Error scoring contracts for workspace '{payload.get('workspace_name')}': {e}", exc_info=True)
                                    job_manager.update_job(job_id, "FAILURE", error=str(e))
                                
                            elif job_type == "audit_contracts":
                                logger.info(f"[Worker] Processing audit_contracts for workspace: {payload.get('workspace_name')}")
                                
                                try:
                                    result = process_audit_contracts_sync(
                                        workspace_name=payload.get('workspace_name')
                                    )
                                    job_manager.update_job(job_id, "SUCCESS", result=result)
                                    logger.info(f"[Worker] ✅ Job {job_id} completed successfully")
                                    
                                except Exception as e:
                                    logger.error(f"[Worker] Error processing audit for workspace '{payload.get('workspace_name')}': {e}", exc_info=True)
                                    job_manager.update_job(job_id, "FAILURE", error=str(e))
                                
                            elif job_type == "legal_analysis":
                                logger.info(f"[Worker] Processing legal_analysis for workspace: {payload.get('workspace_name')}")
                                
                                from services.legal_service import perform_legal_analysis
                                result = perform_legal_analysis(
                                    workspace_name=payload.get('workspace_name')
                                )
                                job_manager.update_job(job_id, "SUCCESS", result=result)
                                logger.info(f"[Worker] ✅ Job {job_id} completed successfully")
                                
                            elif job_type == "qa_processing":
                                logger.info(f"[Worker] Processing qa_processing for workspace: {payload.get('workspace_name')}")
                                
                                from services.rag_service import answer_question_with_rag
                                result, sources = answer_question_with_rag(
                                    query=payload.get('query'),
                                    collection_name=f"contract_docs_{payload.get('workspace_name')}",
                                    response_size=payload.get('response_size', 'medium'),
                                    response_type=payload.get('response_type', 'sentence'),
                                    compare_chatgpt=payload.get('compare_chatgpt', True),
                                    share_data_with_chatgpt=payload.get('share_data_with_chatgpt', True),
                                    use_web=payload.get('use_web', False),
                                    specific_url=payload.get('specific_url', '')
                                )
                                
                                # Format the result to match the expected structure
                                result = {
                                    "answers": result,
                                    "sources": sources
                                }
                                job_manager.update_job(job_id, "SUCCESS", result=result)
                                logger.info(f"[Worker] ✅ Job {job_id} completed successfully")
                                
                            elif job_type == "score_resumes":
                                logger.info(f"[Worker] Processing score_resumes for workspace: {payload.get('workspace_name')}")
                                
                                try:
                                    from services.resume_scoring_service import score_multiple_resumes
                                    
                                    # Load criteria from file
                                    workspace_name = payload.get('workspace_name')
                                    criteria_file = WORKSPACE_ROOT / workspace_name / "resume_criteria.json"
                                    
                                    if not criteria_file.exists():
                                        raise Exception("No criteria found for this workspace.")
                                    
                                    with open(criteria_file, "r") as f:
                                        criteria = json.load(f)
                                    
                                    start_time = time.time()
                                    result = score_multiple_resumes(workspace_name, criteria)
                                    response_time = time.time() - start_time
                                    
                                    # Save results to file (same as endpoint)
                                    results_file = WORKSPACE_ROOT / workspace_name / "resume_scores.json"
                                    with open(results_file, "w") as f:
                                        json.dump(result, f, indent=2)
                                    logger.info(f"[Worker] Resume scoring results saved to {results_file}")
                                    
                                    # Log metrics (same as endpoint)
                                    from datetime import datetime
                                    metrics_file = WORKSPACE_ROOT / workspace_name / "metrics.json"
                                    now = datetime.now().isoformat()
                                    mode = "Score resumes"

                                    new_record = {
                                        "timestamp": now,
                                        "mode": mode,
                                        "response_time": round(response_time, 2)
                                    }
                                    metrics = []
                                    if metrics_file.exists():
                                        try:
                                            with open(metrics_file, "r") as f:
                                                metrics = json.load(f)
                                        except Exception:
                                            logger.warning(f"[Worker] Could not load existing metrics from {metrics_file}, starting new list.")
                                            metrics = []
                                    metrics.append(new_record)
                                    metrics_file.parent.mkdir(parents=True, exist_ok=True)
                                    with open(metrics_file, "w") as f:
                                        json.dump(metrics, f, indent=2)
                                    logger.info(f"[Worker] Logged response time ({response_time:.2f}s) for '{mode}' to {metrics_file}")
                                    
                                    job_manager.update_job(job_id, "SUCCESS", result=result)
                                    logger.info(f"[Worker] ✅ Job {job_id} completed successfully")
                                    
                                except Exception as e:
                                    logger.error(f"[Worker] Error scoring resumes for workspace '{payload.get('workspace_name')}': {e}", exc_info=True)
                                    job_manager.update_job(job_id, "FAILURE", error=str(e))
                                
                            elif job_type == "vendor_recommendations":
                                logger.info(f"[Worker] Processing vendor_recommendations")
                                
                                def process_vendor_recommendations():
                                    from services.vendor_recommendation_service import generate_enhanced_vendor_recommendations
                                    result = generate_enhanced_vendor_recommendations(
                                        project_requirements=payload.get('project_requirements'),
                                        industry=payload.get('industry'),
                                        location_preference=payload.get('location_preference'),
                                        vendor_count=payload.get('vendor_count'),
                                        workspace_name=payload.get('workspace_name'),
                                        preference=payload.get('preference'),
                                        vendor_type=payload.get('vendor_type'),
                                        enable_reddit_analysis=payload.get('enable_reddit_analysis'),
                                        enable_linkedin_analysis=payload.get('enable_linkedin_analysis'),
                                        enable_google_reviews=payload.get('enable_google_reviews')
                                    )
                                    
                                    # Extract the data from the result for the frontend
                                    if result.get("success"):
                                        return {
                                            "summary": result["data"]["summary"],
                                            "recommendations": result["data"]["recommendations"],
                                            "alternate_vendors": result["data"].get("alternate_vendors", []),
                                            "citations": result["citations"],
                                            "enhancement_metadata": result.get("enhancement_metadata", {})
                                        }
                                    else:
                                        return {
                                            "error": result.get("error", "Unknown error"),
                                            "success": False
                                        }
                                
                                process_vendor_job(job_id, payload, process_vendor_recommendations, "Vendor Recommendations")
                                
                            elif job_type == "vendor_research":
                                logger.info(f"[Worker] Processing vendor_research for vendor: {payload.get('vendor_name')}")
                                
                                def process_vendor_research():
                                    from services.vendor_research_service import VendorResearchService
                                    research_service = VendorResearchService()
                                    return research_service.research_vendor(
                                        vendor_name=payload.get('vendor_name'),
                                        location=payload.get('location'),
                                        workspace_name=payload.get('workspace_name'),
                                        enable_reddit_analysis=payload.get('enable_reddit_analysis', False),
                                        enable_linkedin_analysis=payload.get('enable_linkedin_analysis', False),
                                        enable_google_reviews=payload.get('enable_google_reviews', False)
                                    )
                                
                                process_vendor_job(job_id, payload, process_vendor_research, "Vendor Research")
                                
                            elif job_type == "vendor_comparison":
                                logger.info(f"[Worker] Processing vendor_comparison for {len(payload.get('vendors', []))} vendors")
                                
                                def process_vendor_comparison():
                                    from services.vendor_comparison_service import VendorComparisonService
                                    comparison_service = VendorComparisonService()
                                    return comparison_service.compare_vendors(
                                        vendors=payload.get('vendors', []),
                                        workspace_name=payload.get('workspace_name')
                                    )
                                
                                process_vendor_job(job_id, payload, process_vendor_comparison, "Vendor Comparison")

                            elif job_type == "run_ui_flow":
                                logger.info(f"[Worker] Processing run_ui_flow for intent: {payload.get('intent')}")
                                
                                try:
                                    # Import and use the UI automation service
                                    from services.ui_automation_service import UIAutomationService
                                    
                                    # Initialize the automation service
                                    automation_service = UIAutomationService()
                                    
                                    # Process the UI flow with real automation
                                    automation_result = automation_service.process_ui_flow(payload)
                                    
                                    # Create comprehensive result
                                    result = {
                                        "status": "completed",
                                        "intent": payload.get('intent'),
                                        "session_id": payload.get('session_id'),
                                        "user_id": payload.get('user_id'),
                                        "tool_invocation_id": payload.get('tool_invocation_id'),
                                        "page_url": payload.get('page_url'),
                                        "processed_at": automation_result.get('processed_at'),
                                        "processing_time": automation_result.get('processing_time'),
                                        "success": automation_result.get('success'),
                                        "automation_result": automation_result.get('automation_result'),
                                        "dom_analysis": automation_result.get('dom_analysis'),
                                        "screenshots": automation_result.get('automation_result', {}).get('screenshots', []),
                                        "actions_performed": automation_result.get('automation_result', {}).get('actions_performed', []),
                                        "errors": automation_result.get('automation_result', {}).get('errors', []),
                                        "message": f"UI flow '{payload.get('intent')}' {'completed successfully' if automation_result.get('success') else 'failed'}"
                                    }
                                    
                                    if automation_result.get('error'):
                                        result['error'] = automation_result.get('error')
                                    
                                    job_manager.update_job(job_id, "SUCCESS", result=result)
                                    logger.info(f"[Worker] ✅ Job {job_id} completed successfully with automation")
                                    
                                except Exception as automation_error:
                                    logger.error(f"[Worker] ❌ UI automation failed for job {job_id}: {automation_error}")
                                    
                                    # Fallback to basic result if automation fails
                                    fallback_result = {
                                        "status": "failed",
                                        "intent": payload.get('intent'),
                                        "session_id": payload.get('session_id'),
                                        "user_id": payload.get('user_id'),
                                        "tool_invocation_id": payload.get('tool_invocation_id'),
                                        "page_url": payload.get('page_url'),
                                        "processed_at": datetime.now().isoformat(),
                                        "success": False,
                                        "error": str(automation_error),
                                        "message": f"UI flow '{payload.get('intent')}' failed: {automation_error}"
                                    }
                                    
                                    job_manager.update_job(job_id, "SUCCESS", result=fallback_result)
                                    logger.info(f"[Worker] ⚠️ Job {job_id} completed with fallback result")
                                
                            else:
                                error_msg = f"Unknown job type {job_type}"
                                logger.warning(f"[Worker] ❌ {error_msg}")
                                job_manager.update_job(job_id, "FAILURE", error=error_msg)
                        except Exception as e:
                            logger.error(f"[Worker] ❌ Job {job_id} failed: {e}", exc_info=True)
                            job_manager.update_job(job_id, "FAILURE", error=str(e))
                            
            except Exception as e:
                logger.error(f"[Worker] Redis connection error: {e}")
                time.sleep(5)  # Wait longer on connection errors
                
            time.sleep(2)
    except Exception as e:
        logger.error(f"[Worker] Failed to start worker thread: {e}", exc_info=True)

# Start worker thread when FastAPI launches
logger.info("[Main] Starting Redis worker thread...")
worker_thread = threading.Thread(target=job_worker_loop, daemon=True, name="RedisWorker")
worker_thread.start()
logger.info(f"[Main] Redis worker thread started with ID: {worker_thread.ident}")

import uvicorn
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)