import os
import json
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import Request as FastAPIRequest
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
import io
import mimetypes
import logging
import base64
from urllib.parse import urlencode, urlparse, parse_qs
from dotenv import load_dotenv
load_dotenv()
logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

class GoogleDriveService:
 
    def __init__(self, workspace_name: Optional[str] = None):
        self.creds = None
        self.service = None
        self.workspace_name = workspace_name
        
        # credentials_dir = Path(__file__).parent.parent.parent / ".credentials"
        # credentials_dir.mkdir(exist_ok=True)

        # Try multiple possible locations
        possible_paths = [
            Path("/app/.credentials"),
            Path(__file__).parent.parent.parent / ".credentials",
            Path.home() / ".credentials"
        ]

        credentials_dir = None
        for path in possible_paths:
            if path.exists():
                credentials_dir = path
                break

        if not credentials_dir:
            credentials_dir = Path("/app/.credentials")  # Default fallback

        credentials_dir.mkdir(exist_ok=True)
                
        if workspace_name:
            self.token_path = credentials_dir / f"{workspace_name}_token.json"
        else:
            self.token_path = credentials_dir / "token.json"
        
        self.credentials_path = credentials_dir / "credentials.json"
        
    def _get_redirect_uri(self, request: Optional[FastAPIRequest] = None) -> str:
        """Return OAuth2 redirect URI. Use request host/port when available; otherwise fall back to env vars."""
        redirect_path = os.getenv('OAUTH_REDIRECT_PATH', '/api/oauth2callback')
        if request is not None:
            scheme = "https"  # Force HTTPS for production
            host = request.url.hostname
            port = request.url.port
            if (scheme == "http" and port and port != 80) or (scheme == "https" and port and port != 443):
                redirect_uri = f"{scheme}://{host}:{port}{redirect_path}"
            else:
                redirect_uri = f"{scheme}://{host}{redirect_path}"
            logger.info(f"Using dynamic redirect URI from request: {redirect_uri}")
            return redirect_uri
        host = os.getenv('EC2_HOST', 'localhost')
        port = os.getenv('BACKEND_PORT', '8000')
        redirect_uri = f"http://{host}:{port}{redirect_path}"
        logger.info(f"Using fallback redirect URI: {redirect_uri}")
        return redirect_uri
        
    def get_auth_url(self, request: Optional[FastAPIRequest] = None) -> Optional[str]:
        """Get the authorization URL for Google Drive OAuth"""
        try:
            if not self.credentials_path.exists():
                logger.warning("Google Drive credentials file not found. Please set up Google Drive integration first.")
                return None
            with open(self.credentials_path, 'r') as f:
                creds_data = json.load(f)
            if 'web' in creds_data:
                from google_auth_oauthlib.flow import Flow
                redirect_uri = self._get_redirect_uri(request)
                flow = Flow.from_client_config(
                    creds_data,
                    scopes=SCOPES,
                    redirect_uri=redirect_uri
                )
                if self.workspace_name:
                    import urllib.parse
                    encoded_workspace = urllib.parse.quote(self.workspace_name)
                    state = f"workspace={encoded_workspace}"
                else:
                    state = ""
                auth_url, _ = flow.authorization_url(
                    access_type='offline',
                    include_granted_scopes='true',
                    prompt='consent',
                    state=state
                )
                # Begin detailed debug logging for the generated Google OAuth URL
                try:
                    parsed = urlparse(auth_url)
                    q = parse_qs(parsed.query)
                    sent_redirect = q.get('redirect_uri', [''])[0]
                    sent_client_id = q.get('client_id', [''])[0]
                    configured_client_id = (creds_data.get('web') or {}).get('client_id', '')
                    logger.info("[GDRIVE] Generated auth_url: %s", auth_url)
                    logger.info("[GDRIVE] auth_url params -> redirect_uri: %s | client_id (url): %s | client_id (creds.json): %s",
                                sent_redirect, sent_client_id, configured_client_id)
                except Exception as _e:
                    logger.warning("[GDRIVE] Failed to parse auth_url for debug logging: %s", _e)
                # End debug logging
                return auth_url
            elif 'installed' in creds_data:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), SCOPES)
                auth_url, _ = flow.authorization_url(
                    access_type='offline',
                    include_granted_scopes='true',
                    prompt='consent'
                )
                # Begin debug logging for installed client
                try:
                    logger.info("[GDRIVE] Generated auth_url (installed creds): %s", auth_url)
                except Exception as _e:
                    logger.warning("[GDRIVE] Failed to log installed auth_url: %s", _e)
                # End debug logging
                return auth_url
            else:
                logger.error("Invalid credentials file format. Expected 'web' or 'installed' application type.")
                return None
        except Exception as e:
            logger.error(f"Error generating auth URL: {e}")
            return None
    
    def exchange_code_for_token(self, authorization_code: str, request: Optional[FastAPIRequest] = None) -> bool:
        """Exchange authorization code for access token"""
        try:
            if not self.credentials_path.exists():
                logger.error("Google Drive credentials file not found")
                return False
            with open(self.credentials_path, 'r') as f:
                creds_data = json.load(f)
            if 'web' in creds_data:
                from google_auth_oauthlib.flow import Flow
                redirect_uri = self._get_redirect_uri(request)
                flow = Flow.from_client_config(
                    creds_data,
                    scopes=SCOPES,
                    redirect_uri=redirect_uri
                )
                flow.fetch_token(code=authorization_code)
                self.creds = flow.credentials
            elif 'installed' in creds_data:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), SCOPES)
                flow.fetch_token(code=authorization_code)
                self.creds = flow.credentials
            else:
                logger.error("Invalid credentials file format. Expected 'web' or 'installed' application type.")
                return False
            if not self.creds.refresh_token:
                logger.warning("No refresh token received. This may cause authentication issues. Attempting to proceed with access token only.")
            logger.info("[GDRIVE] token exchange succeeded; writing token file")
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_path, 'w') as token:
                token.write(self.creds.to_json())
            logger.info(f"Successfully saved credentials to {self.token_path}")
            self.service = build('drive', 'v3', credentials=self.creds)
            return True
        except Exception as e:
            logger.error(f"Error exchanging code for token: {e}")
            return False

    def download_files_to(self, file_ids: List[str], dest_dir: str) -> List[Dict[str, str]]:
        """
        Download the given Drive file IDs into dest_dir.
        Returns a list of dicts with { 'id', 'name', 'path' } for each saved file.
        Reuses download_file() so Google Docs are exported to standard formats.
        """
        # Ensure destination exists
        Path(dest_dir).mkdir(parents=True, exist_ok=True)

        # Ensure service is ready
        if not getattr(self, 'service', None):
            ok = self.authenticate()
            if not ok:
                raise RuntimeError("Not authenticated with Google Drive. Please connect your account.")

        saved: List[Dict[str, str]] = []
        for fid in file_ids:
            try:
                # Fetch metadata for sensible naming
                meta = self.service.files().get(fileId=fid, fields='id,name,mimeType').execute()
                name = meta.get('name') or fid

                # Use existing single-file logic (handles Google Docs export)
                ok = self.download_file(fid, Path(dest_dir))
                if ok:
                    expected = Path(dest_dir) / name
                    if expected.exists():
                        final_path = expected
                    else:
                        # If exported (e.g., .docx), find the new extension
                        matches = list(Path(dest_dir).glob(f"{name}.*"))
                        final_path = matches[0] if matches else expected
                    saved.append({'id': fid, 'name': name, 'path': str(final_path)})
                else:
                    logger.warning(f"[GDRIVE] download_file returned False for id={fid} name={name}")
            except Exception as e:
                logger.error(f"[GDRIVE] Failed to download file {fid}: {e}", exc_info=True)
        return saved

    def authenticate(self) -> bool:
        """Authenticate with Google Drive API"""
        try:
            # Check if we have stored credentials
            if self.token_path.exists():
                try:
                    self.creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
                    logger.info("Loaded credentials from token file")
                except Exception as e:
                    logger.error(f"Error loading credentials from token file: {e}")
                    # Try fallback: load JSON and build minimal Credentials if access_token exists
                    try:
                        with open(self.token_path, 'r') as f:
                            data = json.load(f)
                        # Construct Credentials even if refresh_token is missing
                        self.creds = Credentials(
                            token=data.get('token'),
                            refresh_token=data.get('refresh_token'),
                            token_uri=data.get('token_uri'),
                            client_id=data.get('client_id'),
                            client_secret=data.get('client_secret'),
                            scopes=SCOPES
                        )
                        logger.info("Loaded minimal credentials from token JSON")
                    except Exception as e2:
                        logger.error(f"Fallback load failed: {e2}")
                        # Remove invalid token file and abort
                        self.token_path.unlink()
                        return False
            
            # If there are no (valid) credentials available, return False
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    try:
                        logger.info("Refreshing expired credentials")
                        self.creds.refresh(GoogleRequest())
                        # Save the refreshed credentials
                        with open(self.token_path, 'w') as token:
                            token.write(self.creds.to_json())
                    except Exception as e:
                        logger.error(f"Error refreshing credentials: {e}")
                        # Refresh failed, need to re-authenticate
                        return False
                else:
                    # No credentials available or no refresh token
                    logger.info("No valid credentials available")
                    return False
            
            self.service = build('drive', 'v3', credentials=self.creds)
            return True
            
        except Exception as e:
            logger.error(f"Error authenticating with Google Drive: {e}")
            return False
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return self.authenticate()
    

    def revoke_access(self) -> bool:
        """
        Revoke access for this workspace and delete the stored token file.
        This is robust: it deletes the token file even if the HTTP revoke fails.
        """
        try:
            # Load creds from token file if not already loaded
            if not getattr(self, "creds", None) and self.token_path.exists():
                try:
                    self.creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
                except Exception as e:
                    logger.warning(f"[GDRIVE] Could not load creds from token file before revoke: {e}")

            # Try to revoke via Google endpoint if we have a token
            try:
                token_to_revoke = None
                if getattr(self, "creds", None):
                    token_to_revoke = getattr(self.creds, "token", None)
                    if not token_to_revoke:
                        try:
                            with open(self.token_path, "r") as f:
                                raw = json.load(f)
                            token_to_revoke = raw.get("token")
                        except Exception:
                            token_to_revoke = None

                if token_to_revoke:
                    import requests as _requests
                    _requests.post(
                        "https://oauth2.googleapis.com/revoke",
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                        data=f"token={token_to_revoke}",
                        timeout=10
                    )
                    logger.info("[GDRIVE] Revoke request sent to Google for workspace '%s'", self.workspace_name)
            except Exception as e:
                logger.warning(f"[GDRIVE] Revoke HTTP call failed (will still delete token): {e}")

            # Always delete the token file
            try:
                if self.token_path.exists():
                    self.token_path.unlink()
                    logger.info("[GDRIVE] Deleted token file: %s", self.token_path)
            except Exception as e:
                logger.error(f"[GDRIVE] Failed to delete token file {self.token_path}: {e}")

            # Clear in-memory state
            self.creds = None
            self.service = None
            return True
        except Exception as e:
            logger.error(f"[GDRIVE] Error in revoke_access: {e}", exc_info=True)
            return False
    

    def list_files(self, folder_id: Optional[str] = None, file_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        List files from Google Drive.
        - If file_types is None or empty -> no MIME filter (return all files in the folder/root).
        - If file_types is provided -> filter by the mapped MIME types for those extensions.
        """
        try:
            if not self.service:
                if not self.authenticate():
                    return []

            query_parts = []
            if folder_id:
                query_parts.append(f"'{folder_id}' in parents")
            else:
                query_parts.append("'root' in parents")

            # Only build MIME filter if file_types provided
            if file_types:
                ext_map = {
                    "pdf": ["application/pdf"],
                    "doc": [
                        "application/msword",
                        "application/vnd.google-apps.document",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ],
                    "docx": [
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "application/vnd.google-apps.document",
                    ],
                    "txt": ["text/plain"],
                    "csv": ["text/csv", "application/vnd.ms-excel"],
                    "xls": ["application/vnd.ms-excel"],
                    "xlsx": [
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "application/vnd.google-apps.spreadsheet",
                    ],
                    "ppt": ["application/vnd.ms-powerpoint"],
                    "pptx": [
                        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        "application/vnd.google-apps.presentation",
                    ],
                    "png": ["image/png"],
                    "jpg": ["image/jpeg"],
                    "jpeg": ["image/jpeg"],
                    "gif": ["image/gif"],
                    "json": ["application/json"],
                    # Google Workspace primary types
                    "gdoc": ["application/vnd.google-apps.document"],
                    "gsheet": ["application/vnd.google-apps.spreadsheet"],
                    "gslide": ["application/vnd.google-apps.presentation"],
                }

                mime_types: List[str] = []
                for ft in file_types:
                    key = ft.lower().strip()
                    if key in ext_map:
                        mime_types.extend(ext_map[key])
                    else:
                        guessed = mimetypes.types_map.get(f".{key}")
                        if guessed:
                            mime_types.append(guessed)

                if mime_types:
                    mime_types = sorted(set(mime_types))
                    mime_query = " or ".join([f"mimeType='{mime}'" for mime in mime_types])
                    query_parts.append(f"({mime_query})")

            query = " and ".join(query_parts)

            files: List[Dict[str, Any]] = []
            page_token = None
            while True:
                results = self.service.files().list(
                    q=query,
                    pageSize=100,
                    fields=(
                        "nextPageToken, files("
                        "id, name, mimeType, size, modifiedTime, parents, "
                        "iconLink, webViewLink, webContentLink)"
                    ),
                    pageToken=page_token
                ).execute()
                files.extend(results.get("files", []))
                page_token = results.get("nextPageToken")
                if not page_token:
                    break

            return files
        except HttpError as error:
            logger.error(f"[GDRIVE] list_files error: {error}")
            return []
    
    def download_file(self, file_id: str, destination_path: Path) -> bool:
        """Download a file from Google Drive"""
        try:
            if not self.service:
                if not self.authenticate():
                    return False
            
            # Get file metadata
            file_metadata = self.service.files().get(fileId=file_id).execute()
            file_name = file_metadata.get('name', 'unknown_file')
            mime_type = file_metadata.get('mimeType', '')
            
            # Handle Google Docs/Sheets/Slides
            if mime_type.startswith('application/vnd.google-apps'):
                return self._export_google_doc(file_id, file_name, destination_path, mime_type)
            
            # Download regular files
            request = self.service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                logger.info(f"Download {int(status.progress() * 100)}%")
            
            # Save the file
            file_path = destination_path / file_name
            with open(file_path, 'wb') as f:
                f.write(fh.getvalue())
            
            logger.info(f"Downloaded {file_name} to {file_path}")
            return True
            
        except HttpError as error:
            logger.error(f'An error occurred downloading file {file_id}: {error}')
            return False
    
    def _export_google_doc(self, file_id: str, file_name: str, destination_path: Path, mime_type: str) -> bool:
        """Export Google Docs/Sheets/Slides to appropriate format"""
        try:
            # Determine export format based on mime type
            export_mime_type = 'application/pdf'
            file_extension = '.pdf'
            
            if mime_type == 'application/vnd.google-apps.document':
                export_mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                file_extension = '.docx'
            elif mime_type == 'application/vnd.google-apps.spreadsheet':
                export_mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                file_extension = '.xlsx'
            elif mime_type == 'application/vnd.google-apps.presentation':
                export_mime_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
                file_extension = '.pptx'
            
            # Export the file
            request = self.service.files().export_media(
                fileId=file_id,
                mimeType=export_mime_type
            )
            
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                logger.info(f"Export {int(status.progress() * 100)}%")
            
            # Save the exported file
            file_path = destination_path / f"{file_name}{file_extension}"
            with open(file_path, 'wb') as f:
                f.write(fh.getvalue())
            
            logger.info(f"Exported {file_name} to {file_path}")
            return True
            
        except HttpError as error:
            logger.error(f'An error occurred exporting file {file_id}: {error}')
            return False
    
    def get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file information"""
        try:
            if not self.service:
                if not self.authenticate():
                    return None
            
            file_metadata = self.service.files().get(fileId=file_id).execute()
            return file_metadata
            
        except HttpError as error:
            logger.error(f'An error occurred getting file info {file_id}: {error}')
            return None

# Global instance
google_drive_service = GoogleDriveService() 