from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import os
import uuid
import boto3
import json
import ollama
from botocore.exceptions import ClientError
from datetime import datetime

from BankStatment import process as bank_process, detect_bank
from DocumentExtractor import extract_text
from Aadhaar          import process as aadhaar_process
from DocumentDetector import detect_document_type

# ─────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────
BUCKET    = "netra-bucket"
S3_FOLDER = "prompts/bank"
MODEL     = "mistral"

s3 = boto3.client(
    "s3",
    endpoint_url          = "http://localhost:4566",
    aws_access_key_id     = "test",
    aws_secret_access_key = "test",
    region_name           = "us-east-1"
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["*"],
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

uploaded_files = {}


# ─────────────────────────────────────────
#  MODELS
# ─────────────────────────────────────────
class QuestionRequest(BaseModel):
    file_id:  str
    question: str

class AddVersionRequest(BaseModel):
    instruction: str
    author:      str = "frontend_user"

class PromoteRequest(BaseModel):
    version: str


# ─────────────────────────────────────────
#  S3 HELPERS
# ─────────────────────────────────────────
def get_stable_version(bank_name):
    try:
        response = s3.get_object(
            Bucket = BUCKET,
            Key    = f"{S3_FOLDER}/{bank_name}/stable.json"
        )
        data = json.loads(response["Body"].read())
        return data["version"]
    except ClientError:
        return None


def get_prompt_text(bank_name, version):
    response = s3.get_object(
        Bucket = BUCKET,
        Key    = f"{S3_FOLDER}/{bank_name}/{version}/prompt.txt"
    )
    return response["Body"].read().decode("utf-8")


def increment_version(version):
    major, minor, patch = map(int, version.split("."))
    patch += 1
    return f"{major}.{minor}.{patch}"


def save_version_to_s3(bank_name, new_version, prompt_text, author, make_stable=False):
    s3.put_object(
        Bucket      = BUCKET,
        Key         = f"{S3_FOLDER}/{bank_name}/{new_version}/prompt.txt",
        Body        = prompt_text.encode("utf-8"),
        ContentType = "text/plain"
    )
    metadata = {
        "bank":       bank_name,
        "version":    new_version,
        "created_at": datetime.utcnow().isoformat(),
        "created_by": author,
        "is_stable":  make_stable
    }
    s3.put_object(
        Bucket      = BUCKET,
        Key         = f"{S3_FOLDER}/{bank_name}/{new_version}/metadata.json",
        Body        = json.dumps(metadata, indent=4).encode("utf-8"),
        ContentType = "application/json"
    )
    if make_stable:
        s3.put_object(
            Bucket      = BUCKET,
            Key         = f"{S3_FOLDER}/{bank_name}/stable.json",
            Body        = json.dumps({"version": new_version}).encode("utf-8"),
            ContentType = "application/json"
        )


# ─────────────────────────────────────────
#  GROUP 1 — PDF Q&A
# ─────────────────────────────────────────

# POST /upload
@app.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")

    file_id = str(uuid.uuid4())
    pdf_path = os.path.join(UPLOAD_DIR, f"{file_id}.pdf")

    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    pages = extract_text(pdf_path)

    # Automatically detect document type
    doc_type = detect_document_type(pages)

    # If bank statement → detect which bank
    bank_name = None
    if doc_type == "bank_statement":
        bank_name = detect_bank(pages)

    uploaded_files[file_id] = {
        "path": pdf_path,
        "doc_type": doc_type,
        "bank": bank_name
    }

    return {
        "file_id": file_id,
        "doc_type": doc_type,
        "bank": bank_name,
        "message": f"Detected: {doc_type}" + (f" → {bank_name}" if bank_name else "")
    }


# POST /question
@app.post("/question")
async def ask_question(request: QuestionRequest):
    file_info = uploaded_files.get(request.file_id)

    if not file_info or not os.path.exists(file_info["path"]):
        raise HTTPException(
            status_code=404,
            detail="File not found. Please upload again."
        )

    doc_type = file_info["doc_type"]
    bank_name = file_info["bank"]
    pdf_path = file_info["path"]

    # Route to correct handler based on document type
    if doc_type == "bank_statement":
        result = bank_process(pdf_path, request.question)

    elif doc_type == "aadhaar":
        result = aadhaar_process(pdf_path, request.question)

    # Future document types
    # elif doc_type == "pan_card":
    #     result = pan_process(pdf_path, request.question)

    # elif doc_type == "gst_return":
    #     result = gst_process(pdf_path, request.question)

    # elif doc_type == "itr":
    #     result = itr_process(pdf_path, request.question)

    # elif doc_type == "audit_report":
    #     result = audit_process(pdf_path, request.question)

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported document type: {doc_type}"
        )

    return {
        "doc_type": doc_type,
        "bank": bank_name,
        "question": request.question,
        "answer": result["answer"]
    }

