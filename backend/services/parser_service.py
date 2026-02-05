from pathlib import Path
import json
import os
import logging
import hashlib # Make sure hashlib is imported for compute_md5
from PyPDF2 import PdfReader # Make sure PyPDF2 is imported
# from allyin.multimodal2text import extract_text # Assuming this is available and correctly installed for docx/xlsx

# --- Placeholder for allyin.multimodal2text if not installed or behaving as expected ---
# If allyin.multimodal2text is giving issues, you might need to use alternative libraries
# or handle its import more robustly. For demonstration, let's include it.
try:
    from allyin.multimodal2text import extract_text
except ImportError:
    logging.warning("allyin.multimodal2text not found. DOCX/XLSX parsing might be limited.")
    def extract_text(file_path):
        # Placeholder/fallback if allyin.multimodal2text isn't available
        # You might implement basic text extraction for known formats,
        # or just return an error/empty string.
        logging.error(f"Cannot extract text from {file_path}. allyin.multimodal2text not available.")
        raise NotImplementedError("DOCX/XLSX parsing not available without allyin.multimodal2text")


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Helper to compute md5 hash of a file (Ensure this is correctly defined)
def compute_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

import pandas as pd

def _extract_text_from_xlsx(filepath: str) -> str:
    """
    Reads .xlsx or .csv file and converts it into a CSV-formatted string,
    which helps downstream parsers to extract scores easily.
    """
    try:
        text_output = []
        ext = os.path.splitext(filepath)[-1].lower()

        if ext == ".csv":
            df = pd.read_csv(filepath)
            text_output.append(f"Sheet: CSV")
            text_output.append(df.to_csv(index=False))
        else:
            xl = pd.ExcelFile(filepath)
            for sheet_name in xl.sheet_names:
                df = xl.parse(sheet_name)
                text_output.append(f"Sheet: {sheet_name}")
                text_output.append(df.to_csv(index=False))

        return "\n\n".join(text_output)

    except Exception as e:
        logger.error(f"Failed to parse Excel or CSV: {e}")
        return ""
    


