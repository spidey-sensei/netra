from extractor import extract_pdf_text
from s3_management import load_latest_prompt
import ollama

MODEL = "mistral:7b"

def get_relevant_text(pages, question):
    print(f"\n[Step 4] Selecting relevant chunk for question: '{question}'")
    q = question.lower()

    # Account details
    account_keywords = [
        "account holder", "account name", "customer name",
        "account number", "account no",
        "account type", "account description",
        "ifsc", "micr", "cif", "email",
        "currency", "available balance",
        "address", "branch",
        "opening balance",
        "closing balance",
        "statement period",
        "statement date"
    ]

    # Transaction-related questions
    transaction_keywords = [
        "transaction", "debit", "credit", "total",
        "how many", "list", "spent", "received",
        "transfer", "upi", "neft", "rtgs", "imps",
        "last transaction",
        "highest", "lowest", "average"
    ]

    # Account details → first + last page
    if any(k in q for k in account_keywords):

        print("         Chunk: first + last page")

        print("\nFIRST PAGE PREVIEW:")
        print(pages[0][:500])

        print("\nLAST PAGE PREVIEW:")
        print(pages[-1][:500])

        if len(pages) == 1:
            return pages[0]

        return pages[0] + "\n" + pages[-1]

    # Transaction questions → all pages
    elif any(k in q for k in transaction_keywords):

        print("         Chunk: all pages (transactions)")

        print("\nFIRST PAGE PREVIEW:")
        print(pages[0][:500])

        print("\nLAST PAGE PREVIEW:")
        print(pages[-1][:500])

        return "\n".join(pages)

    # Default
    else:

        print("         Chunk: first + last page (default)")

        print("\nFIRST PAGE PREVIEW:")
        print(pages[0][:500])

        print("\nLAST PAGE PREVIEW:")
        print(pages[-1][:500])

        if len(pages) == 1:
            return pages[0]

        return pages[0] + "\n" + pages[-1]
    
# ─────────────────────────────────────────
#  STEP 5 — Ask model
# ─────────────────────────────────────────
def ask_model(prompt, relevant_text, question):
    print(f"\n[Step 5] Sending to model ({MODEL})...")
    response = ollama.chat(
        model=MODEL,
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
    answer = response["message"]["content"].strip()
    print(f"         Answer: {answer}")
    return answer

def process_bank_question(
    pdf_path: str,
    question: str,
    bank_name: str | None
):

    # Step 1: Extract text
    pages = extract_pdf_text(pdf_path)

    # Step 2: Load prompt from S3
    prompt = load_latest_prompt(f"bank/{bank_name}")

    # Step 3: Retrieve relevant chunk
    relevant_text = get_relevant_text(
        pages,
        question
    )

    # Step 4: Ask model
    answer = ask_model(
        prompt,
        relevant_text,
        question
    )

    return {
        "document_type": "bank",
        "bank": bank_name,
        "question": question,
        "answer": answer
    }