# ─────────────────────────────────────────
#  GROUP 2 — PROMPT MANAGEMENT
# ─────────────────────────────────────────

# GET /prompt/{bank_name}
@app.get("/prompt/{bank_name}")
def get_prompt(bank_name: str):
    version = get_stable_version(bank_name)
    if version is None:
        raise HTTPException(status_code=404, detail=f"No prompt found for {bank_name}")

    prompt_text = get_prompt_text(bank_name, version)

    return {
        "bank":        bank_name,
        "version":     version,
        "prompt_text": prompt_text
    }


# GET /prompt/{bank_name}/versions
@app.get("/prompt/{bank_name}/versions")
def get_versions(bank_name: str):
    prefix   = f"{S3_FOLDER}/{bank_name}/"
    response = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix)

    versions = []
    for obj in response.get("Contents", []):
        key   = obj["Key"].replace(prefix, "")
        parts = key.split("/")
        if len(parts) >= 2 and parts[0] != "stable.json":
            versions.append(parts[0])

    versions       = sorted(list(set(versions)))
    stable_version = get_stable_version(bank_name)

    return {
        "bank":           bank_name,
        "versions":       versions,
        "stable_version": stable_version
    }


# GET /prompt/{bank_name}/{version}
@app.get("/prompt/{bank_name}/{version}")
def get_prompt_version(bank_name: str, version: str):
    try:
        prompt_text = get_prompt_text(bank_name, version)
        meta_response = s3.get_object(
            Bucket = BUCKET,
            Key    = f"{S3_FOLDER}/{bank_name}/{version}/metadata.json"
        )
        metadata = json.loads(meta_response["Body"].read())
        return {
            "bank":        bank_name,
            "version":     version,
            "prompt_text": prompt_text,
            "metadata":    metadata
        }
    except ClientError:
        raise HTTPException(status_code=404, detail=f"Version {version} not found for {bank_name}")


# POST /prompt/{bank_name}/add-version
@app.post("/prompt/{bank_name}/add-version")
def add_version(bank_name: str, request: AddVersionRequest):
    current_version = get_stable_version(bank_name)
    if current_version is None:
        raise HTTPException(status_code=404, detail=f"No prompt found for {bank_name}")

    current_prompt = get_prompt_text(bank_name, current_version)

    print(f"Updating prompt for {bank_name} with instruction: {request.instruction}")

    ai_response = ollama.chat(
        model = MODEL,
        messages = [
            {
                "role": "system",
                "content": """You are a prompt engineering assistant.
Your job is to update an existing bank statement extraction prompt based on the user's instruction.

RULES:
- Keep all existing rules intact
- Only add or modify what the instruction says
- Keep the same format and structure
- Return ONLY the updated prompt text
- Do not add any explanation or preamble
- Do not wrap in quotes or markdown"""
            },
            {
                "role": "user",
                "content": f"""Current prompt:
{current_prompt}

User instruction:
{request.instruction}

Return the updated prompt only:"""
            }
        ]
    )

    updated_prompt = ai_response["message"]["content"].strip()
    new_version    = increment_version(current_version)

    save_version_to_s3(
        bank_name   = bank_name,
        new_version = new_version,
        prompt_text = updated_prompt,
        author      = request.author,
        make_stable = False
    )

    return {
        "bank":           bank_name,
        "new_version":    new_version,
        "stable_version": current_version,
        "updated_prompt": updated_prompt,
        "message":        f"New version {new_version} created. Current stable is still {current_version}."
    }


# POST /prompt/{bank_name}/promote
@app.post("/prompt/{bank_name}/promote")
def promote_version(bank_name: str, request: PromoteRequest):
    key = f"{S3_FOLDER}/{bank_name}/{request.version}/prompt.txt"
    try:
        s3.head_object(Bucket=BUCKET, Key=key)
        s3.put_object(
            Bucket      = BUCKET,
            Key         = f"{S3_FOLDER}/{bank_name}/stable.json",
            Body        = json.dumps({"version": request.version}).encode("utf-8"),
            ContentType = "application/json"
        )
        return {
            "bank":    bank_name,
            "version": request.version,
            "message": f"{request.version} is now stable. App will use this prompt."
        }
    except ClientError:
        raise HTTPException(status_code=404, detail=f"Version {request.version} not found")


# GET /health
@app.get("/health")
def health():
    return {"status": "running"}
