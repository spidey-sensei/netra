import boto3
import json
from datetime import datetime
from botocore.exceptions import ClientError

s3 = boto3.client(
    "s3",
    endpoint_url="http://localhost:4566",
    aws_access_key_id="test",
    aws_secret_access_key="test",
    region_name="us-east-1"
)
BUCKET_NAME = "netra-bucket"

def create_bucket():
    try:
        s3.create_bucket(Bucket=BUCKET_NAME)
        print(f"Bucket {BUCKET_NAME} created")
    except Exception as e:
        print(e)

def get_stable_version(document_type):
    try:
        response = s3.get_object(
            Bucket=BUCKET_NAME,
            Key=f"prompts/{document_type}/stable.json"
        )
        data = json.loads(
            response["Body"].read()
        )

        return data["version"]

    except ClientError:
        return None
    
def increment_version(version):
    major, minor, patch = map(int, version.split("."))
    patch+=1
    return f"{major}.{minor}.{patch}"

def save_user_prompt(
    document_type,
    prompt_text,
    author="frontend_user"
):
    if not prompt_text.strip():
        raise ValueError("Prompt cannot be empty")

    current_version = get_stable_version(document_type)

    if current_version is None:
        new_version = "1.0.0"
    else:
        new_version = increment_version(current_version)

    metadata = {
        "document_type": document_type,
        "version": new_version,
        "created_at": datetime.utcnow().isoformat(),
        "created_by": author,
        "prompt_length": len(prompt_text)
    }

    try:
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=f"prompts/{document_type}/{new_version}/prompt.txt",
            Body=prompt_text
        )

        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=f"prompts/{document_type}/{new_version}/metadata.json",
            Body=json.dumps(metadata, indent=4)
        )

        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=f"prompts/{document_type}/stable.json",
            Body=json.dumps({
                "version": new_version
            })
        )

        print(
            f"Prompt saved successfully: "
            f"{document_type} -> {new_version}"
        )

        return new_version

    except Exception as e:
        print(f"Failed to save prompt: {e}")
        raise

def load_latest_prompt(document_type):
    version = get_stable_version(document_type)

    print("Document Type:", document_type)
    print("Stable Version:", version)

    if version is None:
        return ""
    try:
        response = s3.get_object(
            Bucket=BUCKET_NAME,
            Key=f"prompts/{document_type}/{version}/prompt.txt"
        )

        return response["Body"].read().decode()

    except Exception:
        return ""

def list_versions(document_type):
    response = s3.list_objects_v2(
        Bucket=BUCKET_NAME,
        Prefix=f"prompts/{document_type}/"
    )

    versions = []

    for obj in response.get("Contents", []):
        key = obj["Key"]
        parts = key.split("/")

        if len(parts) >=3:
            version = parts[2]

            if version!="stable.json":
                versions.append(version)

    return sorted(list(set(versions)))

def load_version(document_type, version):
    response = s3.get_object(
        Bucket = BUCKET_NAME,
        Key = f"prompts/{document_type}/{version}/prompt.txt"
    )

    return (response["Body"].read().decode("utf-8"))

def load_internal_prompt(document_type):
    filepath = (f"documents/{document_type}/{document_type}.txt")

    with open(filepath, "r") as file:
        return file.read()
    
def build_final_prompt(document_type):
    internal_prompt = load_internal_prompt(document_type)
    user_prompt = load_latest_prompt(document_type)

    return f"""
        {internal_prompt}

        USER CONFIGURED PROMPT
        {user_prompt}
        """

