from pypdf import PdfReader
import ollama


def extract_text(pdf_path):
    reader = PdfReader(pdf_path)
    pages = []
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            pages.append(extracted)
    return pages  # returns list of pages now


def get_relevant_text(pages, question):
    q = question.lower()

    detail_keywords = [
        "account holder", "account number", "ifsc",
        "branch", "balance", "account type", "name",
        "address", "email", "cif", "micr", "currency",
        "statement date", "statement period", "opening"
    ]

    transaction_keywords = [
        "transaction", "debit", "credit", "total",
        "how many", "list", "spent", "received",
        "transfer", "upi", "neft", "closing"
    ]

    if any(k in q for k in detail_keywords):
        return pages[0]  # first page only
    elif any(k in q for k in transaction_keywords):
        return "\n".join(pages)  # all pages
    else:
        return "\n".join(pages)  # default — all pages


def load_prompt():
    with open("Bank/HDFC_Bank.txt", "r", encoding="utf-8") as f:
        return f.read()


pages = extract_text("Data/HDFC bank statment.pdf")
prompt = load_prompt()
question = "What is bank account type"

relevant_text = get_relevant_text(pages, question)

response = ollama.chat(
    model="llama3.1:8b ",
    messages=[
        {
            "role": "system",
            "content": prompt
        },
        {
            "role": "user",
            "content": f"QUESTION:\n{question}\n\nDOCUMENT:\n{relevant_text}\n\nAnswer in one line only:"
        }
    ]
)

print(response["message"]["content"])