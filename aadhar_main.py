import easyocr
import ollama

from s3_management import build_final_prompt
from s3_management import load_internal_prompt

MODEL = "mistral:7b"

reader = easyocr.Reader(["en"])

def extract_text(image_path):
    result = reader.readtext(image_path)
    extracted_text = []

    for item in result:
        extracted_text.append(item[1])

    return "\n".join(extracted_text)


def load_prompt():
    return build_final_prompt("aadhar_card")

def ask_model(prompt, document_text, question):
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


            QUESTION:
            {question}

            AADHAAR DOCUMENT:
            {document_text}

            Answer in one line only.
            """
            }
        ]
    )

    return response["message"]["content"].strip()

def process(image_path, question):

    document_text = extract_text(image_path)

    final_prompt = build_final_prompt(
        "aadhar_card"
    )

    answer = ask_model(
        final_prompt,
        document_text,
        question
    )

    return {
        "document_type": "aadhar_card",
        "question": question,
        "answer": answer
    }
