from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import os
import uuid

from aadhar_main import process
from s3_management import create_bucket
from s3_management import save_user_prompt
from s3_management import list_versions
from s3_management import load_version

app = FastAPI()

# --------------------------------------------------

# CORS

# --------------------------------------------------

app.add_middleware(
CORSMiddleware,
allow_origins=["*"],
allow_methods=["*"],
allow_headers=["*"],
)

# --------------------------------------------------

# Storage

# --------------------------------------------------

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

uploaded_files = {}

# --------------------------------------------------

# Models

# --------------------------------------------------

class QuestionRequest(BaseModel):
    file_id: str
    question: str

class PromptRequest(BaseModel):
    prompt: str

@app.on_event("startup")
def startup():
    create_bucket()


# --------------------------------------------------

# Root

# --------------------------------------------------

@app.get("/")
def root():
    return {
    "message": "Aadhaar API Running",
    "docs": "/docs"
    }

# --------------------------------------------------

# Health Check

# --------------------------------------------------

@app.get("/health")
def health():
    return {
    "status": "running"
    }

# --------------------------------------------------

# Upload Aadhaar Image

# --------------------------------------------------

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    allowed_extensions = [".jpg", ".jpeg", ".png", "pdf"]

    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, JPEG and PNG files are allowed"
        )

    file_id = str(uuid.uuid4())

    image_path = os.path.join(
        UPLOAD_DIR,
        f"{file_id}{ext}"
    )

    with open(image_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    uploaded_files[file_id] = image_path

    return {
        "file_id": file_id,
        "message": "Aadhaar image uploaded successfully"
    }

# --------------------------------------------------

# Ask Question

# --------------------------------------------------

@app.post("/prompt")
async def save_prompt(request: PromptRequest):
    version = save_user_prompt(
        document_type = "aadhar_card",
        prompt_text = request.prompt
    )
    return {
        "version": version
    }

@app.get("/prompts")
def get_versions():
    versions = list_versions("aadhar_card")

    return {
        "versions": versions
    }

@app.post("/prompts/{version}")
def get_prompt(version: str):
    content = load_version("aadhar_card", version)

    return {
        "version": version,
        "prompt": content
    }


@app.post("/question")
async def ask_question(request: QuestionRequest):
    image_path = uploaded_files.get(
        request.file_id
    )

    if image_path is None:
        raise HTTPException(
            status_code=404,
            detail="File not found. Upload again."
        )

    if not os.path.exists(image_path):
        raise HTTPException(
            status_code=404,
            detail="Image missing on disk."
        )

    result = process(
        image_path=image_path,
        question=request.question
    )

    return {
        "question": result["question"],
        "answer": result["answer"]
    }



