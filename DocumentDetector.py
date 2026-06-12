import re
import ollama

MODEL = "mistral"


def detect_document_type(pages):
    print("\n[Document Detector] Detecting document type...")

    full_text = "\n".join(pages).lower()

    print("\n====== EXTRACTED TEXT ======")
    print(full_text)
    print("============================")

    # ────────────────────────────────────────
    # Bank Statement
    # ────────────────────────────────────────
    if any(k in full_text for k in [
        "statement of account",
        "account statement",
        "opening balance",
        "closing balance",
        "withdrawal amt",
        "deposit amt",
        "txn date",
        "account number",
        "ifsc",
        "hdfc bank",
        "state bank of india",
        "union bank",
        "bank of baroda",
        "icici bank",
        "axis bank",
        "kotak mahindra",
        "punjab national bank",
        "canara bank",
        "bank of india"
    ]):
        print("Detected: bank_statement")
        return "bank_statement"

    # ────────────────────────────────────────
    # Aadhaar
    # ────────────────────────────────────────
    aadhaar_number = re.search(
        r"\b\d{4}\s?\d{4}\s?\d{4}\b",
        full_text
    )

    if (
        aadhaar_number and
        (
            "male" in full_text
            or "female" in full_text
            or "uidai" in full_text
            or "government of india" in full_text
            or "aadhaar" in full_text
            or "aadhar" in full_text
        )
    ):
        print("Detected: aadhaar")
        return "aadhaar"

    # ────────────────────────────────────────
    # Unknown
    # ────────────────────────────────────────
    print("Detected: unknown")
    return "unknown"