def parse_documents(input_dir: str, output_file: str, workspace: str, use_manifest: bool = True, append_output: bool = True, folder_prefix: str = ""):
    """
    Parses documents from the input directory and writes the parsed output to a JSONL file.
    This version correctly handles binary files like PDF, DOCX, and XLSX.

    Args:
        input_dir (str): Path to the directory containing input documents.
        output_file (str): Path to the output JSONL file.
        workspace (str): Workspace identifier.
        use_manifest (bool): Whether to use manifest for tracking changes.
        append_output (bool): Whether to append to the output file or overwrite.
    """
    logger.info(f"Starting parsing documents in workspace '{workspace}' from '{input_dir}' to '{output_file}'")
    
    manifest = {}
    updated_manifest = {}
    if use_manifest:
        # Load or initialize manifest for tracking changes
        # The manifest_path calculation logic here needs to be consistent
        # with main.py's PROJECT_ROOT if it's not passed as an argument.
        # For now, I'll keep the relative path calculation as it was in your previous parser.
        script_dir = Path(__file__).resolve().parent.parent.parent
        manifest_path = script_dir / "data" / workspace / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except json.JSONDecodeError:
                logger.warning("Manifest is empty or invalid. Starting fresh.")
                manifest = {}
        updated_manifest = manifest.copy()

    output_docs = [] # Renamed from 'output' to 'output_docs' for clarity
    
    try:
        # Get list of files to parse
        files_to_parse = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        
        for filename in files_to_parse:
            filepath = os.path.join(input_dir, filename)
            file_hash = compute_md5(filepath)
            
            # Check if the file is new or has been modified since the last parse
            if use_manifest and filename in manifest and manifest.get(filename) == file_hash:
                logger.info(f"⏩ Skipping unchanged file: {filename}")
                continue
            
            # Use appropriate parsing logic based on file extension
            suffix = Path(filename).suffix.lower()
            
            if suffix == ".pdf":
                try:
                    reader = PdfReader(filepath)
                    for page_num, page in enumerate(reader.pages):
                        page_text = page.extract_text() or ""
                        output_docs.append({
                            "file": f"{folder_prefix}/{filename}" if folder_prefix else filename, # Include folder prefix if provided
                            "page": page_num + 1,
                            "text": page_text,
                            "source_type": "pdf"
                        })
                except Exception as e:
                    logger.error(f"Error parsing PDF file {filename}: {e}. Skipping file.")
                    continue # Skip to the next file if parsing fails
            
            elif suffix in [".docx", ".xlsx"]:
                try:
                    # Ensure allyin.multimodal2text is installed and works
                    text_content = extract_text(str(filepath))
                    output_docs.append({
                        "file": f"{folder_prefix}/{filename}" if folder_prefix else filename, # Include folder prefix if provided
                        "page": 1, # Assumes these files are single logical documents for page tracking
                        "text": text_content,
                        "source_type": suffix.lstrip(".")
                    })
                except NotImplementedError:
                    logger.error(f"DOCX/XLSX parsing not implemented or library missing for {filename}. Skipping file.")
                    continue
                except Exception as e:
                    logger.error(f"Error parsing {suffix} file {filename}: {e}. Skipping file.")
                    continue

            else:
                # For unknown or simple text files, try common encodings
                # If you expect very specific text files (e.g., criteria.txt), adjust encoding.
                # For generic, safer to assume binary then try decoding.
                logger.warning(f"Attempting to read unrecognized file type: {filename}. Trying common text encodings.")
                try:
                    with open(filepath, 'r', encoding='utf-8') as infile:
                        content = infile.read()
                except UnicodeDecodeError:
                    try:
                        with open(filepath, 'r', encoding='latin-1') as infile:
                            content = infile.read()
                    except Exception as e:
                        logger.error(f"Could not decode text file {filename} with UTF-8 or Latin-1: {e}. Skipping file.")
                        continue
                except Exception as e:
                    logger.error(f"Error reading generic file {filename}: {e}. Skipping file.")
                    continue

                output_docs.append({
                    "file": f"{folder_prefix}/{filename}" if folder_prefix else filename, # Include folder prefix if provided
                    "page": 1,
                    "text": content,
                    "source_type": suffix.lstrip(".") or "txt" # Default to 'txt' if no suffix
                })
            
            # If successfully processed, update the manifest with the new hash
            if use_manifest:
                updated_manifest[filename] = file_hash

        # Append new documents to the output file (using append mode 'a' or write mode 'w')
        mode = 'a' if append_output else 'w'
        with open(output_file, mode, encoding='utf-8') as outfile:
            for doc in output_docs:
                json_line = json.dumps(doc)
                outfile.write(json_line + "\n")
        
        # Save the updated manifest
        if use_manifest:
            # Ensure the manifest directory exists
            Path(manifest_path).parent.mkdir(parents=True, exist_ok=True)
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(updated_manifest, f, indent=2)
            
        logger.info(f"Completed parsing documents for workspace '{workspace}'. Added {len(output_docs)} new entries. Output saved to '{output_file}'.")
    
    except Exception as e:
        logger.error(f"Critical error during parsing process for workspace '{workspace}': {e}")
        raise e

# The `run_parsing_for_workspace` function should remain as previously updated
# to accept `base_dir` and create the `criteria_weights` directory.
# (This part is identical to the last corrected version you received)
def run_parsing_for_workspace(workspace: str, base_dir: Path):
    """
    Orchestrates the parsing process for a given workspace.
    This function now uses a consistent `base_dir` passed from `main.py`.
    """
    workspace_path = base_dir / "data" / workspace
    input_dir = workspace_path / "contracts"
    criteria_dir = workspace_path / "criteria_weights"
    output_file = workspace_path / "parsed.jsonl"
    output_cri_file = workspace_path / "parsed_criteria.jsonl"

    # Ensure all necessary directories exist before parsing
    workspace_path.mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)
    criteria_dir.mkdir(parents=True, exist_ok=True) # This fixes the FileNotFoundError

    parse_documents(str(input_dir), str(output_file), workspace, folder_prefix="contracts")
    parse_documents(str(criteria_dir), str(output_cri_file), workspace, use_manifest=False, append_output=False, folder_prefix="criteria_weights")

