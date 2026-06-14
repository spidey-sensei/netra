from pypdf import PdfReader
import ollama
import boto3
import json
from botocore.exceptions import ClientError

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

# ─────────────────────────────────────────
#  BANK DETECTION KEYWORDS
# ─────────────────────────────────────────
BANK_KEYWORDS = {
    "SBI":          ["state bank of india"],
    "HDFC":         ["hdfc bank"],
    "Union_bank":   ["union bank of india", "unionbankofindia.co.in", "union bank bhavan"],
    "Bank_Baroda":  ["bank of baroda", "barb0", "ifsc code-barb"],
    "ICICI":        ["icici bank"],
    "Axis":         ["axis bank"],
    "Kotak":        ["kotak mahindra"],
    "PNB":          ["punjab national bank"],
    "Canara":       ["canara bank"],
    "BOI":          ["bank of india"],
}

# Canonical S3 bank folder names (must match what main.py / MODULE_MAP uses)
# Key = detected bank name, Value = S3 folder under prompts/bank/
BANK_TO_S3_FOLDER = {
    "SBI":          "SBI",
    "HDFC":         "HDFC",
    "Union_bank":   "Union_bank",
    "Bank_Baroda":  "Bank_Baroda",
    "ICICI":        "ICICI",
    "Axis":         "Axis",
    "Kotak":        "Kotak",
    "PNB":          "PNB",
    "Canara":       "Canara",
    "BOI":          "BOI",
    "Generic":      "Generic",
}

DEFAULT_PROMPT = """You are a bank statement assistant.

Rules:
- Answer only from the document.
- Return exact value from the statement.
- Never return blank.
- If answer is not found, return NOT_FOUND.
"""


# ─────────────────────────────────────────
#  STEP 1 — Extract text page by page
# ─────────────────────────────────────────
def extract_text(pdf_path):
    print(f"\n[Step 1] Extracting text from: {pdf_path}")
    reader = PdfReader(pdf_path)
    pages  = []
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            pages.append(extracted)
    print(f"         Pages extracted: {len(pages)}")
    return pages


# ─────────────────────────────────────────
#  STEP 2 — Detect bank
# ─────────────────────────────────────────
def detect_bank(pages):
    print(f"\n[Step 2] Detecting bank...")
    full_text = "\n".join(pages).lower()
    for bank_name, keywords in BANK_KEYWORDS.items():
        if any(k in full_text for k in keywords):
            print(f"         Detected: {bank_name}")
            return bank_name
    print(f"         Not detected → Generic")
    return "Generic"


# ─────────────────────────────────────────
#  STEP 3 — Load stable prompt from S3
#           Uses versioned folder structure:
#           prompts/bank/{BankFolder}/stable.json
#           prompts/bank/{BankFolder}/{version}/prompt.txt
# ─────────────────────────────────────────
def load_prompt_from_s3(bank_name: str) -> str:
    s3_folder_name = BANK_TO_S3_FOLDER.get(bank_name, "Generic")

    # ── 1. Read stable.json ──────────────────────────────────
    stable_key = f"{S3_FOLDER}/{s3_folder_name}/stable.json"
    try:
        response = s3.get_object(Bucket=BUCKET, Key=stable_key)
        stable_data = json.loads(response["Body"].read().decode("utf-8"))
        version = stable_data.get("version")
        if not version:
            raise ValueError("stable.json has no 'version' key")
        print(f"[Step 3] Stable version for {bank_name}: {version}")
    except ClientError as e:
        print(f"[Step 3] stable.json not found for {bank_name} ({stable_key}): {e}")
        # Fallback: try Generic
        if s3_folder_name != "Generic":
            print(f"[Step 3] Falling back to Generic prompt")
            return load_prompt_from_s3("Generic")
        return DEFAULT_PROMPT
    except Exception as e:
        print(f"[Step 3] Unexpected error reading stable.json: {e}")
        return DEFAULT_PROMPT

    # ── 2. Read prompt.txt for that version ──────────────────
    prompt_key = f"{S3_FOLDER}/{s3_folder_name}/{version}/prompt.txt"
    try:
        response = s3.get_object(Bucket=BUCKET, Key=prompt_key)
        prompt   = response["Body"].read().decode("utf-8")
        print(f"[Step 3] Prompt loaded from {prompt_key} ({len(prompt)} chars)")
        return prompt
    except ClientError as e:
        print(f"[Step 3] prompt.txt not found ({prompt_key}): {e}")
        return DEFAULT_PROMPT
    except Exception as e:
        print(f"[Step 3] Unexpected error reading prompt.txt: {e}")
        return DEFAULT_PROMPT


