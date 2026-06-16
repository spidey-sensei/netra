from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import os
import uuid
import json
from datetime import datetime

from detector import detect_bank
from llm_call import process_question
from detector import detect_document_type
from extractor import extract_document
from s3_management import load_latest_prompt

import boto3
from botocore.exceptions import ClientError

# ─────────────────────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────────────────────

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────
# S3 CLIENT (LocalStack)
# ─────────────────────────────────────────────────────────────

BUCKET_NAME = "netra-bucket"

s3 = boto3.client(
    "s3",
    endpoint_url="http://localhost:4566",
    aws_access_key_id="test",
    aws_secret_access_key="test",
    region_name="us-east-1",
)


def ensure_bucket():
    try:
        s3.create_bucket(Bucket=BUCKET_NAME)
    except Exception:
        pass


@app.on_event("startup")
def startup():
    ensure_bucket()


# ─────────────────────────────────────────────────────────────
# UPLOAD DIR
# ─────────────────────────────────────────────────────────────

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

uploaded_files: dict[str, dict] = {}

# ─────────────────────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────────────────────


class QuestionRequest(BaseModel):
    file_id: str
    question: str


class PromptCreateRequest(BaseModel):
    prompt_text: str
    author: str = "admin"


# ─────────────────────────────────────────────────────────────
# HEALTH
# ─────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "running"}


# ─────────────────────────────────────────────────────────────
# UPLOAD
# ─────────────────────────────────────────────────────────────


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1].lower()

    file_path = os.path.join(
        UPLOAD_DIR,
        f"{file_id}{ext}"
    )

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    pages = extract_document(file_path)

    document_type = detect_document_type(pages)

    bank_name = None

    if document_type == "bank":
        bank_name = detect_bank(pages)

    uploaded_files[file_id] = {
    "path": file_path,
    "document_type": document_type,
    "bank_name": bank_name,
    "pages": pages
}

    if document_type == "bank":

        prompt = load_latest_prompt(
            f"bank/{bank_name}"
        )

    else:

        prompt = load_latest_prompt(
            "aadhaar"
        )

    return {
        "file_id": file_id,
        "document_type": document_type,
        "bank_name": bank_name,
        "active_prompt": prompt
    }

    




# ─────────────────────────────────────────────────────────────
# QUESTION
# ─────────────────────────────────────────────────────────────

@app.post("/question")
async def ask_question(request: QuestionRequest):

    doc = uploaded_files.get(request.file_id)

    if not doc:
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )

    return process_question(
        file_path=doc["path"],
        question=request.question,
        document_type=doc["document_type"],
        bank_name=doc.get("bank_name")
    )


# ─────────────────────────────────────────────────────────────
# S3 HELPERS — generic module (bank / aadhar)
# ─────────────────────────────────────────────────────────────


def _s3_get_stable(module: str):
    try:
        resp = s3.get_object(Bucket=BUCKET_NAME, Key=f"prompts/{module}/stable.json")
        data = json.loads(resp["Body"].read())
        return data.get("version")
    except ClientError:
        return None

def _s3_set_stable(module: str, version: str):
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=f"prompts/{module}/stable.json",
        Body=json.dumps({"version": version}).encode(),
        ContentType="application/json",
    )


def _s3_list_versions(module: str):
    prefix   = f"prompts/{module}/"
    response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
    versions = set()
    for obj in response.get("Contents", []):
        key   = obj["Key"].replace(prefix, "")
        parts = key.split("/")
        if len(parts) >= 2 and parts[0] != "stable.json":
            versions.add(parts[0])
    return sorted(versions)


def _s3_load_prompt(module: str, version: str) -> str:
    resp = s3.get_object(
        Bucket=BUCKET_NAME,
        Key=f"prompts/{module}/{version}/prompt.txt",
    )
    return resp["Body"].read().decode("utf-8")


def _s3_load_metadata(module: str, version: str) -> dict:
    try:
        resp = s3.get_object(
            Bucket=BUCKET_NAME,
            Key=f"prompts/{module}/{version}/metadata.json",
        )
        return json.loads(resp["Body"].read())
    except Exception:
        return {}


def _s3_save_version(module: str, version: str, prompt_text: str, author: str):
    metadata = {
        "module":     module,
        "version":    version,
        "created_at": datetime.utcnow().isoformat(),
        "created_by": author,
    }
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=f"prompts/{module}/{version}/prompt.txt",
        Body=prompt_text.encode("utf-8"),
        ContentType="text/plain",
    )
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=f"prompts/{module}/{version}/metadata.json",
        Body=json.dumps(metadata, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


def _increment(version: str) -> str:
    try:
        parts    = version.split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)
    except Exception:
        return "1.0.1"


# ─────────────────────────────────────────────────────────────
# PROMPT MANAGEMENT ROUTES
# ─────────────────────────────────────────────────────────────


@app.get("/prompts/{module:path}/versions")
def get_versions(module: str):
    versions = _s3_list_versions(module)
    return {"versions": versions}


@app.get("/prompts/{module:path}/stable")
def get_stable(module: str):

    version = _s3_get_stable(module)

    if not version:
        raise HTTPException(
            status_code=404,
            detail="No stable version found"
        )

    meta = _s3_load_metadata(module, version)

    prompt = _s3_load_prompt(
        module,
        version
    )

    return {
        "version": version,
        "prompt": prompt,
        **meta
    }

@app.get("/prompts/{module:path}/{version}")
def get_prompt_version(module: str, version: str):
    try:
        content = _s3_load_prompt(module, version)
        meta    = _s3_load_metadata(module, version)
        return {"version": version, "content": content, **meta}
    except ClientError:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")


@app.post("/prompts/{module:path}/create")
def create_version(module: str, request: PromptCreateRequest):
    if not request.prompt_text.strip():
        raise HTTPException(status_code=400, detail="Prompt text cannot be empty")

    current = _s3_get_stable(module)
    new_ver = "1.0.0" if current is None else _increment(current)

    _s3_save_version(module, new_ver, request.prompt_text, request.author)
    _s3_set_stable(module, new_ver)

    return {"version": new_ver, "module": module, "status": "created"}


@app.post("/prompts/{module:path}/{version}/activate")
def activate_version(module: str, version: str):
    # Verify the version actually exists first
    try:
        s3.head_object(
            Bucket=BUCKET_NAME,
            Key=f"prompts/{module}/{version}/prompt.txt",
        )
    except ClientError:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")

    _s3_set_stable(module, version)
    return {"version": version, "module": module, "status": "activated"}


@app.delete("/prompts/{module:path}/{version}")
def delete_version(module: str, version: str):
    stable = _s3_get_stable(module)
    if stable == version:
        raise HTTPException(status_code=400, detail="Cannot delete the currently stable version")

    prefix   = f"prompts/{module}/{version}/"
    response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
    objects  = [{"Key": obj["Key"]} for obj in response.get("Contents", [])]

    if not objects:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")

    s3.delete_objects(Bucket=BUCKET_NAME, Delete={"Objects": objects})
    return {"version": version, "module": module, "status": "deleted"}




