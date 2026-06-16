import easyocr
import ollama

from s3_management import build_final_prompt
from extractor import extract_document
from bank import process_bank_question

MODEL = "gemma3:latest"


def ask_model(prompt, document_text):
    response = ollama.chat(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": prompt
            },
            {
                "role": "user",
                "content": f"""


            

            DOCUMENT:
            {document_text}

            Answer in one line only.
            """
            }
        ]
    )

    return response["message"]["content"].strip()

def process_document(
    file_path,
    question,
    document_type,
    bank_name=None
):

    pages = extract_document(
        file_path
    )

    document_text = "\n".join(pages)

    final_prompt = build_final_prompt(
        document_type=document_type,
        question=question,
        bank_name=bank_name
    )

    answer = ask_model(final_prompt, document_text)

    return {
        "document_type": document_type,
        "question": question,
        "answer": answer
    }

def process_question(
    file_path,
    question,
    document_type,
    bank_name=None
):

    if document_type == "bank":
        return process_bank_question(
            pdf_path=file_path,
            question=question,
            bank_name=bank_name
        )

    return process_document(
        file_path=file_path,
        question=question,
        document_type=document_type,
        bank_name=bank_name
    )


