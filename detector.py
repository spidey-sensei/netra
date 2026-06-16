import re
import ollama

MODEL = "mistral"


def detect_document_type(pages: list[str]) -> str:
    full_text = "\n".join(pages).lower()

    bank_score = 0
    aadhaar_score = 0

    # ────────────────────────────────────────
    # Bank Statement
    # ────────────────────────────────────────
    bank_keyword = [
        "statement of account",
        "account statement",
        "opening balance",
        "closing balance",
        "withdrawal amt",
        "deposit amt",
        "txn date",
        "account number",
        "ifsc",
    ]

    bank_names = [
        "hdfc",
        "sbi",
        "state bank of india",
        "state bank",
        "union bank",
        "bank of baroda",
        "icici",
        "axis",
        "kotak",
        "kotak mahindra",
        "pnb",
        "canara",
        "hdfc bank",
        "bank of india",
        "punjab national bank"
    ]

    for keyword in bank_keyword:
        if keyword in full_text:
            bank_score += 1

    for bank in bank_names:
        if bank in full_text:
            bank_score += 2

    # ────────────────────────────────────────
    # Aadhaar
    # ────────────────────────────────────────

    aadhaar_keywords = [
        "aadhaar",
        "aadhar",
        "uidai",
        "government of india",
        "govt of india",
        "male",
        "female",
        "dob",
        "year of birth",
    ]
    for keyword in aadhaar_keywords:
        if keyword in full_text:
            aadhaar_score += 1

    aadhaar_match = re.search(
    r"\b\d{4}\s?\d{4}\s?\d{4}\b",
    full_text
)

    if aadhaar_match:
        aadhaar_score += 5

    print(
    f"Bank score={bank_score}, Aadhaar score={aadhaar_score}"
)

    if bank_score >= 3:
        return "bank"

    if aadhaar_score >= 4:
        return "aadhaar"

    return "unknown"

BANK_KEYWORDS = {
    "sbi_bank":          ["state bank of india"],
    "hdfc":         ["hdfc bank"],
    "union_bank":   ["union bank of india", "unionbankofindia.co.in", "union bank bhavan"],
    "bank_of_baroda":  ["bank of baroda", "barb0", "ifsc code-barb"],
    "ICICI":        ["icici bank"],
    "Axis":         ["axis bank"],
    "Kotak":        ["kotak mahindra"],
    "PNB":          ["punjab national bank"],
    "Canara":       ["canara bank"],
    "BOI":          ["bank of india"],
}

def detect_bank(pages):
    print(f"\n[Step 2] Detecting bank...")
    full_text = "\n".join(pages).lower()
    for bank_name, keywords in BANK_KEYWORDS.items():
        if any(k in full_text for k in keywords):
            print(f"         Detected: {bank_name}")
            return bank_name
    print(f"         Not detected → Generic")
    return "generic"
