## AqeedAI Project Documentation

### Overview
- **Backend**: FastAPI service (entrypoint `backend/main.py`, app instance `app`) exposing the core APIs.
- **Frontend**: React app in `frontend/` (Create React App).
- **Infra**: Redis and Qdrant used for async jobs and vector search; Docker Compose for local orchestration; GitHub Actions for AWS/GCP deployment.

## Running with Docker (`docker-compose.yaml`)

### Prerequisites
- **Docker** and **Docker Compose** installed.
- Project-level **`.env`** file in the repository root with all required secrets and configuration.
- (Optional but recommended) A local **`.credentials`** directory if you use Google Drive or other external integrations.

### Start the full stack
- **From the project root**:

```bash
cd AqeedAI
docker compose up -d --build    # or: docker-compose up -d --build
```

- This will start:
  - **Redis** on `6379`
  - **Qdrant** on `6333`
  - **Backend (FastAPI)** on `8000`
  - **Frontend (React)** on `3000`

### Accessing services
- **Frontend UI**: `http://localhost:3000`
- **Backend API root**: `http://localhost:8000/api`
- **FastAPI docs**: `http://localhost:8000/api/docs`

### Stopping the stack

```bash
cd AqeedAI
docker compose down    # or: docker-compose down
```

## Running Backend and Frontend Locally (without Docker)

### Backend (FastAPI)

- **Create and activate a virtualenv** (Python 3.x), from the project root.

- **Install backend dependencies**:

```bash
pip install -r backend/requirements.txt
```

- Ensure a `.env` file exists in the project root with all necessary environment variables.

- **Run the backend with Uvicorn** (from the project root so `backend.main` is importable and `.env` is found):

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

- The API will be available at:
  - **Base**: `http://localhost:8000/api`
  - **Docs**: `http://localhost:8000/api/docs`

### Frontend (React)

- **Install Node dependencies**:

```bash
cd AqeedAI/frontend
npm install
```

- **Start the development server**:

```bash
npm start
```

- The app will run at `http://localhost:3000` and will call the backend at `http://localhost:8000` (configured via `src/services/api.js` and build args).

## CI/CD: Automatic Deployment to AWS and GCP

- The repository contains two GitHub Actions workflows in `.github/workflows/`:
  - **`deploy-aws.yml`**: Deploys to an AWS EC2 instance using `docker-compose-aws.yaml`.
  - **`deploy-gcp.yml`**: Deploys to a GCP Compute Engine instance using `docker-compose-gcp.yaml`.

- **Trigger**:
  - Any **push to the `main` branch** triggers **both** workflows.

- **What the workflows do (high level)**:
  - SSH into the target EC2/GCE instance using SSH keys stored in GitHub **Secrets**.
  - Install Docker and Docker Compose if needed.
  - Clone the latest `main` branch of this repository.
  - Write the remote `.env` file from the `ENV_FILE` GitHub secret into the project root.
  - Run `docker compose -f docker-compose-aws.yaml up -d --build` (AWS) or
    `docker compose -f docker-compose-gcp.yaml up -d --build` (GCP).

- **Result**:
  - When you **push to `main`**, the application is automatically rebuilt and redeployed on both **AWS** and **GCP**, using the Docker Compose configurations for each cloud.


