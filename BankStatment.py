import pdfplumber
import ollama
import boto3
import json
import pandas as pd
import re
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
    "Bank_Barodra": ["bank of baroda", "barb0", "ifsc code-barb"],
    "ICICI":        ["icici bank"],
    "Axis":         ["axis bank"],
    "Kotak":        ["kotak mahindra"],
    "PNB":          ["punjab national bank"],
    "Canara":       ["canara bank"],
    "BOI":          ["bank of india"]
}

# ─────────────────────────────────────────
#  BANK CONFIG
# ─────────────────────────────────────────
BANK_CONFIG = {
    "Bank_Barodra": {
        "reverse_order":      False,
        "balance_in_summary": False,
        "opening_label":      "opening balance",
        "closing_label":      "closing balance",
        "debit_keywords":     ["withdrawal", "debit", "dr"],
        "credit_keywords":    ["deposit", "credit", "cr"],
        "balance_keyword":    "balance",
        "amount_type":        "separate"
    },
    "HDFC": {
        "reverse_order":      False,
        "balance_in_summary": True,
        "opening_label":      "opening balance",
        "closing_label":      "closing bal",
        "debit_keywords":     ["withdrawal amt", "withdrawal", "debit"],
        "credit_keywords":    ["deposit amt", "deposit", "credit"],
        "balance_keyword":    "closing balance",
        "amount_type":        "separate"
    },
    "SBI": {
        "reverse_order":      False,
        "balance_in_summary": False,
        "opening_label":      None,
        "closing_label":      None,
        "debit_keywords":     ["debit", "dr"],
        "credit_keywords":    ["credit", "cr"],
        "balance_keyword":    "balance",
        "amount_type":        "separate_suffix"
    },
    "Union_bank": {
        "reverse_order":      True,
        "balance_in_summary": False,
        "opening_label":      None,
        "closing_label":      "closing balance",
        "debit_keywords":     ["dr", "debit"],
        "credit_keywords":    ["cr", "credit"],
        "balance_keyword":    "balance",
        "amount_type":        "single_bracket"
    },
    "Generic": {
        "reverse_order":      False,
        "balance_in_summary": False,
        "opening_label":      "opening balance",
        "closing_label":      "closing balance",
        "debit_keywords":     ["debit", "withdrawal", "dr"],
        "credit_keywords":    ["credit", "deposit", "cr"],
        "balance_keyword":    "balance",
        "amount_type":        "separate"
    }
}

DETAIL_KEYWORDS = [
    "name", "account holder", "account name", "customer name",
    "account number", "account no", "account type",
    "ifsc", "micr", "cif", "email", "currency",
    "address", "branch", "statement period",
    "statement date", "account description",
    "mobile", "phone", "pincode", "customer id"
]

# ─────────────────────────────────────────
#  STEP 1 — Extract text and tables
# ─────────────────────────────────────────
def extract_text_and_tables(pdf_path):
    print(f"\n[Step 1] Extracting from: {pdf_path}")
    pages_text   = []
    pages_tables = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text and len(text.strip()) > 50:
                pages_text.append(text)
                print(f"         Page {i+1}: {len(text)} chars ✓")
            else:
                print(f"         Page {i+1}: EMPTY — skipped")

            tables = page.extract_tables()
            if tables:
                for table in tables:
                    if table and len(table) > 1:
                        pages_tables.extend(table)
                print(f"         Page {i+1}: {len(tables)} table(s) found ✓")

    print(f"         Total text pages : {len(pages_text)}")
    print(f"         Total table rows : {len(pages_tables)}")
    return pages_text, pages_tables


# ─────────────────────────────────────────
#  STEP 2 — Detect bank
# ─────────────────────────────────────────
def detect_bank(pages_text):
    print(f"\n[Step 2] Detecting bank...")
    full_text = "\n".join(pages_text).lower()
    for bank_name, keywords in BANK_KEYWORDS.items():
        if any(k in full_text for k in keywords):
            print(f"         Detected: {bank_name}")
            return bank_name
    print(f"         Not detected → Generic")
    return "Generic"

