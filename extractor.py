import easyocr
from pypdf import PdfReader

reader = easyocr.Reader(["en"])

def extract_pdf_text(pdf_path):
    print(f"\n[Step 1] Extracting text from PDF: {pdf_path}")
    reader = PdfReader(pdf_path)
    pages  = []
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            pages.append(extracted)
    print(f"         Pages extracted: {len(pages)}")
    return pages


def extract_image_text(image_path):
    result = reader.readtext(image_path)

    text = []

    for item in result:
        text.append(item[1])

    return ["\n".join(text)]


def extract_document(file_path):

    ext = file_path.split(".")[-1].lower()

    if ext == "pdf":
        return extract_pdf_text(file_path)

    elif ext in ["png", "jpg", "jpeg"]:
        return extract_image_text(file_path)

    raise Exception("Unsupported file type")