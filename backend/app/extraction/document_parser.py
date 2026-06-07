from io import BytesIO
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from docx import Document
from pypdf import PdfReader


class DocumentParseError(ValueError):
    pass


def extract_text_from_bytes(filename: str, content: bytes) -> str:
    suffix = Path(filename or "").suffix.lower()
    try:
        if suffix == ".pdf":
            return _extract_pdf(content)
        if suffix == ".docx":
            return _extract_docx(content)
        return _extract_plain_text(content)
    except Exception as exc:
        raise DocumentParseError(f"无法解析文件 {filename}: {exc}") from exc


def _extract_pdf(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = _normalize_text("\n".join(pages))
    if text:
        return text
    return _normalize_text(_extract_pdf_with_macos_ocr(content))


def _extract_pdf_with_macos_ocr(content: bytes) -> str:
    if sys.platform != "darwin" or not shutil.which("swift"):
        return ""

    script_path = Path(__file__).resolve().parents[3] / "scripts" / "macos_pdf_ocr.swift"
    if not script_path.exists():
        return ""

    with tempfile.NamedTemporaryFile(suffix=".pdf") as pdf_file:
        pdf_file.write(content)
        pdf_file.flush()
        try:
            result = subprocess.run(
                ["swift", str(script_path), pdf_file.name],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                timeout=90,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ""

    if result.returncode != 0:
        return ""
    return result.stdout


def _extract_docx(content: bytes) -> str:
    document = Document(BytesIO(content))
    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    return _normalize_text("\n".join(paragraphs))


def _extract_plain_text(content: bytes) -> str:
    for encoding in ("utf-8", "gb18030", "latin-1"):
        try:
            return _normalize_text(content.decode(encoding))
        except UnicodeDecodeError:
            continue
    return _normalize_text(content.decode("utf-8", errors="ignore"))


def _normalize_text(text: str) -> str:
    lines = [line.strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()