# ─────────────────────────────────────────
#  STEP 3 — Load prompt from S3
# ─────────────────────────────────────────
def load_prompt_from_s3(bank_name):
    print(f"\n[Step 3] Loading prompt for: {bank_name}")
    try:
        stable_response = s3.get_object(
            Bucket = BUCKET,
            Key    = f"{S3_FOLDER}/{bank_name}/stable.json"
        )
        version = json.loads(stable_response["Body"].read())["version"]
        prompt_response = s3.get_object(
            Bucket = BUCKET,
            Key    = f"{S3_FOLDER}/{bank_name}/{version}/prompt.txt"
        )
        prompt = prompt_response["Body"].read().decode("utf-8")
        print(f"         Prompt loaded: {len(prompt)} chars")
        return prompt
    except ClientError:
        print(f"         Falling back to Generic prompt")
        stable_response = s3.get_object(
            Bucket = BUCKET,
            Key    = f"{S3_FOLDER}/Generic/stable.json"
        )
        version = json.loads(stable_response["Body"].read())["version"]
        prompt_response = s3.get_object(
            Bucket = BUCKET,
            Key    = f"{S3_FOLDER}/Generic/{version}/prompt.txt"
        )
        return prompt_response["Body"].read().decode("utf-8")


# ─────────────────────────────────────────
#  HELPER — Clean amount string to float
# ─────────────────────────────────────────
def clean_amount(value):
    if not value:
        return 0.0
    value = str(value).strip()
    if value in ["-", "", "nan", "None", "null"]:
        return 0.0
    value = re.sub(r"[₹,]", "", value)
    value = re.sub(
        r"\s*(DR|CR|Dr|Cr|\(Dr\)|\(Cr\))\s*",
        "", value, flags=re.IGNORECASE
    )
    value = value.strip()
    try:
        return float(value)
    except:
        return 0.0


# ─────────────────────────────────────────
#  HELPER — Find column indexes from header
# ─────────────────────────────────────────
def find_columns(header_row, bank_config):
    if not header_row:
        return None, None, None, None

    header = [str(h).lower().strip() if h else "" for h in header_row]
    print(f"         Header: {header}")

    debit_col   = None
    credit_col  = None
    balance_col = None
    date_col    = None

    for i, col in enumerate(header):
        # Date column
        if any(k in col for k in ["date", "txn date", "value date"]):
            if date_col is None:
                date_col = i

        # Debit column
        for kw in bank_config["debit_keywords"]:
            if kw in col and debit_col is None:
                debit_col = i
                break

        # Credit column
        for kw in bank_config["credit_keywords"]:
            if kw in col and credit_col is None:
                credit_col = i
                break

        # Balance column
        if bank_config["balance_keyword"] in col and balance_col is None:
            balance_col = i

    print(f"         Cols → date:{date_col} debit:{debit_col} credit:{credit_col} balance:{balance_col}")
    return date_col, debit_col, credit_col, balance_col