# ─────────────────────────────────────────
#  STEP 4 — Select relevant chunk
# ─────────────────────────────────────────
def get_relevant_text(pages, question):
    q = question.lower()

    detail_keywords = [
        "account holder", "account name", "customer name",
        "account number", "account no", "account type",
        "ifsc", "micr", "cif", "email", "currency",
        "available balance", "opening balance", "closing balance",
        "address", "branch", "statement period",
        "statement date", "account description",
    ]
    transaction_keywords = [
        "transaction", "debit", "credit", "total",
        "how many", "list", "spent", "received",
        "transfer", "upi", "neft", "rtgs", "imps",
        "date", "particular date", "between",
        "highest", "lowest", "average", "month",
    ]

    if any(k in q for k in detail_keywords):
        print(f"         → first + last page (details/balance)")
        if len(pages) == 1:
            return pages[0]
        return pages[0] + "\n" + pages[-1]
    elif any(k in q for k in transaction_keywords):
        print(f"         → all pages (transactions)")
        return "\n".join(pages)
    else:
        print(f"         → first + last page (default)")
        if len(pages) == 1:
            return pages[0]
        return pages[0] + "\n" + pages[-1]


# ─────────────────────────────────────────
#  STEP 5 — Ask model
# ─────────────────────────────────────────
def ask_model(prompt, relevant_text, question):
    print(f"\n[Step 5] Asking {MODEL}...")
    try:
        response = ollama.chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": (
                        f"Question:\n{question}\n\n"
                        f"Document:\n{relevant_text}\n\n"
                        "Give a direct answer only. "
                        "If answer exists in document, return exact value. "
                        "Do not return blank."
                    ),
                },
            ],
        )

        answer = response.get("message", {}).get("content", "").strip()
        if not answer:
            answer = "NOT_FOUND"

        print(f"\nANSWER = {repr(answer)}")
        return answer

    except Exception as e:
        print("OLLAMA ERROR:", str(e))
        return f"OLLAMA ERROR: {str(e)}"


# ─────────────────────────────────────────
#  MAIN — called by main.py
# ─────────────────────────────────────────
def process(pdf_path, question):
    print(f"\n{'='*50}")
    print(f"PDF      : {pdf_path}")
    print(f"Question : {question}")
    print(f"{'='*50}")

    pages         = extract_text(pdf_path)
    bank_name     = detect_bank(pages)
    prompt        = load_prompt_from_s3(bank_name)

    print("\nPROMPT LOADED (first 500 chars):")
    print(prompt[:500])

    relevant_text = get_relevant_text(pages, question)

    print("\nRELEVANT TEXT SAMPLE:")
    print(relevant_text[:1000])

    answer = ask_model(prompt, relevant_text, question)

    return {
        "bank":     bank_name,
        "question": question,
        "answer":   answer,
    }


# ─────────────────────────────────────────
#  TEST
# ─────────────────────────────────────────
if __name__ == "__main__":
    test_questions = [
        "What is the account holder name",
        "What is the account number",
        "What is the IFSC code",
        "What is the account type",
        "What is the available balance",
        "What is the statement period",
        "What is the total debit amount",
        "What is the total credit amount",
    ]

    for q in test_questions:
        result = process(pdf_path="Data/SBI bank statment.pdf", question=q)
        print(f"\nQ: {result['question']}")
        print(f"A: {result['answer']}")
        print("-" * 40)
