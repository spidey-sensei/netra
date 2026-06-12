from pypdf import PdfReader
from pdf2image import convert_from_path
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_text(pdf_path):
    print(f"\n[Step 1] Extracting text from: {pdf_path}")

    reader = PdfReader(pdf_path)
    pages = []

    # Try normal extraction first
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted and extracted.strip():
            pages.append(extracted)

    # If no text found, use OCR
    if len(pages) == 0:
        print("No text found. Using OCR...")

        images = convert_from_path(pdf_path)

        for img in images:
            text = pytesseract.image_to_string(img)
            pages.append(text)

    print(f"Pages extracted: {len(pages)}")

    return pages