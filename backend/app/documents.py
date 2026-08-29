"""Extrai texto de PDF/Word para a base da empresa."""
from io import BytesIO

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 80


def extract_text_from_upload(filename: str, data: bytes) -> tuple[str, str]:
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Arquivo acima de 5 MB. Envie um PDF/Word menor.")
    name = (filename or "").lower().strip()
    if name.endswith(".pdf"):
        return _from_pdf(data), "pdf"
    if name.endswith(".docx"):
        return _from_docx(data), "docx"
    if name.endswith(".doc"):
        raise ValueError("Use o formato .docx (Word moderno), não .doc antigo.")
    raise ValueError("Formato não suportado. Envie PDF (.pdf) ou Word (.docx).")


def _from_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    parts: list[str] = []
    for page in reader.pages[:MAX_PDF_PAGES]:
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text.strip())
    content = "\n\n".join(parts).strip()
    if len(content) < 20:
        raise ValueError(
            "Não deu para ler texto neste PDF (pode ser só imagem). "
            "Tente um PDF com texto selecionável ou cole o conteúdo manualmente."
        )
    return content


def _from_docx(data: bytes) -> str:
    from docx import Document

    doc = Document(BytesIO(data))
    parts = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text and c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    content = "\n".join(parts).strip()
    if len(content) < 20:
        raise ValueError("Documento Word sem texto suficiente para publicar.")
    return content
