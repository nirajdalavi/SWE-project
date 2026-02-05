# AqeedAI

AqeedAI
uvicorn main:app --reload --host 0.0.0.0 --port 8000 --loop asyncio --timeout-keep-alive 300 --log-level debug
## 📁 Directory Layout

```
|__ .github/workflows        # workflows
├── backend/                 # Backend services 
├── config/                  # Airflow and service configuration files (e.g., airflow.cfg)
├── dags/                    # Airflow DAGs for workflow orchestration
├── data/                    # Input/output data (score JSONs, generated CSVs, DOCX files)
├── frontend/                # UI components
├── logs/                    # logs
├── plugins/                 # Custom Airflow plugins (hooks, sensors, operators)
├── .env                     # Not pushed to repo — required for local setup
└── docker-compose.yaml      # Docker Compose configuration for full Airflow stack
```

---

## 🔐 `.env` File (Required for Local Setup)

This file stores environment-specific secrets and runtime config.

Although not pushed to version control, you must create a `.env` file at the root with the following:

```env
OPENROUTER_API_KEY=<your_openrouter_api_key>
OPENAI_API_KEY=<your_openai_key>
HF_TOKEN=<your_huggingface_token>
AIRFLOW_UID=50000
AIRFLOW_USERNAME=airflow
AIRFLOW_PASSWORD=airflow
AIRFLOW_WEB_SERVER_URL=http://localhost:8080
AIRFLOW_DAG_ID=scoring_and_reporting_workflow
SMTP_USER=your-mail
SMTP_PASSWORD=your-password
SMTP_MAIL_FROM=your-e-mail

Note: Enable Gmail 2FA and then create an AppPassword.
```

> ℹ️ These variables are used by your backend scoring API, Airflow's webserver setup, and for programmatically triggering the DAG.

---

## 🧩 Component Descriptions

- **`dags/`**: Defines the main workflow — reads a JSON score file, generates per-vendor reports (CSV, DOCX), and simulates approval + delivery steps.
- **`data/`**: DAGs read from and write to this folder. Mounts to `/app/data` inside Docker.
- **`logs/`**: Runtime logs from all DAG tasks.
- **`frontend/`**: 
- **`backend/`**: 

---

## 🐳 Docker Compose Usage

Spin up the full stack locally:

```bash
docker-compose down
docker-compose up --build
```

Make sure `.env` is present and valid.

---

## 📦 Extra Python Packages

This project uses `python-docx` for DOCX report generation. It's installed in Docker via:

```yaml
environment:
  _PIP_ADDITIONAL_REQUIREMENTS: "python-docx pandas fpdf wrap XlsxWriter"
```

Add more packages here as needed (e.g., `pandas`, `requests`).

---

## ✅ Triggering the Workflow

The `/score` endpoint in the backend API accepts a JSON payload like:

```json
{
  "criterion": "project understanding",
  "workspace_name": "allyin",
  "max_score": 10
}
```

It saves the output to `data/{workspace}/last_score.json` and triggers the DAG configured via `AIRFLOW_DAG_ID`.

---