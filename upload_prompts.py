import boto3
from botocore.exceptions import ClientError
import json
import os
from datetime import datetime



# ─────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────
BUCKET    = "netra-bucket"
S3_FOLDER = "prompts/bank"

s3 = boto3.client(
    "s3",
    endpoint_url          = "http://localhost:4566",
    aws_access_key_id     = "test",
    aws_secret_access_key = "test",
    region_name           = "us-east-1"
)

# Add this after s3 = boto3.client(...)
def create_bucket_if_not_exists():
    try:
        s3.head_bucket(Bucket=BUCKET)
    except ClientError:
        s3.create_bucket(Bucket=BUCKET)
        print(f"Bucket '{BUCKET}' created")

# Call it before anything else
create_bucket_if_not_exists()

BANK_FILES = {
    "SBI":          "Bank/SBI_Bank.txt",
    "HDFC":         "Bank/HDFC_Bank.txt",
    "Union_bank":   "Bank/Union_bank.txt",
    "Bank_Barodra": "Bank/Bank_Barodra.txt",
    "Generic":      "Bank/Generic.txt",
}

DOC_FILES = {
    "Aadhaar": "Aadhaar/Aadhaar.txt",
}

S3_DOC_FOLDER = "prompts/aadhaar"


def upload_doc(doc_name, local_path, make_stable=True, author="admin"):
    if not os.path.exists(local_path):
        print(f"  [SKIP] {local_path} not found locally")
        return None

    with open(local_path, "r", encoding="utf-8") as f:
        prompt_text = f.read()

    try:
        response = s3.get_object(
            Bucket = BUCKET,
            Key    = f"{S3_DOC_FOLDER}/{doc_name}/stable.json"
        )
        current     = json.loads(response["Body"].read())["version"]
        new_version = increment_version(current)
    except ClientError:
        new_version = "1.0.0"

    s3.put_object(
        Bucket      = BUCKET,
        Key         = f"{S3_DOC_FOLDER}/{doc_name}/{new_version}/prompt.txt",
        Body        = prompt_text.encode("utf-8"),
        ContentType = "text/plain"
    )

    metadata = {
        "doc":        doc_name,
        "version":    new_version,
        "created_at": datetime.utcnow().isoformat(),
        "created_by": author,
    }
    s3.put_object(
        Bucket      = BUCKET,
        Key         = f"{S3_DOC_FOLDER}/{doc_name}/{new_version}/metadata.json",
        Body        = json.dumps(metadata, indent=4).encode("utf-8"),
        ContentType = "application/json"
    )

    if make_stable:
        s3.put_object(
            Bucket      = BUCKET,
            Key         = f"{S3_DOC_FOLDER}/{doc_name}/stable.json",
            Body        = json.dumps({"version": new_version}).encode("utf-8"),
            ContentType = "application/json"
        )
        print(f"  [OK] {doc_name} → {new_version} uploaded + stable")

    return new_version


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


def increment_version(version):
    major, minor, patch = map(int, version.split("."))
    patch += 1
    return f"{major}.{minor}.{patch}"


def upload_version(bank_name, local_path, make_stable=True, author="admin"):
    if not os.path.exists(local_path):
        print(f"  [SKIP] {local_path} not found locally")
        return None

    with open(local_path, "r", encoding="utf-8") as f:
        prompt_text = f.read()

    current_version = get_stable_version(bank_name)
    if current_version is None:
        new_version = "1.0.0"
    else:
        new_version = increment_version(current_version)

    # Upload prompt.txt
    s3.put_object(
        Bucket      = BUCKET,
        Key         = f"{S3_FOLDER}/{bank_name}/{new_version}/prompt.txt",
        Body        = prompt_text.encode("utf-8"),
        ContentType = "text/plain"
    )

    # Upload metadata.json
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

    print(f"  [OK] {bank_name} → {new_version} uploaded")

    if make_stable:
        s3.put_object(
            Bucket      = BUCKET,
            Key         = f"{S3_FOLDER}/{bank_name}/stable.json",
            Body        = json.dumps({"version": new_version}).encode("utf-8"),
            ContentType = "application/json"
        )
        print(f"  [OK] {bank_name} → stable.json updated to {new_version}")

    return new_version


def promote_to_stable(bank_name, version):
    key = f"{S3_FOLDER}/{bank_name}/{version}/prompt.txt"
    try:
        s3.head_object(Bucket=BUCKET, Key=key)
        s3.put_object(
            Bucket      = BUCKET,
            Key         = f"{S3_FOLDER}/{bank_name}/stable.json",
            Body        = json.dumps({"version": version}).encode("utf-8"),
            ContentType = "application/json"
        )
        print(f"  [OK] {bank_name} → {version} promoted to stable")
    except ClientError:
        print(f"  [FAIL] {bank_name} {version} not found in S3")


def list_versions(bank_name):
    prefix   = f"{S3_FOLDER}/{bank_name}/"
    response = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix)

    versions = []
    for obj in response.get("Contents", []):
        key   = obj["Key"].replace(prefix, "")
        parts = key.split("/")
        if len(parts) >= 2 and parts[0] != "stable.json":
            versions.append(parts[0])

    versions = sorted(list(set(versions)))
    stable   = get_stable_version(bank_name)

    print(f"\n  Versions for {bank_name}:  (stable: {stable})")
    for v in versions:
        marker = " ← stable" if v == stable else ""
        print(f"    {v}{marker}")


def upload_all(make_stable=True):
    print(f"\nUploading all bank prompts...")
    print("=" * 50)
    for bank_name, local_path in BANK_FILES.items():
        upload_version(bank_name, local_path, make_stable=make_stable)
    print("=" * 50)
    print("Done!\n")


def show_all_versions():
    print(f"\nAll versions in S3:")
    print("=" * 50)
    for bank_name in BANK_FILES.keys():
        list_versions(bank_name)
    print("=" * 50)


if __name__ == "__main__":
    # Bank prompts
    upload_all(make_stable=True)

    # Aadhaar prompt
    print("\nUploading Aadhaar prompt...")
    upload_doc("Aadhaar", "Aadhaar/Aadhaar.txt", make_stable=True)

    show_all_versions()