# DAGs Folder – Apache Airflow Workflows

This folder contains all custom DAGs (Directed Acyclic Graphs) used for orchestrating workflows in Apache Airflow.

## 📁 Folder Structure

```
dags/
├── score_to_csv_email_dag.py   # DAG to convert JSON score output to CSV & DOCX, and send via email
├── __init__.py                 # Makes the DAGs directory a package
```

## 📌 DAG: `score_to_csv_email_dag`

This DAG is triggered by an external API call and performs the following steps:

1. **Reads** a JSON score file from the configured `score_output_path`
2. **Generates**:
   - Vendor-wise CSVs (`openrouter.csv`, `chatgpt.csv`)
   - A combined CSV (`final_scores.csv`)
   - A summary report in DOCX format
3. **Simulates** email approval step (placeholder)
4. **Simulates** final output sent to client (placeholder)

### 📤 Trigger Payload Example

```json
{
  "workspace_name": "amazon",
  "score_output_path": "/app/data/amazon/last_score.json"
}
```