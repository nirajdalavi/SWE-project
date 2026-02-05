# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies including build tools
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    gcc \
    g++ \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file and install dependencies
COPY requirements.txt ./
RUN pip install git+https://github.com/openai/whisper.git
RUN pip install --only-binary=all -r requirements.txt || pip install -r requirements.txt


# Copy the rest of the backend code into the container
COPY . /app/

# Set the port Cloud Run expects
ENV PORT=8000

# Run the FastAPI app on the expected port
CMD uvicorn main:app --host 0.0.0.0 --port $PORT --loop asyncio --timeout-keep-alive 300 --log-level debug

# Install Playwright and Chromium for Crawl4AI
RUN pip install playwright
RUN playwright install --with-deps chromium