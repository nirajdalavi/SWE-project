# services/combined_evaluation_service.py

import json
import os
from typing import Dict, Tuple
from pathlib import Path
from collections import defaultdict
import pandas as pd
import logging
import shutil # Import shutil for rmtree
import re # Import re for regular expressions

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
logger = logging.getLogger(__name__)

def find_excel_file(directory: Path) -> Path:
    for file in os.listdir(directory):
        if file.endswith(".xlsx"):
            return directory / file
    raise FileNotFoundError(f"No .xlsx file found in {directory}")

# MODIFIED: To return max_score as well
def extract_scores_from_final_scores_sheet(file_path: Path) -> Tuple[dict, float]:
    df = pd.read_excel(file_path, sheet_name="Final Scores")
    
    # Normalize column names for easier access (strip whitespace, lowercase)
    df.columns = [str(col).strip().lower() for col in df.columns]

    contract_col = next((col for col in df.columns if "contract" in col), None)
    
    # MODIFIED: Find the 'score' column and extract the max score from its header
    score_col_name_raw = None
    max_score_from_header = 100.0 # Default if not found or parse fails
    
    for col in df.columns:
        if "allyin score" in col or "score" in col:
            score_col_name_raw = col # Keep the original column name with "out of X"
            
            # Use regex to find "out of X" in the column name
            match = re.search(r'\(out of (\d+)\)', col)
            if match:
                try:
                    max_score_from_header = float(match.group(1))
                    logger.info(f"Extracted max score of {max_score_from_header} from header: '{col}' in file: {file_path}")
                except ValueError:
                    logger.warning(f"Could not parse max score from header: '{col}'. Using default 100.0.")
            break # Found the score column

    if not contract_col or not score_col_name_raw:
        raise ValueError(f"Expected 'Contract' and 'Allyin Score' (or similar) columns in the 'Final Scores' sheet of {file_path}.")

    scores = {}
    for _, row in df.iterrows():
        contract = str(row[contract_col]).strip().lower().replace(" ", "")
        try:
            score = float(row[score_col_name_raw])
            scores[contract] = score
        except (ValueError, TypeError):
            # Log specific contracts that failed conversion if needed
            logger.warning(f"Skipping score for contract '{contract}' in {file_path} due to non-numeric value: '{row[score_col_name_raw]}'")
            continue

    return scores, max_score_from_header # Return both scores and the extracted max score