# ─────────────────────────────────────────
#  STEP 4 — Build DataFrame from tables
# ─────────────────────────────────────────
def build_dataframe(pages_tables, bank_name):
    print(f"\n[Step 4] Building DataFrame for: {bank_name}")
    config = BANK_CONFIG.get(bank_name, BANK_CONFIG["Generic"])

    if not pages_tables:
        print("         No table rows found!")
        return pd.DataFrame()

    # Find header row
    header_row = None
    header_idx = 0
    for i, row in enumerate(pages_tables):
        if not row:
            continue
        row_text = " ".join(str(c).lower() for c in row if c)
        if (
            any(k in row_text for k in ["balance"]) and
            any(k in row_text for k in ["date", "debit", "credit", "withdrawal", "amount"])
        ):
            header_row = row
            header_idx = i
            print(f"         Header at row {i}: {row}")
            break

    if header_row is None:
        print("         WARNING: No header found — using first row")
        header_row = pages_tables[0]
        header_idx = 0

    # Get column positions
    date_col, debit_col, credit_col, balance_col = find_columns(
        header_row, config
    )

    if balance_col is None:
        print("         WARNING: Balance column not found!")
        return pd.DataFrame()

    # Skip rows keywords
    skip_keywords = [
        "opening balance", "closing balance", "closing bal",
        "statement summary", "total", "page no", "generated",
        "dear", "please", "note", "registered", "branch",
        "narration", "description", "date", "withdrawal",
        "deposit", "debit", "credit", "amount", "balance",
        "txn date", "value date", "ref", "chq", "s.no",
        "transaction id", "remarks"
    ]

    parsed = []

    for row in pages_tables[header_idx + 1:]:
        if not row:
            continue
        if all(c is None or str(c).strip() == "" for c in row):
            continue

        row_text = " ".join(str(c).lower() for c in row if c).strip()

        # Check for opening/closing balance rows — extract but skip adding to df
        if "opening balance" in row_text or "closing bal" in row_text:
            numbers = re.findall(r'[\d,]+\.\d+', row_text)
            if numbers:
                if "opening" in row_text:
                    print(f"         Found Opening Balance row: {numbers}")
                if "closing" in row_text:
                    print(f"         Found Closing Balance row: {numbers}")
            continue

        # Skip header repeats and non-data rows
        if any(k in row_text for k in skip_keywords):
            continue

        # Must have balance value
        if balance_col >= len(row) or not row[balance_col]:
            continue

        balance_val = clean_amount(row[balance_col])
        if balance_val == 0.0:
            continue

        # Get date
        date_val = ""
        if date_col is not None and date_col < len(row) and row[date_col]:
            date_val = str(row[date_col]).strip()
        else:
            # Try to find date pattern in any cell
            for cell in row:
                if cell and re.search(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', str(cell)):
                    date_val = str(cell).strip()
                    break

        # Get debit and credit based on amount type
        debit_val  = 0.0
        credit_val = 0.0

        if config["amount_type"] == "single_bracket":
            # Union Bank — single amount column with (Cr)/(Dr)
            if debit_col is not None and debit_col < len(row) and row[debit_col]:
                amt_str = str(row[debit_col])
                amt     = clean_amount(amt_str)
                if "(cr)" in amt_str.lower():
                    credit_val = amt
                else:
                    debit_val  = amt

        elif config["amount_type"] == "separate_suffix":
            # SBI — DR/CR suffix in cell
            if debit_col is not None and debit_col < len(row) and row[debit_col]:
                val = str(row[debit_col])
                if "dr" in val.lower():
                    debit_val = clean_amount(val)
            if credit_col is not None and credit_col < len(row) and row[credit_col]:
                val = str(row[credit_col])
                if "cr" in val.lower():
                    credit_val = clean_amount(val)

        else:
            # Separate columns — Bank of Baroda, HDFC, Generic
            if debit_col is not None and debit_col < len(row) and row[debit_col]:
                debit_val  = clean_amount(row[debit_col])
            if credit_col is not None and credit_col < len(row) and row[credit_col]:
                credit_val = clean_amount(row[credit_col])

        # Get description — all non-numeric cells except date/debit/credit/balance
        desc = ""
        skip_cols = {date_col, debit_col, credit_col, balance_col}
        for ci, cell in enumerate(row):
            if ci not in skip_cols and cell:
                val = str(cell).strip()
                if val and not re.match(r'^[\d,]+\.?\d*$', val):
                    desc += val + " "
        desc = desc.strip()

        # Only add rows that have actual transaction data
        if debit_val > 0 or credit_val > 0:
            parsed.append({
                "date":        date_val,
                "description": desc,
                "debit":       round(debit_val,  2),
                "credit":      round(credit_val, 2),
                "balance":     round(balance_val, 2)
            })

    df = pd.DataFrame(parsed)

    # Reverse if needed (Union Bank — newest first)
    if config["reverse_order"] and not df.empty:
        df = df.iloc[::-1].reset_index(drop=True)
        print(f"         Reversed order for {bank_name}")

    print(f"         DataFrame shape: {df.shape}")
    if not df.empty:
        print(f"         First row: {df.iloc[0].to_dict()}")
        print(f"         Last row : {df.iloc[-1].to_dict()}")

    return df


# ─────────────────────────────────────────
#  STEP 5 — Extract opening/closing balance
# ─────────────────────────────────────────
def extract_balances(df, pages_text, bank_name):
    print(f"\n[Step 5] Extracting balances...")
    config  = BANK_CONFIG.get(bank_name, BANK_CONFIG["Generic"])
    opening = None
    closing = None

    # ── Method 1: Labeled rows in raw text ──
    full_text = "\n".join(pages_text)
    for line in full_text.split("\n"):
        line_lower = line.lower().strip()

        if config["opening_label"] and config["opening_label"] in line_lower:
            numbers = re.findall(r'[\d,]+\.\d+', line)
            if numbers:
                opening = clean_amount(numbers[-1])
                print(f"         Opening (label): ₹{opening:,.2f}")

        if config["closing_label"] and config["closing_label"] in line_lower:
            numbers = re.findall(r'[\d,]+\.\d+', line)
            if numbers:
                closing = clean_amount(numbers[-1])
                print(f"         Closing (label): ₹{closing:,.2f}")

    # ── Method 2: HDFC Statement Summary ──
    if bank_name == "HDFC" and (opening is None or closing is None):
        last_page = pages_text[-1] if pages_text else ""
        lines     = last_page.split("\n")
        for i, line in enumerate(lines):
            if "statement summary" in line.lower():
                summary_text = " ".join(lines[i:i+5])
                numbers      = re.findall(r'[\d,]+\.\d+', summary_text)
                if len(numbers) >= 2:
                    opening = clean_amount(numbers[0])
                    closing = clean_amount(numbers[-1])
                    print(f"         HDFC Opening (Summary): ₹{opening:,.2f}")
                    print(f"         HDFC Closing (Summary): ₹{closing:,.2f}")
                break

    # ── Method 3: Calculate from DataFrame ──
    if not df.empty:
        if opening is None:
            first_row = df.iloc[0]
            if first_row["credit"] > 0:
                opening = round(first_row["balance"] - first_row["credit"], 2)
            else:
                opening = round(first_row["balance"] + first_row["debit"], 2)
            print(f"         Opening (calculated): ₹{opening:,.2f}")

        if closing is None:
            closing = round(df.iloc[-1]["balance"], 2)
            print(f"         Closing (last row): ₹{closing:,.2f}")

    return opening, closing


# ─────────────────────────────────────────
#  HELPER — Extract date from question
# ─────────────────────────────────────────
def extract_date_from_question(q):
    # DD-MM-YYYY or DD/MM/YYYY or DD-MM-YY
    pattern = re.search(r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b', q)
    if pattern:
        return pattern.group(1)

    # "23 june" / "june 23" / "23rd june"
    months = {
        "january":"01","february":"02","march":"03","april":"04",
        "may":"05","june":"06","july":"07","august":"08",
        "september":"09","october":"10","november":"11","december":"12",
        "jan":"01","feb":"02","mar":"03","apr":"04","jun":"06",
        "jul":"07","aug":"08","sep":"09","oct":"10","nov":"11","dec":"12"
    }
    for month_name, month_num in months.items():
        m = re.search(rf'\b(\d{{1,2}})(st|nd|rd|th)?\s+{month_name}\b', q)
        if m:
            return f"{m.group(1).zfill(2)}/{month_num}"
        m = re.search(rf'\b{month_name}\s+(\d{{1,2}})(st|nd|rd|th)?\b', q)
        if m:
            return f"{m.group(1).zfill(2)}/{month_num}"
    return None


# ─────────────────────────────────────────
#  HELPER — Extract month from question
# ─────────────────────────────────────────
def extract_month_from_question(q):
    months = {
        "january":"01","february":"02","march":"03","april":"04",
        "may":"05","june":"06","july":"07","august":"08",
        "september":"09","october":"10","november":"11","december":"12",
        "jan":"01","feb":"02","mar":"03","apr":"04","jun":"06",
        "jul":"07","aug":"08","sep":"09","oct":"10","nov":"11","dec":"12"
    }
    for month_name, month_num in months.items():
        if month_name in q:
            return month_name.capitalize(), month_num
    return None, None


# ─────────────────────────────────────────
#  HELPER — Filter by date
# ─────────────────────────────────────────
def filter_by_date(df, date_str):
    if "date" not in df.columns or df.empty:
        return pd.DataFrame()
    normalized = date_str.replace("-", "/")
    return df[df["date"].astype(str).str.contains(
        normalized, na=False
    )]


# ─────────────────────────────────────────
#  HELPER — Filter by month
# ─────────────────────────────────────────
def filter_by_month(df, month_num):
    if "date" not in df.columns or df.empty:
        return pd.DataFrame()
    return df[df["date"].astype(str).str.contains(
        f"/{month_num}/|/{month_num}-|-{month_num}-|-{month_num}/",
        na=False
    )]


# ─────────────────────────────────────────
#  HELPER — Extract merchant keyword
# ─────────────────────────────────────────
def extract_merchant_from_question(q):
    remove_words = [
        "how much", "did i", "pay to", "paid to", "received from",
        "transactions with", "transactions from", "transaction for",
        "show me", "list", "all", "total", "amount", "what is",
        "the", "my", "for", "in", "on", "of", "from", "to",
        "a", "an", "is", "are", "was", "give me", "tell me",
        "how many", "number of", "find", "search", "get"
    ]
    cleaned = q.lower()
    for word in sorted(remove_words, key=len, reverse=True):
        cleaned = cleaned.replace(word, " ")
    cleaned = " ".join(cleaned.split()).strip()

    # Must be meaningful — at least 3 chars and not just numbers
    if len(cleaned) >= 3 and not cleaned.replace(".", "").isdigit():
        return cleaned
    return None


# ─────────────────────────────────────────
#  STEP 6 — Answer directly from DataFrame
# ─────────────────────────────────────────
def answer_from_dataframe(question, df, opening, closing):
    q = question.lower().strip()

    if df.empty and opening is None and closing is None:
        return None

    total_debit  = round(df["debit"].sum(),  2) if not df.empty else 0.0
    total_credit = round(df["credit"].sum(), 2) if not df.empty else 0.0
    net_change   = round((closing or 0) - (opening or 0), 2)

    # ── Opening / Closing Balance ──
    if "opening balance" in q:
        if opening is not None:
            return f"Opening Balance: ₹{opening:,.2f}"

    if "closing balance" in q:
        if closing is not None:
            return f"Closing Balance: ₹{closing:,.2f}"

    if df.empty:
        return None

    # ── Totals ──
    if any(k in q for k in ["total debit", "total withdrawal", "total withdrawals"]):
        return f"Total Debits: ₹{total_debit:,.2f}"

    if any(k in q for k in ["total credit", "total deposit", "total deposits"]):
        return f"Total Credits: ₹{total_credit:,.2f}"

    if any(k in q for k in ["net change", "net saving", "net difference"]):
        return (
            f"Net Change: ₹{net_change:,.2f}\n"
            f"({'Surplus' if net_change >= 0 else 'Deficit'} for this period)"
        )

    # ── Transaction count ──
    if any(k in q for k in ["how many transaction", "transaction count", "number of transaction"]):
        total_dr = len(df[df["debit"] > 0])
        total_cr = len(df[df["credit"] > 0])
        return (
            f"Total Transactions : {len(df)}\n"
            f"  Debits           : {total_dr}\n"
            f"  Credits          : {total_cr}"
        )

    # ── Highest / Lowest balance ──
    if any(k in q for k in ["highest balance", "maximum balance"]):
        idx = df["balance"].idxmax()
        row = df.iloc[idx]
        return (
            f"Highest Balance: ₹{row['balance']:,.2f}"
            + (f" on {row['date']}" if row.get('date') else "")
        )

    if any(k in q for k in ["lowest balance", "minimum balance"]):
        idx = df["balance"].idxmin()
        row = df.iloc[idx]
        return (
            f"Lowest Balance: ₹{row['balance']:,.2f}"
            + (f" on {row['date']}" if row.get('date') else "")
        )

    # ── Date-specific questions ──
    date_match = extract_date_from_question(q)
    if date_match:
        filtered = filter_by_date(df, date_match)
        if not filtered.empty:

            if any(k in q for k in ["balance"]):
                last_balance = filtered.iloc[-1]["balance"]
                return f"Balance on {date_match}: ₹{last_balance:,.2f}"

            elif any(k in q for k in ["debit", "spent", "paid", "withdrawal", "send", "sent"]):
                debits = filtered[filtered["debit"] > 0]
                if not debits.empty:
                    total = debits["debit"].sum()
                    lines = [f"Debits on {date_match}: ₹{total:,.2f} ({len(debits)} transactions)"]
                    for _, row in debits.iterrows():
                        lines.append(f"  DR  ₹{row['debit']:>10,.2f}  {row['description'][:45]}")
                    return "\n".join(lines)
                return f"No debit transactions on {date_match}"

            elif any(k in q for k in ["credit", "received", "deposit"]):
                credits = filtered[filtered["credit"] > 0]
                if not credits.empty:
                    total = credits["credit"].sum()
                    lines = [f"Credits on {date_match}: ₹{total:,.2f} ({len(credits)} transactions)"]
                    for _, row in credits.iterrows():
                        lines.append(f"  CR  ₹{row['credit']:>10,.2f}  {row['description'][:45]}")
                    return "\n".join(lines)
                return f"No credit transactions on {date_match}"

            else:
                # Show all transactions on that date
                lines = [f"All transactions on {date_match} ({len(filtered)} total):"]
                for _, row in filtered.iterrows():
                    if row["debit"] > 0:
                        lines.append(f"  DR  ₹{row['debit']:>10,.2f}  {row['description'][:45]}")
                    else:
                        lines.append(f"  CR  ₹{row['credit']:>10,.2f}  {row['description'][:45]}")
                total_dr = filtered["debit"].sum()
                total_cr = filtered["credit"].sum()
                lines.append(f"\nTotal Debits  : ₹{total_dr:,.2f}")
                lines.append(f"Total Credits : ₹{total_cr:,.2f}")
                return "\n".join(lines)

        else:
            return f"No transactions found on {date_match}"

    # ── Month-specific questions ──
    month_name, month_num = extract_month_from_question(q)
    if month_name and month_num:
        filtered = filter_by_month(df, month_num)
        if not filtered.empty:
            month_debit  = filtered["debit"].sum()
            month_credit = filtered["credit"].sum()

            if any(k in q for k in ["debit", "spent", "paid", "withdrawal"]):
                debits = filtered[filtered["debit"] > 0]
                lines  = [f"Total Debits in {month_name}: ₹{month_debit:,.2f} ({len(debits)} transactions)"]
                for _, row in debits.iterrows():
                    lines.append(f"  {row.get('date','')}  DR  ₹{row['debit']:>10,.2f}  {row['description'][:35]}")
                return "\n".join(lines)

            elif any(k in q for k in ["credit", "received", "deposit"]):
                credits = filtered[filtered["credit"] > 0]
                lines   = [f"Total Credits in {month_name}: ₹{month_credit:,.2f} ({len(credits)} transactions)"]
                for _, row in credits.iterrows():
                    lines.append(f"  {row.get('date','')}  CR  ₹{row['credit']:>10,.2f}  {row['description'][:35]}")
                return "\n".join(lines)

            else:
                return (
                    f"Summary for {month_name}:\n"
                    f"  Total Debits   : ₹{month_debit:,.2f}\n"
                    f"  Total Credits  : ₹{month_credit:,.2f}\n"
                    f"  Net            : ₹{round(month_credit - month_debit, 2):,.2f}\n"
                    f"  Transactions   : {len(filtered)}"
                )
        else:
            return f"No transactions found in {month_name}"

    # ── Amount threshold questions ──
    amount_match = re.search(
        r'(above|more than|greater than|over)\s+₹?\s*(\d[\d,]*)',
        q
    )
    if amount_match:
        threshold = clean_amount(amount_match.group(2))

        if any(k in q for k in ["debit", "spent", "paid", "withdrawal"]):
            filtered = df[df["debit"] > threshold]
            if not filtered.empty:
                lines = [f"Debit transactions above ₹{threshold:,.2f} ({len(filtered)} found):"]
                for _, row in filtered.iterrows():
                    lines.append(f"  {row.get('date','')}  DR  ₹{row['debit']:>10,.2f}  {row['description'][:35]}")
                lines.append(f"\nTotal: ₹{filtered['debit'].sum():,.2f}")
                return "\n".join(lines)

        elif any(k in q for k in ["credit", "received", "deposit"]):
            filtered = df[df["credit"] > threshold]
            if not filtered.empty:
                lines = [f"Credit transactions above ₹{threshold:,.2f} ({len(filtered)} found):"]
                for _, row in filtered.iterrows():
                    lines.append(f"  {row.get('date','')}  CR  ₹{row['credit']:>10,.2f}  {row['description'][:35]}")
                lines.append(f"\nTotal: ₹{filtered['credit'].sum():,.2f}")
                return "\n".join(lines)

        else:
            filtered = df[(df["debit"] > threshold) | (df["credit"] > threshold)]
            if not filtered.empty:
                lines = [f"Transactions above ₹{threshold:,.2f} ({len(filtered)} found):"]
                for _, row in filtered.iterrows():
                    if row["debit"] > threshold:
                        lines.append(f"  {row.get('date','')}  DR  ₹{row['debit']:>10,.2f}  {row['description'][:35]}")
                    else:
                        lines.append(f"  {row.get('date','')}  CR  ₹{row['credit']:>10,.2f}  {row['description'][:35]}")
                return "\n".join(lines)

    # ── Merchant / keyword search ──
    keyword = extract_merchant_from_question(q)
    if keyword and len(keyword) >= 3:
        filtered = df[df["description"].str.lower().str.contains(
            keyword, na=False
        )]
        if not filtered.empty:
            total_dr = filtered["debit"].sum()
            total_cr = filtered["credit"].sum()
            lines    = [f"Transactions matching '{keyword}' ({len(filtered)} found):"]
            for _, row in filtered.iterrows():
                if row["debit"] > 0:
                    lines.append(f"  {row.get('date','')}  DR  ₹{row['debit']:>10,.2f}  {row['description'][:35]}")
                else:
                    lines.append(f"  {row.get('date','')}  CR  ₹{row['credit']:>10,.2f}  {row['description'][:35]}")
            if total_dr > 0:
                lines.append(f"\nTotal Paid    : ₹{total_dr:,.2f}")
            if total_cr > 0:
                lines.append(f"\nTotal Received: ₹{total_cr:,.2f}")
            return "\n".join(lines)

    return None


# ─────────────────────────────────────────
#  STEP 7 — Build clean LLM context
# ─────────────────────────────────────────
def build_llm_context(df, pages_text, opening, closing, bank_name):
    context = []

    # Account details from page 1
    context.append("=== ACCOUNT DETAILS ===")
    context.append(pages_text[0] if pages_text else "")

    # Key statistics
    context.append("\n=== KEY STATISTICS ===")
    if opening is not None:
        context.append(f"Opening Balance : ₹{opening:,.2f}")
    if closing is not None:
        context.append(f"Closing Balance : ₹{closing:,.2f}")

    if not df.empty:
        context.append(f"Total Debits    : ₹{df['debit'].sum():,.2f}")
        context.append(f"Total Credits   : ₹{df['credit'].sum():,.2f}")
        context.append(f"Net Change      : ₹{round((closing or 0)-(opening or 0),2):,.2f}")
        context.append(f"Total Txns      : {len(df)}")
        context.append(f"Highest Balance : ₹{df['balance'].max():,.2f}")
        context.append(f"Lowest Balance  : ₹{df['balance'].min():,.2f}")

    # Recent transactions only (faster than sending entire dataframe)
    if not df.empty:
        context.append("\n=== RECENT TRANSACTIONS ===")

        sample_df = df.tail(50)

        clean_df = sample_df.drop(
            columns=["raw_row"],
            errors="ignore"
        )

        context.append(clean_df.to_csv(index=False))

    return "\n".join(context)


# ─────────────────────────────────────────
#  HELPER — Get page text for account details
# ─────────────────────────────────────────
def get_detail_text(pages_text):
    if pages_text:
        return pages_text[0]

    return ""


# ─────────────────────────────────────────
#  HELPER — Answer account detail questions
# ─────────────────────────────────────────
def answer_account_details(question, pages_text, prompt):
    relevant_text = get_detail_text(pages_text)

    response = ollama.chat(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": prompt
            },
            {
                "role": "user",
                "content": (
                    f"QUESTION:\n{question}\n\n"
                    f"DOCUMENT:\n{relevant_text}\n\n"
                    "Answer in one line only.\n"
                    "Return only the value.\n\n"

                    "Examples:\n"
                    "Question: What is the account holder name\n"
                    "Answer: JOHN DOE\n\n"

                    "Question: What is the IFSC code\n"
                    "Answer: SBIN0001234"
                )
            }
        ]
    )

    return response["message"]["content"].strip()

