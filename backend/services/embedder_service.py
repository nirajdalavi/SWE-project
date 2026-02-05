import os
import json
import hashlib
from pathlib import Path
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from langchain.text_splitter import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Qdrant config from .env
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))


def run_embedding_for_workspace(workspace: str, select_parsed: str, base_dir: Path):
    """
    Generates embeddings for new documents and upserts them to Qdrant.
    Now uses a consistent `base_dir` passed from `main.py`.
    """
    input_file = base_dir / "data" / workspace / select_parsed
    manifest_path = base_dir / "data" / workspace / "embedder" / "manifest.json"
    
    collection_name = f"contract_docs_{workspace}"

    manifest = set()
    if os.path.exists(manifest_path):
        with open(manifest_path, "r") as f:
            manifest = set(json.load(f))

    raw_docs = []
    if not os.path.exists(input_file):
        print(f"⚠️  Parsed input file not found: {input_file}")
        return {"status": "error", "message": f"Parsed input file not found: {input_file}"}

    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            doc = json.loads(line)
            if doc["file"] not in manifest:
                raw_docs.append(doc)

    if not raw_docs:
        print("✅ No new files to embed.")
        return {"status": "ok", "message": "No new files to embed."}

    # Chunk documents
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=50)
    docs = []
    for doc in raw_docs:
        chunks = text_splitter.split_text(doc["text"])
        for chunk in chunks:
            docs.append({
                "text": chunk,
                "file": doc["file"],
                "page": doc.get("page", 1),
                "source_type": doc.get("source_type", Path(doc["file"]).suffix.lower().lstrip("."))
            })

    # Generate embeddings
    texts = [doc["text"] for doc in docs]
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(texts)

    # Connect to Qdrant
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    if not client.collection_exists(collection_name):
        try:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=len(embeddings[0]), distance=Distance.COSINE),
            )
        except Exception as e:
            return {"status": "error", "message": f"Failed to create collection '{collection_name}': {e}"}

    # Upsert points
    points = []
    for i, (text, embedding) in enumerate(zip(texts, embeddings)):
        points.append(
            PointStruct(
                id=int(hashlib.md5(text.encode()).hexdigest()[:8], 16),
                vector=embedding.tolist(),
                payload={
                    "text": text,
                    "source_file": docs[i]["file"],
                    "page": docs[i]["page"],
                    "source_type": docs[i]["source_type"]
                }
            )
        )

    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        client.upsert(collection_name=collection_name, points=batch)

    new_files = {doc["file"] for doc in raw_docs}
    updated_manifest = list(manifest.union(new_files))
    os.makedirs(manifest_path.parent, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(updated_manifest, f, indent=2)

    return {"status": "ok", "message": f"Uploaded {len(points)} chunks to Qdrant collection '{collection_name}'."}


def sync_embedder_manifest(workspace: str, base_dir: Path):
    """
    Synchronizes the embedder manifest with parsed files to track changes.
    """
    parsed_manifest_path = base_dir / "data" / workspace / "manifest.jsonl"
    embedder_manifest_path = base_dir / "data" / workspace / "embedder" / "manifest.json"

    parsed_files = set()
    if os.path.exists(parsed_manifest_path):
        with open(parsed_manifest_path, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    parsed_files.add(entry.get("file"))
                except json.JSONDecodeError:
                    continue

    embedder_manifest = set()
    if os.path.exists(embedder_manifest_path):
        with open(embedder_manifest_path, "r") as f:
            embedder_manifest = set(json.load(f))

    updated_manifest = list(parsed_files.intersection(embedder_manifest))
    os.makedirs(embedder_manifest_path.parent, exist_ok=True)
    with open(embedder_manifest_path, "w") as f:
        json.dump(updated_manifest, f, indent=2)

    return {"status": "ok", "message": f"Synchronized embedder manifest for workspace '{workspace}'."}