# MODIFIED: To use dynamic max scores
def perform_combined_evaluation(
    workspace_name: str,
    technical_weight: float,
    financial_weight: float
) -> Dict:
    logger.info(f"Starting combined evaluation for workspace '{workspace_name}' with technical_weight={technical_weight}, financial_weight={financial_weight}")

    tech_weight_norm = technical_weight / 100.0
    fin_weight_norm = financial_weight / 100.0

    technical_scores_by_contract = {}
    financial_scores_by_contract = {}
    
    tech_max_score_for_normalization = 100.0 # Initialize with a default
    fin_max_score_for_normalization = 100.0  # Initialize with a default

    # Extract Allyin scores and max score from XLSX files in each report folder
    try:
        technical_dir = PROJECT_ROOT / "data" / workspace_name / "technical_reports"
        technical_file = find_excel_file(technical_dir)
        technical_scores_by_contract, tech_max_score_for_normalization = extract_scores_from_final_scores_sheet(technical_file)
        if tech_max_score_for_normalization == 0: # Avoid division by zero
            logger.warning(f"Technical max score for normalization is 0. Setting to 1.0 to prevent division by zero.")
            tech_max_score_for_normalization = 1.0
    except Exception as e:
        raise RuntimeError(f"Failed to extract technical scores or max score: {e}")

    try:
        financial_dir = PROJECT_ROOT / "data" / workspace_name / "financial_reports"
        financial_file = find_excel_file(financial_dir)
        financial_scores_by_contract, fin_max_score_for_normalization = extract_scores_from_final_scores_sheet(financial_file)
        if fin_max_score_for_normalization == 0: # Avoid division by zero
            logger.warning(f"Financial max score for normalization is 0. Setting to 1.0 to prevent division by zero.")
            fin_max_score_for_normalization = 1.0
    except Exception as e:
        raise RuntimeError(f"Failed to extract financial scores or max score: {e}")

    all_contract_names = set(technical_scores_by_contract) | set(financial_scores_by_contract)
    if not all_contract_names:
        return {"error": "No contract scores found in 'Final Scores' sheet of technical or financial reports."}

    sorted_contract_names = sorted(all_contract_names)
    combined_raw_contracts = {}
    combined_final_scores = {}
    
    # max_report_score_for_normalization will now be dynamic, no longer a fixed value here.
    # The output is always 'out of 100' regardless of input scales.

    combined_contracts_list = []

    for contract in sorted_contract_names:
        tech_score_raw = technical_scores_by_contract.get(contract, 0)
        fin_score_raw = financial_scores_by_contract.get(contract, 0)

        # Normalize scores to a 0-1 scale using their respective max scores
        normalized_tech_score = tech_score_raw / tech_max_score_for_normalization
        normalized_fin_score = fin_score_raw / fin_max_score_for_normalization

        # Calculate combined weighted score
        if tech_weight_norm == 0 and fin_weight_norm == 0:
            combined_score_normalized = 0.0
        else:
            combined_score_normalized = (
                normalized_tech_score * tech_weight_norm +
                normalized_fin_score * fin_weight_norm
            ) / (tech_weight_norm + fin_weight_norm)

        # Scale the final combined score to be always out of 100
        final_combined_score_out_of_100 = round(combined_score_normalized * 100, 2)
        final_combined_percentage = round(final_combined_score_out_of_100, 2)

        combined_contracts_list.append({
            "name": contract,
            "score": final_combined_score_out_of_100, # This is the final score out of 100
            "rationale": f"Technical Score: {tech_score_raw} (out of {tech_max_score_for_normalization}), Financial Score: {fin_score_raw} (out of {fin_max_score_for_normalization}). Weights: Tech {technical_weight}%, Fin {financial_weight}%.", # Updated rationale for clarity
            "technical_score": tech_score_raw,
            "financial_score": fin_score_raw,
            "weighted_technical_score": round(normalized_tech_score * technical_weight, 2), # Correctly calculate weighted scores relative to 100% total weight
            "weighted_financial_score": round(normalized_fin_score * financial_weight, 2),
            "weight": 1 # This 'weight' field is for individual criterion if used in a different context.
        })

        combined_final_scores[contract] = {
            "score_out_of_100": final_combined_score_out_of_100,
            "percentage": final_combined_percentage
        }

    best_combined_contract = None
    if combined_final_scores:
        best_combined_contract = max(combined_final_scores.items(), key=lambda x: x[1]['score_out_of_100'])[0]

    summary_of_combined_best = {
        "best_contract": best_combined_contract,
        "summary": [
            f"Overall combined evaluation identifies {best_combined_contract} as the strongest proposal.",
            "This result is based on a weighted analysis integrating technical and financial evaluation criteria.",
            f"Technical reports contributed {technical_weight}% and financial reports contributed {financial_weight}% to the combined score.",
            "Review the 'Combined Breakdown' for detailed scores and rationales."
        ]
    }
    if best_combined_contract:
        summary_of_combined_best["summary"].append(f"Technical score for {best_combined_contract}: {technical_scores_by_contract.get(best_combined_contract, 'N/A')} (out of {tech_max_score_for_normalization})") # Update summary
        summary_of_combined_best["summary"].append(f"Financial score for {best_combined_contract}: {financial_scores_by_contract.get(best_combined_contract, 'N/A')} (out of {fin_max_score_for_normalization})") # Update summary


    combined_results = {
        "raw_combined": {"contracts": combined_contracts_list},
        "final_scores_combined": combined_final_scores,
        "summary_of_combined_best": summary_of_combined_best,
        "response_time": 0
    }

    # Save to combined_score.json
    combined_score_file_path = PROJECT_ROOT / "data" / workspace_name / "combined_score.json"
    full_score_data = {}
    if combined_score_file_path.exists():
        try:
            with open(combined_score_file_path, "r") as f:
                full_score_data = json.load(f)
        except json.JSONDecodeError:
            logger.warning(f"Malformed combined_score.json for {workspace_name}, overwriting.")
            full_score_data = {}

    full_score_data["raw_combined"] = combined_results["raw_combined"]
    full_score_data["final_scores_combined"] = combined_results["final_scores_combined"]
    # FIX: Correctly save the combined summary under the expected key
    full_score_data["summary_of_combined_best"] = combined_results["summary_of_combined_best"] #
    full_score_data["response_time_combined"] = combined_results["response_time"]

    with open(combined_score_file_path, "w", encoding='utf-8') as f:
        json.dump(full_score_data, f, indent=2)

    logger.info(f"Combined evaluation results saved to {combined_score_file_path}")

    return combined_results