# from fastapi import APIRouter, UploadFile, File
# from typing import List
# from services.parser_service import run_parsing_for_workspace
# from services.embedder_service import run_embedding_for_workspace, sync_embedder_manifest

# router = APIRouter()

# @router.get("/")
# async def root():
#     return {"message": "Welcome to the Azegate Backend API"}

# @router.post("/upload/{workspace}")
# async def upload_files(workspace: str, files: List[UploadFile] = File(...)):
#     filenames = [file.filename for file in files]
#     return {"workspace": workspace, "uploaded_files": filenames}

# @router.post("/parse/{workspace}")
# async def parse_workspace(workspace: str):
#     run_parsing_for_workspace(workspace)
#     return {"message": f"Parsing completed for workspace: {workspace}"}

# @router.post("/embed/{workspace}")
# async def embed_workspace(workspace: str, select_parsed: str):
#     run_embedding_for_workspace(workspace, select_parsed)
#     sync_embedder_manifest(workspace)
#     return {"message": f"Embedding completed for workspace: {workspace}, file: {select_parsed}"}