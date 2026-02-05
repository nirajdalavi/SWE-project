# services/helper_service.py
import json
import re
from collections import defaultdict
from pathlib import Path # Added for path handling if needed in future

def extract_criteria_from_jsonl(file_path, outpath):
    """
    Extracts structured criteria from a .jsonl file and saves it to a JSON file.
    It parses text content using regex to find serial, criteria, and weightage.
    """
    parsed_data = []
    if not Path(file_path).exists():
        print(f"Warning: Criteria JSONL file not found at {file_path}. Skipping criteria extraction.")
        # Return an empty list or raise an error, depending on desired behavior
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                parsed_data.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"Warning: Skipping malformed JSON line in {file_path}: {line.strip()} - {e}")
                continue

    # Extract structured info from the 'text' field using regex
    # Pattern for sub-criteria (e.g., 1a, 2b)
    pattern = re.compile(r"^\s*(\d+[a-zA-Z]?)\s+(.*?)\s+(\d+\.\d{2})$", re.MULTILINE)
    # Pattern for top-level criteria (e.g., 1, 2)
    top_level_pattern = re.compile(r"^\s*(\d+)\s+(.*?)\s+(\d+\.\d{2})$", re.MULTILINE)
    
    sub_criteria_by_parent = defaultdict(list)
    top_level_entries = {}

    for entry in parsed_data:
        text = entry.get("text", "") # Use .get() for safety
        if not text:
            continue

        # Find sub-criteria
        for serial, criteria, weight in pattern.findall(text):
            # Extract parent number (e.g., '1' from '1a')
            parent_match = re.match(r"^(\d+)", serial)
            if parent_match:
                parent = parent_match.group(1)
                cleaned_criteria = criteria.replace("NaN", "").strip()
                sub_criteria_by_parent[parent].append({
                    "serial": serial.strip(),
                    "criteria": cleaned_criteria,
                    "weightage": float(weight)
                })

        # Find top-level criteria
        for serial, criteria, weight in top_level_pattern.findall(text):
            cleaned_criteria = criteria.replace("NaN", "").strip()
            top_level_entries[serial.strip()] = {
                "serial": serial.strip(),
                "criteria": cleaned_criteria,
                "weightage": float(weight)
            }

    all_criteria = []

    for parent, subs in sub_criteria_by_parent.items():
        all_criteria.extend(subs)

    all_criteria = [c for c in all_criteria if not c['serial'].isdigit()]

    for serial, entry in top_level_entries.items():
        if serial not in sub_criteria_by_parent and not serial.isdigit():
            all_criteria.append(entry)

    if not all_criteria:
        # Fallback: return original parsed_data if structured extraction failed
        all_criteria = parsed_data
    # Save the extracted criteria to a JSON file
    Path(outpath).parent.mkdir(parents=True, exist_ok=True) # Ensure output directory exists
    with open(outpath, "w", encoding="utf-8") as out_file:
        json.dump(all_criteria, out_file, indent=2)

    return all_criteria

# The `if __name__ == "__main__":` block is removed as this is now a service module.