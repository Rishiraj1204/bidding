from pathlib import Path

from pypdf import PdfReader
from docx import Document as DocxDocument


def extract_pdf_text(file_path: str) -> str:
    reader = PdfReader(file_path)

    pages = []

    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)

    return "\n".join(pages).strip()


def extract_docx_text(file_path: str) -> str:
    document = DocxDocument(file_path)

    paragraphs = [
        paragraph.text
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    ]

    return "\n".join(paragraphs).strip()


def extract_text(file_path: str) -> str:
    path = Path(file_path)
    extension = path.suffix.lower()

    if extension == ".pdf":
        return extract_pdf_text(str(path))

    if extension == ".docx":
        return extract_docx_text(str(path))

    return ""