# ─────────────────────────────────────────
#  STEP 8 — Ask LLM
# ─────────────────────────────────────────
def ask_model(prompt, context, question):
    print(f"\n[Step 7] Asking {MODEL}...")
    response = ollama.chat(
        model    = MODEL,
        messages = [
            {"role": "system", "content": prompt},
            {
                "role":    "user",
                "content": (
                    f"QUESTION:\n{question}\n\n"
                    f"DATA:\n{context}\n\n"
                    f"Answer clearly and concisely based only on the data above."
                )
            }
        ]
    )
    answer = response["message"]["content"].strip()
    print(f"         Answer: {answer}")
    return answer


# ─────────────────────────────────────────
#  MAIN — called by api.py
# ─────────────────────────────────────────
def process(pdf_path, question):
    print(f"\n{'='*50}")
    print(f"PDF      : {pdf_path}")
    print(f"Question : {question}")
    print(f"{'='*50}")

    # Step 1 — Extract text and tables
    pages_text, pages_tables = extract_text_and_tables(pdf_path)

    # Step 2 — Detect bank
    bank_name = detect_bank(pages_text)

    # Step 3 — Load prompt
    prompt = load_prompt_from_s3(bank_name)

    # Step 4 — Handle account detail questions first
    q = question.lower()

    if any(k in q for k in DETAIL_KEYWORDS):

        detail_answer = answer_account_details(
            question,
            pages_text,
            prompt
        )

        print(f"\nDetail Answer (LLM): {detail_answer}")

        return {
            "bank": bank_name,
            "question": question,
            "answer": detail_answer,
            "source": "details_llm"
        }

    # Step 5 — Build DataFrame
    df = build_dataframe(
        pages_tables,
        bank_name
    )

    # Step 6 — Extract balances
    opening, closing = extract_balances(
        df,
        pages_text,
        bank_name
    )

    # Step 7 — Try direct DataFrame answer
    direct_answer = answer_from_dataframe(
        question,
        df,
        opening,
        closing
    )

    if direct_answer:
        print(f"\nDirect Answer (DataFrame): {direct_answer}")

        return {
            "bank": bank_name,
            "question": question,
            "answer": direct_answer,
            "source": "dataframe"
        }

    # Step 8 — Fall back to LLM
    print("\nFalling back to LLM...")

    llm_context = build_llm_context(
        df,
        pages_text,
        opening,
        closing,
        bank_name
    )

    llm_answer = ask_model(
        prompt,
        llm_context,
        question
    )

    return {
        "bank": bank_name,
        "question": question,
        "answer": llm_answer,
        "source": "llm"
    }
# ─────────────────────────────────────────
#  TEST
# ─────────────────────────────────────────
if __name__ == "__main__":
    test_questions = [
        "What is the account holder name",
        "What is the IFSC code",
        "What is the opening balance",
        "What is the closing balance",
        "What is the total debit amount",
        "What is the total credit amount",
        "What is the highest balance",
        "What is the lowest balance",
        "How many transactions are there",
        "What are the transactions on 23 june",
        "How much did I spend on 23 june",
        "Total debits in june",
        "Transactions above 10000",
        "How much paid to credclub",
        "Give me a summary of this statement",
        "List all UPI transactions",
        "Category wise spending summary",
    ]

    for q in test_questions:
        result = process(
            pdf_path = "Data/Bank_of_Baroda_statment.pdf",
            question = q
        )
        print(f"\nQ: {result['question']}")
        print(f"A: {result['answer']}")
        print(f"S: {result['source']}")
        print("-" * 40)